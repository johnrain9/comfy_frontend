#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from db import QueueDB
from defs import load_all
from prompt_builder import build_prompts, resolve_params


DEFAULT_API = os.environ.get("VIDEO_QUEUE_API", "http://127.0.0.1:8585")
ROOT = Path(os.environ.get("VIDEO_QUEUE_ROOT", str(Path.home() / "video_queue"))).expanduser().resolve()
DEFS_DIR = Path(os.environ.get("WORKFLOW_DEFS_DIR", str(ROOT / "workflow_defs_v2"))).expanduser().resolve()
COMFY_INPUT_DIR = Path(os.environ.get("COMFY_ROOT", str(Path.home() / "ComfyUI"))).expanduser().resolve() / "input"



def api_call(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{DEFAULT_API.rstrip('/')}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        txt = resp.read().decode("utf-8")
        return json.loads(txt) if txt else {}



def parse_params(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"invalid --param '{item}', expected key=value")
        k, v = item.split("=", 1)
        out[k.strip()] = v
    return out



def local_submit(workflow_name: str, input_dir: str, params: dict[str, Any], dry_run: bool) -> int:
    workflows = {w.name: w for w in load_all(DEFS_DIR)}
    wf = workflows.get(workflow_name)
    if not wf:
        raise ValueError(f"unknown workflow: {workflow_name}")

    src = Path(input_dir).expanduser().resolve()
    if not src.exists() or not src.is_dir():
        raise ValueError(f"input directory not found: {src}")

    allowed = {e.lower() for e in wf.input_extensions}
    files = sorted([p for p in src.iterdir() if p.is_file() and p.suffix.lower() in allowed])
    if not files:
        raise ValueError(f"no matching files in {src}")

    resolved = resolve_params(wf, params)
    specs = build_prompts(wf, files, resolved, comfy_input_dir=COMFY_INPUT_DIR)

    if dry_run:
        for i, spec in enumerate(specs, 1):
            print(f"--- prompt {i} ({spec.input_file}) ---")
            print(json.dumps(spec.prompt_json, indent=2))
        return 0

    db = QueueDB(ROOT / "data" / "queue.db")
    job_id = db.create_job(
        workflow_name=wf.name,
        input_dir=str(src),
        params_json=resolved,
        prompt_specs=specs,
        priority=0,
        move_processed=wf.move_processed,
    )
    print(job_id)
    return 0



def cmd_list() -> int:
    try:
        data = api_call("GET", "/api/workflows")
    except Exception:
        data = [
            {
                "name": w.name,
                "description": w.description,
                "input_type": w.input_type,
            }
            for w in load_all(DEFS_DIR)
        ]

    for item in data:
        print(f"{item['name']}\t{item.get('input_type', '')}\t{item.get('description', '')}")
    return 0



def cmd_submit(args: argparse.Namespace) -> int:
    params = parse_params(args.param or [])
    if args.dry_run:
        return local_submit(args.workflow, args.dir, params, dry_run=True)

    try:
        data = api_call(
            "POST",
            "/api/jobs",
            {
                "workflow_name": args.workflow,
                "input_dir": args.dir,
                "params": params,
            },
        )
        print(data["job_id"])
        return 0
    except urllib.error.URLError:
        return local_submit(args.workflow, args.dir, params, dry_run=False)



def cmd_status(job_id: int | None) -> int:
    try:
        if job_id is None:
            jobs = api_call("GET", "/api/jobs")
            print("ID\tWorkflow\tStatus\tPrompts")
            for j in jobs:
                print(f"{j['id']}\t{j['workflow_name']}\t{j['status']}\t{j.get('prompt_count', 0)}")
        else:
            detail = api_call("GET", f"/api/jobs/{job_id}")
            print(json.dumps(detail, indent=2))
        return 0
    except Exception:
        db = QueueDB(ROOT / "data" / "queue.db")
        if job_id is None:
            jobs = db.list_jobs(limit=20)
            print("ID\tWorkflow\tStatus\tPrompts")
            for j in jobs:
                print(f"{j['id']}\t{j['workflow_name']}\t{j['status']}\t{j.get('prompt_count', 0)}")
        else:
            detail = db.get_job(job_id)
            if not detail:
                print("job not found", file=sys.stderr)
                return 1
            print(json.dumps(detail, indent=2))
        return 0



def cmd_cancel(job_id: int) -> int:
    try:
        api_call("POST", f"/api/jobs/{job_id}/cancel")
        print(f"canceled {job_id}")
        return 0
    except Exception:
        db = QueueDB(ROOT / "data" / "queue.db")
        if not db.cancel_job(job_id):
            print("job not found", file=sys.stderr)
            return 1
        print(f"canceled {job_id}")
        return 0



def cmd_retry(job_id: int) -> int:
    try:
        api_call("POST", f"/api/jobs/{job_id}/retry")
        print(f"retried {job_id}")
        return 0
    except Exception:
        db = QueueDB(ROOT / "data" / "queue.db")
        if not db.retry_job(job_id):
            print("job not found", file=sys.stderr)
            return 1
        print(f"retried {job_id}")
        return 0



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="comfy-run")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")

    p_submit = sub.add_parser("submit")
    p_submit.add_argument("--workflow", required=True)
    p_submit.add_argument("--dir", required=True)
    p_submit.add_argument("--param", action="append", default=[])
    p_submit.add_argument("--dry-run", action="store_true")

    p_status = sub.add_parser("status")
    p_status.add_argument("job_id", nargs="?", type=int)

    p_cancel = sub.add_parser("cancel")
    p_cancel.add_argument("job_id", type=int)

    p_retry = sub.add_parser("retry")
    p_retry.add_argument("job_id", type=int)

    return parser



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.cmd == "list":
            return cmd_list()
        if args.cmd == "submit":
            return cmd_submit(args)
        if args.cmd == "status":
            return cmd_status(args.job_id)
        if args.cmd == "cancel":
            return cmd_cancel(args.job_id)
        if args.cmd == "retry":
            return cmd_retry(args.job_id)
        return 2
    except argparse.ArgumentError:
        return 2
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
