#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from auto_prompt.generator import AutoPromptGenerator
from defs import load_all


ROOT = Path(os.environ.get("VIDEO_QUEUE_ROOT", str(Path.home() / "video_queue"))).expanduser().resolve()
DEFS_DIR = Path(os.environ.get("WORKFLOW_DEFS_DIR", str(ROOT / "workflow_defs_v2"))).expanduser().resolve()
LMSTUDIO_URL = os.environ.get("LMSTUDIO_URL", "http://127.0.0.1:1234")


class _MockClient:
    def check_available(self) -> None:
        return

    def ensure_model_loaded(self, model: str, auto_load: bool = True) -> None:
        return

    def chat(self, *, model: str, system_prompt: str, user_prompt: str) -> str:
        if "Caption:" in user_prompt:
            return "(at 0 second: subtle motion)(at 1.5 second: gradual transition)(at 3 second: settle)"
        return "subject in frame, stable camera, clear identity"


def _load_workflow(name: str):
    workflows = {w.name: w for w in load_all(DEFS_DIR)}
    wf = workflows.get(name)
    if not wf:
        raise ValueError(f"unknown workflow: {name}")
    return wf


def _read_captions_file(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise ValueError(f"captions file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("captions file must be object mapping path->caption")
    return {str(k): str(v) for k, v in data.items()}


def _discover_images(input_dir: str | None, images: list[str]) -> list[str]:
    if images:
        return [str(Path(p).expanduser().resolve()) for p in images]
    if not input_dir:
        return []
    d = Path(input_dir).expanduser().resolve()
    if not d.exists() or not d.is_dir():
        raise ValueError(f"input dir not found: {d}")
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    return [str(p.resolve()) for p in sorted(d.iterdir()) if p.is_file() and p.suffix.lower() in allowed]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="auto-prompt-cli")
    p.add_argument("--stage", choices=["caption", "motion", "both"], default="both")
    p.add_argument("--workflow-name", required=True)
    p.add_argument("--dir", default="")
    p.add_argument("--image", action="append", default=[])
    p.add_argument("--captions-file", default="")
    p.add_argument("--system-prompt-override", default="")
    p.add_argument("--lmstudio-url", default=LMSTUDIO_URL)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--output", default="")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        wf = _load_workflow(args.workflow_name)
        image_paths = _discover_images(args.dir or None, args.image)
        captions = _read_captions_file(args.captions_file or None)

        client = _MockClient() if args.mock else None
        gen = AutoPromptGenerator(lmstudio_url=args.lmstudio_url, client=client)
        gen.check_available()
        ctx = gen.extract_workflow_context(wf)

        if args.stage in {"caption", "both"} and not image_paths:
            raise ValueError("image inputs required for caption/both stage")
        if args.stage == "motion" and not captions:
            raise ValueError("captions required for motion stage")
        if args.stage == "motion" and not image_paths:
            image_paths = sorted(captions.keys())

        out = gen.generate_batch(
            image_paths=image_paths,
            workflow_context=ctx,
            stage=args.stage,
            captions=captions,
            system_prompt_override=args.system_prompt_override or None,
        )

        payload: dict[str, Any] = {
            "stage": args.stage,
            "workflow_name": args.workflow_name,
            **out,
        }
        txt = json.dumps(payload, indent=2)
        if args.output:
            out_path = Path(args.output).expanduser().resolve()
            out_path.write_text(txt, encoding="utf-8")
            print(str(out_path))
        else:
            print(txt)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
