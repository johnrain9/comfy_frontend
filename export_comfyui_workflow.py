from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}


def _fetch_object_info(base_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/object_info") as response:
        return json.load(response)


def _load_prompt_row(db_path: Path, *, job_id: int | None, prompt_row_id: int | None) -> sqlite3.Row:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if prompt_row_id is not None:
            row = conn.execute(
                """
                SELECT p.*, j.workflow_name, j.job_name
                FROM prompts p
                JOIN jobs j ON j.id = p.job_id
                WHERE p.id = ?
                """,
                (prompt_row_id,),
            ).fetchone()
        elif job_id is not None:
            row = conn.execute(
                """
                SELECT p.*, j.workflow_name, j.job_name
                FROM prompts p
                JOIN jobs j ON j.id = p.job_id
                WHERE p.job_id = ?
                ORDER BY p.id DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        else:
            raise ValueError("either --job-id or --prompt-row-id is required")
    finally:
        conn.close()

    if row is None:
        raise ValueError("prompt row not found")
    return row


def _input_defs(info: dict[str, Any]) -> list[dict[str, Any]]:
    defs: list[dict[str, Any]] = []
    inputs = info.get("input") or {}
    order = info.get("input_order") or {}
    for section in ("required", "optional"):
        section_inputs = inputs.get(section) or {}
        names = order.get(section) or list(section_inputs.keys())
        for name in names:
            spec = section_inputs.get(name)
            if not isinstance(spec, list) or not spec:
                continue
            raw_type = spec[0]
            meta = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if isinstance(raw_type, list):
                field_type = "COMBO"
                default = meta.get("default", raw_type[0] if raw_type else None)
            else:
                field_type = str(raw_type)
                default = meta.get("default")
            defs.append(
                {
                    "name": name,
                    "type": field_type,
                    "widget": field_type in WIDGET_TYPES,
                    "default": default,
                }
            )
    return defs


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[1], int)
        and isinstance(value[0], (str, int))
    )


def _depths(prompt: dict[str, Any]) -> dict[str, int]:
    memo: dict[str, int] = {}

    def visit(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]
        node = prompt[node_id]
        max_parent = -1
        for value in (node.get("inputs") or {}).values():
            if _is_link(value):
                max_parent = max(max_parent, visit(str(value[0])))
        memo[node_id] = max_parent + 1
        return memo[node_id]

    for node_id in prompt:
        visit(str(node_id))
    return memo


def _node_size(class_type: str, input_defs: list[dict[str, Any]]) -> dict[str, float]:
    width = 320.0
    height = max(46.0, 26.0 * len(input_defs) + 24.0)
    if class_type == "TextEncodeQwenImageEditPlus":
        width = 430.0
        height = 220.0
    elif class_type == "KSampler":
        width = 320.0
        height = 250.0
    elif class_type == "SaveImage":
        width = 320.0
        height = 80.0
    return {"0": width, "1": height}


def build_workflow(prompt: dict[str, Any], object_info: dict[str, Any], name: str) -> dict[str, Any]:
    prompt = {str(k): v for k, v in prompt.items()}
    depth_by_node = _depths(prompt)
    columns: dict[int, list[str]] = defaultdict(list)
    for node_id, depth in depth_by_node.items():
        columns[depth].append(node_id)
    for depth in columns:
        columns[depth].sort(key=lambda nid: int(nid))

    input_defs_by_node: dict[str, list[dict[str, Any]]] = {}
    input_slot_by_node: dict[str, dict[str, int]] = {}
    for node_id, node in prompt.items():
        class_type = node["class_type"]
        info = object_info.get(class_type)
        if not info:
            raise ValueError(f"missing object_info for node type {class_type}")
        defs = _input_defs(info)
        input_defs_by_node[node_id] = defs
        input_slot_by_node[node_id] = {entry["name"]: idx for idx, entry in enumerate(defs)}

    links: list[list[Any]] = []
    link_id = 1
    input_link_id: dict[tuple[str, str], int] = {}
    output_links: dict[tuple[str, int], list[int]] = defaultdict(list)

    for target_id, node in prompt.items():
        target_class = node["class_type"]
        target_inputs = node.get("inputs") or {}
        target_slot_map = input_slot_by_node[target_id]
        for input_name, value in target_inputs.items():
            if not _is_link(value):
                continue
            origin_id = str(value[0])
            origin_slot = int(value[1])
            target_slot = target_slot_map.get(input_name)
            if target_slot is None:
                continue
            origin_class = prompt[origin_id]["class_type"]
            origin_info = object_info[origin_class]
            output_types = origin_info.get("output") or []
            link_type = output_types[origin_slot] if origin_slot < len(output_types) else "*"
            links.append([link_id, int(origin_id), origin_slot, int(target_id), target_slot, link_type])
            input_link_id[(target_id, input_name)] = link_id
            output_links[(origin_id, origin_slot)].append(link_id)
            link_id += 1

    nodes: list[dict[str, Any]] = []
    order = 0
    for depth in sorted(columns):
        for row, node_id in enumerate(columns[depth]):
            node = prompt[node_id]
            class_type = node["class_type"]
            info = object_info[class_type]
            defs = input_defs_by_node[node_id]
            actual_inputs = node.get("inputs") or {}
            node_inputs: list[dict[str, Any]] = []
            widgets_values: list[Any] = []

            for idx, entry in enumerate(defs):
                input_name = entry["name"]
                input_value = actual_inputs.get(input_name, entry["default"])
                link = input_link_id.get((node_id, input_name))
                input_entry: dict[str, Any] = {
                    "name": input_name,
                    "type": entry["type"],
                    "link": link,
                }
                if link is not None:
                    input_entry["slot_index"] = idx
                if entry["widget"]:
                    input_entry["widget"] = {"name": input_name}
                    widgets_values.append(entry["default"] if _is_link(input_value) else input_value)
                node_inputs.append(input_entry)

            output_types = info.get("output") or []
            output_names = info.get("output_name") or output_types
            node_outputs: list[dict[str, Any]] = []
            for out_idx, out_type in enumerate(output_types):
                node_outputs.append(
                    {
                        "name": output_names[out_idx] if out_idx < len(output_names) else out_type,
                        "type": out_type,
                        "links": output_links.get((node_id, out_idx)) or None,
                        "slot_index": out_idx,
                    }
                )

            node_obj: dict[str, Any] = {
                "id": int(node_id),
                "type": class_type,
                "pos": [80 + depth * 360, 60 + row * 220],
                "size": _node_size(class_type, defs),
                "flags": {},
                "order": order,
                "mode": 0,
                "inputs": node_inputs,
                "outputs": node_outputs,
                "properties": {"Node name for S&R": class_type},
            }
            if widgets_values:
                node_obj["widgets_values"] = widgets_values
            if class_type == "TextEncodeQwenImageEditPlus":
                prompt_text = actual_inputs.get("prompt", "")
                if "low quality" in str(prompt_text):
                    node_obj["title"] = "Text Encode (Negative Prompt)"
                    node_obj["color"] = "#322"
                    node_obj["bgcolor"] = "#533"
                else:
                    node_obj["title"] = "Text Encode (Positive Prompt)"
                    node_obj["color"] = "#232"
                    node_obj["bgcolor"] = "#353"
            nodes.append(node_obj)
            order += 1

    return {
        "last_node_id": max(int(node_id) for node_id in prompt),
        "last_link_id": link_id - 1,
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {
            "ds": {"scale": 0.85, "offset": [120.0, 120.0]},
            "generated_by": "codex",
        },
        "version": 0.4,
        "name": name,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a queued Comfy prompt to a loadable ComfyUI workflow JSON.")
    parser.add_argument("--db", default="data/queue.db", help="Path to queue.db")
    parser.add_argument("--base-url", default="http://127.0.0.1:8188", help="ComfyUI base URL")
    parser.add_argument("--job-id", type=int, help="Job id to export (exports the latest prompt row for the job)")
    parser.add_argument("--prompt-row-id", type=int, help="Prompt row id to export")
    parser.add_argument("--output", required=True, help="Output .json path")
    args = parser.parse_args()

    row = _load_prompt_row(Path(args.db), job_id=args.job_id, prompt_row_id=args.prompt_row_id)
    prompt = json.loads(row["prompt_json"])
    object_info = _fetch_object_info(args.base_url)
    workflow_name = row["workflow_name"] or "workflow"
    job_name = row["job_name"] or f"job-{row['job_id']}"
    name = f"{workflow_name} - {job_name}"
    workflow = build_workflow(prompt, object_info, name)

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
