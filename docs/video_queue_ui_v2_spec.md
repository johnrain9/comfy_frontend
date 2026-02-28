# Video Queue UI V2 API and Architecture Spec

## Scope
This document is the contract for the Svelte V2 UI (`ui/`) running at `/v2` against the existing FastAPI backend in `app.py`.

Compatibility constraints:
- V1 (`/` + `static/index.html`) and V2 (`/v2`) share the same backend and DB.
- V2 implementation must not require backend behavior changes to existing endpoints.
- Route precedence must keep `/v2` isolated from V1 root handling.

## Endpoint Contract

### `GET /api/workflows`
- Purpose: load available workflows and dynamic parameter schema.
- Response: `WorkflowDef[]`
- Shape per item:
  - `name: string`
  - `display_name: string`
  - `group: string`
  - `category: 'video_gen' | 'image_gen' | 'video_upscale' | 'image_upscale'`
  - `description: string`
  - `input_type: 'none' | 'image' | 'video'`
  - `input_extensions: string[]`
  - `supports_resolution: boolean`
  - `parameters: Record<string, { label: string; type: 'text'|'int'|'float'|'bool'; default: string|number|boolean|null; min: number|null; max: number|null }>`
- Errors:
  - `500` unexpected backend failure

### `GET /api/resolution-presets`
- Purpose: resolution dropdown for compatible workflows.
- Response: `{ presets: { id: string; label: string; width: number; height: number }[] }`
- Errors: `500`

### `GET /api/input-dirs/default`
- Purpose: default input directory hint.
- Response: `{ default_path: string; exists: boolean }`
- Errors: `500`

### `POST /api/input-dirs/normalize`
- Purpose: normalize/validate user-provided path.
- Request: `{ path: string }`
- Response: `{ normalized_path: string }`
- Errors:
  - `400` with `{"detail": string}` for invalid path

### `GET /api/prompt-presets?mode=<mode>`
- Purpose: prompt preset list scoped by mode.
- Response: `{ items: PromptPreset[] }`
- `PromptPreset`: `{ name, mode, positive_prompt, negative_prompt, updated_at }`
- Errors: `400` for bad query args, `500`

### `POST /api/prompt-presets`
- Purpose: save/overwrite prompt preset.
- Request: `{ name: string; mode: string; positive_prompt: string; negative_prompt: string }`
- Response: `PromptPreset`
- Errors:
  - `400` with `{"detail": string}` validation issues

### `GET /api/settings-presets`
- Purpose: load reusable submit/settings bundles.
- Response: `{ items: SettingsPreset[] }`
- `SettingsPreset`: `{ name: string; payload: object; updated_at: string }`
- Errors: `500`

### `POST /api/settings-presets`
- Purpose: save/overwrite settings preset.
- Request: `{ name: string; payload: object }`
- Response: `SettingsPreset`
- Errors:
  - `400` with `{"detail": string}` validation issues

### `POST /api/upload/input-image`
- Purpose: upload dropped/browsed images into Comfy input hierarchy.
- Headers:
  - `x-filename: string`
  - `x-subdir: string`
- Body: raw bytes
- Response: `{ path: string; dir: string }`
- Errors:
  - `400` with `{"detail": string}` for unsupported extension, empty file, invalid subdir

### `POST /api/jobs`
- Purpose: submit one or split-many jobs.
- Request:
  - `workflow_name: string`
  - `job_name: string | null`
  - `input_dir: string`
  - `params: object`
  - `resolution_preset: string | null`
  - `flip_orientation: boolean`
  - `move_processed: boolean`
  - `split_by_input: boolean`
  - `priority: number`
- Response:
  - single submit: `{ job_id: number; job_name: string|null; prompt_count: number; input_dir: string }`
  - split submit: `{ job_ids: number[]; job_count: number; prompt_count: number; input_dir: string }`
- Errors:
  - `400` with `{"detail": string}` (unknown workflow, invalid input dir, no files, bad params)

### `GET /api/jobs`
- Purpose: queue list polling.
- Response: `JobListItem[]`
- Errors: `500`

### `GET /api/jobs/{id}`
- Purpose: lazy-loaded row detail.
- Response: `{ job: object; prompts: JobPromptRow[] }`
- Errors:
  - `404` with `{"detail":"job not found"}`

### `GET /api/jobs/{id}/log`
- Purpose: lazy-loaded logs for expanded detail.
- Response: plain text (`text/plain`)
- Errors:
  - `404` with `{"detail":"job not found"}`

### `POST /api/jobs/{id}/cancel`
- Purpose: cancel pending/running prompts for a job.
- Response: object summary from DB layer
- Errors: `404` when job does not exist

### `POST /api/jobs/{id}/retry`
- Purpose: reset failed/canceled prompts for retry.
- Response: object summary from DB layer
- Errors: `404` when job does not exist

### `POST /api/queue/pause`
- Purpose: pause worker processing.
- Response: `{ worker: 'paused' }`

### `POST /api/queue/resume`
- Purpose: resume worker processing.
- Response: `{ worker: 'running' }`

### `POST /api/queue/clear`
- Purpose: clear queue state.
- Response: `{ ok: true, ...summary }`

### `POST /api/reload/workflows`
- Purpose: reload workflow defs on disk.
- Response: `{ count: number; workflows: string[] }`
- Errors: `400` with `{"detail": string}` for definition errors

### `POST /api/reload/loras`
- Response: `{ count: number; loras: string[] }`

### `GET /api/health`
- Purpose: status bar polling.
- Response: `{ comfy: boolean; worker: string; pending: number; running: number }`

## Error Handling Model (V2 client)
`ui/src/lib/api.ts` normalizes failures into thrown `Error` objects.

Expected classes:
- Network failure / unreachable backend: fetch throws (surfaced directly).
- Timeout: request abort -> `Error("Request timed out after <ms>ms")`.
- HTTP 4xx/5xx JSON payload: uses `detail` when present.
- HTTP 4xx/5xx text payload: uses text body when non-empty.
- Malformed success payload: throws explicit "Invalid API response for <endpoint>...".

## Frontend State/Data Flow

### Jobs polling flow
1. `startJobsPolling()` schedules immediate poll.
2. Previous in-flight request is aborted on next tick.
3. Latest response wins using request id monotonic guard.
4. Failures increment exponential backoff up to `MAX_BACKOFF_MS`.
5. Hidden tab pauses timer and aborts in-flight; focus resumes fast refresh.

### Health polling flow
Same mechanics as jobs polling with independent interval/backoff settings.

### Submit flow
1. User selects mode -> workflows filtered by category.
2. Active workspace state provides tab/workflow/input/params.
3. Param values are rendered from backend schema and coerced by type.
4. Optional uploads go through `/api/upload/input-image`, writing input dir.
5. Submit posts to `/api/jobs`; queue refresh triggered on success.

### Job detail/log flow
1. Row expand requests `/api/jobs/{id}` once, then caches in component state.
2. Log panel is manual toggle and lazy-loads `/api/jobs/{id}/log` once.
3. Cancel/retry actions are per-row and trigger queue refresh.

## Non-Functional Limits and Guardrails
- Jobs poll interval: `2500ms`
- Health poll interval: `3000ms`
- Jobs backoff cap: `15000ms`
- Health backoff cap: `20000ms`
- Request timeout defaults:
  - general API calls: `15000ms`
  - jobs/health polling: `12000ms`
  - submit: `45000ms`
  - upload: `30000ms`
- Queue render window: initial 200 rows, `Load More` increments by 200.
- Target responsiveness: queue interactions remain responsive at 200+ rows with continuous polling.

## Route/Mount Contract
- V1 root: `GET /` serves `static/index.html`.
- V2: `/v2` static mount from `ui/build` when present.
- Missing V2 build: `/v2` returns 503 plain-text setup guidance.
- Optional legacy alias: `GET /legacy` serves `static/index.html`.
