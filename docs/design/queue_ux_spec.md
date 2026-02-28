# Queue UX Spec (T23)

Date: 2026-02-25
Scope: `video_queue` queue page usability/visibility improvements based on `docs/research/queue_ui_best_practices.md`.

## Goals
- Reduce time to find failed/running jobs.
- Make prompt/settings provenance visible without clutter.
- Keep queue usable at 200+ jobs.
- Preserve existing backend behavior unless required for visibility features.

## Information Hierarchy

1. Global status bar (top, sticky)
- Counters: `running`, `pending`, `failed`, `completed`, `canceled`.
- Quick actions: `Failed only`, `Running only`, `Clear filters`.

2. Queue controls row
- Search input (job name, prompt text, file path, IDs).
- Status filter chips (multi-select).
- Sort dropdown:
  - Default: action priority (`running`, `failed`, `pending`, `completed`, `canceled`) then newest first.
  - Optional: newest, oldest, name.

3. Queue list/table
- Compact default row fields:
  - status
  - prefixed job name
  - input source summary
  - created/updated time
  - short error summary (failed only)
  - actions (`expand`, `cancel`, `retry`)

4. Expandable row details (disclosure)
- Prompt(s) used for each stage.
- Settings snapshot used at submit time.
- IDs (`job_id`, `prompt_row_id`, `comfy_prompt_id`).
- Full error payload and outputs.

## Progressive Disclosure Behavior
- Collapsed by default for all rows.
- Expand state survives polling refresh.
- For large JSON payloads:
  - pretty-print only when expanded
  - fixed-height scroll container
  - copy button for JSON block

## Filtering/Search
- Search: client-side for loaded rows; server-side when row count exceeds threshold.
- Search tokens match:
  - job name
  - input path/file name
  - prompt snippet
  - local IDs and Comfy ID
  - error text
- Presets:
  - `Needs attention` = failed + running
  - `Failed only`

## Bulk and Destructive Actions
- Bulk-select rows via checkbox column.
- Bulk actions:
  - `Cancel selected`
  - `Retry selected failed`
- Destructive safeguards:
  - `Clear queue` always requires confirmation modal
  - modal shows impact count and requires explicit confirmation click
  - action remains disabled while request in-flight

## Live Updates and Stale-State Handling
- Polling interval remains current default unless changed by perf testing.
- Preserve across refresh:
  - selected filters
  - search text
  - sort choice
  - expanded rows
  - current scroll position (best effort)
- Show inline stale warning if API unreachable; keep last known data visible.

## Empty/Loading/Error States
- Loading: skeleton rows and status bar placeholders.
- Empty queue: clear empty-state copy plus shortcut to submit.
- Empty filtered result: "No jobs match current filters" + clear-filters action.
- API error: inline warning with retry button and timestamp of last successful refresh.

## Accessibility Requirements
- Disclosure buttons implement ARIA disclosure semantics.
- Full keyboard navigation:
  - tab sequence includes filters, rows, row actions, disclosure content
  - enter/space toggles disclosure
- Status encoded by text label + color (not color-only).
- Minimum contrast and visible focus rings on all actionable controls.

## Mobile/Desktop Behavior
- Desktop:
  - table-like dense layout with sticky status/control rows
- Mobile:
  - card rows with same information hierarchy
  - filters collapse into top sheet/popover
  - row actions remain visible without hover

## Wireframes (Text)

### A) Default Queue View
- Header: status counters and quick filters.
- Controls: search, filter chips, sort.
- Rows: one-line summary + actions.

### B) Failed Triage View
- Active chip: `failed`.
- Rows emphasize short error reason and retry/cancel.
- Optional bulk retry bar appears when rows selected.

### C) Expanded Detail View
- Top section: IDs and timestamps.
- Mid section: prompt/settings JSON blocks (collapsible within detail).
- Bottom: output files + full error payload.

### D) Bulk Action Confirmation
- Modal title: `Clear Queue` or `Cancel N Jobs`.
- Body: explicit counts and irreversible note.
- Actions: primary confirm + secondary cancel.

## Implementation Backlog (Prioritized)

### P0
1. Queue state bar + status chips + default actionable sort
- Scope: add status counters, filter chips, default sort behavior.
- Dependencies: existing `/api/jobs` status fields.
- Tests: frontend unit (sort/filter), integration (state bar updates), e2e (failed triage flow).
- Rollback: hide new controls and revert previous sort.

2. Collapsible row detail panel with prompt/settings/IDs
- Scope: move verbose details into disclosure panel.
- Dependencies: ensure detail API returns prompt/settings snapshot and IDs.
- Tests: ARIA behavior, expand/collapse persistence through polling, JSON render correctness.
- Rollback: fallback to current expanded static details.

3. Destructive-action confirmation hardening
- Scope: standardize modal for clear-queue/cancel-all; disable duplicate submits.
- Dependencies: existing queue clear/cancel endpoints.
- Tests: modal gating, single-flight request behavior, error path messaging.
- Rollback: keep endpoint behavior, remove modal layer if needed.

### P1
1. Bulk select + cancel/retry actions
- Scope: checkbox selection model and bulk actions.
- Dependencies: batch API endpoints or iterative action wrapper.
- Tests: selection model, mixed-status behavior, partial failure handling.
- Rollback: hide bulk action bar.

2. Inline stale-state/error UX
- Scope: retain last-known queue state and show inline connectivity warnings.
- Dependencies: polling/error hooks.
- Tests: simulated API outage, recovery flow.
- Rollback: revert to current hard error display.

3. Mobile queue layout adaptation
- Scope: card-based mobile row rendering with preserved action visibility.
- Dependencies: none beyond frontend layout.
- Tests: responsive snapshots, touch-target checks.
- Rollback: desktop-only fallback under breakpoint.

### P2
1. Virtualized list above threshold
- Scope: virtualization for large queue sizes.
- Dependencies: list component refactor.
- Tests: performance benchmark, keyboard nav in virtualized view.
- Rollback: disable virtualization flag.

2. Saved filter presets
- Scope: persisted quick views like `Needs attention`.
- Dependencies: local storage state model.
- Tests: persistence and reset behavior.
- Rollback: disable preset persistence.

3. Advanced search token parsing
- Scope: query tokens like `status:failed`, `name:batch`.
- Dependencies: search parser utility.
- Tests: parser unit tests + integration with visible filtering.
- Rollback: fallback to simple text search.

## API/Data Contract Notes
- Required per row:
  - status, job_id, prompt_row_id(s), comfy_prompt_id (nullable), created_at, updated_at
  - short_error_summary (nullable)
- Required for expanded detail:
  - prompt JSON used at submission time
  - settings snapshot used at submission time
  - outputs, raw error payload
- Required for status bar:
  - aggregated counts per status (or compute client-side if pagination small)

## Rollout Plan
1. Ship P0 behind a UI feature flag.
2. Verify validation checklist in `docs/research/queue_ui_validation_checklist.md`.
3. Enable for all users after no regressions in cancel/retry/clear flows.
4. Stage P1 and P2 in smaller follow-up PRs.
