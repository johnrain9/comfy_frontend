# video_queue codebase readout

## 1) How ComfyUI workflows are defined

- Primary format: YAML workflow definition files loaded by `defs.py` (`load_all`, `load_one`).
- Active location by default: `workflow_defs_v2/*.yaml` (configured via `WORKFLOW_DEFS_DIR`, default set in `app.py` and `cli.py`).
- Legacy definitions also exist in `workflow_defs/*.yaml`.
- Template source in YAML:
  - `template: <path-to-json>` (external Comfy prompt JSON file), or
  - `template_inline: { ... }` (inline prompt JSON mapping).
- Parameter schema (`parameters` map in YAML):
  - `type` in `{text, bool, int, float}`
  - optional `label`, `default`, `min`, `max`
  - optional binding target: `nodes` + (`field` or `fields`) for writing into template node inputs.
- Other schema fields:
  - required: `name`, `description`, `input_type` (`image|video`), `input_extensions`
  - optional: `display_name`, `group`, `file_bindings`, `switch_states`, `move_processed`.
- `file_bindings` map logical bindings (`load_image`, `load_video`, `input_file`, `output_prefix`, `seed`) to node ids and fields.

## 2) End-to-end path: submission -> Comfy prompt JSON API call

### API path (primary)
1. User submits via UI/HTTP (`POST /api/jobs` or `POST /api/jobs/single`) in `app.py`.
2. `app.py` validates workflow, normalizes input path, filters matching files by `input_extensions`.
3. `resolve_params(wf, params)` (`prompt_builder.py`) validates/coerces user params to typed values and defaults.
4. `build_prompts(...)` (`prompt_builder.py`) clones template prompt and applies:
   - input-file bindings (`load_image`/`load_video`/`input_file`)
   - parameter overrides by node/field bindings
   - `switch_states`
   - context schedule normalization
   - optional resolution preset override (width/height)
   - optional orientation flip (swap width/height)
   - output prefix/stem
   - randomized seed write when enabled.
5. `QueueDB.create_job(...)` stores job + one prompt row per generated `PromptSpec` with `prompt_json` persisted.
6. Worker loop (`worker.py`) picks next pending prompt row, loads `prompt_json`, then calls Comfy via `queue_prompt(base_url, prompt_json)` (`comfy_client.py`).

### CLI path (alternate)
- `cli.py submit` normally calls `POST /api/jobs`.
- If API unreachable, it falls back to local `resolve_params` + `build_prompts` + direct `QueueDB.create_job`.

## 3) ComfyUI API endpoints used by worker

Used by worker/client code:
- Queue prompt: `POST /prompt` (payload `{ "prompt": <prompt_json> }`)
- Poll status/history: `GET /history/{prompt_id}` (used repeatedly in `poll_until_done`)
- Get history outputs: `GET /history/{prompt_id}` (again, parsed for output files in `get_outputs`)
- Health check: `GET /system_stats`

Cancel behavior:
- No Comfy cancel endpoint is called by this worker.
- Job cancel is internal DB semantics (`cancel_requested`, pending prompts marked canceled, running prompt allowed to finish).

## 4) Current workflows and exposed params

Note: runtime default loads `workflow_defs_v2`.

### Active default set (`workflow_defs_v2`)
- `wan-context-2stage`
  - Task type: i2v (input image -> video)
  - Model(s) in template path `/home/cobra/ComfyUI/user/workflows/wan22_enhancedH_q5L_2stage_gguf_vertical_ctxwindow2.api.json`: WAN 2.2 GGUF UNet(s) + WAN CLIP/VAE; LoRA high/low nodes exposed.
  - User params: `positive_prompt`, `negative_prompt`, `randomize_seed`, `tries`, `output_prefix`, `lora_high_name`, `lora_low_name`, `lora_strength`.
- `wan-context-lite-2stage`
  - Task type: i2v (image -> video)
  - Model(s) in template `workflow_defs_v2/templates/wan22_enhancedH_q5L_2stage_gguf_vertical_ctxwindow_singlepass.api.json`: WAN 2.2 GGUF (`...Q8H.gguf`, `...Q8L.gguf`), WAN CLIP (`umt5_xxl...`), WAN VAE (`wan_2.1_vae.safetensors`), two LoRA loaders.
  - User params: `positive_prompt`, `negative_prompt`, `randomize_seed`, `tries`, `output_prefix`, `lora_high_name`, `lora_low_name`, `lora_strength`.

### Legacy set present in repo (`workflow_defs`)
- `upscale-interpolate`
  - Task type: v2v (video interpolation + upscale)
  - Model(s): `RIFE VFI` with `rife47.pth` + `ImageScaleBy`
  - User params: `scale_by`, `multiplier`, `output_prefix`, `flip_orientation`.
- `wan-i2v-ctxwindow` (i2v; WAN template), params: `positive_prompt`, `negative_prompt`, `randomize_seed`, `tries`, `output_prefix`, `flip_orientation`.
- `wan-i2v-single` (i2v; WAN template), same params as above.
- `wan-i2v-single-extra-lora` (i2v; WAN + extra LoRA), params above plus `extra_lora_high_name`, `extra_lora_low_name`, `extra_lora_strength`.
- `wan-i2v-vertical-extra-lora` (i2v; WAN + extra LoRA), same as previous.

## 5) Resolution/orientation handling

- Resolution is preset-driven in API/UI: hardcoded presets in `app.py` (`RESOLUTION_PRESETS`, e.g. `640x1136`).
- Submission carries `resolution_preset`; app resolves this to `(width,height)` then `build_prompts` writes those dimensions to any template nodes containing numeric `width` and `height` inputs.
- Orientation flip is dynamic at build time: `flip_orientation` swaps all numeric `width`/`height` pairs in prompt nodes.
- So: preset list is hardcoded; application into prompt nodes is dynamic.

## 6) Any templates/presets beyond workflow YAML/JSON?

- Workflow templating: yes, exactly YAML definitions + referenced/inline Comfy prompt JSON.
- Additional preset concept: only resolution presets (`/api/resolution-presets`, from hardcoded `RESOLUTION_PRESETS`).
- No separate higher-level workflow preset/template registry beyond those files.

## 7) Persisted DB data per job and per prompt

SQLite schema (`db.py`):

- `jobs` table:
  - `id`, `workflow_name`, `status`, `cancel_requested`, `priority`
  - `input_dir`, `params_json`
  - `created_at`, `started_at`, `finished_at`
  - `last_error`, `log_path`, `move_processed`

- `prompts` table:
  - `id`, `job_id`, `input_file`, `prompt_json`, `status`
  - `prompt_id` (Comfy prompt id)
  - `started_at`, `finished_at`, `exit_status`, `error_detail`
  - `output_paths` (JSON string list of relative output paths)
  - `seed_used`

Also persisted:
- `queue_state(paused)`
- `input_dir_history(path, last_used_at, use_count)`

## 8) Post-completion output file behavior

- On prompt success, worker reads output paths from Comfy `/history/{prompt_id}` and stores them in DB (`prompts.output_paths`).
- The worker does not copy/move generated Comfy outputs; outputs remain where Comfy wrote them (relative paths from history, typically under Comfy output tree).
- If workflow has `move_processed: true` and the whole job status becomes `succeeded`, worker moves source input files from `job.input_dir` into `job.input_dir/_processed`.
- Metadata sidecars for media files are not written by this app.
- Execution logs are written per prompt to `data/logs/{job_id}_{prompt_row_id}.log`, and latest log path is stored in `jobs.log_path`.
