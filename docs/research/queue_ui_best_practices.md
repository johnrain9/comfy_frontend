# Queue UI Best Practices Research (T23)

Date: 2026-02-25
Scope: Improve queue usability/visibility for `video_queue` using proven patterns, not custom one-offs.

## Sources and Decisions

### 1) Carbon Design System: Data Table
- Source: https://carbondesignsystem.com/components/data-table/usage/
- Accessed: 2026-02-25
- Extracted pattern:
  - Dense, scan-friendly tabular layouts for operational data
  - Toolbar-level filtering/search and row-level actions
  - Progressive disclosure for row details
- Applicability to `video_queue`: High. Queue is operational/tabular and requires fast triage.
- Decision: Adopt (with minor adaptation to existing queue card/table hybrid).

### 2) U.S. Web Design System (USWDS): Table
- Source: https://designsystem.digital.gov/components/table/
- Accessed: 2026-02-25
- Extracted pattern:
  - Clear headers, sortable columns, predictable reading order
  - Emphasis on accessibility and responsive table behavior
- Applicability to `video_queue`: High for accessibility and semantics.
- Decision: Adopt for semantic table structure, keyboard and screen-reader support.

### 3) W3C WAI-ARIA APG: Disclosure Pattern
- Source: https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- Accessed: 2026-02-25
- Extracted pattern:
  - Expand/collapse with correct `aria-expanded` and control relationships
  - Keyboard behavior expectations for toggles
- Applicability to `video_queue`: High for collapsible prompt/settings payload.
- Decision: Adopt directly.

### 4) web.dev: Virtualize Large Lists with react-window
- Source: https://web.dev/articles/virtualize-long-lists-react-window
- Accessed: 2026-02-25
- Extracted pattern:
  - Render-windowing for large lists to avoid UI slowdown
  - Keep DOM small under large item counts
- Applicability to `video_queue`: High for 200+ queued jobs and frequent polling.
- Decision: Adapt (use virtualization only above threshold; keep simple rendering for small queues).

### 5) Apache Airflow docs: UI Overview
- Source: https://airflow.apache.org/docs/apache-airflow/stable/ui.html
- Accessed: 2026-02-25
- Extracted pattern:
  - State-first workflows: clear status chips, failure triage, drill-in details
  - Operational dashboards prioritize "what failed" and "what is running now"
- Applicability to `video_queue`: High. Same operator workflow: monitor, triage, retry/cancel.
- Decision: Adopt status-first hierarchy and fast failed-job filtering.

### 6) Sidekiq Wiki: Error Handling
- Source: https://github.com/sidekiq/sidekiq/wiki/Error-Handling
- Accessed: 2026-02-25
- Extracted pattern:
  - Queue systems should expose failure context and retries clearly
  - Operators need quick access to failure reason, not just "failed"
- Applicability to `video_queue`: High for failed prompt diagnostics.
- Decision: Adopt richer failed-row summaries and one-click error detail view.

### 7) Material Design 3: Dialog
- Source: https://m3.material.io/components/dialogs/overview
- Accessed: 2026-02-25
- Extracted pattern:
  - Confirmation dialogs for high-impact or destructive actions
  - Clear primary/secondary action hierarchy
- Applicability to `video_queue`: High for cancel-all/clear-queue actions.
- Decision: Adopt for destructive action guardrails.

### 8) Atlassian Design System: Warning Message
- Source: https://atlassian.design/components/inline-message/warning-message/
- Accessed: 2026-02-25
- Extracted pattern:
  - Contextual warnings should be inline, specific, and actionable
  - Avoid generic alert text without next step
- Applicability to `video_queue`: Medium-high for queue errors, clear-queue failures, stale state notices.
- Decision: Adapt for inline actionable error/warning UX.

## Consolidated Patterns to Use

1. State-first queue layout:
- Default sort by actionable status (`running`, `failed`, `pending`) then recency.
- Sticky summary counters for each status.

2. Fast triage:
- First-class status filters and text search.
- Single-click "Failed only" view.

3. Progressive disclosure:
- Row stays compact by default.
- Expand row to reveal prompt/settings/debug IDs/error JSON.

4. Safe bulk actions:
- Bulk select + bulk cancel/retry.
- Confirmation modal for destructive actions (clear queue/cancel all).

5. Large queue performance:
- Virtualized rendering for large row counts.
- Poll updates that do not reset current scroll/filter/expanded state.

6. Accessibility baseline:
- Semantic table/grid where applicable.
- Disclosure keyboard support and ARIA state.
- Status indicators must not rely on color alone.

## Patterns Explicitly Rejected

- Infinite decorative animation for status transitions: rejected, adds noise in operator UI.
- Hidden action menus for critical actions only: rejected, retry/cancel should remain obvious.
- Full-page job detail navigation as default: rejected; in-row expandable details are faster for triage.

## Risks and Mitigations

- Risk: Too much data in each row causes clutter.
- Mitigation: Keep default row minimal; move payload/details into disclosure panel.

- Risk: Polling causes flicker and loses user context.
- Mitigation: Stable row keys, preserve filter/sort/expand state between refreshes.

- Risk: Large queues degrade browser performance.
- Mitigation: Apply virtualization above threshold and cap expensive JSON pretty-print to expanded rows only.
