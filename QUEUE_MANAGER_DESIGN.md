# Queue Manager Design for ComfyUI Batch I2V

## 1) Motivation

Current generation flow relies on direct CLI runs of:

`/home/cobra/ComfyUI/script_examples/batch_i2v_from_folder.py`

This works, but it breaks down when generation times are long and multiple experiments must be run across different folders/prompts/workflows. The pain points are:

- No persistent queue across terminal/session restarts.
- Hard to run many jobs with different prompts and keep order.
- Limited visibility into status (pending/running/failed/completed).
- Manual retries and seed variation are error-prone.
- Difficult to pause/cancel safely without losing context.

Goal: add a queue management layer around the existing script without replacing it.

## 2) Scope and Non-Goals

### In scope

- Queueing jobs that ultimately execute `batch_i2v_from_folder.py`.
- Simple GUI/TUI for job submission, monitoring, and control.
- Persistent metadata/logging/history.
- Safe operation on one GPU by default.

### Out of scope (initially)

- Rewriting ComfyUI internals.
- Replacing workflow JSON mechanics used by current script.
- Multi-GPU scheduling in v1.
- Distributed workers across machines.

## 3) Requirements

## 3.1 Functional requirements

- Create job from UI with per-job parameters:
  - `--input-subdir`
  - `--positive`
  - `--negative` (optional)
  - `--profile`
  - `--template-api`
  - `--tries`
  - `--randomize-seed` / seed mode
  - `--wait`
- Persist jobs with status lifecycle:
  - `pending`, `running`, `succeeded`, `failed`, `canceled`, `paused`
- Queue actions:
  - enqueue, cancel, pause, resume, retry failed
  - reorder priority (at least move-up/move-down)
- Capture stdout/stderr and store per-job log file path.
- Show outputs (saved video paths if discoverable from logs).

## 3.2 Operational requirements

- One active worker by default (avoid VRAM contention).
- Survive restarts:
  - queue state in SQLite
  - recover orphaned `running` jobs as `failed` or `pending_recovery`
- Idempotent execution:
  - each job has immutable config snapshot at run time
- Simple install and local use in WSL/Linux.

## 3.3 UX requirements

- Quick add form for common defaults.
- Job list with filters and search.
- Live-ish logs for running job.
- Clear errors (ComfyUI HTTP 400, node validation, timeout, etc.).

## 4) Proposed Architecture

## 4.1 Components

1. UI layer (Streamlit recommended for v1)
- Form to create jobs.
- Queue table with actions.
- Job detail page for logs/config/output.

2. Queue DB (SQLite)
- Tables: `jobs`, `job_attempts`, `events`, `settings`.
- Single source of truth for state.

3. Worker process
- Polls next runnable job.
- Spawns subprocess for batch script.
- Streams logs to file and DB.
- Handles cancel/pause signals.

4. Runner adapter
- Converts stored job fields into CLI args.
- Central place for argument validation and defaults.

## 4.2 Execution model

- FIFO by default, optional priority score.
- Worker picks one `pending` job, marks `running`.
- Execute script command with captured output.
- On success -> `succeeded`.
- On non-zero exit -> `failed` and store error summary.
- If canceled by user -> `canceled`.

## 4.3 Data model (minimal)

`jobs`
- `id` (uuid)
- `created_at`, `updated_at`
- `status`
- `priority` (integer)
- `input_subdir`
- `positive_prompt`
- `negative_prompt`
- `profile`
- `template_api`
- `tries`
- `randomize_seed` (bool)
- `extra_args_json`
- `log_path`
- `last_error`

`job_attempts`
- `id`, `job_id`, `attempt_index`
- `started_at`, `ended_at`
- `exit_code`
- `seed_used` (nullable)
- `result_summary`

`events`
- `id`, `job_id`, `ts`, `event_type`, `payload_json`

## 5) Solution Options

## Option A: Streamlit + SQLite + single worker (Recommended)

Why:
- Fastest path to usable graphical queue manager.
- Low complexity, easy local deployment.
- Good enough for one-user local workflow.

Tradeoffs:
- Not ideal for heavy multi-user access.
- UI interactions are less flexible than full frontend frameworks.

## Option B: Textual TUI + SQLite

Why:
- Robust terminal experience over SSH.
- No browser/network issues.

Tradeoffs:
- Less approachable than web UI.
- Lower visual clarity for non-terminal users.

## Option C: FastAPI backend + web frontend

Why:
- Best long-term architecture for scaling and richer controls.

Tradeoffs:
- Higher build and maintenance cost.
- Slower to first value.

## Option D: ComfyUI extension panel

Why:
- Native integration in ComfyUI UX.

Tradeoffs:
- Highest plugin-specific effort.
- More coupling to ComfyUI internals/update churn.

## 6) Recommended Plan

Phase 1 (MVP, 1-2 days)
- Build Option A with:
  - enqueue form
  - pending/running/completed tables
  - single worker
  - cancel + retry
  - per-job logs
- Keep existing script unchanged.

Phase 2 (stability)
- Add pause/resume semantics.
- Add queue reorder and priority.
- Add startup recovery for interrupted jobs.
- Add output parsing and direct links to generated files.

Phase 3 (quality of life)
- Saved presets (e.g., look-dev, medium, production).
- Batch create jobs from multiple folders/prompts.
- Notifications (desktop/Telegram/webhook) on completion/failure.

## 7) Command Contract (Wrapper)

Canonical command generated by runner:

```bash
/home/cobra/ComfyUI/venv/bin/python \
  /home/cobra/ComfyUI/script_examples/batch_i2v_from_folder.py \
  --wait \
  --profile <profile> \
  --template-api <workflow.api.json> \
  --input-subdir <subdir> \
  --positive "<prompt>" \
  [--negative "<neg_prompt>"] \
  [--tries <n>] \
  [--randomize-seed] \
  [extra args...]
```

Design rule: treat this as the stable execution contract; queue manager orchestrates it but does not fork script logic.

## 8) Failure Handling Strategy

- ComfyUI API validation errors (HTTP 400):
  - detect and summarize node-level error text in `last_error`
  - mark job `failed`
- Timeout/errors during queueing:
  - capture stderr/stdout
  - expose retry button
- Worker crash/restart:
  - on boot, transition stale `running` jobs to `failed_recoverable`
  - allow one-click requeue

## 9) Security and Safety

- Store only local paths; block path traversal (`..`) for subdir inputs.
- Escape/sanitize shell args by using subprocess arg lists (no raw shell concatenation).
- Keep commands and logs auditable.

## 10) Why this approach is practical now

- Reuses your proven script and workflow JSONs.
- Adds queue reliability and visibility with minimal disruption.
- Keeps room to evolve into FastAPI later without wasting work:
  - DB schema and worker can be reused.

## 11) Open Questions

- Should pause mean "finish current image then pause" or hard interrupt immediately?
- Do we need per-job output directory override?
- Should failed jobs auto-retry (N attempts) for transient API timeouts?
- Is one-worker-only acceptable for now, or do you want a guarded `max_workers=2` mode?

## 12) Next Implementation Step

Build Option A MVP in `/home/cobra/video_queue/` with:

- `app.py` (Streamlit UI)
- `db.py` (SQLite models/helpers)
- `worker.py` (single worker loop)
- `runner.py` (CLI adapter for batch script)
- `README.md` (run instructions + alias suggestions)
