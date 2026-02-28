from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass
from pathlib import Path
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



def _set_output_prefix(prompt: dict[str, Any], workflow_def: WorkflowDef, output_prefix: str, stem: str) -> str:
    binding = workflow_def.file_bindings.get("output_prefix")
    if not binding:
        return stem

    base = output_prefix.rstrip("/")
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
