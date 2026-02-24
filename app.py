from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from comfy_client import health_check
from db import QueueDB
from defs import ParameterDef, WorkflowDef, WorkflowDefError, load_all
from prompt_builder import build_prompts, resolve_params
from worker import Worker

LORA_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
WAN_POSITIVE_TEMPLATE = "(at 0 second: )(at 3 second: )(at 7 second: )"
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
RESOLUTION_PRESETS: list[dict[str, Any]] = [
    {"id": "384x672", "label": "384 x 672", "width": 384, "height": 672},
    {"id": "480x848", "label": "480 x 848", "width": 480, "height": 848},
    {"id": "576x1024", "label": "576 x 1024", "width": 576, "height": 1024},
    {"id": "640x1136", "label": "640 x 1136", "width": 640, "height": 1136},
    {"id": "768x1360", "label": "768 x 1360", "width": 768, "height": 1360},
]
RESOLUTION_PRESET_MAP: dict[str, tuple[int, int]] = {
    str(item["id"]): (int(item["width"]), int(item["height"])) for item in RESOLUTION_PRESETS
}


class JobCreateRequest(BaseModel):
    workflow_name: str
    job_name: str | None = None
    input_dir: str
    params: dict[str, Any] = Field(default_factory=dict)
    resolution_preset: str | None = None
    flip_orientation: bool = False
    move_processed: bool = False
    split_by_input: bool = False
    priority: int = 0


class SingleJobCreateRequest(BaseModel):
    workflow_name: str
    job_name: str | None = None
    input_image: str
    params: dict[str, Any] = Field(default_factory=dict)
    resolution_preset: str | None = None
    flip_orientation: bool = False
    move_processed: bool = False
    priority: int = 0


class PickDirectoryRequest(BaseModel):
    start_dir: str | None = None


class PickImageRequest(BaseModel):
    start_path: str | None = None


class InputPathRequest(BaseModel):
    path: str


class PromptPresetSaveRequest(BaseModel):
    name: str
    positive_prompt: str = ""
    negative_prompt: str = ""


class SettingsPresetSaveRequest(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AppState:
    def __init__(self) -> None:
        self.root = Path(os.environ.get("VIDEO_QUEUE_ROOT", str(Path.home() / "video_queue"))).expanduser().resolve()
        self.data_dir = self.root / "data"
        self.static_dir = self.root / "static"
        self.defs_dir = Path(os.environ.get("WORKFLOW_DEFS_DIR", str(self.root / "workflow_defs_v2"))).expanduser().resolve()
        self.comfy_root = Path(os.environ.get("COMFY_ROOT", str(Path.home() / "ComfyUI"))).expanduser().resolve()
        self.comfy_input_dir = self.comfy_root / "input"
        self.comfy_base_url = os.environ.get("COMFY_BASE_URL", "http://127.0.0.1:8188")
        self.db = QueueDB(self.data_dir / "queue.db")
        self.workflows: dict[str, WorkflowDef] = {}
        self.worker: Worker | None = None

    def reload_workflows(self) -> None:
        loaded = load_all(self.defs_dir)
        refreshed = {w.name: w for w in loaded}
        self.workflows.clear()
        self.workflows.update(refreshed)


state = AppState()
app = FastAPI(title="ComfyUI Workflow Manager")

if state.static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(state.static_dir)), name="static")


@app.on_event("startup")
def on_startup() -> None:
    state.data_dir.mkdir(parents=True, exist_ok=True)
    try:
        state.reload_workflows()
    except WorkflowDefError as exc:
        raise RuntimeError(f"Failed to load workflow definitions: {exc}") from exc
    state.worker = Worker(state.db, state.workflows, state.comfy_base_url, state.data_dir)
    state.worker.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    if state.worker:
        state.worker.stop()
    state.db.close()


@app.get("/")
def index() -> FileResponse:
    index_file = state.static_dir / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index_file)


def _template_default(wf: WorkflowDef, param: ParameterDef) -> str | None:
    if not param.nodes:
        return None

    field = param.field
    if field is None and param.fields and len(param.fields) == 1:
        field = param.fields[0]
    if not field:
        return None

    first_node = wf.template_prompt.get(param.nodes[0])
    if not isinstance(first_node, dict):
        return None
    inputs = first_node.get("inputs")
    if not isinstance(inputs, dict):
        return None

    value = inputs.get(field)
    return value if isinstance(value, str) else None


def _api_param_default(wf: WorkflowDef, name: str, param: ParameterDef) -> Any:
    default = param.default

    # WAN workflows get a scaffolded positive prompt by default in UI.
    if name == "positive_prompt" and wf.name.startswith("wan-") and (default is None or default == ""):
        return WAN_POSITIVE_TEMPLATE

    # For empty text defaults, use the value already present in the template node.
    if param.type == "text" and (default is None or default == ""):
        template_value = _template_default(wf, param)
        if template_value is not None:
            return template_value

    return default


def _discover_loras() -> list[str]:
    roots = [
        state.comfy_root / "models" / "loras",
        state.comfy_root / "loras",
    ]

    seen: set[str] = set()
    found: list[str] = []

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in LORA_EXTENSIONS:
                continue
            try:
                name = path.relative_to(root).as_posix()
            except ValueError:
                name = path.name
            if name in seen:
                continue
            seen.add(name)
            found.append(name)

    return sorted(found, key=str.lower)


def _run_capture(cmd: list[str], timeout: int = 300) -> str | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return None
    return out.splitlines()[-1].strip()


def _extract_windows_fragment(path: str) -> str:
    text = path.strip()
    lower = text.lower()
    marker_idx = lower.find("wsl.localhost")
    if marker_idx < 0:
        return text

    slash_idx = text.rfind("\\", 0, marker_idx)
    if slash_idx < 0:
        slash_idx = text.rfind("/", 0, marker_idx)
    if slash_idx < 0:
        return text

    return text[slash_idx:]


def _normalize_input_dir(raw_path: str, field_label: str = "input directory") -> str:
    value = str(raw_path or "").strip().strip('"').strip("'")
    if not value:
        raise ValueError(f"{field_label} is required")

    value = value.replace("\r", "").replace("\n", "")
    value = _extract_windows_fragment(value)

    if value.startswith("//wsl.localhost/"):
        value = "\\\\" + value.lstrip("/").replace("/", "\\")
    elif value.startswith("\\wsl.localhost\\"):
        value = "\\" + value

    is_windows = value.startswith("\\\\") or bool(WINDOWS_DRIVE_RE.match(value))
    if is_windows:
        converted = _run_capture(["wslpath", "-u", value])
        if converted:
            value = converted
        else:
            value = value.replace("\\", "/")
    elif "\\" in value:
        value = value.replace("\\", "/")

    resolved = Path(value).expanduser().resolve()
    return str(resolved)


def _as_windows_path(path: str) -> str | None:
    return _run_capture(["wslpath", "-w", path])


def _pick_with_powershell(start_dir: str | None) -> str | None:
    if not shutil.which("powershell.exe"):
        return None

    init_stmt = ""
    if start_dir:
        win_dir = _as_windows_path(start_dir)
        if win_dir:
            escaped = win_dir.replace("'", "''")
            init_stmt = f"$dlg.SelectedPath = '{escaped}'; "

    script = (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null; "
        "$dlg = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dlg.Description = 'Select input directory'; "
        "$dlg.ShowNewFolderButton = $true; "
        f"{init_stmt}"
        "if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
        "Write-Output $dlg.SelectedPath }"
    )
    return _run_capture(["powershell.exe", "-NoProfile", "-STA", "-Command", script], timeout=1200)


def _pick_with_zenity(start_dir: str | None) -> str | None:
    if not shutil.which("zenity"):
        return None
    cmd = ["zenity", "--file-selection", "--directory", "--title=Select input directory"]
    if start_dir:
        cmd.append(f"--filename={start_dir.rstrip('/')}/")
    return _run_capture(cmd, timeout=1200)


def _pick_with_kdialog(start_dir: str | None) -> str | None:
    if not shutil.which("kdialog"):
        return None
    base = start_dir or str(state.comfy_input_dir)
    return _run_capture(["kdialog", "--getexistingdirectory", base, "--title", "Select input directory"], timeout=1200)


def _pick_image_with_powershell(start_dir: str | None) -> str | None:
    if not shutil.which("powershell.exe"):
        return None

    init_stmt = ""
    if start_dir:
        win_dir = _as_windows_path(start_dir)
        if win_dir:
            escaped = win_dir.replace("'", "''")
            init_stmt = f"$dlg.InitialDirectory = '{escaped}'; "

    script = (
        "Add-Type -AssemblyName System.Windows.Forms | Out-Null; "
        "$dlg = New-Object System.Windows.Forms.OpenFileDialog; "
        "$dlg.Filter = 'Image Files|*.png;*.jpg;*.jpeg;*.webp;*.bmp|All Files|*.*'; "
        "$dlg.Multiselect = $false; "
        f"{init_stmt}"
        "if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
        "Write-Output $dlg.FileName }"
    )
    return _run_capture(["powershell.exe", "-NoProfile", "-STA", "-Command", script], timeout=1200)


def _pick_image_with_zenity(start_dir: str | None) -> str | None:
    if not shutil.which("zenity"):
        return None
    cmd = ["zenity", "--file-selection", "--title=Select image file"]
    if start_dir:
        cmd.append(f"--filename={start_dir.rstrip('/')}/")
    cmd.append("--file-filter=Images | *.png *.jpg *.jpeg *.webp *.bmp")
    return _run_capture(cmd, timeout=1200)


def _pick_image_with_kdialog(start_dir: str | None) -> str | None:
    if not shutil.which("kdialog"):
        return None
    base = start_dir or str(state.comfy_input_dir)
    return _run_capture(
        ["kdialog", "--getopenfilename", base, "*.png *.jpg *.jpeg *.webp *.bmp", "--title", "Select image file"],
        timeout=1200,
    )


def _pick_directory(start_dir: str | None) -> str | None:
    normalized_start: str | None = None
    if start_dir:
        try:
            start_raw = _normalize_input_dir(start_dir)
        except ValueError:
            start_raw = ""
        start_path = Path(start_raw).expanduser() if start_raw else Path("/")
        if start_path.exists() and start_path.is_dir():
            normalized_start = str(start_path.resolve())

    for picker in (_pick_with_powershell, _pick_with_zenity, _pick_with_kdialog):
        selected = picker(normalized_start)
        if not selected:
            continue
        try:
            resolved = Path(_normalize_input_dir(selected)).expanduser()
        except ValueError:
            return None
        if resolved.exists() and resolved.is_dir():
            return str(resolved)
        return None

    return None


def _pick_image(start_path: str | None) -> str | None:
    normalized_start: str | None = None
    if start_path:
        try:
            start_raw = _normalize_input_dir(start_path, field_label="start path")
        except ValueError:
            start_raw = ""
        path_obj = Path(start_raw).expanduser() if start_raw else state.comfy_input_dir
        if path_obj.exists():
            if path_obj.is_file():
                normalized_start = str(path_obj.parent.resolve())
            elif path_obj.is_dir():
                normalized_start = str(path_obj.resolve())

    if not normalized_start:
        normalized_start = str(state.comfy_input_dir)

    for picker in (_pick_image_with_powershell, _pick_image_with_zenity, _pick_image_with_kdialog):
        selected = picker(normalized_start)
        if not selected:
            continue
        try:
            resolved = Path(_normalize_input_dir(selected, field_label="input image")).expanduser()
        except ValueError:
            return None
        if resolved.exists() and resolved.is_file():
            return str(resolved)
        return None

    return None


def _workflow_supports_resolution(wf: WorkflowDef) -> bool:
    for node in wf.template_prompt.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        width = inputs.get("width")
        height = inputs.get("height")
        if isinstance(width, bool) or isinstance(height, bool):
            continue
        if isinstance(width, (int, float)) and isinstance(height, (int, float)):
            return True
    return False


def _resolve_resolution_preset(preset_id: str | None) -> tuple[int, int] | None:
    if preset_id is None:
        return None
    key = str(preset_id).strip()
    if not key:
        return None
    if key not in RESOLUTION_PRESET_MAP:
        raise ValueError(
            f"unknown resolution_preset '{key}', expected one of: {', '.join(sorted(RESOLUTION_PRESET_MAP.keys()))}"
        )
    return RESOLUTION_PRESET_MAP[key]


@app.get("/api/workflows")
def api_workflows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for wf in state.workflows.values():
        out.append(
            {
                "name": wf.name,
                "display_name": wf.display_name or wf.name,
                "group": wf.group or "Workflows",
                "description": wf.description,
                "input_type": wf.input_type,
                "input_extensions": wf.input_extensions,
                "supports_resolution": _workflow_supports_resolution(wf),
                "parameters": {
                    name: {
                        "label": p.label,
                        "type": p.type,
                        "default": _api_param_default(wf, name, p),
                        "min": p.min,
                        "max": p.max,
                    }
                    for name, p in wf.parameters.items()
                },
            }
        )
    return sorted(out, key=lambda x: (x.get("group", ""), x.get("display_name", x["name"])))


@app.get("/api/resolution-presets")
def api_resolution_presets() -> dict[str, Any]:
    return {"presets": RESOLUTION_PRESETS}


@app.get("/api/loras")
def api_loras() -> list[str]:
    return _discover_loras()


@app.get("/api/prompt-presets")
def api_prompt_presets(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    return {"items": state.db.list_prompt_presets(limit=limit)}


@app.post("/api/prompt-presets", status_code=201)
def api_save_prompt_preset(req: PromptPresetSaveRequest) -> dict[str, Any]:
    try:
        item = state.db.save_prompt_preset(req.name, req.positive_prompt, req.negative_prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return item


@app.get("/api/settings-presets")
def api_settings_presets(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    return {"items": state.db.list_settings_presets(limit=limit)}


@app.post("/api/settings-presets", status_code=201)
def api_save_settings_preset(req: SettingsPresetSaveRequest) -> dict[str, Any]:
    try:
        item = state.db.save_settings_preset(req.name, req.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return item


@app.post("/api/reload/workflows")
def api_reload_workflows() -> dict[str, Any]:
    try:
        state.reload_workflows()
    except WorkflowDefError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(state.workflows), "workflows": sorted(state.workflows.keys())}


@app.post("/api/reload/loras")
def api_reload_loras() -> dict[str, Any]:
    loras = _discover_loras()
    return {"count": len(loras), "loras": loras}


@app.post("/api/input-dirs/normalize")
def api_normalize_input_dir(req: InputPathRequest) -> dict[str, str]:
    try:
        normalized = _normalize_input_dir(req.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"normalized_path": normalized}


@app.get("/api/input-dirs/recent")
def api_recent_input_dirs(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    return {"paths": state.db.list_input_dir_history(limit=limit)}


@app.get("/api/input-dirs/default")
def api_default_input_dir() -> dict[str, Any]:
    path = state.comfy_input_dir.expanduser().resolve()
    return {"default_path": str(path), "exists": path.exists() and path.is_dir()}


@app.post("/api/input-dirs/recent")
def api_touch_input_dir(req: InputPathRequest) -> dict[str, str]:
    try:
        normalized = _normalize_input_dir(req.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    path_obj = Path(normalized)
    if not path_obj.exists() or not path_obj.is_dir():
        raise HTTPException(status_code=400, detail=f"input directory not found: {normalized}")
    state.db.touch_input_dir_history(normalized)
    return {"path": normalized}


@app.post("/api/pick-directory")
def api_pick_directory(req: PickDirectoryRequest | None = None) -> dict[str, str]:
    start_dir = req.start_dir if req else None
    picked = _pick_directory(start_dir)
    if not picked:
        raise HTTPException(status_code=400, detail="directory selection canceled or no picker available")
    return {"path": picked}


@app.post("/api/pick-image")
def api_pick_image(req: PickImageRequest | None = None) -> dict[str, str]:
    start_path = req.start_path if req else None
    picked = _pick_image(start_path)
    if not picked:
        raise HTTPException(status_code=400, detail="image selection canceled or no picker available")
    return {"path": picked}


@app.post("/api/upload/input-image")
async def api_upload_input_image(
    request: Request,
    x_filename: str | None = Header(default=None),
) -> dict[str, str]:
    raw_name = Path(x_filename or "upload.png").name
    suffix = Path(raw_name).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported image extension: {suffix or '(none)'} (allowed: {', '.join(sorted(IMAGE_EXTENSIONS))})",
        )

    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(raw_name).stem).strip("._") or "upload"
    unique = f"{int(time.time() * 1000)}_{safe_stem}{suffix}"
    state.comfy_input_dir.mkdir(parents=True, exist_ok=True)
    dest = (state.comfy_input_dir / unique).resolve()

    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="uploaded file is empty")
    dest.write_bytes(data)

    return {"path": str(dest)}


def _list_inputs(input_dir: Path, exts: list[str]) -> list[Path]:
    allowed = {e.lower() for e in exts}
    return sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed])


def _derive_split_job_name(base_name: str | None, input_file: Path) -> str:
    base = str(base_name or "").strip()
    stem = input_file.stem
    if base:
        return f"{base} | {stem}"
    return stem


def _enqueue_job_from_files(
    wf: WorkflowDef,
    files: list[Path],
    params: dict[str, Any],
    resolution_preset: str | None,
    flip_orientation: bool,
    priority: int,
    input_dir: str,
    job_name: str | None = None,
    move_processed: bool = False,
) -> dict[str, Any]:
    try:
        resolved = resolve_params(wf, params)
        resolution = _resolve_resolution_preset(resolution_preset)
        specs = build_prompts(
            wf,
            files,
            resolved,
            comfy_input_dir=state.comfy_input_dir,
            resolution=resolution,
            flip_orientation=bool(flip_orientation),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = state.db.create_job(
        workflow_name=wf.name,
        job_name=(str(job_name).strip() if job_name is not None else None),
        input_dir=input_dir,
        params_json=resolved,
        prompt_specs=specs,
        priority=priority,
        move_processed=bool(move_processed),
    )
    state.db.touch_input_dir_history(input_dir)
    return {"job_id": job_id, "job_name": (str(job_name).strip() if job_name else None), "prompt_count": len(specs), "input_dir": input_dir}


@app.post("/api/jobs", status_code=201)
def create_job(req: JobCreateRequest) -> dict[str, Any]:
    wf = state.workflows.get(req.workflow_name)
    if not wf:
        raise HTTPException(status_code=400, detail=f"unknown workflow: {req.workflow_name}")

    try:
        normalized_input_dir = _normalize_input_dir(req.input_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    input_dir = Path(normalized_input_dir).expanduser().resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"input directory not found: {input_dir}")

    files = _list_inputs(input_dir, wf.input_extensions)
    if not files:
        raise HTTPException(status_code=400, detail=f"no matching input files in {input_dir}")

    if bool(req.split_by_input):
        created: list[dict[str, Any]] = []
        for src in files:
            created.append(
                _enqueue_job_from_files(
                    wf=wf,
                    files=[src],
                    params=req.params,
                    resolution_preset=req.resolution_preset,
                    flip_orientation=bool(req.flip_orientation),
                    priority=req.priority,
                    input_dir=normalized_input_dir,
                    job_name=_derive_split_job_name(req.job_name, src),
                    move_processed=bool(req.move_processed),
                )
            )
        return {
            "job_ids": [int(item["job_id"]) for item in created],
            "job_count": len(created),
            "prompt_count": int(sum(int(item["prompt_count"]) for item in created)),
            "input_dir": normalized_input_dir,
        }

    return _enqueue_job_from_files(
        wf=wf,
        files=files,
        params=req.params,
        resolution_preset=req.resolution_preset,
        flip_orientation=bool(req.flip_orientation),
        priority=req.priority,
        input_dir=normalized_input_dir,
        job_name=req.job_name,
        move_processed=bool(req.move_processed),
    )


@app.post("/api/jobs/single", status_code=201)
def create_single_job(req: SingleJobCreateRequest) -> dict[str, Any]:
    wf = state.workflows.get(req.workflow_name)
    if not wf:
        raise HTTPException(status_code=400, detail=f"unknown workflow: {req.workflow_name}")

    try:
        normalized_image = _normalize_input_dir(req.input_image, field_label="input image")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    image_path = Path(normalized_image).expanduser().resolve()
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=400, detail=f"input image not found: {image_path}")

    allowed = {ext.lower() for ext in wf.input_extensions}
    if image_path.suffix.lower() not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise HTTPException(status_code=400, detail=f"unsupported input image extension: {image_path.suffix} (allowed: {allowed_text})")

    return _enqueue_job_from_files(
        wf=wf,
        files=[image_path],
        params=req.params,
        resolution_preset=req.resolution_preset,
        flip_orientation=bool(req.flip_orientation),
        priority=req.priority,
        input_dir=str(image_path.parent),
        job_name=req.job_name,
        move_processed=bool(req.move_processed),
    )


@app.get("/api/jobs")
def list_jobs(status: str | None = Query(default=None)) -> list[dict[str, Any]]:
    return state.db.list_jobs(status=status)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int) -> dict[str, Any]:
    detail = state.db.get_job(job_id)
    if not detail:
        raise HTTPException(status_code=404, detail="job not found")
    return detail


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: int) -> dict[str, Any]:
    detail = state.db.cancel_job(job_id)
    if not detail:
        raise HTTPException(status_code=404, detail="job not found")
    return detail


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: int) -> dict[str, Any]:
    detail = state.db.retry_job(job_id)
    if not detail:
        raise HTTPException(status_code=404, detail="job not found")
    return detail


@app.post("/api/queue/pause")
def queue_pause() -> dict[str, Any]:
    state.db.pause()
    return {"worker": "paused"}


@app.post("/api/queue/resume")
def queue_resume() -> dict[str, Any]:
    state.db.resume()
    return {"worker": "running"}


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    counts = state.db.queue_counts()
    return {
        "comfy": health_check(state.comfy_base_url),
        "worker": "paused" if state.db.is_paused() else "running",
        "pending": counts["pending"],
        "running": counts["running"],
    }


@app.get("/api/jobs/{job_id}/log")
def get_job_log(job_id: int) -> PlainTextResponse:
    detail = state.db.get_job(job_id)
    if not detail:
        raise HTTPException(status_code=404, detail="job not found")

    logs: list[str] = []
    for prompt in detail["prompts"]:
        log_file = state.data_dir / "logs" / f"{job_id}_{prompt['id']}.log"
        if log_file.exists():
            logs.append(f"=== prompt {prompt['id']} ===")
            logs.append(log_file.read_text())

    return PlainTextResponse("\n".join(logs))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8585"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
