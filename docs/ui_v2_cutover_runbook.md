# UI V2 Cutover Runbook

## Goal
Promote V2 from `/v2` to default root (`/`) safely, with rollback in one edit.

Current state:
- `/` serves legacy UI.
- `/v2` serves Svelte V2 when `ui/build` exists.

## Preconditions
- `cd ui && npm install && npm run check && npm run build`
- V2 smoke passed for submit/monitor/cancel/retry/presets/workspace behavior.
- Backend API tests pass.

## Cutover Steps
1. In `app.py`, change `@app.get("/")` to return `ui/build/index.html` instead of `static/index.html`.
2. Keep `/legacy` mapped to `static/index.html`.
3. Keep `/v2` mount active for one transition window.
4. Restart server.
5. Verify:
   - `/` loads V2
   - `/legacy` loads old UI
   - `/api/*` unchanged

## Rollback Steps
1. Revert root handler in `app.py` to `static/index.html`.
2. Restart server.
3. Verify `/` is legacy and `/v2` is still available.

## Failure Signatures
- `Cannot GET /v2/...` asset 404s:
  - likely missing build output or wrong base path.
  - run `npm run build` and verify `kit.paths.base='/v2'`.
- `/v2` returns 503 setup message:
  - build directory missing.
- Queue data/actions fail in V2 but work in V1:
  - inspect browser network calls to `/api/*`; backend contract drift likely.
