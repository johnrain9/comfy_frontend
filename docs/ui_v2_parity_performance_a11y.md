# UI V2 Parity, Performance, and Accessibility Gate

## Parity Checklist
- [x] Health/status polling + quick actions (pause/resume/reload workflows/reload LoRAs).
- [x] Queue cards with status filter, text search, actionable sort.
- [x] Queue bulk actions with confirmations (cancel selected, clear queue).
- [x] Lazy job detail + prompt rows + lazy log viewer.
- [x] Submit panel modes: Batch, Image Gen, Upscale Video, Upscale Image.
- [x] Dynamic workflow parameter rendering from `/api/workflows`.
- [x] Drag/drop image upload path for image-input flows.
- [x] Prompt and settings preset save/apply.
- [x] Multi-workspace tabs with localStorage persistence.

## Performance Guardrails
- Jobs polling: 2.5s base, exponential backoff to 15s.
- Health polling: 3.0s base, exponential backoff to 20s.
- Render strategy: in-memory filtering/sort + incremental rendering (`RENDER_STEP=200`).
- Target: responsive interaction at 200+ rows under sustained polling.

## Accessibility Checklist
- [x] Status region uses `aria-live`.
- [x] Workspace and mode controls are keyboard-focusable buttons.
- [x] Expand/collapse control is explicit button with label.
- [x] Drag-drop area has explicit role and remains browse-operable.
- [x] Status uses text labels, not color-only encoding.

## Validation Commands
- Frontend type/svelte checks: `cd ui && npm run check`
- Frontend build: `cd ui && npm run build`
- Backend/UI contract tests: `./venv/bin/pytest -q tests/test_ui_v2_mount.py tests/test_ui_v2_contract.py`

## Known Deviations
- V2 currently remains mounted at `/v2` (root remains legacy by design).
- No WebSocket transport; polling is used for simplicity and robustness.
