# UI V2 Setup

UI V2 static assets are generated into `ui/build` and served by FastAPI at `/v2`.

## Local Development
1. `cd ui`
2. `npm install`
3. `npm run dev`

Notes:
- Vite dev server opens `/v2` and proxies `/api` to `http://127.0.0.1:8585`.
- For type checks: `npm run check`.

## Production Build
1. `cd ui`
2. `npm install` (or `npm ci` once lockfile is committed)
3. `npm run build`

Result:
- Static output written to `ui/build`.
- FastAPI mounts build at `/v2` when present.
- If build is missing, `/v2` returns a 503 setup message.

## Route Behavior
- `/` -> legacy UI (`static/index.html`)
- `/legacy` -> legacy UI alias
- `/v2` -> V2 Svelte UI (when built)

This keeps V2 rollout reversible without changing backend API behavior.
