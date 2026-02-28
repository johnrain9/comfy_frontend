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

from auto_prompt import AutoPromptGenerator, LMStudioUnavailable
from comfy_client import health_check
from db import QueueDB
from defs import ParameterDef, WorkflowDef, WorkflowDefError, load_all
from prompt_builder import PromptSpec, build_prompts, resolve_params
from worker import Worker

LORA_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
UPSCALE_MODEL_EXTENSIONS = {".pth", ".pt", ".ckpt", ".safetensors", ".bin"}
WAN_POSITIVE_TEMPLATE = "(at 0 second: )(at 3 second: )(at 7 second: )"
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
QUEUE_STAGING_DIRNAME = "_video_queue_staging"
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
    input_dir: str = ""
    prompt_mode: str = "manual"
    params: dict[str, Any] = Field(default_factory=dict)
    per_file_params: dict[str, dict[str, Any]] = Field(default_factory=dict)
    auto_prompt_meta: dict[str, Any] = Field(default_factory=dict)
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
    mode: str = "video_gen"
    positive_prompt: str = ""
    negative_prompt: str = ""


class SettingsPresetSaveRequest(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AutoPromptRequest(BaseModel):
    image_paths: list[str] = Field(default_factory=list)
    workflow_name: str
    stage: str = "both"
    captions: dict[str, str] = Field(default_factory=dict)
    system_prompt_override: str | None = None
    lmstudio_url: str | None = None


class AppState:
    def __init__(self) -> None:
        self.root = Path(os.environ.get("VIDEO_QUEUE_ROOT", str(Path.home() / "video_queue"))).expanduser().resolve()
        self.data_dir = self.root / "data"
        self.static_dir = self.root / "static"
        self.ui_build_dir = self.root / "ui" / "build"
        self.defs_dir = Path(os.environ.get("WORKFLOW_DEFS_DIR", str(self.root / "workflow_defs_v2"))).expanduser().resolve()
        self.comfy_root = Path(os.environ.get("COMFY_ROOT", str(Path.home() / "ComfyUI"))).expanduser().resolve()
        self.comfy_input_dir = self.comfy_root / "input"
        self.comfy_base_url = os.environ.get("COMFY_BASE_URL", "http://127.0.0.1:8188")
        self.lmstudio_url = os.environ.get("LMSTUDIO_URL", "http://127.0.0.1:1234")
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
# Mount V2 before declaring root handlers so /v2 is always resolved explicitly.
if state.ui_build_dir.exists():
    app.mount("/v2", StaticFiles(directory=str(state.ui_build_dir), html=True), name="ui_v2")
else:
    @app.get("/v2")
    @app.get("/v2/{path:path}")
    def ui_v2_unavailable() -> PlainTextResponse:
        return PlainTextResponse(
            "UI V2 build not found. Run: cd ui && npm install && npm run build",
            status_code=503,
        )


@app.on_event("startup")
def on_startup() -> None:
    state.data_dir.mkdir(parents=True, exist_ok=True)
    try:
        state.reload_workflows()
    except WorkflowDefError as exc:
        raise RuntimeError(f"Failed to load workflow definitions: {exc}") from exc
    state.worker = Worker(state.db, state.workflows, state.comfy_base_url, state.data_dir)
    state.worker.start()
    if state.ui_build_dir.exists():
        print(f"[video_queue] UI V2 enabled at /v2 from {state.ui_build_dir}")
    else:
        print(f"[video_queue] UI V2 build missing at {state.ui_build_dir}; /v2 returns setup instructions")


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


@app.get("/legacy")
def legacy_index() -> FileResponse:
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


def _discover_upscale_models() -> list[str]:
    roots = [
        state.comfy_root / "models" / "upscale_models",
        state.comfy_root / "upscale_models",
    ]

    seen: set[str] = set()
    found: list[str] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in UPSCALE_MODEL_EXTENSIONS:
                continue
            try:
                name = path.relative_to(root).as_posix()
            except ValueError:
                name = path.name
            if not name or name in seen:
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


def _infer_workflow_category(wf: WorkflowDef) -> str:
    if wf.category:
        return str(wf.category).strip().lower()
    name = str(wf.name or "").lower()
    if "image-gen" in name or "t2i" in name or "i2i" in name:
        return "image_gen"
    if "upscale-images" in name:
        return "image_upscale"
    if "upscale" in name:
        return "video_upscale"
    return "video_gen"


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
                "category": _infer_workflow_category(wf),
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


@app.get("/api/upscale-models")
def api_upscale_models() -> list[str]:
    return _discover_upscale_models()


@app.get("/api/prompt-presets")
def api_prompt_presets(
    limit: int = Query(default=200, ge=1, le=1000),
    mode: str | None = Query(default=None),
) -> dict[str, Any]:
    return {"items": state.db.list_prompt_presets(limit=limit, mode=mode)}


@app.post("/api/prompt-presets", status_code=201)
def api_save_prompt_preset(req: PromptPresetSaveRequest) -> dict[str, Any]:
    try:
        item = state.db.save_prompt_preset(req.name, req.positive_prompt, req.negative_prompt, mode=req.mode)
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


@app.post("/api/reload/upscale-models")
def api_reload_upscale_models() -> dict[str, Any]:
    models = _discover_upscale_models()
    return {"count": len(models), "models": models}


@app.get("/api/auto-prompt/capability")
def api_auto_prompt_capability(lmstudio_url: str | None = Query(default=None)) -> dict[str, Any]:
    gen = _auto_prompt_generator(lmstudio_url=lmstudio_url)
    try:
        gen.check_available()
        gen.ensure_required_models_loaded(stage="both")
    except LMStudioUnavailable as exc:
        return {
            "available": False,
            "message": str(exc),
            "lmstudio_url": gen.lmstudio_url,
            "stage1_model": gen.stage1_model,
            "stage2_model": gen.stage2_model,
        }
    return {
        "available": True,
        "message": "ok",
        "lmstudio_url": gen.lmstudio_url,
        "stage1_model": gen.stage1_model,
        "stage2_model": gen.stage2_model,
    }


@app.post("/api/auto-prompt")
def api_auto_prompt(req: AutoPromptRequest) -> dict[str, Any]:
    stage = str(req.stage or "both").strip().lower()
    if stage not in {"caption", "motion", "both"}:
        raise HTTPException(status_code=400, detail="stage must be one of: caption, motion, both")

    wf = state.workflows.get(req.workflow_name)
    if not wf:
        raise HTTPException(status_code=400, detail=f"unknown workflow: {req.workflow_name}")

    image_paths: list[str] = []
    for raw in req.image_paths:
        normalized = _normalize_input_dir(raw, field_label="image path")
        p = Path(normalized).expanduser().resolve()
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=400, detail=f"image file not found: {p}")
        image_paths.append(str(p))

    if stage in {"caption", "both"} and not image_paths:
        raise HTTPException(status_code=400, detail="image_paths is required for caption/both stage")
    if stage == "motion" and not req.captions:
        raise HTTPException(status_code=400, detail="captions is required for motion stage")
    if stage == "motion" and not image_paths and req.captions:
        image_paths = sorted({str(Path(k).expanduser().resolve()) for k in req.captions.keys()})

    gen = _auto_prompt_generator(lmstudio_url=req.lmstudio_url)
    try:
        gen.check_available()
        gen.ensure_required_models_loaded(stage=stage)
    except LMStudioUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    ctx = gen.extract_workflow_context(wf)
    try:
        result = gen.generate_batch(
            image_paths=image_paths,
            workflow_context=ctx,
            stage=stage,
            captions=req.captions,
            system_prompt_override=req.system_prompt_override,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"auto-prompt generation failed: {exc}") from exc
    return result


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
    x_subdir: str | None = Header(default=None),
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
    subdir = str(x_subdir or "").strip().replace("\\", "/")
    if subdir:
        subdir = re.sub(r"[^A-Za-z0-9_./-]+", "_", subdir).strip("/")
    base_dir = state.comfy_input_dir
    if subdir:
        base_dir = (state.comfy_input_dir / subdir).resolve()
        try:
            base_dir.relative_to(state.comfy_input_dir.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid upload subdir") from exc
    base_dir.mkdir(parents=True, exist_ok=True)
    dest = (base_dir / unique).resolve()

    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="uploaded file is empty")
    dest.write_bytes(data)

    return {"path": str(dest), "dir": str(base_dir)}


def _list_inputs(input_dir: Path, exts: list[str]) -> list[Path]:
    allowed = {e.lower() for e in exts}
    return sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed])


def _sanitize_stage_filename(name: str) -> str:
    base = Path(name or "").name
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(base).stem).strip("._") or "input"
    suffix = Path(base).suffix
    if suffix and not re.fullmatch(r"\.[A-Za-z0-9]+", suffix):
        suffix = re.sub(r"[^A-Za-z0-9]+", "", suffix)
        suffix = f".{suffix}" if suffix else ""
    return f"{stem}{suffix.lower()}"


def _dedupe_stage_dest(stage_dir: Path, filename: str) -> Path:
    candidate = stage_dir / filename
    if not candidate.exists():
        return candidate

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    idx = 2
    while True:
        candidate = stage_dir / f"{stem}__{idx}{suffix}"
        if not candidate.exists():
            return candidate
        idx += 1


def _stage_input_files(files: list[Path]) -> tuple[list[Path], dict[str, str]]:
    batch_token = f"{int(time.time() * 1000)}_{time.time_ns() % 1_000_000:06d}"
    stage_dir = (state.comfy_input_dir / QUEUE_STAGING_DIRNAME / batch_token).resolve()
    stage_dir.mkdir(parents=True, exist_ok=True)

    staged_paths: list[Path] = []
    source_by_staged: dict[str, str] = {}
    for src in files:
        source_path = src.expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"input file not found for staging: {source_path}")
        filename = _sanitize_stage_filename(source_path.name)
        dest = _dedupe_stage_dest(stage_dir, filename).resolve()
        shutil.copy2(source_path, dest)
        staged_paths.append(dest)
        source_by_staged[str(dest)] = str(source_path)

    return staged_paths, source_by_staged


def _derive_split_job_name(base_name: str | None, input_file: Path) -> str:
    base = str(base_name or "").strip()
    stem = input_file.stem
    if base:
        return f"{base} | {stem}"
    return stem


def _ensure_worker_running() -> None:
    if not state.worker:
        return
    if state.db.is_paused():
        return
    if state.worker.running:
        return
    state.worker.start()


def _resolve_per_file_overrides_for_staged(
    source_files: list[Path],
    staged_files: list[Path],
    per_file_params: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    raw = per_file_params or {}
    if not raw:
        return {}

    out: dict[str, dict[str, Any]] = {}
    for src, staged in zip(source_files, staged_files):
        src_abs = str(src.expanduser().resolve())
        src_name = src.name
        override = raw.get(src_abs)
        if override is None:
            override = raw.get(src_name)
        if override is None:
            continue
        if not isinstance(override, dict):
            raise ValueError(f"per_file_params[{src_name}] must be an object")
        out[str(staged.expanduser().resolve())] = dict(override)
    return out


def _auto_prompt_generator(lmstudio_url: str | None = None) -> AutoPromptGenerator:
    return AutoPromptGenerator(lmstudio_url=lmstudio_url or state.lmstudio_url)


def _validate_prompt_mode(
    *,
    prompt_mode: str,
    per_file_params: dict[str, dict[str, Any]] | None,
) -> str:
    mode = str(prompt_mode or "manual").strip().lower()
    valid = {"manual", "per-image manual", "per-image auto"}
    if mode not in valid:
        raise ValueError("prompt_mode must be one of: manual, per-image manual, per-image auto")
    if mode in {"per-image manual", "per-image auto"} and not (per_file_params or {}):
        raise ValueError("per_file_params is required for prompt_mode per-image manual/auto")
    return mode


def _enqueue_job_from_files(
    wf: WorkflowDef,
    files: list[Path],
    params: dict[str, Any],
    per_file_params: dict[str, dict[str, Any]] | None,
    resolution_preset: str | None,
    flip_orientation: bool,
    priority: int,
    input_dir: str,
    job_name: str | None = None,
    move_processed: bool = False,
) -> dict[str, Any]:
    _ensure_worker_running()
    source_files = [Path(p).expanduser().resolve() for p in files]
    try:
        resolved = resolve_params(wf, params)
        resolution = _resolve_resolution_preset(resolution_preset)
        if source_files:
            staged_files, source_by_staged = _stage_input_files(source_files)
        else:
            staged_files, source_by_staged = [], {}
        staged_per_file_params = _resolve_per_file_overrides_for_staged(source_files, staged_files, per_file_params)
        staged_specs = build_prompts(
            wf,
            staged_files,
            resolved,
            per_file_params=staged_per_file_params,
            comfy_input_dir=state.comfy_input_dir,
            resolution=resolution,
            flip_orientation=bool(flip_orientation),
        )
        specs: list[PromptSpec] = []
        for spec in staged_specs:
            staged_key = str(Path(spec.input_file).expanduser().resolve())
            source_input = source_by_staged.get(staged_key, spec.input_file)
            specs.append(
                PromptSpec(
                    input_file=source_input,
                    prompt_json=spec.prompt_json,
                    seed_used=spec.seed_used,
                    output_prefix=spec.output_prefix,
                )
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
        _validate_prompt_mode(prompt_mode=req.prompt_mode, per_file_params=req.per_file_params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    files: list[Path] = []
    if wf.input_type in {"image", "video"}:
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
    else:
        normalized_input_dir = str(state.comfy_input_dir.expanduser().resolve())

    if bool(req.split_by_input) and files:
        created: list[dict[str, Any]] = []
        for src in files:
            created.append(
                _enqueue_job_from_files(
                    wf=wf,
                    files=[src],
                    params=req.params,
                    per_file_params=req.per_file_params,
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
        per_file_params=req.per_file_params,
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
        per_file_params={},
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
    _ensure_worker_running()
    return {"worker": "running"}


@app.post("/api/queue/clear")
def queue_clear() -> dict[str, Any]:
    summary = state.db.clear_queue()
    return {
        "ok": True,
        **summary,
    }


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    _ensure_worker_running()
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
