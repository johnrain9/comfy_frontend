# Auto Prompt Runbook

## Overview
Auto Prompt is a two-stage flow for Wan i2v:
1. Stage 1 (`caption`): image -> concise visual caption.
2. Stage 2 (`motion`): caption -> temporal motion prompt(s) aligned to workflow timing.

Defaults:
- Stage 1 model: `Qwen3-VL-8B-NSFW-Caption-V4.5`
- Stage 2 model: `Dolphin-Mistral-24B-Venice-Edition`
- LM Studio URL: `http://127.0.0.1:1234`

## Dependencies
- Python package: `requests`
- No local `torch/transformers/autoawq` required by `video_queue`.

## Endpoints
- Capability check: `GET /api/auto-prompt/capability`
- Generate prompts: `POST /api/auto-prompt`

If LM Studio is unavailable, API returns `503` with actionable message.

## Prompt Modes
Submit supports:
- `manual`
- `per-image manual`
- `per-image auto`

Per-image modes require `per_file_params` payload.

## Split Workflow Behavior
For workflows with `positive_prompt_stageN` parameters, Stage 2 returns clip prompts:
- `clip_1`, `clip_2`, ...
UI terminology should use `Clip N` labels.

## Timing Derivation
Workflow context is derived from workflow template and parameter shape:
- `fps` from template nodes containing `fps`
- `total_frames` from template nodes containing `length`
- split stage count from `positive_prompt_stageN` keys

Default marker anchors for current 81f/24fps flows:
- `0s`
- `1.5s`
- `3s`

## CLI Harness
Use `auto_prompt_cli.py` for rapid iteration.

Examples:

```bash
./venv/bin/python auto_prompt_cli.py \
  --stage both \
  --workflow-name wan-context-2stage-split-prompts \
  --dir /home/cobra/ComfyUI/input/my_batch \
  --output /tmp/auto_prompt_out.json
```

Stage 2-only rerun from cached captions:

```bash
./venv/bin/python auto_prompt_cli.py \
  --stage motion \
  --workflow-name wan-context-2stage-split-prompts \
  --captions-file /tmp/captions.json \
  --system-prompt-override "custom stage2 instruction"
```

Mock mode (no LM Studio dependency) for development:

```bash
./venv/bin/python auto_prompt_cli.py --mock --stage both --workflow-name wan-context-2stage --dir /tmp/images
```

## Troubleshooting
- `503 LM Studio unavailable`: ensure LM Studio server is running and model loaded.
- `captions is required for motion stage`: provide `captions` in API request or use `stage=both`.
- `prompt_mode requires per-image prompt overrides`: apply auto/generated per-file prompts before submit.
