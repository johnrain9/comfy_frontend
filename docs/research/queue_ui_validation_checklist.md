# Queue UI Validation Checklist (T23)

Date: 2026-02-25
Purpose: Validate queue UX improvements with measurable outcomes before full rollout.

## Baseline vs After Metrics

1. Time to locate first failed job
- Method: start from default queue view with mixed statuses.
- Measure: seconds until user opens failed job details.
- Target: at least 30% faster than baseline.

2. Time to cancel a specific running job
- Method: identify running job by name and cancel it.
- Measure: seconds and click count.
- Target: no more than 3 clicks and 25% faster than baseline.

3. Settings visibility discoverability
- Method: user must find exact prompt/settings used for a completed job.
- Measure: completion rate and seconds.
- Target: 100% completion in under 20 seconds.

4. Failed-job triage throughput
- Method: process five failed jobs (inspect reason and trigger retry/cancel choice).
- Measure: total time and mis-click/error rate.
- Target: at least 25% faster, with zero destructive-action misfires.

## Functional UX Checks

- [ ] Status counters match actual row counts.
- [ ] Status chips filter rows correctly and can be cleared quickly.
- [ ] Search matches name/path/prompt/IDs/error text.
- [ ] Expanded detail shows prompt JSON and settings snapshot for each job.
- [ ] Expanded state survives polling refresh.
- [ ] Cancel/retry actions remain operational from both row and detail view.
- [ ] Clear queue requires explicit confirmation and prevents double-submit.

## Accessibility Checks

- [ ] All interactive controls reachable via keyboard only.
- [ ] Disclosure toggles expose correct `aria-expanded` state.
- [ ] Focus order is logical after filtering, expanding, and modal open/close.
- [ ] Status is understandable without color alone.
- [ ] Visible focus ring and contrast meet baseline accessibility expectations.

## Large Queue Performance Checks

- [ ] 200+ jobs: scrolling remains smooth and interaction latency acceptable.
- [ ] Polling updates do not reset search/filter/sort/expanded state.
- [ ] Rendering prompt/settings JSON only when expanded avoids frame drops.

## Required Automated Coverage Mapping

1. Frontend unit tests
- filter and sort reducers
- disclosure state logic
- status counter calculations

2. Frontend integration tests
- filter + search combined behavior
- expand/collapse and JSON rendering
- destructive modal flows (`clear queue`, `cancel all`)

3. API contract tests
- presence and type of IDs per row
- presence of prompt/settings snapshot in job detail payload
- status aggregation fields or client-computable equivalents

4. End-to-end tests
- submit jobs -> observe status transitions -> triage failed -> retry/cancel
- clear queue confirmation and completion path
- outage simulation and stale-state recovery

## Sign-off Criteria
- [ ] All P0 tests pass.
- [ ] Baseline-vs-after metric targets met.
- [ ] No regression in existing queue cancel/retry/clear behaviors.
