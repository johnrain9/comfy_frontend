# Video Queue UI V2: Modern Rewrite

## 1. Problem

The current UI is a single 3,000-line `index.html` with inline CSS and JS. It works, but:
- **Visually dense** — the queue table has ~10 columns all at equal weight, hard to scan
- **No component structure** — everything is one monolithic file, painful to extend
- **Status at a glance is poor** — small colored badges, no progress bars, no timeline
- **Job detail is crammed** — expanding a row dumps raw JSON and a wall of prompt rows
- **Submit form is tall** — dynamic params, presets, drag-drop, resolution all stacked vertically
- **No visual hierarchy** — submit panel and queue panel compete for attention
- **Mobile/responsive is bolted on** — flexbox tweaks, but fundamentally desktop-only layout

The goal is not to change backend behavior — the FastAPI + SQLite + worker architecture is solid. We're replacing the presentation layer only.

## 2. Goals

1. Modern, polished UI that's pleasant to use daily
2. Clear visual hierarchy — submit vs monitor vs detail are distinct zones
3. Job status scannable at a glance — color, progress, timing
4. Componentized codebase — maintainable, each feature in its own file
5. Keep the same FastAPI API (no backend changes needed)
6. Ship as a new app at a different port; old UI stays as-is until deprecated

## 3. Non-goals

- Rewriting the backend (FastAPI, DB, worker, prompt builder stay unchanged)
- Adding new backend features (new endpoints come later, separately)
- Mobile-first design (desktop WSL2 browser is primary target)
- Server-side rendering or complex build pipelines

## 4. Tech Stack Decision

### Option chosen: **SvelteKit (static SPA mode)**

| Consideration | Decision |
|---|---|
| Framework | Svelte 5 — minimal boilerplate, reactive by default, compiles to tiny JS bundles |
| Build | Vite — fast dev server, HMR, single `npm run build` produces static files |
| Styling | Tailwind CSS — utility-first, dark theme built-in, consistent spacing/colors |
| Component lib | shadcn-svelte (headless, accessible, themeable) — gives us badges, dropdowns, tables, dialogs, tabs, toasts without building from scratch |
| Icons | Lucide icons (tree-shakeable SVGs) |
| State | Svelte stores (built-in) — no Redux/Zustand needed |
| API client | Plain `fetch` with a thin typed wrapper |
| Deployment | `npm run build` → static files served by FastAPI's `StaticFiles` mount |

### Why Svelte over alternatives
- **vs React/Next**: Svelte has no virtual DOM overhead, smaller bundles, less boilerplate. For a single-user tool, React's ecosystem advantages don't matter.
- **vs plain HTML/JS (current)**: Current approach already hit its limit at 3,000 lines. Components, reactivity, and scoped styles are needed.
- **vs Vue**: Similar capability, but Svelte's compiler approach produces smaller output and the DX is cleaner for small teams.

## 5. Architecture

```
video_queue/
├── app.py                    # existing FastAPI backend (unchanged)
├── db.py                     # existing (unchanged)
├── worker.py                 # existing (unchanged)
├── ...                       # all other backend files (unchanged)
├── static/                   # old UI (kept for deprecation period)
│   └── index.html
├── ui/                       # NEW: Svelte project
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app.html          # shell HTML
│   │   ├── app.css           # Tailwind imports + theme vars
│   │   ├── lib/
│   │   │   ├── api.ts        # typed fetch wrapper for all endpoints
│   │   │   ├── stores/
│   │   │   │   ├── jobs.ts       # job list polling store
│   │   │   │   ├── health.ts     # ComfyUI + worker status store
│   │   │   │   ├── workflows.ts  # workflow definitions store
│   │   │   │   └── workspace.ts  # multi-workspace state
│   │   │   ├── components/
│   │   │   │   ├── StatusBar.svelte
│   │   │   │   ├── SubmitPanel/
│   │   │   │   │   ├── SubmitPanel.svelte
│   │   │   │   │   ├── BatchTab.svelte
│   │   │   │   │   ├── ImageGenTab.svelte
│   │   │   │   │   ├── UpscaleTab.svelte
│   │   │   │   │   ├── ParamFields.svelte
│   │   │   │   │   ├── DropZone.svelte
│   │   │   │   │   ├── PresetSelector.svelte
│   │   │   │   │   └── ResolutionPicker.svelte
│   │   │   │   ├── Queue/
│   │   │   │   │   ├── QueuePanel.svelte
│   │   │   │   │   ├── JobRow.svelte
│   │   │   │   │   ├── JobDetail.svelte
│   │   │   │   │   ├── PromptRow.svelte
│   │   │   │   │   ├── StatusBadge.svelte
│   │   │   │   │   └── BulkActions.svelte
│   │   │   │   └── shared/
│   │   │   │       ├── Toast.svelte
│   │   │   │       └── ConfirmDialog.svelte
│   │   │   └── types.ts      # TypeScript interfaces matching API responses
│   │   └── routes/
│   │       └── +page.svelte   # single page (SPA)
│   └── build/                 # output → served by FastAPI
└── ...
```

### Mounting

In `app.py`, add alongside the existing mount:

```python
# New UI (V2)
app.mount("/v2", StaticFiles(directory="ui/build", html=True), name="ui_v2")

# Old UI stays at /
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

Visit `http://localhost:8585/v2` for the new UI. Old UI remains at `/`.

## 6. Layout Design

### 6.1 Overall page structure

```
┌──────────────────────────────────────────────────────────────────────┐
│ ● ComfyUI connected    Worker: Running    Pending: 3  Running: 1    │
│                                          [Pause] [Reload Workflows] │
╞══════════════════════════════════════════════════════════════════════╡
│                                                                      │
│  ┌─ Submit ──────────────────────────────────────────────────────┐   │
│  │ [Batch] [Image Gen] [Upscale Video] [Upscale Image]          │   │
│  │                                                               │   │
│  │  Workflow: [────────▾]    Resolution: [480×848 ▾] [⟲]        │   │
│  │                                                               │   │
│  │  ┌─ Parameters ────────────┐  ┌─ Input ──────────────────┐   │   │
│  │  │ Positive prompt         │  │                           │   │
│  │  │ [                     ] │  │   Drop images here        │   │
│  │  │ Negative prompt         │  │   or Browse               │   │
│  │  │ [                     ] │  │                           │   │
│  │  │ LoRA: [──────▾]        │  │   📄 img1.jpg  📄 img2.jpg│   │
│  │  │ Steps: [30        ]    │  │                           │   │
│  │  └─────────────────────────┘  └───────────────────────────┘   │   │
│  │                                                               │   │
│  │  Presets: [Saved prompt ▾] [Saved settings ▾]    [Submit ▶]  │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─ Queue ───────────────────────────────────────────────────────┐   │
│  │ 41 total  ● 1 running  ● 28 succeeded  ● 1 failed  ...      │   │
│  │ [Search...                        ] [Sort: Priority ▾]       │   │
│  │                                                               │   │
│  │  ┌─────────────────────────────────────────────────────────┐  │   │
│  │  │ □  #52  my_batch_job       wan-i2v     ● Running       │  │   │
│  │  │         3/12 prompts done   ████████░░░░  2m ago       │  │   │
│  │  ├─────────────────────────────────────────────────────────┤  │   │
│  │  │ □  #51  upscale_set_3      topaz-4x    ● Succeeded     │  │   │
│  │  │         8/8 prompts done    ████████████  5m ago       │  │   │
│  │  ├─────────────────────────────────────────────────────────┤  │   │
│  │  │ □  #50  failed_run         wan-i2v     ● Failed        │  │   │
│  │  │         0/4 — "CUDA OOM"   ░░░░░░░░░░░░  12m ago  [↻] │  │   │
│  │  └─────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │ [Cancel Selected]                          [Clear Queue]      │   │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 Key layout changes vs current UI

| Current | V2 |
|---|---|
| 10-column flat table | 2-line card per job (name+workflow on line 1, progress+timing on line 2) |
| Tiny colored text status | Large colored pill badges with icons |
| No progress indication | Progress bar per job (completed/total prompts) |
| Raw JSON in expanded detail | Formatted detail panel with sections |
| Params and input stacked vertically | Side-by-side: params left, input/drop-zone right |
| Submit form always fully expanded | Submit panel collapsible (collapse when monitoring) |
| Workspace tabs above submit form | Workspace tabs integrated into submit panel header |

### 6.3 Job detail (click to expand)

```
┌─ Job #52: my_batch_job ──────────────────────────────────────────┐
│                                                                   │
│  Workflow: wan-i2v          Created: 2m ago                      │
│  Input: /mnt/d/V/batch_3    Started: 1m ago                      │
│  Status: Running (3/12)     Elapsed: 1m 22s                      │
│                                                                   │
│  Parameters                                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ positive_prompt: "beautiful landscape, cinematic"          │   │
│  │ steps: 30  │  cfg: 7.0  │  lora: detail_enhancer_v2       │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  Prompts                                                          │
│  ✅ img_001.jpg  →  output/vid_001.mp4     seed: 827134          │
│  ✅ img_002.jpg  →  output/vid_002.mp4     seed: 991283          │
│  ✅ img_003.jpg  →  output/vid_003.mp4     seed: 445521          │
│  ⏳ img_004.jpg  →  running...              seed: 102938          │
│  ⬚ img_005.jpg                                                   │
│  ⬚ img_006.jpg                                                   │
│  ... (6 more)                                                    │
│                                                                   │
│  [View Full Log]  [Cancel Job]  [Retry Failed]                   │
└───────────────────────────────────────────────────────────────────┘
```

### 6.4 Status bar

Persistent top bar shows at-a-glance system health:
- ComfyUI connection dot (green/red) with tooltip showing last check
- Worker state (Running/Paused) with pause/resume toggle
- Queue counts as colored pills: pending (blue), running (amber), failed (red)
- Quick actions: Reload Workflows, Reload LoRAs

## 7. Visual Design Principles

1. **Dark theme** — matches current aesthetic, easier on eyes for long sessions
2. **Muted palette with accent highlights** — keep current `--bg`/`--panel`/`--accent` color tokens
3. **Status drives color** — green=success, amber=running, red=failed, blue=pending, gray=canceled
4. **Progressive disclosure** — submit form collapses, job detail expands on demand
5. **Whitespace over borders** — use spacing to separate, not lines everywhere
6. **Monospace for paths/params** — clear distinction between UI text and data values

## 8. Component Breakdown

### 8.1 StatusBar
- Polls `GET /api/health` every 3s
- Shows connection dot, worker state, queue counts
- Pause/Resume buttons call `POST /api/queue/{pause,resume}`

### 8.2 SubmitPanel
- Tab switcher (Batch / Image Gen / Upscale Video / Upscale Image)
- Each tab renders its own input component but shares: workflow selector, resolution picker, param fields, preset selector, submit button
- **ParamFields** dynamically renders fields from workflow definition (text, number, toggle, dropdown)
- **DropZone** handles drag-and-drop with thumbnail preview
- **PresetSelector** manages prompt and settings presets
- Collapsible — click header to toggle open/closed

### 8.3 QueuePanel
- Summary row with status counts (clickable to filter)
- Search input + sort dropdown
- Job list as card-style rows (not a wide table)
- Shift+click range selection for bulk actions
- Auto-polls `GET /api/jobs` every 2s

### 8.4 JobRow
- Two-line card: top line = ID + name + workflow + status badge, bottom line = progress bar + timing
- Click to expand JobDetail
- Inline action buttons (cancel, retry) on hover

### 8.5 JobDetail
- Formatted metadata (not raw JSON)
- Parameter display as key-value pairs in a grid
- Prompt list with status icons, input/output paths, timing
- Log viewer (lazy-loaded from `GET /api/jobs/{id}/log`)

### 8.6 WorkspaceManager
- Tab bar for switching workspaces
- Each workspace stores its own submit form state in a Svelte store
- localStorage persistence (same as current behavior)

## 9. Migration Strategy

### Principle: V2 is a new app, V1 stays untouched

- V1 (`static/index.html`) continues to serve at `http://localhost:8585/` — **no changes to V1 at any point**
- V2 (Svelte) is mounted at `/v2` on the same FastAPI server
- Both hit the same API endpoints and the same SQLite DB — changes in one are visible in the other
- V1 is only removed after V2 reaches full parity and has been the daily driver for a reasonable period
- There is no hybrid phase — V1 and V2 are fully independent frontends

### Phase 1: Scaffold + Status Bar + Queue View
1. Init Svelte project in `ui/`, configure Tailwind + shadcn-svelte
2. Create `api.ts` typed client matching all existing endpoints
3. Build StatusBar component
4. Build QueuePanel with card-style JobRow and status filtering
5. Mount at `/v2`, test alongside old UI
6. **V1 status: untouched, still primary UI**

### Phase 2: Submit Panel
1. Build SubmitPanel shell with tab switcher
2. Implement ParamFields (dynamic field rendering from workflow defs)
3. Implement DropZone with drag-and-drop and thumbnail preview
4. Implement PresetSelector (prompt + settings presets)
5. Wire up job submission
6. **V1 status: untouched. Can start daily-driving V2 for submit + monitor workflows**

### Phase 3: Job Detail + Polish
1. Build JobDetail expandable panel
2. Build prompt list with status tracking
3. Add log viewer
4. Workspace management (multi-tab state)
5. Keyboard shortcuts, toast notifications, confirm dialogs
6. **Milestone: full feature parity with V1**
7. **V1 status: untouched but no longer needed**

### Phase 4: Deprecation + Removal
1. Add a one-line banner to V1: "This UI is deprecated. Use /v2"
2. Continue serving V1 for one release cycle as fallback
3. Remove old `static/index.html`
4. V2 becomes the only UI, served at `/`

## 10. Risks

| Risk | Mitigation |
|---|---|
| Svelte/Tailwind adds build step complexity | Single `npm run build`, output is static files. Dev server is just `npm run dev` with proxy to FastAPI |
| Feature parity gap during migration | Old UI stays at `/` throughout. Only cut over when V2 is at full parity |
| Dynamic param rendering is complex | Current JS already solves this — port the logic, don't redesign it |
| Two UIs to maintain during transition | Keep transition period short. V2 Phase 1+2 should cover daily use |

## 11. Open Questions

1. **Svelte 5 vs Svelte 4?** Svelte 5 (runes) is stable and the future. Use it.
2. **Should V2 add new features (e.g., output gallery, job comparison)?** Not in scope for the rewrite. Add later once V2 is at parity.
3. **WebSocket for real-time updates instead of polling?** Nice-to-have, but polling works fine for a single-user app. Can add later without UI changes (just swap the store internals).
