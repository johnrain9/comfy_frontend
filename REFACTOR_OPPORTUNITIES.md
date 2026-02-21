# Refactor Opportunities and Implementation Plan

## Scope
This document is a point-in-time assessment of refactor opportunities in this repository (`/home/cobra/video_queue`).  
Because multiple agents may be editing concurrently, treat this as guidance for planning and staged execution.

## Executive Summary
Refactoring is beneficial, but should be incremental.  
A full rewrite is not justified. The highest ROI is improving module boundaries and reducing duplicate logic between API, CLI, DB, and worker flows.

## Current Architecture Snapshot
- API + app state + utility logic are concentrated in `app.py`.
- Queue persistence and status derivation are in `db.py`.
- Execution loop and Comfy orchestration are in `worker.py`.
- Prompt construction and parameter coercion are in `prompt_builder.py`.
- Workflow schema/loading is in `defs.py`.
- CLI duplicates parts of API submit flow in `cli.py`.
- Frontend is a single inline HTML/JS file in `static/index.html`.

## Prioritized Refactor Opportunities

## 1) Unify job submission flow (API + CLI)
- Problem: submit path is partially duplicated across `app.py` and `cli.py`.
- Benefit:
  - Prevent behavior drift between CLI and API.
  - Reduce maintenance overhead for validation/prompt-building changes.
- Approach:
  - Add a shared service module (e.g. `job_service.py`) with:
    - `prepare_job(workflow, input_dir, params, resolution, flip)`
    - `enqueue_job(db, workflow, prepared_job, priority)`
  - Use it from both API handler and CLI local submit path.
- Effort: Medium
- Risk: Low

## 2) Tighten DB boundary and thread-safety
- Problem: worker directly writes via `db.conn` outside `QueueDB` methods.
- Benefit:
  - Stronger invariants for writes and transactions.
  - Lower risk of subtle race/locking issues with concurrent API + worker access.
- Approach:
  - Remove direct `db.conn` usage from non-DB modules.
  - Add explicit methods like `set_job_log_path(job_id, log_path)`.
  - Optionally migrate to per-operation connections (or thread-local connection strategy).
- Effort: Medium
- Risk: Medium

## 3) Decompose worker loop into explicit phases
- Problem: `Worker._run_loop` handles scheduling, execution, status transitions, and logging in one path.
- Benefit:
  - Easier debugging and future policy changes.
  - Better unit-test coverage of transitions and error paths.
- Approach:
  - Split into methods:
    - `claim_next_prompt()`
    - `execute_prompt()`
    - `persist_prompt_result()`
    - `finalize_job_if_complete()`
- Effort: Medium
- Risk: Medium

## 4) Split API by domain modules
- Problem: `app.py` currently owns startup/shutdown, endpoint handlers, path normalization, picker utilities, and metadata shaping.
- Benefit:
  - Lower cognitive load per file.
  - Faster onboarding and safer edits.
- Approach:
  - Create:
    - `api/jobs.py`
    - `api/workflows.py`
    - `api/system.py`
    - `services/paths.py`
    - `services/lora.py`
  - Keep `app.py` as thin bootstrap + router registration.
- Effort: Medium
- Risk: Low

## 5) Move frontend behavior to schema-driven rendering
- Problem: UI uses name-based heuristics (`/prompt/i`, `/lora/i`) and duplicated defaults.
- Benefit:
  - Fewer UI regressions when adding new workflow parameters.
  - Clear source of truth from backend metadata.
- Approach:
  - Extend workflow parameter API with optional UI hints:
    - `widget` (`text`, `textarea`, `checkbox`, `select`)
    - `options_source` (e.g., `loras`)
    - `placeholder`, `help`, `multiline`
  - Refactor frontend to render strictly from hints.
- Effort: Medium
- Risk: Low

## 6) Add focused tests before major code movement
- Problem: current tests are mostly coarse E2E.
- Benefit:
  - Enables safe refactoring with fast feedback.
  - Reduces fear of boundary changes.
- Approach:
  - Add unit tests for:
    - `resolve_params` coercion and validation
    - `build_prompts` fan-out/seed/output-prefix behavior
    - input-dir normalization edge cases
    - `update_job_status` and queue selection logic
- Effort: Medium
- Risk: Low

## Refactor Plan (Staged)

## Phase 1: Shared submit service + tests
- Introduce shared job submission service.
- Refactor API and CLI to use it.
- Add tests for submit validation and prompt generation.

## Phase 2: DB hardening
- Eliminate direct DB connection usage from worker.
- Add missing DB methods and isolate transactions.
- Add tests for status transitions and retry/cancel behavior.

## Phase 3: Worker decomposition
- Break loop into discrete methods with explicit inputs/outputs.
- Add tests for each failure class (`validation`, `unreachable`, timeout/exception).

## Phase 4: API module split
- Move routes/utilities into routers and services.
- Keep API contract unchanged.

## Phase 5: Frontend maintainability improvements
- Extract inline JS into separate modules.
- Shift to backend-driven field metadata.

## Suggested Target Layout
```text
video_queue/
  app.py
  api/
    jobs.py
    workflows.py
    system.py
  services/
    job_service.py
    path_utils.py
    lora_service.py
  db/
    queue_db.py
  worker/
    runner.py
  static/
    index.html
    app.js
    api.js
```

## What Not To Do Now
- Do not do a framework rewrite (backend or frontend) as a first step.
- Do not change API contracts while splitting internals.
- Do not mix schema redesign and module extraction in the same PR.

## Success Criteria
- API and CLI use the same submit path.
- No direct `QueueDB.conn` access outside DB layer.
- `app.py` acts mainly as composition/bootstrap.
- Existing endpoints and UI behavior remain stable.
- New tests cover prompt generation, path normalization, and status derivation.

## First PR Recommendation
1. Add `services/job_service.py` with shared submit logic.
2. Refactor `app.py` and `cli.py` to use it.
3. Add tests for submit-path parity (API vs CLI local flow).

