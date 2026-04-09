# AI Guide

This file is the fast-start brief for another AI working in `video_queue`.

It is written from the current code, not just historical docs.

## 1. What this repo is

`video_queue` is a local queue manager for ComfyUI workflows.

It provides:
- A FastAPI backend in `app.py`
- A SQLite queue in `data/queue.db` via `db.py`
- A background worker thread in `worker.py`
- Workflow definitions in YAML in `workflow_defs_v2/`
- A legacy static UI at `/`
- A Svelte V2 UI at `/v2` from `ui/build`
- A small CLI in `cli.py`
- A two-stage LM Studio powered auto-prompt subsystem in `auto_prompt/`

The dominant use case is batch image-to-video WAN workflows, but the repo also supports:
- image generation
- image upscaling
- video upscale/interpolation
- per-image prompt overrides
- split-prompt workflows with `positive_prompt_stageN`

## 2. Current stack

Backend:
- Python
- FastAPI
- SQLite
- plain thread-based worker
- `urllib` for Comfy API calls

Frontend:
- SvelteKit static build in `ui/`
- Tailwind present, but the app is mostly hand-authored Svelte/CSS

Minimal Python deps from `requirements.txt`:
- `fastapi`
- `uvicorn`
- `pyyaml`
- `requests`

Important runtime dependency:
- ComfyUI must be reachable

Optional runtime dependency:
- LM Studio for auto-prompt

## 3. Repo map

Core backend:
- `app.py`: FastAPI app, route handlers, request validation, staging, startup/shutdown
- `db.py`: schema, job/prompt CRUD, queue state, preset storage
- `worker.py`: polling loop, Comfy submission, reconciliation, processed-file moves
- `defs.py`: workflow YAML loader and validator
- `prompt_builder.py`: prompt JSON generation from workflow defs + input files + params
- `comfy_client.py`: Comfy HTTP client wrapper

Operator/dev tools:
- `cli.py`: list/status/submit/cancel/retry
- `auto_prompt_cli.py`: dev harness for auto-prompt iteration
- `run.sh`: local server launcher
- `services/job_service.py`: shared submit/staging/prompt-build helpers used by both API and CLI

Auto-prompt:
- `auto_prompt/generator.py`
- `auto_prompt/prompts.py`
- `auto_prompt/cache.py`

Frontend:
- `ui/src/routes/+page.svelte`
- `ui/src/lib/api.ts`
- `ui/src/lib/stores/*.ts`
- `ui/src/lib/components/**/*`

Docs worth trusting:
- `README.md`
- `docs/codebase_readout.md`
- `docs/video_queue_ui_v2_spec.md`
- `docs/auto_prompt_runbook.md`
- `docs/review/cancel_reliability.md`

Docs that are more planning/historical:
- `QUEUE_MANAGER_DESIGN.md`
- `REFACTOR_OPPORTUNITIES.md`
- `tasks.md`

## 4. Startup and environment

Expected env vars:
- `VIDEO_QUEUE_ROOT`
  - app root for `data/`, `static/`, `ui/build/`, default workflow location
- `WORKFLOW_DEFS_DIR`
  - active workflow YAML directory
- `COMFY_ROOT`
  - used for input dir defaults and model discovery
- `COMFY_BASE_URL`
  - Comfy HTTP base URL, default `http://127.0.0.1:8188`
- `LMSTUDIO_URL`
  - auto-prompt backend, default `http://127.0.0.1:1234`
- `PORT`
  - FastAPI port, default `8585`
- `VIDEO_QUEUE_API`
  - CLI target API, default `http://127.0.0.1:8585`

Recommended local values from repo root:

```bash
export VIDEO_QUEUE_ROOT="$(pwd)"
export WORKFLOW_DEFS_DIR="$(pwd)/workflow_defs_v2"
export COMFY_ROOT="$HOME/ComfyUI"
export COMFY_BASE_URL="http://127.0.0.1:8188"
export PORT=8585
```

Start server:

```bash
./run.sh
```

Launcher detail:
- `run.sh` prefers `./venv/bin/python -m uvicorn ...`
- this avoids stale shebang breakage if the repo directory moved and `venv/bin/uvicorn` still points at an old path

UI routes:
- `/` -> legacy UI from `static/index.html`
- `/legacy` -> same legacy UI
- `/v2` -> Svelte V2 from `ui/build` if present
- `/v2` -> `503` setup message if build missing

Important gotcha:
- `defs.py` validates workflow template existence at app startup
- active workflow YAMLs currently use repo-relative `template:` paths, which is the correct pattern
- if a new workflow is added with machine-local absolute paths, startup will fail loudly on reload/startup

## 5. Mental model of the system

The system is:

1. Load workflow YAML definitions into memory at startup.
2. Accept job submissions via API or CLI.
3. Normalize params and build concrete Comfy prompt JSON for each input file / try.
4. Persist those prompts into SQLite.
5. Worker thread picks the next pending prompt and submits it to Comfy.
6. Worker polls Comfy history until terminal.
7. Worker stores outputs/logs/status back in SQLite.

Important design detail:
- the DB stores fully materialized `prompt_json` per prompt row
- the worker does not rebuild prompts later
- nearly all submission bugs are upstream of `QueueDB.create_job()`

## 6. End-to-end execution path

Primary submit path:

1. `POST /api/jobs` or `POST /api/jobs/single` in `app.py`
2. workflow lookup from `state.workflows`
3. shared submit helpers in `services/job_service.py` normalize paths, validate inputs, stage files, normalize legacy aliases, and prepare prompt specs
4. input files are copied into `COMFY_ROOT/input/_video_queue_staging/<batch>/`
5. `resolve_params()` validates/coerces values
6. `build_prompts()` produces one `PromptSpec` per file per try
7. `QueueDB.create_job()` inserts one job row and N prompt rows
8. worker picks pending prompt
9. `queue_prompt()` posts to Comfy `/prompt`
10. `poll_until_done()` watches `/history/{prompt_id}`
11. outputs from Comfy history are stored in `prompts.output_paths`

Single-image submit is not a different system:
- `/api/jobs/single` just validates one file and then calls the same enqueue helper

CLI submit path:
- tries API first
- falls back to the same shared local submit service if API is unreachable
- dry-run always uses local build logic

Compatibility note:
- legacy submit aliases like `lora_high_name`, `lora_low_name`, and `lora_strength` are normalized in `services/job_service.py`
- that compatibility does not live in `prompt_builder.py`

## 7. Queue and worker semantics

The worker is a single background thread created in FastAPI startup.

Selection policy:
- next prompt ordered by `jobs.priority DESC`, then `jobs.created_at ASC`, then `prompts.id ASC`

Pause semantics:
- `queue_state.paused=1` blocks worker pickup
- pausing does not stop already-running Comfy work

Cancel semantics:
- pending prompts are canceled immediately
- running prompts are not hard-killed
- behavior is explicitly "cancel after current"
- worker checks `cancel_requested` before queueing a pending prompt

Recovery semantics:
- on startup, the worker reconciles any `running` rows using Comfy history/queue
- prompts missing from both queue/history can be marked interrupted/failed

Output semantics:
- output files remain in Comfy output locations
- this app only stores relative output paths from history
- no output copy-back is performed

Processed-source semantics:
- if `move_processed` is true and a job fully succeeds, input source files may be moved into `<input_dir>/_processed`
- this is skipped when other active jobs still reference the same input file

Logs:
- per prompt log file under `data/logs/{job_id}_{prompt_row_id}.log`
- current/latest log path also stored on `jobs.log_path`

## 8. Database model

Main tables:

`jobs`
- `id`
- `workflow_name`
- `job_name`
- `status`
- `cancel_requested`
- `priority`
- `input_dir`
- `params_json`
- `created_at`
- `started_at`
- `finished_at`
- `last_error`
- `log_path`
- `move_processed`

`prompts`
- `id`
- `job_id`
- `input_file`
- `prompt_json`
- `status`
- `prompt_id`
- `started_at`
- `finished_at`
- `exit_status`
- `error_detail`
- `output_paths`
- `seed_used`

Other tables:
- `queue_state`
- `input_dir_history`
- `prompt_presets`
- `settings_presets`

Important DB behavior:
- `db.py` performs lightweight in-place schema migration with `ALTER TABLE` guards
- `DELETE FROM jobs` clears prompts too because prompts reference jobs `ON DELETE CASCADE`

## 9. Workflow definition system

Workflow defs are YAML files loaded by `defs.py`.

Required fields:
- `name`
- `description`
- `input_type` in `image | video | none`
- `input_extensions`

Optional but common:
- `display_name`
- `group`
- `category`
- `move_processed`
- `file_bindings`
- `parameters`
- `switch_states`

Template source:
- `template: /path/to/template.json`
- or `template_inline: { ... }`

Parameter types:
- `text`
- `bool`
- `int`
- `float`

Binding model:
- `file_bindings` map logical concepts like `load_image`, `load_video`, `output_prefix`, `seed`
- `parameters.*.nodes + field/fields` map user params into prompt node inputs

Validation rules enforced by `defs.py`:
- referenced template file must exist
- template JSON must parse
- binding node IDs must exist in template
- parameter node IDs must exist in template
- switch node IDs must exist in template

This means:
- workflow YAML edits are usually safe to validate via `POST /api/reload/workflows`
- bad YAML/template paths fail loudly

## 10. Prompt building rules

`prompt_builder.py` is the main implementation hotspot for submit behavior.

What it does:
- validate and coerce all params
- reject unknown params
- deep-copy template prompt
- bind input file path to workflow nodes
- apply parameter overrides
- apply switch states
- normalize specific context schedule values
- optionally apply resolution preset to every node with numeric `width` and `height`
- optionally flip orientation by swapping numeric `width`/`height`
- set output prefix
- randomize seeds if requested or if `tries > 1`

Important behavior:
- input-less workflows still build one prompt using a fake `None` input
- `per_file_params` can override resolved params per source file
- keys for `per_file_params` can be absolute path or basename
- staging rewrites those overrides to staged file paths before build

Special-case logic exists for:
- extra LoRA enable/disable behavior
- the single-pass workflow `wan-context-lite-2stage`
- split extra-LoRA chain rewiring

If a change affects:
- per-image overrides
- split prompts
- extra LoRA enable flags
- resolution/orientation

then start in `prompt_builder.py` first.

## 11. Current workflow inventory

Active default workflow set in `workflow_defs_v2/`:
- `wan-context-2stage`
- `wan-context-2stage-split-prompts`
- `wan-context-3stage-split-prompts`
- `wan-context-lite-2stage`
- `image-gen-flux-img2img`
- `upscale-images-i2v`
- `upscale-interpolate-only`

Categories used by the UI:
- `video_gen`
- `image_gen`
- `video_upscale`
- `image_upscale`

Split-prompt convention:
- workflows exposing `positive_prompt_stage1`, `positive_prompt_stage2`, etc. are treated as split workflows
- auto-prompt stage 2 returns `clip_1`, `clip_2`, ... for these

Move-processed defaults:
- `wan-context-2stage` and `wan-context-lite-2stage` currently set `move_processed: true`
- several others do not

## 12. API surface

Core endpoints:
- `GET /api/workflows`
- `GET /api/resolution-presets`
- `GET /api/loras`
- `GET /api/upscale-models`
- `GET /api/prompt-presets`
- `POST /api/prompt-presets`
- `GET /api/settings-presets`
- `POST /api/settings-presets`
- `POST /api/reload/workflows`
- `POST /api/reload/loras`
- `POST /api/reload/upscale-models`
- `GET /api/auto-prompt/capability`
- `POST /api/auto-prompt`
- `POST /api/input-dirs/normalize`
- `GET /api/input-dirs/recent`
- `GET /api/input-dirs/default`
- `POST /api/input-dirs/recent`
- `POST /api/pick-directory`
- `POST /api/pick-image`
- `POST /api/upload/input-image`
- `POST /api/jobs`
- `POST /api/jobs/single`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`
- `POST /api/jobs/{job_id}/retry`
- `POST /api/queue/pause`
- `POST /api/queue/resume`
- `POST /api/queue/clear`
- `GET /api/health`
- `GET /api/jobs/{job_id}/log`

API implementation is still monolithic inside `app.py`.

Useful route facts:
- `/api/jobs` supports `prompt_mode`, `per_file_params`, `split_by_input`, `move_processed`, `priority`
- `/api/jobs/single` is simpler and does not expose `prompt_mode`
- upload uses raw bytes with headers `x-filename` and `x-subdir`
- upload preserves a sanitized original filename when possible and dedupes collisions as `name__2.ext`, `name__3.ext`, etc.
- upload response currently includes `path`, `dir`, and `original_filename`
- auto-prompt returns `503` if LM Studio is unavailable

## 13. Auto-prompt subsystem

Auto-prompt is opt-in and separate from base queue execution.

Main flow:
- Stage 1 `caption`: image -> caption
- Stage 2 `motion`: caption -> motion prompt(s)
- Stage `both`: run both

Main code:
- `auto_prompt/generator.py`

Key types:
- `WorkflowContext`
- `LMStudioClient`
- `AutoPromptGenerator`

Availability checks:
- `check_available()` verifies LM Studio API responds
- `ensure_required_models_loaded()` ensures stage models are loaded, optionally auto-loading them

Defaults from code/tests:
- Stage 1 model: `Qwen3-VL-8B-NSFW-Caption-V4.5`
- Stage 2 model: `Dolphin-Mistral-24B-Venice-Edition`

Workflow context derivation:
- split workflow detection is based on `positive_prompt_stageN` params
- FPS and total frames are inferred from template node inputs
- default markers for current 81f / 24fps flows are `0.0`, `1.5`, `3.0`

Prompt modes supported by submit:
- `manual`
- `per-image manual`
- `per-image auto`

Validation rule:
- per-image modes require non-empty `per_file_params`

## 14. Frontend architecture

There are effectively two frontends:

Legacy:
- `static/index.html`
- still the default at `/`

V2:
- Svelte static app in `ui/`
- served at `/v2`

V2 entry:
- `ui/src/routes/+page.svelte`

High-level V2 structure:
- `StatusBar`
- `SubmitPanel`
- `QueuePanel`

Current V2 layout direction:
- desktop-first "control room" shell
- hero/status/workspace shell at top
- submission desk on the left
- sticky queue board on the right
- queue cards are deliberately more editorial than dashboard-like

Global stores:
- `ui/src/lib/stores/workflows.ts`
- `ui/src/lib/stores/health.ts`
- `ui/src/lib/stores/jobs.ts`
- `ui/src/lib/stores/workspace.ts`

Important frontend behavior:
- jobs polling with abort + latest-request-wins + exponential backoff
- health polling with same pattern
- hidden tab pauses polling
- multi-workspace tabs persist in localStorage
- current workspace rename still uses `window.prompt`, so that is a good future polish target if UX work continues

Workspace state includes:
- active tab
- workflow
- resolution preset
- flip orientation
- move processed
- input dir
- job name
- prompt mode
- params by workflow
- per-file params
- dropped input paths
- preset names

This means frontend work often touches store shape first, not just components.

## 15. Frontend API contract notes

The TS API layer in `ui/src/lib/api.ts` is intentionally strict:
- validates response shapes
- converts HTTP error payloads to thrown `Error`
- has request timeouts

Polling constants:
- jobs poll: `2500ms`
- health poll: `3000ms`
- jobs max backoff: `15000ms`
- health max backoff: `20000ms`

If backend response shapes drift, V2 will fail loudly.

Recent shape detail that matters:
- `/api/upload/input-image` now returns optional `original_filename`
- if upload response shape changes, update both `ui/src/lib/api.ts` and `docs/video_queue_ui_v2_spec.md`

One thing to watch:
- some TS interfaces are more aspirational than exact backend field names
- trust the live backend and UI usage over stale type assumptions if there is a mismatch

## 16. File staging model

Submission does not hand arbitrary source paths directly to Comfy.

Instead:
- source files are copied into `COMFY_ROOT/input/_video_queue_staging/<batch_token>/`
- prompt JSON points at staged input paths or Comfy-relative paths
- DB `prompts.input_file` keeps the original source path

Why this matters:
- source files can be deleted after submit and the queued job can still run
- tests assert this behavior
- any change to submit code must preserve the original-path vs staged-path separation

## 17. Testing strategy

Python:

```bash
PYTHONPATH=. ./venv/bin/pytest -q
```

Node state test:

```bash
node --test tests/frontend_state.test.mjs
```

UI package checks:

```bash
cd ui
npm ci
npm run check
npm run build
```

Test harness facts:
- `tests/conftest.py` spins up a fake Comfy HTTP server
- tests run against a temp `VIDEO_QUEUE_ROOT` and temp `COMFY_ROOT`
- if `ui/build` exists, the fixture copies it into temp root

Representative test coverage:
- API contract and submit behavior
- cancel/retry semantics
- prompt-builder parity
- auto-prompt generation and API behavior
- UI mount/build assumptions
- frontend state contract

When changing behavior, prefer adding or updating:
- prompt-builder tests for prompt JSON changes
- API tests for payload/response contract changes
- UI contract tests if DOM ids or payload assembly change

## 18. Known implementation traps

1. Workflow template path validation is unforgiving
- repo-relative `template:` paths are safe
- machine-local absolute paths are still a portability footgun if someone reintroduces them

2. `app.py` is large and mixes concerns
- route changes can accidentally break unrelated behavior

3. Submission logic is now partially centralized, not fully decomposed
- API and CLI both route through `services/job_service.py` for the main submit/staging/prompt-prep path
- route handlers in `app.py` are still large, so submit behavior can still be easy to regress if logic is re-inlined

4. Worker is single-threaded and best-effort
- no hard cancel for active Comfy execution

5. `build_prompts()` has workflow-specific branching
- changing generic logic can break only one workflow family

6. UI V2 is not the root UI yet
- changing `/v2` does not change `/`

7. Some docs are historical
- verify against code before trusting them

8. `ui/build/` is checked in
- repo may contain stale built assets relative to `ui/src`

9. Local dirty worktree
- current `git status` shows untracked `.codex`
- do not assume a clean tree

10. V2 now has a stronger hand-authored visual system
- typography/tokens/layout live across `ui/src/app.css`, `ui/src/app.html`, and queue/submit components
- avoid reverting to generic system-font dark-dashboard styling when editing the frontend
- preserve the desktop-first split between submission desk and queue board unless the task explicitly changes product direction

## 19. Best places to start, depending on task

If the task is about:

Workflow schema or startup failures:
- `defs.py`
- `workflow_defs_v2/*.yaml`

Prompt values not appearing in Comfy:
- `prompt_builder.py`
- then the target workflow YAML

Queue status / cancel / retry / processed-file movement:
- `db.py`
- `worker.py`

API payload validation or response shape:
- `app.py`

Comfy communication failures:
- `comfy_client.py`

Prompt presets / settings presets / recent dirs:
- `db.py`
- `app.py`

Auto-prompt:
- `auto_prompt/generator.py`
- `app.py`
- `auto_prompt_cli.py`

V2 UI behavior:
- `ui/src/lib/api.ts`
- `ui/src/lib/stores/*`
- `ui/src/lib/components/*`

Shared submit behavior or staging semantics:
- `services/job_service.py`
- then `app.py` / `cli.py`

## 20. Safe implementation workflow for another AI

1. Read the workflow YAML and target template if the task touches prompt construction.
2. Read the relevant tests before editing behavior.
3. Prefer changing backend behavior through existing helpers rather than adding new route-local logic.
4. If the change touches submit behavior, start in `services/job_service.py` before adding logic to `app.py` or `cli.py`.
5. For new submit semantics, keep DB-stored `prompt_json` as the source of truth.
6. Preserve staged-input behavior unless the task explicitly changes it.
7. Run focused tests first, then broader ones.
8. If touching V2, check whether the change also needs legacy UI parity or only `/v2`.

## 21. Quick commands

Backend server:

```bash
./run.sh
```

Convenience launcher on this machine:

```bash
vq
```

It exports the expected env vars, `cd`s into the repo, and runs `./run.sh`.

CLI examples:

```bash
./venv/bin/python cli.py list
./venv/bin/python cli.py status
./venv/bin/python cli.py submit --workflow wan-context-lite-2stage --dir /path/to/input
./venv/bin/python cli.py submit --workflow wan-context-lite-2stage --dir /path/to/input --dry-run
./venv/bin/python cli.py cancel 42
./venv/bin/python cli.py retry 42
```

Auto-prompt harness:

```bash
./venv/bin/python auto_prompt_cli.py --mock --stage both --workflow-name wan-context-2stage --dir /tmp/images
```

Focused backend tests:

```bash
PYTHONPATH=. ./venv/bin/pytest tests/test_api_single_submit.py -q
PYTHONPATH=. ./venv/bin/pytest tests/test_job_service.py -q
PYTHONPATH=. ./venv/bin/pytest tests/test_upload_and_staging_helpers.py -q
PYTHONPATH=. ./venv/bin/pytest tests/test_worker_cancel_timing.py -q
PYTHONPATH=. ./venv/bin/pytest tests/test_api_image_gen.py -q
PYTHONPATH=. ./venv/bin/pytest tests/test_auto_prompt_generator.py -q
```

Frontend checks:

```bash
cd ui
npm ci
npm run check
npm run build
```

## 22. Bottom line

This repo is easiest to work in if you keep these invariants in your head:
- workflow YAML + prompt builder define runtime prompt shape
- API and CLI submit parity now depends on `services/job_service.py`
- DB stores final prompt JSON, not deferred recipes
- the worker is simple and intentionally conservative
- staged input files are part of the contract
- V2 is strict about backend response shape
- V2 now also has a deliberate visual system; keep changes cohesive with it
- auto-prompt is layered on top of submit, not a replacement for it

If you need to move quickly, start from the specific execution path the feature touches, then validate with the nearest existing tests.
