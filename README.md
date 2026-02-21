# comfy_frontend

FastAPI + SQLite queue manager for running ComfyUI workflows from a web UI and CLI.

This project provides:
- A web UI at `/` for batch and single-image job submission
- A REST API for workflows/jobs/queue control
- A background worker that submits prompts to ComfyUI
- A CLI (`cli.py`) that can use the API or fall back to local DB submission

## Current status note

Some docs in `docs/` are historical. Runtime behavior in this README is based on the current code.

Also, the checked-in `workflow_defs_v2/*.yaml` currently use absolute `template:` paths. At least one points to a non-existent path on a clean machine, so app startup will fail until you fix those workflow definitions.

## Requirements

- Python 3.10+
- ComfyUI running and reachable (default: `http://127.0.0.1:8188`)
- Linux/WSL/macOS shell (examples use bash/zsh)

## Quick start

1. Create/install Python deps:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Set environment variables (recommended for local dev from this repo):

```bash
export VIDEO_QUEUE_ROOT="$(pwd)"
export WORKFLOW_DEFS_DIR="$(pwd)/workflow_defs_v2"
export COMFY_ROOT="$HOME/ComfyUI"
export COMFY_BASE_URL="http://127.0.0.1:8188"
export PORT=8585
```

3. Fix workflow template paths in `workflow_defs_v2/*.yaml` so each `template:` points to a real file on your machine.

4. Start the server:

```bash
./run.sh
```

Then open `http://127.0.0.1:8585`.

## Environment variables

- `VIDEO_QUEUE_ROOT`
  - App root for `data/`, `static/`, and default workflow defs
  - Default: `~/video_queue`
- `WORKFLOW_DEFS_DIR`
  - Workflow YAML directory
  - Default: `$VIDEO_QUEUE_ROOT/workflow_defs_v2`
- `COMFY_ROOT`
  - Used for `input/` default path and LoRA discovery
  - Default: `~/ComfyUI`
- `COMFY_BASE_URL`
  - ComfyUI HTTP URL used by worker
  - Default: `http://127.0.0.1:8188`
- `PORT`
  - API/UI port
  - Default: `8585`
- `VIDEO_QUEUE_API` (CLI)
  - API base URL the CLI talks to first
  - Default: `http://127.0.0.1:8585`

## API overview

Key endpoints:
- `GET /api/workflows`
- `GET /api/resolution-presets`
- `GET /api/loras`
- `POST /api/jobs`
- `POST /api/jobs/single`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`
- `POST /api/jobs/{job_id}/retry`
- `POST /api/queue/pause`
- `POST /api/queue/resume`
- `GET /api/health`
- `GET /api/jobs/{job_id}/log`

## CLI usage

```bash
./venv/bin/python cli.py list
./venv/bin/python cli.py status
./venv/bin/python cli.py status 42
./venv/bin/python cli.py submit --workflow wan-context-lite-2stage --dir /path/to/input
./venv/bin/python cli.py submit --workflow wan-context-lite-2stage --dir /path/to/input --dry-run
./venv/bin/python cli.py cancel 42
./venv/bin/python cli.py retry 42
```

`submit` first tries API mode, then falls back to local DB submission if API is unreachable.

## Tests

Python tests:

```bash
PYTHONPATH=. ./venv/bin/pytest -q
```

Frontend state test (Node):

```bash
node --test tests/frontend_state.test.mjs
```

Baseline reproducibility script:

```bash
bash docs/refactor/baseline_commands.sh
```

## Project layout

- `app.py` FastAPI app + route handlers
- `worker.py` background queue worker
- `db.py` SQLite schema and queue operations
- `defs.py` workflow YAML loader/validator
- `prompt_builder.py` prompt generation and parameter resolution
- `cli.py` command-line interface
- `workflow_defs_v2/` current workflow definitions
- `static/index.html` single-page UI

