from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from db import QueueDB
from defs import WorkflowDef
from prompt_builder import PromptSpec, build_prompts, resolve_params

WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


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


def normalize_submit_path(raw_path: str, field_label: str = "input directory") -> str:
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

    return str(Path(value).expanduser().resolve())


def get_workflow_or_error(workflows: dict[str, WorkflowDef], workflow_name: str) -> WorkflowDef:
    wf = workflows.get(workflow_name)
    if not wf:
        raise ValueError(f"unknown workflow: {workflow_name}")
    return wf


def list_matching_input_files(input_dir: Path, extensions: list[str]) -> list[Path]:
    allowed = {e.lower() for e in extensions}
    return sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed])


def validate_batch_input_dir(workflow: WorkflowDef, input_dir: str) -> tuple[str, list[Path]]:
    normalized_input_dir = normalize_submit_path(input_dir)
    path = Path(normalized_input_dir).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"input directory not found: {path}")

    files = list_matching_input_files(path, workflow.input_extensions)
    if not files:
        raise ValueError(f"no matching input files in {path}")
    return normalized_input_dir, files


def validate_single_input_file(workflow: WorkflowDef, input_path: str, field_label: str = "input image") -> Path:
    normalized = normalize_submit_path(input_path, field_label=field_label)
    path = Path(normalized).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"{field_label} not found: {path}")

    allowed = {ext.lower() for ext in workflow.input_extensions}
    if path.suffix.lower() not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"unsupported {field_label} extension: {path.suffix} (allowed: {allowed_text})")
    return path


def sanitize_stage_filename(name: str) -> str:
    base = Path(name or "").name
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(base).stem).strip("._") or "input"
    suffix = Path(base).suffix
    if suffix and not re.fullmatch(r"\.[A-Za-z0-9]+", suffix):
        suffix = re.sub(r"[^A-Za-z0-9]+", "", suffix)
        suffix = f".{suffix}" if suffix else ""
    return f"{stem}{suffix.lower()}"


def dedupe_stage_dest(stage_dir: Path, filename: str) -> Path:
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


def stage_input_files(
    files: list[Path],
    comfy_input_dir: Path,
    staging_dirname: str = "_video_queue_staging",
) -> tuple[list[Path], dict[str, str]]:
    batch_token = f"{int(time.time() * 1000)}_{time.time_ns() % 1_000_000:06d}"
    stage_dir = (comfy_input_dir / staging_dirname / batch_token).resolve()
    stage_dir.mkdir(parents=True, exist_ok=True)

    staged_paths: list[Path] = []
    source_by_staged: dict[str, str] = {}
    for src in files:
        source_path = src.expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"input file not found for staging: {source_path}")
        filename = sanitize_stage_filename(source_path.name)
        dest = dedupe_stage_dest(stage_dir, filename).resolve()
        shutil.copy2(source_path, dest)
        staged_paths.append(dest)
        source_by_staged[str(dest)] = str(source_path)

    return staged_paths, source_by_staged


def resolve_per_file_overrides_for_staged(
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


def normalize_legacy_submit_params(workflow: WorkflowDef, params: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(params or {})
    if not out:
        return out

    if "extra_lora_high_name" in workflow.parameters and "lora_high_name" in out and "extra_lora_high_name" not in out:
        out["extra_lora_high_name"] = out.pop("lora_high_name")
    if "extra_lora_low_name" in workflow.parameters and "lora_low_name" in out and "extra_lora_low_name" not in out:
        out["extra_lora_low_name"] = out.pop("lora_low_name")
    if "lora_strength" in out:
        strength = out.pop("lora_strength")
        if "extra_lora_strength_high" in workflow.parameters and "extra_lora_strength_high" not in out:
            out["extra_lora_strength_high"] = strength
        if "extra_lora_strength_low" in workflow.parameters and "extra_lora_strength_low" not in out:
            out["extra_lora_strength_low"] = strength

    if (
        "extra_lora_enabled" in workflow.parameters
        and "extra_lora_enabled" not in out
        and any(key in out for key in ("extra_lora_high_name", "extra_lora_low_name", "extra_lora_strength_high", "extra_lora_strength_low"))
    ):
        out["extra_lora_enabled"] = True

    return out


def prepare_prompt_specs(
    workflow: WorkflowDef,
    input_files: list[str | Path],
    params: dict[str, Any],
    *,
    comfy_input_dir: Path,
    resolution: tuple[int, int] | None = None,
    flip_orientation: bool = False,
    per_file_params: dict[str, dict[str, Any]] | None = None,
    stage_inputs: bool = True,
    staging_dirname: str = "_video_queue_staging",
) -> tuple[dict[str, Any], list[PromptSpec]]:
    source_files = [Path(p).expanduser().resolve() for p in input_files]
    normalized_params = normalize_legacy_submit_params(workflow, params)
    resolved = resolve_params(workflow, normalized_params)

    files_for_build = source_files
    prompt_overrides = per_file_params or {}
    source_by_built: dict[str, str] = {}
    if stage_inputs and source_files:
        files_for_build, source_by_built = stage_input_files(
            source_files,
            comfy_input_dir=comfy_input_dir,
            staging_dirname=staging_dirname,
        )
        prompt_overrides = resolve_per_file_overrides_for_staged(source_files, files_for_build, per_file_params)

    built_specs = build_prompts(
        workflow,
        files_for_build,
        normalized_params,
        per_file_params=prompt_overrides,
        comfy_input_dir=comfy_input_dir,
        resolution=resolution,
        flip_orientation=bool(flip_orientation),
    )

    specs: list[PromptSpec] = []
    for spec in built_specs:
        built_key = str(Path(spec.input_file).expanduser().resolve()) if spec.input_file else spec.input_file
        source_input = source_by_built.get(built_key, spec.input_file)
        specs.append(
            PromptSpec(
                input_file=source_input,
                prompt_json=spec.prompt_json,
                seed_used=spec.seed_used,
                output_prefix=spec.output_prefix,
            )
        )
    return resolved, specs


def enqueue_job(
    db: QueueDB,
    *,
    workflow: WorkflowDef,
    input_dir: str,
    params_json: dict[str, Any],
    prompt_specs: list[PromptSpec],
    priority: int = 0,
    job_name: str | None = None,
    move_processed: bool = False,
) -> int:
    return db.create_job(
        workflow_name=workflow.name,
        job_name=(str(job_name).strip() if job_name is not None else None),
        input_dir=input_dir,
        params_json=params_json,
        prompt_specs=prompt_specs,
        priority=priority,
        move_processed=bool(move_processed),
    )


__all__ = [
    "dedupe_stage_dest",
    "enqueue_job",
    "get_workflow_or_error",
    "list_matching_input_files",
    "normalize_submit_path",
    "normalize_legacy_submit_params",
    "prepare_prompt_specs",
    "resolve_per_file_overrides_for_staged",
    "sanitize_stage_filename",
    "stage_input_files",
    "validate_batch_input_dir",
    "validate_single_input_file",
]
