# Refactor Baseline

This baseline captures behavior before deeper refactors so future changes can be compared against known-good contracts.

## Endpoint Contract Snapshots

Base URL examples use `http://127.0.0.1:8585`.

### `GET /api/workflows`
Request:
```bash
curl -s http://127.0.0.1:8585/api/workflows
```
Representative response shape:
```json
[
  {
    "name": "wan-context-lite-2stage",
    "display_name": "WAN ContextWindow Single Pass (81f)",
    "group": "WAN V2",
    "description": "...",
    "input_type": "image",
    "input_extensions": [".png", ".jpg", ".jpeg", ".webp", ".bmp"],
    "supports_resolution": true,
    "parameters": {
      "positive_prompt": {
        "label": "Positive prompt",
        "type": "text",
        "default": "(at 0 second: )(at 3 second: )(at 7 second: )",
        "min": null,
        "max": null
      }
    }
  }
]
```

### `POST /api/jobs`
Request:
```bash
curl -s -X POST http://127.0.0.1:8585/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "workflow_name": "wan-context-lite-2stage",
    "input_dir": "/home/cobra/ComfyUI/input/my_folder",
    "params": {"tries": 1, "randomize_seed": false},
    "resolution_preset": "640x1136",
    "flip_orientation": false,
    "priority": 0
  }'
```
Representative response shape:
```json
{"job_id": 42, "prompt_count": 3, "input_dir": "/home/cobra/ComfyUI/input/my_folder"}
```

### `GET /api/jobs`
Request:
```bash
curl -s http://127.0.0.1:8585/api/jobs
```
Representative response shape:
```json
[
  {
    "id": 42,
    "workflow_name": "wan-context-lite-2stage",
    "status": "pending",
    "prompt_count": 3,
    "created_at": "2026-02-21T14:00:00Z"
  }
]
```

### `GET /api/jobs/{job_id}`
Request:
```bash
curl -s http://127.0.0.1:8585/api/jobs/42
```
Representative response shape:
```json
{
  "job": {
    "id": 42,
    "workflow_name": "wan-context-lite-2stage",
    "status": "running"
  },
  "prompts": [
    {
      "id": 101,
      "prompt_id": "fake-1",
      "status": "running",
      "prompt_json": {"...": "..."}
    }
  ]
}
```

### `POST /api/jobs/{job_id}/cancel`
Request:
```bash
curl -s -X POST http://127.0.0.1:8585/api/jobs/42/cancel
```
Representative response shape:
```json
{
  "ok": true,
  "job": {"id": 42, "status": "canceled"},
  "cancel_summary": {
    "mode": "immediate",
    "canceled_pending": 2,
    "running_prompts": 0
  }
}
```

### `POST /api/jobs/{job_id}/retry`
Request:
```bash
curl -s -X POST http://127.0.0.1:8585/api/jobs/42/retry
```
Representative response shape:
```json
{"ok": true, "job": {"id": 42, "status": "pending"}}
```

### `GET /api/health`
Request:
```bash
curl -s http://127.0.0.1:8585/api/health
```
Representative response shape:
```json
{
  "worker_paused": false,
  "comfy": true,
  "stats": {"pending": 0, "running": 0, "succeeded": 0, "failed": 0, "canceled": 0}
}
```

## Golden Fixtures

- API workflows payload snapshot:
  - `tests/fixtures/baseline/api/workflows_payload.json`
- Prompt-generation golden fixtures (two workflows + multi-try):
  - `tests/fixtures/baseline/prompts/wan-context-lite-2stage.single.json`
  - `tests/fixtures/baseline/prompts/wan-context-2stage.single.json`
  - `tests/fixtures/baseline/prompts/wan-context-lite-2stage.multi_try.json`
- CLI snapshots:
  - `tests/fixtures/baseline/cli/list.txt`
  - `tests/fixtures/baseline/cli/status_empty.txt`
  - `tests/fixtures/baseline/cli/submit_dry_run.txt`

## Known Intentional Quirks

- `tries > 1` implies randomized seeds even when `randomize_seed=false`.
- WAN workflows scaffold the UI default positive prompt to:
  - `(at 0 second: )(at 3 second: )(at 7 second: )`
- Cancel semantics are best-effort:
  - pending prompts cancel immediately
  - currently running prompt(s) complete and remaining pending are canceled (`cancel_after_current` mode)

## Reproducible Baseline Commands

Run the curated baseline command list:

```bash
bash docs/refactor/baseline_commands.sh
```

The script prints endpoint and CLI outputs in a deterministic way and runs Task 0 baseline tests.
