# UI V2 Scaffold

This directory contains the Svelte-based V2 UI scaffold.

## Dev

- `cd ui`
- `npm ci`
- `npm run dev`

The Vite dev server proxies `/api` requests to `http://127.0.0.1:8585`.

## Build

- `cd ui`
- `npm ci`
- `npm run build`

Static output is written to `ui/build` and served by FastAPI at `/v2`.
