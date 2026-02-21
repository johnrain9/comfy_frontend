# Video Queue Refactor Plan — Detailed Tasks

## Goal
Refactor the codebase incrementally to improve maintainability, reliability, and testability without changing user-visible behavior or breaking existing API/CLI usage.

## Global Constraints
- Keep existing HTTP endpoint paths and response shapes backward compatible unless explicitly versioned.
- Preserve current workflow execution behavior unless a task explicitly calls for behavioral changes.
- Ship in small, reversible PRs.
- Every task must include tests before merge.

## Definition of Done (Applies to Every Task)
- Code compiles/runs with current runtime dependencies.
- New/changed behavior is covered by automated tests.
- Existing tests pass.
- No direct writes through internal DB connection object outside DB layer.
- Changelog entry in PR description (behavioral impact + rollback notes).

---

## Task 0: Baseline Behavior Lock and Refactor Guardrails
## Objective
Create a baseline of current behavior so refactors can be validated against it.

## Deliverables
- `docs/refactor/baseline.md` documenting:
  - current endpoint contract snapshots
  - CLI command outputs for key flows
  - known intentional quirks
- Golden fixtures for representative workflow definitions and generated prompts.

## Acceptance Criteria
- [x] Baseline docs include API examples for: list workflows, submit, list jobs, get job, cancel, retry, health.
- [x] Golden prompt fixtures exist for at least two workflows and one multi-try case.
- [x] A reproducible script/command list exists for baseline comparison.

## Comprehensive Testing Requirements
- [x] Snapshot tests for `/api/workflows` payload schema (field presence/types).
- [x] Golden-file tests for prompt JSON generation parity.
- [x] CLI output snapshot tests for `list`, `status`, `submit --dry-run`.

---

## Task 1: Test Infrastructure Upgrade
## Objective
Establish a robust test harness to support safe incremental refactors.

## Deliverables
- Test directory layout:
  - `tests/unit/`
  - `tests/integration/`
  - `tests/e2e/`
  - `tests/fixtures/`
- Shared fixtures for temp DB, temp workflow defs, and fake Comfy responses.
- CI command contract (single command to run all tests).

## Acceptance Criteria
- [ ] Tests run in isolated temp directories (no mutation of production `data/queue.db`).
- [ ] Fake Comfy server fixture exists for deterministic integration tests.
- [ ] Test runtime is documented and acceptable for local iteration.

## Comprehensive Testing Requirements
- [ ] Unit tests run independently of network and external Comfy instance.
- [ ] Integration tests validate API + DB + worker interactions with fake Comfy.
- [ ] E2E tests verify full startup/submit/cancel/retry path.
- [ ] Failure-injection tests cover unreachable Comfy and malformed history payload.

---

## Task 2: Shared Job Submission Service Extraction
## Objective
Eliminate duplicated submit logic by introducing a single service used by API and CLI.

## Deliverables
- New service module (e.g. `services/job_service.py`) containing:
  - workflow lookup
  - input dir normalization/validation
  - input file discovery
  - parameter resolution
  - prompt spec generation
  - enqueue persistence
- Thin adapters in API and CLI that call the shared service.

## Acceptance Criteria
- [ ] API job submission and CLI local submission use the same shared code path.
- [ ] No duplicated validation logic remains across API and CLI for submit flow.
- [ ] Returned errors remain user-readable and include root cause context.

## Comprehensive Testing Requirements
- [ ] Unit tests for service methods:
  - unknown workflow
  - missing input dir
  - empty matching files
  - bad parameter type/range
  - valid job preparation/enqueue
- [ ] API integration tests verify unchanged response contract for successful and failed submits.
- [ ] CLI integration tests verify parity with API behavior on same inputs.
- [ ] Regression tests ensure prompt count and input dir normalization match baseline fixtures.

---

## Task 3: API/CLI Submit Parity and Contract Tests
## Objective
Guarantee API and CLI produce equivalent queued jobs for equivalent inputs.

## Deliverables
- Contract test suite asserting parity for:
  - params handling
  - resolution/flip options
  - multi-try prompt fan-out
  - seed randomization toggle behavior

## Acceptance Criteria
- [ ] Equivalent inputs produce equivalent persisted prompt payloads (excluding time/seed fields where expected).
- [ ] CLI fallback path (API unavailable) and API path are both validated.
- [ ] Exit code behavior remains stable (`0`, `1`, `2`) with explicit tests.

## Comprehensive Testing Requirements
- [ ] Differential tests comparing API-created vs CLI-created job records.
- [ ] Negative tests for malformed CLI `--param` syntax and invalid values.
- [ ] Integration tests for API-unavailable scenario and local DB fallback path.

---

## Task 4: Database Boundary Hardening
## Objective
Enforce DB access encapsulation and strengthen transaction integrity.

## Deliverables
- Remove external direct usage of `QueueDB.conn`.
- Add explicit DB methods for all write operations currently done externally.
- Audit transaction scope and commit semantics in all DB methods.

## Acceptance Criteria
- [ ] No production module outside DB layer accesses raw DB connection directly.
- [ ] Job status and prompt status updates remain consistent under concurrent reads.
- [ ] Schema/migration path (if needed) is documented and reversible.

## Comprehensive Testing Requirements
- [ ] Unit tests for each DB write method (happy and error paths).
- [ ] Concurrency tests:
  - worker writes + API reads in parallel
  - repeated cancel/retry operations under load
- [ ] Integrity tests ensuring no partial insert state after failed create transaction.
- [ ] Recovery tests for stale `running` prompts on startup.

---

## Task 5: Worker Decomposition Into Explicit State Transitions
## Objective
Refactor worker loop into smaller, testable phases with clear state transitions.

## Deliverables
- Worker methods split by responsibility:
  - prompt claim
  - prompt execute
  - result persist
  - job finalize
  - post-success file move
- Structured logging for worker events.

## Acceptance Criteria
- [ ] Worker behavior matches baseline for success, validation failure, unreachable Comfy, and timeout.
- [ ] Pause/resume/cancel semantics remain unchanged and deterministic.
- [ ] Worker shutdown remains graceful.

## Comprehensive Testing Requirements
- [ ] Unit tests for each transition function with mocked dependencies.
- [ ] Integration tests with fake Comfy statuses:
  - success
  - failed/canceled status
  - never-completes timeout
  - malformed response
- [ ] Restart tests validate interrupted prompt recovery logic.
- [ ] File-move tests validate `_processed` behavior on all-success vs partial-failure jobs.

---

## Task 6: Path and Environment Service Extraction
## Objective
Move path normalization, OS picker logic, and related utilities out of API module.

## Deliverables
- New path utility service (e.g. `services/path_utils.py`) for:
  - Windows/WSL normalization
  - path conversion wrappers
  - directory picker orchestration

## Acceptance Criteria
- [ ] `app.py` no longer contains path normalization implementation logic.
- [ ] Normalization behavior remains backward compatible for all supported input styles.
- [ ] Picker failures return stable, user-facing errors.

## Comprehensive Testing Requirements
- [ ] Unit tests for normalization edge cases:
  - Linux absolute paths
  - Windows drive paths
  - `\\wsl.localhost` variants
  - quoted/newline-tainted values
- [ ] Integration tests for API normalize endpoint with valid/invalid directories.
- [ ] Platform-conditional tests for picker availability/fallback behavior.

---

## Task 7: API Modularization (Routers + Services)
## Objective
Reduce `app.py` complexity by splitting API into domain routers and services.

## Deliverables
- Router modules:
  - jobs
  - workflows
  - queue/system
  - input-dir utilities
- Thin app bootstrap for startup/shutdown and router registration.

## Acceptance Criteria
- [ ] Endpoint paths and response schemas remain unchanged.
- [ ] Startup/shutdown lifecycle still initializes DB, workflows, and worker correctly.
- [ ] Route modules are cohesive and dependency wiring is explicit.

## Comprehensive Testing Requirements
- [ ] Route-level contract tests for all existing endpoints.
- [ ] Startup/shutdown integration tests validate worker starts/stops and DB closes.
- [ ] Regression tests ensure static UI serving still works.

---

## Task 8: Workflow Metadata/UI Hint Contract
## Objective
Replace frontend name-heuristics with backend-provided UI metadata.

## Deliverables
- Workflow parameter metadata extensions, e.g.:
  - widget type
  - multiline hint
  - select options source
  - placeholder/help text
- API serialization of UI hints.

## Acceptance Criteria
- [ ] Existing workflows render correctly without name-regex assumptions.
- [ ] WAN prompt default behavior is represented by metadata, not duplicated constants.
- [ ] Unsupported or missing hints degrade gracefully to sane defaults.

## Comprehensive Testing Requirements
- [ ] Unit tests for metadata serialization defaults and overrides.
- [ ] Frontend integration tests for widget rendering by metadata.
- [ ] Regression tests ensure old workflows without new hint fields still render correctly.

---

## Task 9: Frontend Refactor (Module Split + Error Resilience)
## Objective
Split monolithic inline JS into maintainable modules and harden UI error handling.

## Deliverables
- Frontend files:
  - `static/app.js`
  - `static/api.js`
  - `static/render.js`
  - `static/state.js`
- `index.html` reduced to structure + script imports.
- Improved error surfaces for polling, submit, detail loading.

## Acceptance Criteria
- [ ] UI behavior matches baseline (submit, refresh, cancel, retry, detail expansion).
- [ ] Polling failures do not break subsequent interactions.
- [ ] No loss of mobile/desktop compatibility.

## Comprehensive Testing Requirements
- [ ] Browser-level smoke tests for primary flows.
- [ ] Failure-path tests: API 500, invalid JSON, network interruption during refresh.
- [ ] Performance checks for large queue rendering (e.g. 200+ jobs) without UI lockups.

---

## Task 10: End-to-End Reliability and Failure Injection Suite
## Objective
Add comprehensive system-level tests covering realistic failures and recovery.

## Deliverables
- Expanded E2E suite covering:
  - server restart with in-flight work
  - Comfy outage and return
  - cancel/retry loops
  - multiple jobs with priority ordering

## Acceptance Criteria
- [ ] E2E suite verifies submit -> run/fail -> retry -> succeed lifecycle.
- [ ] Restart scenario correctly marks interrupted prompts and recovers queue state.
- [ ] Priority and FIFO ordering behavior is validated.

## Comprehensive Testing Requirements
- [ ] Failure-injection tests with deterministic fake Comfy behavior controls.
- [ ] Long-poll timeout tests for prompt completion tracking.
- [ ] Persistence tests verifying DB correctness after abrupt process termination.

---

## Task 11: Documentation and Operational Playbooks
## Objective
Document refactor outcomes and provide runbook coverage for operations/debugging.

## Deliverables
- Updated docs:
  - architecture overview
  - module map
  - testing guide
  - troubleshooting runbook
  - rollback instructions per phase

## Acceptance Criteria
- [ ] Docs reflect actual post-refactor module boundaries and flows.
- [ ] Troubleshooting covers top operational failure modes with concrete commands.
- [ ] Test execution instructions are complete and reproducible.

## Comprehensive Testing Requirements
- [ ] Doc verification checklist executed (all commands/paths valid).
- [ ] New contributor dry-run: can run tests and start service using docs only.

---

## Task 12: Final Regression Gate and Release Readiness
## Objective
Perform final compatibility and quality gate before considering refactor complete.

## Deliverables
- Final regression report with:
  - behavior parity summary
  - known deviations (if any)
  - risk assessment
  - sign-off checklist

## Acceptance Criteria
- [ ] All unit, integration, and E2E tests pass.
- [ ] API contract parity with baseline snapshots is confirmed.
- [ ] CLI behavior parity with baseline is confirmed.
- [ ] No open high-severity defects.

## Comprehensive Testing Requirements
- [ ] Full test matrix run:
  - unit
  - integration
  - E2E
  - failure injection
  - restart/recovery
- [ ] Manual sanity checks:
  - UI submit/cancel/retry
  - CLI submit/status/cancel/retry
  - worker pause/resume
- [ ] Regression diff report generated against Task 0 baseline.

---

## Task 13: Persist UI Options Across Refresh and Reopen
## Objective
Ensure video queue form options do not reset to defaults on page refresh or browser reopen, so users do not need to re-enter their common settings.

## Deliverables
- Frontend persistence layer for user selections (e.g. localStorage) covering:
  - selected workflow
  - selected resolution preset
  - flip orientation toggle
  - input directory
  - parameter values for the selected workflow
- Workflow-aware state model:
  - global UI settings persisted once
  - per-workflow parameter values stored and restored independently
- Safe state loading:
  - missing/removed parameters ignored
  - type coercion/validation for stored values
  - corrupted storage fallback to defaults
- Optional "reset saved options" UI control.

## Acceptance Criteria
- [x] Reloading the page restores previously selected workflow and all saved options instead of resetting to defaults.
- [x] Closing and reopening the browser tab restores the same saved options for the same origin.
- [x] Switching between workflows preserves each workflow's own parameter values and restores them when switching back.
- [x] Reloading workflow definitions does not crash restore logic when parameters are added/removed/renamed.
- [x] Invalid or corrupted persisted data is safely ignored and defaults are used.
- [x] Submission does not clear saved options unless user explicitly chooses reset.
- [x] "Reset saved options" clears persisted state and returns form to default values.

## Comprehensive Testing Requirements
- [x] Frontend unit tests for persistence helpers:
  - save/load/remove operations
  - schema/version handling
  - typed value restore for bool/int/float/text
- [x] Frontend integration tests:
  - set values -> refresh -> values restored
  - workflow A values do not overwrite workflow B values
  - reload workflows endpoint with changed parameter schema still restores safely
- [x] Negative-path tests:
  - malformed JSON in storage
  - missing storage API availability/failure path
  - stale values outside min/max are clamped or rejected per defined behavior
- [x] Browser-level E2E test:
  - configure form -> hard refresh -> submit -> API payload matches restored settings
- [ ] Manual verification checklist for desktop and mobile viewport behavior after refresh.

---

## Task 14: Add Single I2V Tab With One-Image Input
## Objective
Add a new UI tab for single-image I2V submission while retaining the existing batch tab. The single tab should accept one image input and otherwise use the same option set and behavior as batch submission.

## Deliverables
- UI tab structure with:
  - `Batch` tab (existing behavior)
  - `Single I2V` tab (new behavior)
- Single I2V form additions:
  - image input field (file picker and/or path input per current architecture constraints)
  - same workflow/parameter controls as batch where applicable
  - same resolution/orientation and other shared options
- Backend/API support as needed for single-image submit:
  - either reuse existing job endpoint with single-input adaptation
  - or add a dedicated single-submit endpoint while preserving existing contracts
- Clear UX feedback for selected image, validation errors, and submission success.

## Acceptance Criteria
- [x] UI shows two tabs: `Batch` and `Single I2V`.
- [x] `Batch` tab behavior is unchanged from current baseline.
- [x] `Single I2V` tab allows selecting exactly one image and prevents empty submit.
- [x] All shared options (prompts, seeds, tries, output prefix, resolution/orientation, etc.) match batch behavior and validation rules.
- [x] Submitting from `Single I2V` creates a job with exactly one input image (subject to `tries` fan-out).
- [x] Queue table and job detail views display single-tab jobs the same as batch jobs.
- [x] Tab switching preserves entered values per tab (and integrates with persisted options task if implemented).
- [x] Mobile and desktop layouts both support tab interaction and form submission without regressions.

## Comprehensive Testing Requirements
- [x] Frontend unit tests:
  - tab state switching/render logic
  - single-image field validation (missing file, invalid type)
  - shared-option value mapping to payload
- [x] Frontend integration tests:
  - submit from batch tab still works unchanged
  - submit from single tab creates expected request payload
  - tab-switch state retention behavior
- [x] Backend integration tests:
  - single submit with valid image succeeds and enqueues correct prompt count
  - invalid/missing image input returns clear validation error
  - parity tests for shared option processing between batch and single modes
- [ ] E2E tests:
  - open UI -> submit one single-image job -> verify queue entry and prompt details
  - switch between tabs -> refresh page -> verify expected restored state behavior
- [ ] Regression tests:
  - no changes to existing batch endpoint behavior and response shape
  - no regressions in cancel/retry/status flows for both single and batch jobs
- [ ] Manual QA checklist:
  - desktop and mobile tab usability
  - keyboard navigation/accessibility for tabs and image input
  - clear error/success messaging for single submit flow

---

## Task 15: Investigate and Fix `Cancel` Reliability
## Objective
Investigate why cancel appears not to work in some flows, identify root causes, and implement a reliable end-to-end cancel behavior for queued and running work.

## Deliverables
- Investigation report (`docs/review/cancel_reliability.md`) including:
  - reproducible scenarios where cancel fails or appears ineffective
  - root-cause analysis across UI/API/DB/worker layers
  - proposed remediation options and chosen approach
- Implementation updates to ensure cancel behavior is explicit and consistent:
  - cancel pending prompts immediately
  - define and implement running prompt cancel semantics (best-effort cancel vs cancel-after-current)
  - user-visible status updates and messaging
- Updated API/worker docs for cancel semantics.

## Acceptance Criteria
- [x] Repro steps for the original issue are documented and no longer reproduce after fixes.
- [x] Cancel from UI and API consistently transitions eligible pending prompts to `canceled`.
- [x] Running-prompt cancel semantics are explicitly documented and reflected in behavior.
- [x] Job-level status is updated correctly after cancel actions.
- [x] UI feedback clearly indicates whether cancel is immediate, queued, or partial.

## Comprehensive Testing Requirements
- [x] Unit tests for DB cancel/update status edge cases.
- [ ] Worker integration tests for cancel timing windows:
  - before prompt pickup
  - after pickup before queue submission
  - while polling in-progress prompt
  - after prompt completion
- [x] API integration tests for cancel endpoint idempotency and response payload correctness.
- [ ] E2E tests:
  - submit multi-prompt job -> cancel mid-run -> verify final prompt/job statuses
  - repeated cancel clicks do not create inconsistent state
- [ ] Regression tests for retry/status behavior after cancel.

---

## Task 16: Show Matchable Task IDs and Collapsible Prompt Details in UI
## Objective
Improve observability by showing IDs needed to correlate queue tasks with ComfyUI, and expose the prompt payload used for each task in a collapsible view.

## Deliverables
- Queue and detail UI updates to display:
  - local job ID
  - local prompt row ID(s)
  - Comfy prompt ID (`prompt_id`) when available
- Collapsible prompt viewer per prompt/job:
  - human-readable formatted JSON prompt
  - collapsed by default
  - supports large prompts without freezing UI
- API support updates (if needed) so required IDs and prompt payloads are available in detail responses.

## Acceptance Criteria
- [x] Each submitted task can be matched from UI to ComfyUI using visible IDs.
- [x] For completed/running prompts with Comfy assignment, Comfy `prompt_id` is visible.
- [x] Prompt payload is viewable in a collapsible section without cluttering default table view.
- [x] Collapsible prompt section works for both batch and single-I2V jobs.
- [x] Existing queue actions (cancel/retry/expand) continue to work unchanged.

## Comprehensive Testing Requirements
- [x] API contract tests for presence/type of ID fields in job detail responses.
- [x] Frontend unit tests for ID rendering and collapsible state behavior.
- [ ] Frontend integration tests:
  - expand/collapse prompt payload
  - large prompt JSON rendering performance and truncation/scroll behavior
  - Comfy ID shown when available and hidden/placeholder when unavailable
- [ ] E2E test:
  - submit job -> wait until queued to Comfy -> verify displayed IDs match backend values
- [ ] Regression tests ensuring no breakage to existing queue refresh and action handlers.

---

## Task 17: Default Batch Input Directory to `/home/cobra/ComfyUI/input`
## Objective
Set the batch input directory field to open/default to `/home/cobra/ComfyUI/input` so users start in the common input path without manual navigation each session.

## Deliverables
- Default initialization behavior for batch input dir:
  - first-load default set to `/home/cobra/ComfyUI/input`
  - compatibility with persisted state (if saved value exists, saved value wins)
- Directory picker integration so browse starts in the default path when no prior selection exists.
- Clear fallback behavior if default path is unavailable.

## Acceptance Criteria
- [x] On first load with no persisted value, batch input dir shows `/home/cobra/ComfyUI/input`.
- [x] Browse dialog starts from `/home/cobra/ComfyUI/input` when input field is empty/unset.
- [x] If persisted input dir exists, it overrides the default and is used on load.
- [x] If `/home/cobra/ComfyUI/input` does not exist, UI shows a clear validation/fallback path instead of failing silently.
- [x] Single-I2V tab behavior remains correct and is not unintentionally overridden by batch default logic.

## Comprehensive Testing Requirements
- [x] Frontend unit tests for defaulting precedence:
  - persisted value > explicit current value > static default
- [x] Integration tests for picker start-dir payload on empty vs populated field.
- [x] API integration tests for normalization/touch flows using the default path.
- [x] E2E tests:
  - clean browser profile -> load page -> default path present
  - set custom path -> refresh -> custom path persists (with Task 13 behavior)
- [x] Negative-path tests when default path is missing or inaccessible.

---

## Suggested Execution Order
1. Task 0
2. Task 1
3. Task 2
4. Task 3
5. Task 4
6. Task 5
7. Task 6
8. Task 7
9. Task 8
10. Task 9
11. Task 10
12. Task 11
13. Task 12
14. Task 13
15. Task 14
16. Task 15
17. Task 16
18. Task 17

## Parallelizable Work Streams
- Stream A: Task 2 + Task 3
- Stream B: Task 4 + Task 5 + Task 15
- Stream C: Task 6 + Task 7
- Stream D: Task 8 + Task 9 + Task 13 + Task 14 + Task 16 + Task 17
- Stream E: Task 10 (after Streams A/B mature)

## Exit Criteria for Refactor Program
- All task acceptance criteria complete.
- Full regression gate passes.
- Operational docs and rollback playbooks are complete.
