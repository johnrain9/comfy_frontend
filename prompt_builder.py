from __future__ import annotations

import copy
import random
import struct
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from defs import ParameterDef, WorkflowDef

_CONTEXT_SCHEDULE_MAP = {
    "uniform_standard": "standard_uniform",
}


@dataclass(frozen=True)
class PromptSpec:
    input_file: str
    prompt_json: dict[str, Any]
    seed_used: int | None
    output_prefix: str



def _coerce_param(param: ParameterDef, value: Any) -> Any:
    if param.type == "text":
        return "" if value is None else str(value)
    if param.type == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"1", "true", "yes", "on"}:
                return True
            if v in {"0", "false", "no", "off"}:
                return False
        raise ValueError(f"parameter '{param.name}' must be bool")
    if param.type == "int":
        if isinstance(value, bool):
            raise ValueError(f"parameter '{param.name}' must be int")
        try:
            out = int(value)
        except Exception as exc:
            raise ValueError(f"parameter '{param.name}' must be int") from exc
        if param.min is not None and out < param.min:
            raise ValueError(f"parameter '{param.name}' below min {param.min}")
        if param.max is not None and out > param.max:
            raise ValueError(f"parameter '{param.name}' above max {param.max}")
        return out
    if param.type == "float":
        try:
            out = float(value)
        except Exception as exc:
            raise ValueError(f"parameter '{param.name}' must be float") from exc
        if param.min is not None and out < param.min:
            raise ValueError(f"parameter '{param.name}' below min {param.min}")
        if param.max is not None and out > param.max:
            raise ValueError(f"parameter '{param.name}' above max {param.max}")
        return out
    raise ValueError(f"unsupported parameter type: {param.type}")



def resolve_params(workflow_def: WorkflowDef, params: dict[str, Any] | None) -> dict[str, Any]:
    params = params or {}

    unknown = sorted(set(params.keys()) - set(workflow_def.parameters.keys()))
    if unknown:
        raise ValueError(f"unknown parameters for {workflow_def.name}: {', '.join(unknown)}")

    resolved: dict[str, Any] = {}
    for name, param in workflow_def.parameters.items():
        raw = params[name] if name in params else param.default
        resolved[name] = _coerce_param(param, raw)

    return resolved



def _set_candidate_field(node_inputs: dict[str, Any], preferred: str | None, candidates: list[str] | None, value: Any) -> bool:
    if preferred:
        if preferred in node_inputs:
            node_inputs[preferred] = value
            return True
        node_inputs[preferred] = value
        return True

    if candidates:
        for field in candidates:
            if field in node_inputs:
                node_inputs[field] = value
                return True
        node_inputs[candidates[0]] = value
        return True

    return False



def _normalize_context_schedule_values(prompt: dict[str, Any]) -> None:
    for node in prompt.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "WanContextWindowsManual":
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        value = inputs.get("context_schedule")
        if isinstance(value, str) and value in _CONTEXT_SCHEDULE_MAP:
            inputs["context_schedule"] = _CONTEXT_SCHEDULE_MAP[value]


def _flip_orientation(prompt: dict[str, Any]) -> None:
    for node in prompt.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        width = inputs.get("width")
        height = inputs.get("height")
        if isinstance(width, bool) or isinstance(height, bool):
            continue
        if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
            continue
        inputs["width"], inputs["height"] = height, width


def _apply_resolution(prompt: dict[str, Any], width: int, height: int) -> None:
    for node in prompt.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        current_w = inputs.get("width")
        current_h = inputs.get("height")
        if isinstance(current_w, bool) or isinstance(current_h, bool):
            continue
        if not isinstance(current_w, (int, float)) or not isinstance(current_h, (int, float)):
            continue
        inputs["width"] = int(width)
        inputs["height"] = int(height)


def _read_png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as fh:
        header = fh.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return (int(width), int(height))


def _read_gif_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as fh:
        header = fh.read(10)
    if len(header) < 10 or header[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    width, height = struct.unpack("<HH", header[6:10])
    return (int(width), int(height))


def _read_bmp_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as fh:
        header = fh.read(26)
    if len(header) < 26 or header[:2] != b"BM":
        return None
    dib_size = struct.unpack("<I", header[14:18])[0]
    if dib_size < 12:
        return None
    if dib_size >= 40:
        width, height = struct.unpack("<ii", header[18:26])
        return (abs(int(width)), abs(int(height)))
    width, height = struct.unpack("<HH", header[18:22])
    return (int(width), int(height))


def _read_webp_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as fh:
        header = fh.read(40)
    if len(header) < 16 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        return None
    chunk = header[12:16]
    if chunk == b"VP8X" and len(header) >= 30:
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return (width, height)
    if chunk == b"VP8 " and len(header) >= 30 and header[23:26] == b"\x9d\x01\x2a":
        width, height = struct.unpack("<HH", header[26:30])
        return (width & 0x3FFF, height & 0x3FFF)
    if chunk == b"VP8L" and len(header) >= 25 and header[20] == 0x2F:
        bits = int.from_bytes(header[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return (width, height)
    return None


def _read_jpeg_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as fh:
        if fh.read(2) != b"\xFF\xD8":
            return None
        while True:
            prefix = fh.read(1)
            if not prefix:
                return None
            if prefix != b"\xFF":
                continue
            marker = fh.read(1)
            while marker == b"\xFF":
                marker = fh.read(1)
            if not marker or marker in (b"\xD8", b"\xD9"):
                return None
            if marker in (b"\x01",) or 0xD0 <= marker[0] <= 0xD7:
                continue
            length_raw = fh.read(2)
            if len(length_raw) < 2:
                return None
            segment_length = struct.unpack(">H", length_raw)[0]
            if segment_length < 2:
                return None
            if marker[0] in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                sof = fh.read(5)
                if len(sof) < 5:
                    return None
                height, width = struct.unpack(">HH", sof[1:5])
                return (int(width), int(height))
            fh.seek(segment_length - 2, 1)


def _read_image_size(path: Path) -> tuple[int, int] | None:
    try:
        suffix = path.suffix.lower()
        if suffix == ".png":
            return _read_png_size(path)
        if suffix in {".jpg", ".jpeg"}:
            return _read_jpeg_size(path)
        if suffix == ".webp":
            return _read_webp_size(path)
        if suffix == ".bmp":
            return _read_bmp_size(path)
        if suffix == ".gif":
            return _read_gif_size(path)
    except Exception:
        return None
    return None


def _rounded_multiple(value: float, multiple: int = 16) -> int:
    return max(multiple, int(round(value / multiple) * multiple))


def _aspect_preserving_bounded_dims(
    src_w: int,
    src_h: int,
    scale_multiple: float,
    width_def: ParameterDef | None,
    height_def: ParameterDef | None,
) -> tuple[int, int]:
    target_w = max(1.0, float(src_w) * scale_multiple)
    target_h = max(1.0, float(src_h) * scale_multiple)

    min_scale = 1.0
    if width_def and width_def.min is not None and target_w < width_def.min:
        min_scale = max(min_scale, float(width_def.min) / target_w)
    if height_def and height_def.min is not None and target_h < height_def.min:
        min_scale = max(min_scale, float(height_def.min) / target_h)

    target_w *= min_scale
    target_h *= min_scale

    max_scale = 1.0
    if width_def and width_def.max is not None and target_w > width_def.max:
        max_scale = min(max_scale, float(width_def.max) / target_w)
    if height_def and height_def.max is not None and target_h > height_def.max:
        max_scale = min(max_scale, float(height_def.max) / target_h)

    if max_scale < 1.0:
        target_w *= max_scale
        target_h *= max_scale

    width = _rounded_multiple(target_w)
    height = _rounded_multiple(target_h)

    if width_def:
        if width_def.min is not None:
            width = max(int(width_def.min), width)
        if width_def.max is not None:
            width = min(int(width_def.max), width)
    if height_def:
        if height_def.min is not None:
            height = max(int(height_def.min), height)
        if height_def.max is not None:
            height = min(int(height_def.max), height)

    return width, height


def _apply_scale_multiple_dimensions(
    prompt: dict[str, Any],
    workflow_def: WorkflowDef,
    file_path: Path | None,
    resolved_params: dict[str, Any],
    raw_params: dict[str, Any],
) -> None:
    if file_path is None or "scale_multiple" not in workflow_def.parameters:
        return
    if "width" in raw_params or "height" in raw_params:
        return

    dims = _read_image_size(file_path)
    if dims is None:
        return

    src_w, src_h = dims
    scale_multiple = float(resolved_params.get("scale_multiple", 1.0) or 1.0)
    width_def = workflow_def.parameters.get("width")
    height_def = workflow_def.parameters.get("height")
    width, height = _aspect_preserving_bounded_dims(src_w, src_h, scale_multiple, width_def, height_def)

    for pname, value in (("width", width), ("height", height)):
        pdef = workflow_def.parameters.get(pname)
        if not pdef or not pdef.nodes:
            continue
        for nid in pdef.nodes:
            node = prompt.get(nid)
            if not isinstance(node, dict):
                continue
            inputs = node.setdefault("inputs", {})
            _set_candidate_field(inputs, pdef.field, pdef.fields, value)



def _resolve_for_comfy_input(file_path: Path, comfy_input_dir: Path | None) -> str:
    if comfy_input_dir is None:
        return str(file_path)

    try:
        rel = file_path.resolve().relative_to(comfy_input_dir.resolve())
        return rel.as_posix()
    except ValueError:
        return str(file_path)



def _set_seed(prompt: dict[str, Any], workflow_def: WorkflowDef, randomize: bool) -> int | None:
    if not randomize:
        return None

    binding = workflow_def.file_bindings.get("seed")
    if not binding:
        return None

    seed = int((time.time_ns() ^ random.getrandbits(31)) % (2**63 - 1))
    for nid in binding.nodes:
        node = prompt.get(nid)
        if not isinstance(node, dict):
            continue
        inputs = node.setdefault("inputs", {})
        if binding.fields:
            for f in binding.fields:
                if f in inputs:
                    inputs[f] = seed
        elif binding.field:
            inputs[binding.field] = seed
    return seed



def _normalize_output_prefix(output_prefix: str) -> str:
    raw = str(output_prefix or "").strip()
    if not raw:
        return ""

    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    home_path = PurePosixPath(str(Path.home()).replace("\\", "/"))

    if path.is_absolute() and len(path.parts) >= len(home_path.parts) and path.parts[: len(home_path.parts)] == home_path.parts:
        path = PurePosixPath(*path.parts[len(home_path.parts) :])

    parts = [part for part in path.parts if part not in ("", "/", ".", "..")]
    return PurePosixPath(*parts).as_posix() if parts else ""


def _set_output_prefix(prompt: dict[str, Any], workflow_def: WorkflowDef, output_prefix: str, stem: str) -> str:
    binding = workflow_def.file_bindings.get("output_prefix")
    if not binding:
        return stem

    base = _normalize_output_prefix(output_prefix)
    final = f"{base}/{stem}" if base else stem
    for nid in binding.nodes:
        node = prompt.get(nid)
        if not isinstance(node, dict):
            continue
        inputs = node.setdefault("inputs", {})
        _set_candidate_field(inputs, binding.field, binding.fields, final)
    return final



def _apply_input_binding(prompt: dict[str, Any], workflow_def: WorkflowDef, relative_input_path: str) -> None:
    for binding_name in ("load_image", "load_video", "input_file"):
        binding = workflow_def.file_bindings.get(binding_name)
        if not binding:
            continue
        for nid in binding.nodes:
            node = prompt.get(nid)
            if not isinstance(node, dict):
                continue
            inputs = node.setdefault("inputs", {})
            _set_candidate_field(inputs, binding.field, binding.fields, relative_input_path)



def _apply_switch_states(prompt: dict[str, Any], workflow_def: WorkflowDef) -> None:
    for switch in workflow_def.switch_states:
        node = prompt.get(switch.node_id)
        if not isinstance(node, dict):
            continue
        inputs = node.setdefault("inputs", {})
        inputs[switch.field] = switch.value



def _apply_param_overrides(prompt: dict[str, Any], workflow_def: WorkflowDef, resolved_params: dict[str, Any]) -> None:
    for pname, pdef in workflow_def.parameters.items():
        if not pdef.nodes:
            continue
        value = resolved_params[pname]
        # Some LoRA loader nodes validate lora_name against a non-empty list even when
        # strength is 0. Keep template defaults when extra lora name is left blank.
        if (
            isinstance(value, str)
            and value.strip() == ""
            and pname.startswith("extra_lora")
            and pname.endswith("_name")
        ):
            continue
        for nid in pdef.nodes:
            node = prompt.get(nid)
            if not isinstance(node, dict):
                continue
            inputs = node.setdefault("inputs", {})
            _set_candidate_field(inputs, pdef.field, pdef.fields, value)

    def _extra_slot_active(slot_idx: int) -> bool:
        key_base = "extra_lora" if slot_idx == 1 else f"extra_lora{slot_idx}"
        enabled = bool(resolved_params.get(f"{key_base}_enabled", False))
        if not enabled:
            return False
        high = str(resolved_params.get(f"{key_base}_high_name", "") or "").strip()
        low = str(resolved_params.get(f"{key_base}_low_name", "") or "").strip()
        # Slot is active only when both high/low names are explicitly provided.
        return bool(high and low)

    # Explicit enable + name requirements for extra LoRA slots take precedence over strength values.
    # If inactive, force slot strength to 0 so users do not have to rely on manual zeroing.
    for idx in (1, 2, 3):
        key_base = "extra_lora" if idx == 1 else f"extra_lora{idx}"
        active = _extra_slot_active(idx)
        if active:
            continue
        strength_keys = [
            f"{key_base}_strength_high",
            f"{key_base}_strength_low",
            f"{key_base}_strength",  # backward compatibility
        ]
        for strength_key in strength_keys:
            strength_def = workflow_def.parameters.get(strength_key)
            if not strength_def or not strength_def.nodes:
                continue
            for nid in strength_def.nodes:
                node = prompt.get(nid)
                if not isinstance(node, dict):
                    continue
                inputs = node.setdefault("inputs", {})
                _set_candidate_field(inputs, strength_def.field, strength_def.fields, 0.0)

    # For single-pass WAN workflow, bypass unused extra LoRA nodes to preserve original
    # base-model path when extras are not enabled.
    if workflow_def.name == "wan-context-lite-2stage":
        e1 = _extra_slot_active(1)
        e2 = _extra_slot_active(2)

        def _set_model_input(node_id: str, src_id: str) -> None:
            node = prompt.get(node_id)
            if not isinstance(node, dict):
                return
            inputs = node.setdefault("inputs", {})
            inputs["model"] = [src_id, 0]

        # Slot 1 always chains from base 4-step LoRA nodes.
        _set_model_input("201", "101")
        _set_model_input("202", "102")

        # Slot 2 either chains from slot 1 (when enabled) or directly from base nodes.
        if e1:
            _set_model_input("211", "201")
            _set_model_input("212", "202")
        else:
            _set_model_input("211", "101")
            _set_model_input("212", "102")

        # Sampler model source should follow highest enabled slot; otherwise base path.
        if e2:
            _set_model_input("104", "211")  # high-noise branch
            _set_model_input("103", "212")  # low-noise branch
        elif e1:
            _set_model_input("104", "201")
            _set_model_input("103", "202")
        else:
            _set_model_input("104", "101")
            _set_model_input("103", "102")



def build_prompts(
    workflow_def: WorkflowDef,
    input_files: list[str | Path],
    params: dict[str, Any] | None,
    per_file_params: dict[str, dict[str, Any]] | None = None,
    comfy_input_dir: str | Path | None = None,
    resolution: tuple[int, int] | None = None,
    flip_orientation: bool = False,
) -> list[PromptSpec]:
    raw_params = dict(params or {})
    comfy_input = Path(comfy_input_dir).expanduser().resolve() if comfy_input_dir else None
    paths: list[Path | None]
    if input_files:
        paths = [Path(p).expanduser().resolve() for p in input_files]
    else:
        # Input-less workflows (e.g. T2I) still need one prompt per try.
        paths = [None]
    resolved = resolve_params(workflow_def, params)
    per_file_params = per_file_params or {}

    tries = int(resolved.get("tries", 1))
    randomize = bool(resolved.get("randomize_seed", False) or tries > 1)
    flip = bool(flip_orientation or resolved.get("flip_orientation", False))
    output_prefix_base = str(resolved.get("output_prefix", ""))

    specs: list[PromptSpec] = []
    for file_path in paths:
        rel_input = _resolve_for_comfy_input(file_path, comfy_input) if file_path is not None else None
        effective = resolved
        if file_path is not None:
            override_raw = per_file_params.get(str(file_path))
            if override_raw is None:
                override_raw = per_file_params.get(file_path.name)
            if override_raw is not None:
                merged = dict(resolved)
                merged.update(dict(override_raw))
                effective = resolve_params(workflow_def, merged)
        for attempt in range(1, tries + 1):
            prompt = copy.deepcopy(workflow_def.template_prompt)
            if rel_input is not None:
                _apply_input_binding(prompt, workflow_def, rel_input)
            _apply_param_overrides(prompt, workflow_def, effective)
            _apply_scale_multiple_dimensions(prompt, workflow_def, file_path, effective, raw_params)
            _apply_switch_states(prompt, workflow_def)
            _normalize_context_schedule_values(prompt)
            if resolution is not None:
                _apply_resolution(prompt, int(resolution[0]), int(resolution[1]))
            if flip:
                _flip_orientation(prompt)

            if file_path is None:
                stem_base = "prompt"
            else:
                stem_base = file_path.stem
            stem = stem_base if tries == 1 else f"{stem_base}_try{attempt:02d}"
            out_prefix = _set_output_prefix(prompt, workflow_def, output_prefix_base, stem)
            seed_used = _set_seed(prompt, workflow_def, randomize)

            specs.append(
                PromptSpec(
                    input_file=str(file_path) if file_path is not None else "",
                    prompt_json=prompt,
                    seed_used=seed_used,
                    output_prefix=out_prefix,
                )
            )

    return specs
