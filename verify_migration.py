#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from defs import load_all
from prompt_builder import build_prompts, resolve_params


def main() -> int:
    workflows = {w.name: w for w in load_all(Path(__file__).resolve().parent / "workflow_defs")}

    for name in ("wan-i2v-ctxwindow", "upscale-interpolate"):
        if name not in workflows:
            raise SystemExit(f"missing workflow: {name}")

    sample_i2v_input = [Path("/home/cobra/ComfyUI/input/test_input/example.png")]
    sample_up_input = [Path("/home/cobra/ComfyUI/input/test_videos/example.mp4")]

    i2v = workflows["wan-i2v-ctxwindow"]
    i2v_params = resolve_params(i2v, {"positive_prompt": "test"})
    i2v_prompts = build_prompts(i2v, sample_i2v_input, i2v_params, "/home/cobra/ComfyUI/input")
    print("wan-i2v-ctxwindow prompt sample")
    print(json.dumps(i2v_prompts[0].prompt_json, indent=2)[:2000])

    up = workflows["upscale-interpolate"]
    up_params = resolve_params(up, {})
    up_prompts = build_prompts(up, sample_up_input, up_params, "/home/cobra/ComfyUI/input")
    print("upscale-interpolate prompt sample")
    print(json.dumps(up_prompts[0].prompt_json, indent=2)[:2000])

    print("verification script completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
