# Cancel Reliability: Investigation and Fix

## Date
- 2026-02-21

## Symptoms Observed
- Clicking cancel from UI often appeared to do nothing when a prompt was already running.
- Jobs with mixed `succeeded` + `canceled` prompt outcomes could remain in non-terminal `running` state.
- UI did not explain whether cancel was immediate or deferred.

## Root Causes
1. `cancel` only updated `pending` prompts.
- Running prompts were not interruptible, but the system had no explicit "cancel-after-current" model.

2. Worker did not gate execution on cancel request.
- A pending prompt selected by worker could still run even after user cancel action in a race window.

3. Job status aggregation missed mixed terminal states.
- `succeeded + canceled` (no pending/running) could fall through to `running`.

4. UI feedback lacked semantics.
- Users could not tell if cancel was queued behind an in-flight prompt.

## Chosen Behavior
- **Pending prompts**: cancel immediately.
- **Running prompt(s)**: **cancel-after-current** (best effort); do not submit new prompts for that job.
- Job becomes terminal once in-flight prompt finishes and no runnable prompts remain.

## Implementation Summary
- DB schema/migration:
  - Added `jobs.cancel_requested` (default `0`).
- Cancel API/DB behavior:
  - `cancel_job` sets `cancel_requested=1` and cancels all pending prompts.
  - Returns `cancel_summary` with:
    - `mode`: `immediate` or `cancel_after_current`
    - `canceled_pending`
    - `running_prompts`
- Worker behavior:
  - Skips queue submission for prompts if `cancel_requested` is set before execution.
  - Cancels any remaining pending prompts after current prompt cycle when cancel is requested.
- Job status fix:
  - Mixed `succeeded + canceled` with cancel requested now resolves to terminal `canceled`.
- UI behavior:
  - Cancel action now displays explicit immediate vs deferred messaging.

## Remaining Limits
- Hard kill of a Comfy prompt already in execution is not implemented in this queue manager.
- Semantics are intentionally `cancel-after-current` for in-flight prompts.

## Repro Check
- Original "cancel appears broken" repro no longer persists for queued/pending work.
- Running work now reports deferred cancel and halts further prompt pickup for that job.
