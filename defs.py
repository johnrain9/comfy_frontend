from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ALLOWED_PARAM_TYPES = {"text", "bool", "int", "float"}


class WorkflowDefError(ValueError):
    pass


@dataclass(frozen=True)
class NodeBinding:
    nodes: list[str]
    field: str | None = None
    fields: list[str] | None = None


@dataclass(frozen=True)
class ParameterDef:
    name: str
    label: str
    type: str
    default: Any = None
    min: int | float | None = None
    max: int | float | None = None
    nodes: list[str] | None = None
    field: str | None = None
    fields: list[str] | None = None


@dataclass(frozen=True)
class SwitchState:
    node_id: str
    field: str
    value: Any


@dataclass(frozen=True)
class WorkflowDef:
    name: str
    display_name: str | None
    group: str | None
    category: str | None
    description: str
    template_path: str | None
    input_type: str
    input_extensions: list[str]
    file_bindings: dict[str, NodeBinding]
    parameters: dict[str, ParameterDef]
    switch_states: list[SwitchState]
    move_processed: bool
    template_prompt: dict[str, Any]
    source_file: Path



def _err(path: Path, field: str, msg: str) -> WorkflowDefError:
    return WorkflowDefError(f"{path}: field '{field}': {msg}")



def _load_template(path: Path, raw: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    if "template_inline" in raw:
        inline = raw["template_inline"]
        if not isinstance(inline, dict):
            raise _err(path, "template_inline", "must be a mapping")
        return None, inline

    template = raw.get("template")
    if not isinstance(template, str) or not template.strip():
        raise _err(path, "template", "is required unless template_inline is provided")

    template_path = Path(template).expanduser()
    if not template_path.is_absolute():
        template_path = (path.parent / template_path).resolve()

    if not template_path.exists():
        raise _err(path, "template", f"template file does not exist: {template_path}")

    try:
        obj = json.loads(template_path.read_text())
    except json.JSONDecodeError as exc:
        raise _err(path, "template", f"invalid JSON: {exc}") from exc

    prompt = obj.get("prompt") if isinstance(obj, dict) and "prompt" in obj else obj
    if not isinstance(prompt, dict):
        raise _err(path, "template", "template JSON must be a prompt mapping")

    return str(template_path), prompt



def _parse_binding(path: Path, name: str, value: Any) -> NodeBinding:
    if not isinstance(value, dict):
        raise _err(path, f"file_bindings.{name}", "must be a mapping")

    nodes = value.get("nodes")
    if not isinstance(nodes, list) or not nodes or not all(isinstance(n, str) for n in nodes):
        raise _err(path, f"file_bindings.{name}.nodes", "must be a non-empty list[str]")

    field = value.get("field")
    fields = value.get("fields")
    if field is None and fields is None:
        raise _err(path, f"file_bindings.{name}", "must include 'field' or 'fields'")
    if field is not None and not isinstance(field, str):
        raise _err(path, f"file_bindings.{name}.field", "must be a string")
    if fields is not None:
        if not isinstance(fields, list) or not fields or not all(isinstance(f, str) for f in fields):
            raise _err(path, f"file_bindings.{name}.fields", "must be a non-empty list[str]")

    return NodeBinding(nodes=nodes, field=field, fields=fields)



def _parse_parameter(path: Path, name: str, value: Any) -> ParameterDef:
    if not isinstance(value, dict):
        raise _err(path, f"parameters.{name}", "must be a mapping")

    ptype = value.get("type")
    if ptype not in ALLOWED_PARAM_TYPES:
        raise _err(path, f"parameters.{name}.type", f"must be one of {sorted(ALLOWED_PARAM_TYPES)}")

    label = value.get("label", name)
    if not isinstance(label, str):
        raise _err(path, f"parameters.{name}.label", "must be a string")

    nodes = value.get("nodes")
    if nodes is not None:
        if not isinstance(nodes, list) or not all(isinstance(n, str) for n in nodes):
            raise _err(path, f"parameters.{name}.nodes", "must be list[str]")

    field = value.get("field")
    fields = value.get("fields")
    if field is not None and not isinstance(field, str):
        raise _err(path, f"parameters.{name}.field", "must be a string")
    if fields is not None:
        if not isinstance(fields, list) or not all(isinstance(f, str) for f in fields):
            raise _err(path, f"parameters.{name}.fields", "must be list[str]")

    minimum = value.get("min")
    maximum = value.get("max")
    if minimum is not None and not isinstance(minimum, (int, float)):
        raise _err(path, f"parameters.{name}.min", "must be numeric")
    if maximum is not None and not isinstance(maximum, (int, float)):
        raise _err(path, f"parameters.{name}.max", "must be numeric")

    return ParameterDef(
        name=name,
        label=label,
        type=ptype,
        default=value.get("default"),
        min=minimum,
        max=maximum,
        nodes=nodes,
        field=field,
        fields=fields,
    )



def _validate_template_refs(path: Path, prompt: dict[str, Any], workflow: WorkflowDef) -> None:
    node_ids = set(prompt.keys())

    for bname, binding in workflow.file_bindings.items():
        for nid in binding.nodes:
            if nid not in node_ids:
                raise _err(path, f"file_bindings.{bname}.nodes", f"node id '{nid}' not in template")

    for pname, param in workflow.parameters.items():
        if not param.nodes:
            continue
        for nid in param.nodes:
            if nid not in node_ids:
                raise _err(path, f"parameters.{pname}.nodes", f"node id '{nid}' not in template")

    for switch in workflow.switch_states:
        if switch.node_id not in node_ids:
            raise _err(path, "switch_states", f"node id '{switch.node_id}' not in template")



def load_one(path: Path) -> WorkflowDef:
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise WorkflowDefError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise WorkflowDefError(f"{path}: top-level YAML must be a mapping")

    for required in ("name", "description", "input_type", "input_extensions"):
        if required not in raw:
            raise _err(path, required, "is required")

    name = raw["name"]
    if not isinstance(name, str) or not name.strip():
        raise _err(path, "name", "must be a non-empty string")

    description = raw["description"]
    if not isinstance(description, str):
        raise _err(path, "description", "must be a string")

    display_name = raw.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        raise _err(path, "display_name", "must be a string")

    group = raw.get("group")
    if group is not None and not isinstance(group, str):
        raise _err(path, "group", "must be a string")

    category = raw.get("category")
    if category is not None and not isinstance(category, str):
        raise _err(path, "category", "must be a string")

    input_type = raw["input_type"]
    if input_type not in {"image", "video", "none"}:
        raise _err(path, "input_type", "must be 'image', 'video', or 'none'")

    input_extensions = raw["input_extensions"]
    if not isinstance(input_extensions, list) or not input_extensions:
        raise _err(path, "input_extensions", "must be a non-empty list")
    if not all(isinstance(ext, str) and ext.startswith(".") for ext in input_extensions):
        raise _err(path, "input_extensions", "must contain extensions like '.png'")

    template_path, template_prompt = _load_template(path, raw)

    file_bindings_raw = raw.get("file_bindings", {})
    if not isinstance(file_bindings_raw, dict):
        raise _err(path, "file_bindings", "must be a mapping")
    file_bindings = {k: _parse_binding(path, k, v) for k, v in file_bindings_raw.items()}

    params_raw = raw.get("parameters", {})
    if not isinstance(params_raw, dict):
        raise _err(path, "parameters", "must be a mapping")
    parameters = {k: _parse_parameter(path, k, v) for k, v in params_raw.items()}

    switches_raw = raw.get("switch_states", {})
    if not isinstance(switches_raw, dict):
        raise _err(path, "switch_states", "must be a mapping")
    switch_states: list[SwitchState] = []
    for node_id, cfg in switches_raw.items():
        if not isinstance(cfg, dict):
            raise _err(path, f"switch_states.{node_id}", "must be a mapping")
        field = cfg.get("field")
        if not isinstance(field, str):
            raise _err(path, f"switch_states.{node_id}.field", "must be a string")
        if "value" not in cfg:
            raise _err(path, f"switch_states.{node_id}.value", "is required")
        switch_states.append(SwitchState(node_id=str(node_id), field=field, value=cfg["value"]))

    move_processed = bool(raw.get("move_processed", False))

    workflow = WorkflowDef(
        name=name,
        display_name=display_name,
        group=group,
        category=category,
        description=description,
        template_path=template_path,
        input_type=input_type,
        input_extensions=input_extensions,
        file_bindings=file_bindings,
        parameters=parameters,
        switch_states=switch_states,
        move_processed=move_processed,
        template_prompt=template_prompt,
        source_file=path,
    )
    _validate_template_refs(path, template_prompt, workflow)
    return workflow



def load_all(defs_dir: str | Path | None = None) -> list[WorkflowDef]:
    root = Path(defs_dir).expanduser().resolve() if defs_dir else Path(__file__).resolve().parent / "workflow_defs"
    if not root.exists():
        return []

    workflows: list[WorkflowDef] = []
    names: set[str] = set()
    for yaml_path in sorted(root.glob("*.yaml")):
        wf = load_one(yaml_path)
        if wf.name in names:
            raise WorkflowDefError(f"duplicate workflow name '{wf.name}' in {yaml_path}")
        names.add(wf.name)
        workflows.append(wf)
    return workflows
