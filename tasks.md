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

## Simple Multi-AI Workflow (Planner + Manual Workers)
- Use `Txx` task IDs as the dispatch contract across tools and repos.
- Planner dispatch format: `do task Txx` (repo can be omitted because each task includes `Repo`).
- Worker kickoff: read `Task Txx`, confirm `Repo`, then execute against Global Constraints + Definition of Done.
- Worker closeout format: `Txx | done|blocked | tests: <cmd/result> | ref: <branch/commit/notes>`.
- Worker completion rule: update the task's `## Status` in this file before closeout.
- Worker completion rule: update relevant checkboxes in Acceptance Criteria and Testing Requirements.
- Blocked tasks must include one explicit unblocker request.
- No custom per-task prompts are required; the task body is the prompt.

## Task Index (Dispatch IDs)
- `T00` Baseline Behavior Lock and Refactor Guardrails
- `T01` Test Infrastructure Upgrade
- `T02` Shared Job Submission Service Extraction
- `T03` API/CLI Submit Parity and Contract Tests
- `T04` Database Boundary Hardening
- `T05` Worker Decomposition Into Explicit State Transitions
- `T06` Path and Environment Service Extraction
- `T07` API Modularization (Routers + Services)
- `T08` Workflow Metadata/UI Hint Contract
- `T09` Frontend Refactor (Module Split + Error Resilience)
- `T10` End-to-End Reliability and Failure Injection Suite
- `T11` Documentation and Operational Playbooks
- `T12` Final Regression Gate and Release Readiness
- `T13` Persist UI Options Across Refresh and Reopen
- `T14` Add Single I2V Tab With One-Image Input
- `T15` Investigate and Fix `Cancel` Reliability
- `T16` Show Matchable Task IDs and Collapsible Prompt Details in UI
- `T17` Default Batch Input Directory to `/home/cobra/ComfyUI/input`
- `T18` Add New 2-Pass Split-Prompt Workflow (legacy Task A)
- `T19` Add New 3-Pass Workflow (Extended Length, legacy Task B)
- `T20` UI Support for New Stage-Prompt Workflows (legacy Task C)
- `T21` Dynamic Arbitrary Stage Count ("Add Stage", legacy Task D)
- `T22` Source Image Upscale Mode for I2V Prep (legacy Task E)
- `T23` Queue UX/Visibility Redesign (research-backed)
- `T24` Queue UX P0 Implementation (status controls, actionable sort, safe actions)
- `T25` Queue-Owned Input Staging for Durable Execution Paths
- `T26` Upload Filename Policy: Preserve Original Name + Suffix on Collision
- `T27` Input Duplication Policy and Configurable Staging Scope
- `T28` Staging Retention and Cleanup Policy
- `T29` Full-Page UI Hierarchy and Visual Refresh
- `T30` Video I2V Multi-Image Drag/Drop with Thumbnails
- `T31` Multi-Tab Workspaces for Queue Control Panel
- `T32` Add Image Generation Mode (Text-to-Image) to Queue
- `T33` Workspace Isolation and Visual Separation Upgrade
- `T34` UI V2 Foundation Scaffold (`/v2` Svelte App)
- `T35` UI V2 Phase 1: Status Bar + Queue Panel
- `T36` UI V2 Phase 2: Submit Panel + Dynamic Params + Presets
- `T37` UI V2 Phase 3: Job Detail + Log Viewer + Workspace Manager
- `T38` UI V2 Compatibility, Performance, and Accessibility Gate
- `T39` UI V2 Cutover Plan (`/v2` -> `/`, legacy fallback)
- `T40` Auto-Prompt Two-Stage LM Studio Generator Skeleton
- `T41` LM Studio Connectivity and Capability Gate
- `T42` Two-Stage Auto-Prompt API Endpoint (`POST /api/auto-prompt`)
- `T43` Per-File Prompt Overrides in Prompt Builder and Job Schema
- `T44` Prompt Mode Contract (`manual`, `per-image manual`, `per-image auto`)
- `T45` UI Two-Stage Auto-Prompt Panel
- `T46` Auto-Prompt Test Matrix (unit + integration + regression)
- `T47` Auto-Prompt Docs and Operator Runbook
- `T48` Auto-Prompt CLI Dev Harness for Prompt Iteration
- `T49` End-to-End Batch Acceptance and Quality Sign-off

## Task Template (Self-Contained)
```md
## Task Txx: <Title>
## Repo
`<repo_name>` (`/abs/path/to/repo`)

## Status
`todo` (update to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
<why this task exists>

## Deliverables
- <artifact/output>

## Acceptance Criteria
- [ ] <verifiable behavior/result>

## Comprehensive Testing Requirements
- [ ] <required unit/integration/e2e coverage>
```

---

## Task T00: Baseline Behavior Lock and Refactor Guardrails
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T01: Test Infrastructure Upgrade
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`in_progress` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T02: Shared Job Submission Service Extraction
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T03: API/CLI Submit Parity and Contract Tests
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T04: Database Boundary Hardening
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T05: Worker Decomposition Into Explicit State Transitions
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T06: Path and Environment Service Extraction
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T07: API Modularization (Routers + Services)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

---

## Workflow Prompt-Stage Expansion Plan (New Feature)

## Task T18 (Legacy A): Add New 2-Pass Split-Prompt Workflow
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Create a new copy of current WAN 2-pass workflow where stage 1 and stage 2 use different prompts.

## Deliverables
- New workflow definition in `workflow_defs_v2/` (do not replace current one yet).
- New template JSON with distinct stage prompt nodes/parameters:
  - `positive_prompt_stage1`
  - `positive_prompt_stage2`
- Keep existing base 4-step LoRA chain and extra LoRA chain behavior unchanged.

## Acceptance Criteria
- [x] Both stage prompts are independently editable and persist into queued prompt JSON.
- [x] Stage 1 uses stage-1 prompt only; stage 2 uses stage-2 prompt only.
- [x] Legacy 2-pass workflow remains available during transition.

## Testing Requirements
- [x] Prompt-build unit test verifying stage-specific node text values.
- [x] API submit integration test verifying persisted `prompt_json` contains both stage prompt values correctly.

---

## Task T19 (Legacy B): Add New 3-Pass Workflow (Extended Length)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Introduce a 3-stage WAN workflow that extends sequence length and supports 3 stage prompts.

## Deliverables
- New 3-pass template JSON (stage chain 1 -> 2 -> 3).
- New workflow YAML with parameters:
  - `positive_prompt_stage1`
  - `positive_prompt_stage2`
  - `positive_prompt_stage3`
- Preserve existing seed/resolution/output-prefix/extra-LoRA semantics.

## Acceptance Criteria
- [x] 3-stage graph validates and queues in Comfy.
- [x] All three prompt values map to correct stage nodes.
- [x] Output generation path remains compatible with existing queue worker.

## Testing Requirements
- [x] Prompt-build test verifying stage1/2/3 prompt mapping.
- [x] Regression test verifying seed bindings cover all sampler stages.

---

## Task T20 (Legacy C): UI Support for New Stage-Prompt Workflows
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Expose stage prompt inputs clearly in UI for 2-pass-split and 3-pass workflows.

## Deliverables
- Stage prompt grouping/labels in submit form.
- Maintain compatibility with existing prompt preset/save behavior.
- Ensure queue detail view shows saved params for stage prompts.

## Acceptance Criteria
- [x] Users can submit with different stage prompts without manual JSON edits.
- [x] Saved prompt presets do not break with new stage fields.
- [x] Existing workflows continue to render correctly.

## Testing Requirements
- [x] Frontend test verifying stage fields render for matching workflows.
- [x] Frontend submit payload test for stage prompt fields.

---

## Task T21 (Legacy D, Phase 2): Dynamic Arbitrary Stage Count ("Add Stage")
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Design and implement an advanced dynamic stage builder so users can add N stages from UI at submit time.

## Deliverables
- Design doc for dynamic graph generation strategy (node cloning/rewiring rules).
- Backend builder capable of generating prompt graph for arbitrary stage count.
- UI controls:
  - Add/remove stage
  - Stage prompt inputs per stage
- Maintain extra LoRA configuration at end of chain.

## Acceptance Criteria
- [ ] User can add stages dynamically without editing workflow files.
- [ ] Generated graph validates in Comfy for supported stage counts.
- [ ] Stage continuity (seed, model chain, prompt mapping) is deterministic.

## Testing Requirements
- [ ] Property-style tests for generated graph validity across multiple stage counts.
- [ ] Integration tests for submit/build/queue path with dynamic stages.
- [ ] Performance test to ensure prompt build remains responsive for higher stage counts.

---

## Task T22 (Legacy E): Source Image Upscale Mode for I2V Prep
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Add a dedicated image-upscale workflow/mode for preparing source images before WAN I2V.

## Deliverables
- New image-upscale workflow definition in `workflow_defs_v2/` for image inputs.
- New UI mode/tab (separate from video upscale/interpolate) that targets this workflow.
- Default upscale factor set to `1.5x` with configurable output prefix.

## Acceptance Criteria
- [x] Users can select `Upscale Images` mode and submit a directory of images.
- [x] Each image is queued through the new image-upscale workflow.
- [x] Existing `Batch`, `Single I2V`, and `Upscale` (video) modes continue working.

## Testing Requirements
- [x] Workflow definition loads successfully via `load_all`.
- [x] Frontend state tests pass with new mode present.
- [x] Static UI contract tests still pass.

## Comprehensive Testing Requirements
- [x] Route-level contract tests for all existing endpoints.
- [x] Startup/shutdown integration tests validate worker starts/stops and DB closes.
- [x] Regression tests ensure static UI serving still works.

---

## Task T08: Workflow Metadata/UI Hint Contract
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T09: Frontend Refactor (Module Split + Error Resilience)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T10: End-to-End Reliability and Failure Injection Suite
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T11: Documentation and Operational Playbooks
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T12: Final Regression Gate and Release Readiness
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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
- [ ] Regression diff report generated against Task T00 baseline.

---

## Task T13: Persist UI Options Across Refresh and Reopen
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T14: Add Single I2V Tab With One-Image Input
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T15: Investigate and Fix `Cancel` Reliability
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T16: Show Matchable Task IDs and Collapsible Prompt Details in UI
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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

## Task T17: Default Batch Input Directory to `/home/cobra/ComfyUI/input`
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

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
  - set custom path -> refresh -> custom path persists (with Task T13 behavior)
- [x] Negative-path tests when default path is missing or inaccessible.

---

## Task T23: Queue UX/Visibility Redesign (Research-Backed)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Improve queue usability and operational visibility using established UI patterns from modern queue/task-management systems instead of ad hoc redesign decisions.

## Deliverables
- Research doc: `docs/research/queue_ui_best_practices.md` with at least 6 high-quality references (design systems, production queue UIs, workflow dashboards, accessibility guidance), each including:
  - source link
  - access date
  - extracted pattern
  - applicability note for `video_queue`
  - explicit "adopt / adapt / reject" decision
- Queue UX spec: `docs/design/queue_ux_spec.md` covering:
  - information hierarchy for `pending/running/completed/failed/canceled`
  - progressive disclosure for prompt/settings payloads
  - row density strategy for large queues
  - filtering and quick-search behavior
  - sorting defaults and secondary sort keys
  - bulk actions and destructive-action safeguards
  - live-update behavior and stale-state handling
  - empty/loading/error states
- Wireframes (low/medium fidelity) for:
  - default queue view
  - filtered/failed triage view
  - expanded job detail view
  - bulk-action confirmation flow
- Prioritized implementation backlog in task format:
  - P0 (highest usability impact, lowest implementation risk)
  - P1 (strong improvement, moderate effort)
  - P2 (nice-to-have enhancements)
  - include frontend/API dependencies and migration notes per item

## Acceptance Criteria
- [x] Research document includes at least 6 cited sources and each major queue UX decision links back to source-backed reasoning.
- [x] UX spec defines concrete behavior for queue visibility at scale (200+ jobs) without requiring full-page scanning.
- [x] Spec includes keyboard and accessibility requirements (focus order, expand/collapse semantics, readable status indicators).
- [x] Desktop and mobile behavior differences are explicitly documented.
- [x] Backlog items are implementation-ready (scope, dependencies, test expectations, rollback note).

## Comprehensive Testing Requirements
- [x] Add `docs/research/queue_ui_validation_checklist.md` with measurable UX checks (time-to-locate-failed-job, cancel confidence, settings visibility discoverability).
- [x] Map each proposed UX change to required automated coverage:
  - frontend unit tests (rendering, state transitions)
  - frontend integration tests (filters, expand/collapse, bulk actions)
  - API contract tests (fields required for visibility features)
- [x] Define at least one before/after manual benchmark scenario using current queue and proposed design.

---

## Task T24: Queue UX P0 Implementation (Status Controls, Actionable Sort, Safe Actions)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Implement P0 queue UX items from `docs/design/queue_ux_spec.md` with minimal backend risk, preserving existing API compatibility.

## Deliverables
- Queue status bar with counters and filter chips.
- Search + sort controls with default actionable sort (`running`, `failed`, `pending`, `canceled`, `succeeded`).
- Queue list rendering that preserves expanded job detail rows across refresh/filter changes.
- Hardened destructive/critical actions:
  - cancel confirmation before API call
  - clear queue confirmation includes job count and single-flight guard.
- Tests covering new queue visibility controls and action safeguards.

## Acceptance Criteria
- [x] Queue defaults to actionable sorting and prioritizes running/failed work.
- [x] Status chips filter rows and update counts correctly.
- [x] Search narrows visible rows by job fields.
- [x] Expanded details remain expanded after queue refresh.
- [x] Cancel action requires explicit confirmation.
- [x] Existing queue clear flow still works with two-step confirmation and in-flight protection.

## Comprehensive Testing Requirements
- [x] Frontend tests for actionable sort order.
- [x] Frontend tests for status-chip filtering and search.
- [x] Frontend tests for cancel confirmation guard.
- [x] Static UI contract test coverage for new queue controls.

---

## Task T25: Queue-Owned Input Staging for Durable Execution Paths
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`in_progress` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Eliminate queued-job failures caused by source files being moved/renamed/deleted after submit by ensuring execution uses queue-owned immutable staged paths.

## Deliverables
- Staging path design and implementation under `data/staging/` (or equivalent) for queued input assets.
- Submit flow updates so prompt input bindings point to staged file paths, not volatile source paths.
- Metadata preservation:
  - source/original path retained for UI/debug visibility
  - staged execution path retained for worker/comfy use
- Backward-compatible API behavior for existing job submission endpoints.

## Acceptance Criteria
- [x] After submit, deleting/renaming the original source file does not break execution for already-queued prompts.
- [x] `prompt_json` for queued prompts references staged/owned input paths.
- [x] UI still shows meaningful original source context for operators.
- [x] Existing non-staged workflows/endpoints remain functional.

## Comprehensive Testing Requirements
- [ ] Unit tests for staging path generation and copy semantics.
- [x] Integration tests:
  - submit job -> mutate/delete original file -> queued job still validates and runs
  - staged file missing/corrupt -> clear actionable error path
- [x] Regression tests for single-image and batch submission paths.

---

## Task T26: Upload Filename Policy: Preserve Original Name + Suffix on Collision
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Replace always-on timestamp-prefix renaming with human-readable naming that preserves original filenames when possible and only adds a deterministic suffix on collision.

## Deliverables
- Upload naming strategy update for `/api/upload/input-image`:
  - keep sanitized original filename by default
  - append suffix (`__2`, `__3`, ...) only when target filename already exists
- Optional metadata field(s) for `original_filename` in upload response payload.
- Migration note documenting old timestamp-prefix behavior vs new naming policy.

## Acceptance Criteria
- [ ] Uploading a unique filename preserves readable original name (sanitized).
- [ ] Uploading duplicate names in same destination never overwrites existing files.
- [ ] Collision handling is deterministic and user-comprehensible.
- [ ] Existing clients using upload API remain compatible.

## Comprehensive Testing Requirements
- [ ] Unit tests for filename sanitization and suffix increment logic.
- [ ] API integration tests for:
  - unique name upload
  - repeated same-name upload in same dir
  - same-name upload across different subdirs
- [ ] Regression tests for drop-upload flows in single and upscale-images tabs.

---

## Task T27: Input Duplication Policy and Configurable Staging Scope
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Define and implement explicit policy for when inputs are duplicated into queue-managed storage vs referenced in place, balancing reliability and disk usage.

## Deliverables
- Policy doc section in `docs/` covering:
  - uploads: always staged
  - path-based submits: configurable (`stage_on_submit` true/false)
  - tradeoffs (reliability, disk footprint, throughput)
- Config surface (env/config flag and default) for staging scope.
- UI/API observability of active mode (staged vs in-place) where appropriate.

## Acceptance Criteria
- [ ] Default behavior is explicitly documented and visible in code/config.
- [ ] Operators can switch policy without code edits.
- [ ] Behavior is consistent across batch, single, and upscale-images flows.
- [ ] Policy change does not alter endpoint shapes unexpectedly.

## Comprehensive Testing Requirements
- [ ] Integration tests for both policy modes (`stage_on_submit=true/false`).
- [ ] Regression tests ensuring job creation/counts/prompt mapping parity across modes.
- [ ] Manual QA checklist for operator understanding and safe-mode selection.

---

## Task T28: Staging Retention and Cleanup Policy
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Prevent unbounded growth of queue-owned staged inputs while keeping enough retention for debugging/retry workflows.

## Deliverables
- Retention policy implementation (TTL and/or state-based cleanup) for staged assets.
- Cleanup command/endpoint or scheduled sweep mechanism with dry-run mode.
- Safety guards:
  - never delete assets still referenced by active/runnable prompts
  - audit/log output for deleted files
- Operator docs for retention configuration and manual cleanup procedures.

## Acceptance Criteria
- [ ] Staged storage usage is bounded under sustained operation.
- [ ] Cleanup never removes files needed by pending/running prompts.
- [ ] Operators can run cleanup safely in dry-run and apply modes.
- [ ] Cleanup behavior is observable via logs/metrics.

## Comprehensive Testing Requirements
- [ ] Unit tests for retention candidate selection logic.
- [ ] Integration tests:
  - completed jobs cleaned after policy threshold
  - active jobs excluded from cleanup
  - dry-run reports expected file set without deletion
- [ ] Failure-path tests for partial deletion errors and retry-safe recovery.

---

## Task T29: Full-Page UI Hierarchy and Visual Refresh
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Improve visual hierarchy and readability across the entire app (top status bar, submit panel, presets, workflow params, queue section), not just queue rows.

## Deliverables
- Global design token cleanup in `static/index.html`:
  - clearer surface/background/line/text tiers
  - semantic state colors for success/warning/error/info
- Layout hierarchy pass:
  - stronger section separation between global controls, submit, and queue
  - clearer heading/label hierarchy and spacing scale
  - sticky/anchored controls where useful for long pages
- Submit panel UX polish:
  - better grouping for workflow, inputs, presets, and advanced settings
  - stronger visual distinction for destructive/high-impact actions
- Queue panel visual alignment with refreshed page style:
  - preserve current queue behavior while matching revised design language
- Responsive pass for desktop + mobile breakpoints.

## Acceptance Criteria
- [x] Entire page has clear visual hierarchy with recognizable section boundaries.
- [x] Primary actions and current system state are distinguishable at a glance.
- [x] Form readability improves (labels, inputs, helper text, advanced sections).
- [x] No regressions in existing interactions (submit, presets, drag/drop, queue actions).
- [x] Mobile layout remains usable without horizontal overflow in core controls.

## Comprehensive Testing Requirements
- [x] Frontend regression tests still pass (`tests/frontend_state.test.mjs`).
- [x] Static UI contract tests updated for any new anchors/IDs.
- [ ] Manual QA checklist for key flows:
  - batch submit
  - single I2V submit
  - upscale images submit
  - queue cancel/retry/clear
  - prompt/settings preset save/apply

---

## Task T30: Video I2V Multi-Image Drag/Drop with Thumbnails
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Bring Batch Video I2V drag/drop behavior to parity with Upscale Images: allow multiple image drop, show thumbnails, and submit against dropped set without requiring manual input directory handling.

## Deliverables
- UI behavior in Batch (video_gen) mode:
  - drag/drop zone accepts multiple supported image types
  - thumbnail strip/list for dropped files
  - clear dropped set action
  - input directory field is visually ignored/disabled while dropped set is active
- Submission behavior:
  - dropped files uploaded/staged and mapped to a queue-owned input directory
  - submit uses dropped-set directory automatically
  - switching away/clearing drop state restores normal input dir behavior
- Consistency improvements:
  - shared helper logic between Upscale Images and Batch drag/drop to reduce divergence
  - clear user messaging for which source set will be submitted

## Acceptance Criteria
- [x] In Batch mode, dropping N images renders N thumbnails and enables submission without manual directory entry.
- [x] While dropped set is active, input dir is ignored and clearly indicated as such.
- [x] Clearing dropped set re-enables normal input directory flow.
- [x] Existing Upscale Images drag/drop flow remains functional.
- [x] Submission payload routes to `/api/jobs` with expected behavior for split-by-input queueing.

## Comprehensive Testing Requirements
- [x] Frontend tests for Batch drag/drop multi-file state and thumbnail rendering.
- [x] Frontend tests for input-dir disable/enable transitions during drop/clear.
- [ ] API integration coverage for upload + submit path used by Batch dropped-set flow.
- [x] Regression tests ensuring single-I2V and Upscale Images drop behavior still works.

---

## Task T31: Multi-Tab Workspaces for Queue Control Panel
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Allow users to keep multiple independent workflow configurations open at once (like browser tabs) so they can switch contexts without resetting form state.

## Deliverables
- Workspace tab bar in submit panel with actions:
  - create tab
  - rename tab
  - close tab
  - switch active tab
- Per-tab isolated state for:
  - mode (`batch` / `single` / `upscale` / `upscale_images`)
  - selected workflow
  - workflow params
  - prompt preset selection
  - settings preset selection
  - input path/image fields
  - dropped-image batch state (if applicable)
- Persistence across refresh/reopen via local storage.
- Safe close behavior:
  - closing active tab activates adjacent tab
  - cannot close last remaining tab (or auto-create replacement)
- UI indicators for active tab and unsaved edits (if implemented).

## Acceptance Criteria
- [x] User can maintain at least 3 independent workspace tabs without settings collision.
- [x] Switching tabs restores each tab’s exact prior form values and mode.
- [x] Refreshing browser preserves tabs and active tab selection.
- [x] Submit action uses currently active tab state only.
- [x] Existing queue list/actions continue to function unchanged.

## Comprehensive Testing Requirements
- [x] Frontend tests for tab create/switch/close behavior.
- [x] Frontend tests for per-tab state isolation across workflows and modes.
- [x] Frontend persistence test for multi-tab state restore after reload.
- [x] Regression tests for submit payload correctness under tab switching.

---

## Task T32: Add Image Generation Mode (T2I + I2I) to Queue
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Add first-class image generation support so queue can submit and track both text-to-image and image-to-image jobs alongside existing video and upscale modes.

## Deliverables
- New unified `Image Gen` mode in UI with clearly selectable source type:
  - `Text-to-Image (T2I)`
  - `Image-to-Image (I2I)`
- New mode/category support for `image_gen` workflows in backend and UI.
- Workflow dropdown filtering so Image Gen mode only shows `image_gen` workflows.
- Submission payload path for image-gen workflows (no video-only assumptions), supporting:
  - prompt-only submission for T2I
  - directory or multi-image drag-drop submission for I2I
- Queue/job detail compatibility for image outputs.
- I2I drag-drop UX parity with existing image drop zones:
  - multi-image drop
  - thumbnail previews
  - clear dropped set action

## Acceptance Criteria
- [x] UI includes one `Image Gen` mode with a clearly visible toggle/selector for `T2I` vs `I2I`.
- [x] `Image Gen` mode only shows workflows with category `image_gen`.
- [x] T2I submission works without input images and creates queued prompt(s) successfully.
- [x] I2I submission supports multi-image drag-drop with thumbnail preview and creates queued prompt(s) successfully.
- [ ] Completed image-gen jobs show output paths and metadata in queue/job detail views.
- [x] Existing video-gen/video-upscale/image-upscale flows remain unchanged.

## Comprehensive Testing Requirements
- [ ] API tests for T2I and I2I submit validation and queue creation.
- [x] Prompt-builder tests for image-gen workflow parameter mapping.
- [x] Frontend tests for source-type selector behavior (`T2I`/`I2I`) and payload correctness.
- [x] Frontend tests for I2I multi-image drag-drop thumbnails and clear/reset behavior.
- [x] Regression tests confirming no behavior changes in current non-image-gen modes.

---

## Task T33: Workspace Isolation and Visual Separation Upgrade
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`todo` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Improve workspace usability by making each workspace start clean/default and by creating clearer visual/functional separation between workspaces.

## Deliverables
- New workspace initialization behavior:
  - New workspace starts with default/empty settings (not cloned from current workspace).
- Stronger workspace-scoped state boundaries for:
  - mode, workflow, input paths, job name, prompt preset, settings preset, workflow params.
- Visual redesign of workspace tabs/panels to better differentiate active vs inactive workspaces.

## Acceptance Criteria
- [ ] Creating a new workspace opens a clean default form state.
- [ ] Switching workspaces restores only that workspace's saved state with no cross-workspace leakage.
- [ ] Visual active-state hierarchy is clear at a glance (active tab, inactive tabs, context boundary).
- [ ] Workspace rename/close behavior remains stable with new separation.

## Comprehensive Testing Requirements
- [ ] Frontend tests: new workspace initializes defaults instead of cloning current values.
- [ ] Frontend tests: state isolation across at least 3 workspaces for modes/workflows/params.
- [ ] Frontend persistence tests: reload restores each workspace independently.
- [ ] Manual QA checklist for readability and workspace switching ergonomics.

---

## Task T34: UI V2 Foundation Scaffold (`/v2` Svelte App)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Establish the new V2 frontend project and static mount point at `/v2` without changing existing `/` UI behavior.

## Deliverables
- Create `ui/` project scaffold with:
  - SvelteKit SPA/static output configuration
  - Tailwind setup and base theme tokens matching current dark palette
  - typed API client shell (`ui/src/lib/api.ts`)
  - store skeletons (`jobs`, `health`, `workflows`, `workspace`)
- FastAPI static mount for V2:
  - `app.mount("/v2", StaticFiles(directory="ui/build", html=True), name="ui_v2")`
  - keep existing legacy mount at `/`
- Build/run docs:
  - local dev instructions (`npm run dev`, proxy to API)
  - production build instructions (`npm run build`)

## Acceptance Criteria
- [x] Visiting `/v2` serves the new app shell successfully.
- [x] Existing legacy UI at `/` continues to work unchanged.
- [x] `npm run build` outputs static assets consumable by FastAPI mount.
- [x] V2 app can call existing API endpoints with no backend schema changes.

## Comprehensive Testing Requirements
- [x] API smoke test for `/`, `/v2`, `/api/health` served concurrently.
- [x] Build verification in CI/local for `ui` (`npm ci`, `npm run build`).
- [x] Static mount integration test for V2 path resolution and fallback routing.

---

## Task T35: UI V2 Phase 1 - Status Bar + Queue Panel
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Ship the first usable V2 monitoring experience: health/status at top and card-based queue browsing with filtering/sorting/bulk-safe actions.

## Deliverables
- `StatusBar` component:
  - polls `/api/health`
  - shows Comfy status, worker state, pending/running counts
  - pause/resume + reload workflows/LoRAs actions
- `QueuePanel` with:
  - summary chips for statuses
  - search + actionable sort default
  - card-style rows (`JobRow`) replacing dense table layout
  - stable expanded-row state across refresh
- Safe destructive actions in V2:
  - confirm cancel
  - confirm clear queue with count and in-flight guard

## Acceptance Criteria
- [x] V2 queue view supports daily monitoring without using legacy queue table.
- [x] Running/failed items are prioritized by default actionable sort.
- [x] Status chips and search filter update visible rows correctly.
- [x] Cancel and clear queue require explicit confirmation.
- [x] Polling failures surface UI errors but do not crash panel interactivity.

## Comprehensive Testing Requirements
- [x] Component tests for status chips, search, sort, and row expansion state.
- [x] Integration tests for cancel/clear confirmation flows and API call guards.
- [x] Regression tests ensuring queue refresh does not reset expanded items or selection unexpectedly.

---

## Task T36: UI V2 Phase 2 - Submit Panel + Dynamic Params + Presets
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Reach submission parity in V2 for Batch, Image Gen, Upscale Video, and Upscale Image modes with reusable dynamic parameter rendering and preset controls.

## Deliverables
- `SubmitPanel` with mode tabs:
  - Batch
  - Image Gen (T2I/I2I)
  - Upscale Video
  - Upscale Image
- Dynamic `ParamFields` renderer from workflow definitions, including:
  - text/int/float/bool/select fields
  - stage prompts, LoRA toggles, grouped sections
  - range clamping/default fallback
- Input UX:
  - directory picker/browse support
  - shared drag-drop component with multi-image thumbnails and clear actions
- Presets:
  - prompt presets scoped by mode/category
  - settings presets (including prompt preset linkage)
- Submission mapping parity to `/api/jobs` payloads.

## Acceptance Criteria
- [x] V2 can submit jobs for all current supported modes/workflow categories.
- [x] Dynamic fields render consistently with workflow metadata and legacy behavior.
- [x] I2I/upscale drop zones support multi-file thumbnail preview and clear/reset.
- [x] Saved prompts/settings persist and re-apply correctly in V2.
- [x] Submissions from V2 produce equivalent queued job records as legacy UI for same inputs.

## Comprehensive Testing Requirements
- [x] Component tests for param rendering by type and conditional visibility.
- [x] Integration tests for each mode submit payload (`batch`, `image_gen`, `video_upscale`, `image_upscale`).
- [x] Preset tests for save/overwrite/apply with mode scoping.
- [x] Regression tests for edge cases:
  - inputless workflows
  - image-required workflows in wrong source mode
  - multi-try seed behavior.

---

## Task T37: UI V2 Phase 3 - Job Detail + Log Viewer + Workspace Manager
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Complete V2 operational depth with rich detail panels, prompt-level traceability, log inspection, and robust multi-workspace state.

## Deliverables
- `JobDetail` component:
  - metadata grid (status, created/started/completed, elapsed)
  - parameters section (formatted key/value)
  - prompt rows with statuses, seeds, input/output paths
  - prompt JSON disclosure (collapsed by default)
- Log viewer:
  - lazy-load from `/api/jobs/{id}/log`
  - error/empty/loading states
- `WorkspaceManager`:
  - create/rename/close/switch tabs
  - isolated workspace state for mode/workflow/params/presets/input/drop-state
  - localStorage persistence and restore

## Acceptance Criteria
- [x] Expanded job detail is readable and does not dump raw unstructured JSON by default.
- [x] Prompt and Comfy correlation IDs are visible where available.
- [x] Log viewer works without freezing UI on larger logs.
- [x] Multiple workspaces can be used without state leakage.
- [x] Refresh/reopen restores active workspace and per-workspace state.

## Comprehensive Testing Requirements
- [x] Component/integration tests for expand/collapse, prompt row rendering, and log fetch lifecycle.
- [x] Workspace tests for isolation across at least 3 tabs and persistence after reload.
- [x] Regression tests for queue actions from expanded rows (cancel/retry) with detail open.

---

## Task T38: UI V2 Compatibility, Performance, and Accessibility Gate
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Validate V2 is production-ready for real usage volumes and accessible operation before cutover.

## Deliverables
- Compatibility checklist:
  - all existing workflows render and submit in V2
  - all queue actions operate correctly
- Performance tuning for large queues (target 200+ jobs):
  - efficient polling diffing
  - render throttling/virtualization if needed
- Accessibility pass:
  - keyboard navigation
  - focus visibility/order
  - semantic labels/ARIA for tabs, dialogs, expandable rows
- QA report documenting gaps and fixes.

## Acceptance Criteria
- [x] V2 reaches feature parity with legacy UI for daily workflows.
- [x] Queue interactions remain responsive at 200+ jobs.
- [x] No blocking accessibility issues remain for keyboard-only operation.
- [x] Known deviations are documented with severity and mitigation.

## Comprehensive Testing Requirements
- [x] Performance benchmark script/report for queue rendering and polling churn.
- [x] Automated accessibility checks on key screens (status bar, submit panel, queue, detail).
- [x] End-to-end parity checklist run with pass/fail evidence.

---

## Task T39: UI V2 Cutover Plan (`/v2` -> `/`, Legacy Fallback)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Execute safe rollout from legacy UI to V2 with rollback-ready mount strategy and minimal user disruption.

## Deliverables
- Cutover implementation:
  - V2 mounted at `/`
  - legacy UI moved to `/legacy`
- Release notes and operator runbook for:
  - cutover steps
  - rollback steps
  - cache busting/static asset refresh guidance
- Deprecation banner period plan (optional pre-cutover stage).

## Acceptance Criteria
- [x] Users can access V2 at `/` after cutover.
- [x] Legacy UI remains reachable at `/legacy` during transition.
- [x] Rollback to legacy-first mount is documented and tested.
- [x] No API/backend behavior changes are required for UI cutover.

## Comprehensive Testing Requirements
- [x] Route tests for `/`, `/v2` (if retained), `/legacy`, and API paths post-cutover.
- [x] Manual smoke run:
  - submit in each mode
  - monitor queue
  - cancel/retry/clear queue
  - save/apply presets
- [x] Rollback dry-run verification in a staging/local environment.

---

## Task T40: Auto-Prompt Two-Stage LM Studio Generator Skeleton
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Define and scaffold the two-stage auto-prompt subsystem for Wan i2v using LM Studio as the inference backend.

## Deliverables
- New module scaffolding:
  - `auto_prompt/__init__.py`
  - `auto_prompt/generator.py`
  - `auto_prompt/prompts.py`
  - `auto_prompt/cache.py` (optional, but task-owned design point)
- `AutoPromptGenerator` contract with:
  - `caption_image(image_path)`
  - `caption_to_motion(caption, workflow_context)`
  - `generate_batch(image_paths, callback=None)`
- Default stage model mapping:
  - Stage 1 caption model: `Qwen3-VL-8B-NSFW-Caption-V4.5`
  - Stage 2 motion model: `Dolphin-Mistral-24B-Venice-Edition`
- Workflow-aware context extraction:
  - detect split-prompt workflows by parameter keys (`positive_prompt_stageN`)
  - read clip timing (`fps`, `frames_per_stage`, `duration`) from workflow template
- Two system prompts in `prompts.py`:
  - Stage 1 prompt optimized for motion-relevant physical details
  - Stage 2 prompt optimized for Wan temporal motion output with runtime timing placeholders

## Acceptance Criteria
- [x] Module paths exist and are importable from project runtime.
- [x] Generator contract is documented in code comments/docstrings and aligns with design doc behavior.
- [x] Stage model defaults and two-stage pipeline behavior are explicit and documented.
- [x] Generator contract explicitly supports both single-prompt and split-prompt workflows.
- [x] Prompt content for both stages is externalized and not hardcoded in endpoint handlers.

## Comprehensive Testing Requirements
- [x] Unit test verifies module import and generator skeleton initialization.
- [x] Unit test verifies batch callback contract shape (`stage, path, i, total`) for `caption` and `motion`.
- [x] Unit test verifies default Stage 1 and Stage 2 model identifiers are wired correctly.
- [x] Unit test verifies workflow timing extraction and split-prompt detection behavior.

---

## Task T41: LM Studio Connectivity and Capability Gate
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Add runtime capability checks and graceful failure behavior for LM Studio-backed auto-prompt generation.

## Deliverables
- Minimal dependency contract:
  - `requests` as the only required new Python package
  - no `transformers`/`torch`/`autoawq` runtime requirement in `video_queue`
- Capability-check helper used by API/UI layers.
- Stable unavailable-backend response contract (HTTP 503 + actionable message).
- LM Studio connectivity probe behavior for configurable base URL.

## Acceptance Criteria
- [x] Service startup does not depend on local ML framework installs.
- [x] Auto-prompt requests return deterministic 503 responses when LM Studio is unreachable.
- [x] UI capability probe can safely disable auto-prompt actions with a clear operator hint.
- [x] Error copy instructs user to start LM Studio and load the required stage model.

## Comprehensive Testing Requirements
- [x] Unit tests for connectivity-check behavior (reachable, timeout, connection failure).
- [x] Integration test confirms endpoint returns 503 with expected error shape when LM Studio is unavailable.
- [x] Regression test confirms non-auto submission flows still function when LM Studio is down.

---

## Task T42: Two-Stage Auto-Prompt API Endpoint (`POST /api/auto-prompt`)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Expose stage-selectable two-stage auto-prompt generation through a backend API that UI and tooling can call.

## Deliverables
- Request/response models matching the design:
  - `image_paths`
  - `workflow_name`
  - `stage` (`caption`, `motion`, `both`)
  - `captions` (for stage-2-only reruns)
  - `system_prompt_override` (Stage 2 override)
  - `lmstudio_url`
- New endpoint: `POST /api/auto-prompt`.
- Response contract with:
  - per-path `caption` and/or `motion_prompt`
  - `stage1_model`, `stage2_model`
  - `elapsed_seconds`

## Acceptance Criteria
- [x] Endpoint validates input image paths and rejects invalid payloads clearly.
- [x] `stage=caption` returns captions without requiring Stage 2 execution.
- [x] `stage=motion` requires supplied captions and returns motion prompts only.
- [x] `stage=both` runs caption then motion and returns both outputs per image.
- [x] Endpoint validates `workflow_name` and uses workflow context for Stage 2 timing/template behavior.
- [x] For default 81-frame/24fps workflows, temporal markers align with `0s`, `1.5s`, and `3s` (or equivalent rounded output).
- [x] Endpoint handles generator failures with user-readable error context.

## Comprehensive Testing Requirements
- [x] API tests for success path with mocked generator.
- [x] API tests for stage-specific behavior (`caption`, `motion`, `both`).
- [x] API tests for validation failures and empty-input behavior.
- [x] API tests for invalid/missing `workflow_name` and split-vs-single workflow behavior.
- [x] API tests for generator exception handling and response code stability.

---

## Task T43: Per-File Prompt Overrides in Prompt Builder and Job Schema
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Allow each input file in a batch to carry workflow-compatible prompt overrides (single or split) without changing worker execution flow.

## Deliverables
- Extend `JobCreateRequest` with optional `per_file_params`.
- Extend `build_prompts()` to apply per-file overrides deterministically for:
  - `positive_prompt` (single-prompt workflows)
  - `positive_prompt_stage1..N` (split-prompt workflows)
- Ensure persisted prompt specs reflect per-file overrides for selected workflow type.

## Acceptance Criteria
- [x] Existing single-prompt behavior is unchanged when `per_file_params` is omitted.
- [x] Per-file overrides apply only to matching files and do not bleed across entries.
- [x] Prompt JSON written to DB matches requested per-file prompt values for both single and split prompt schemas.

## Comprehensive Testing Requirements
- [x] Unit tests for prompt-builder merge behavior and precedence.
- [x] API integration tests covering mixed batches (some files overridden, some default).
- [x] Integration tests for split-prompt workflows confirm stage-specific node mapping remains correct.
- [x] Regression tests confirming existing submit flows remain unchanged without override field.

---

## Task T44: Prompt Mode Contract (`manual`, `per-image manual`, `per-image auto`)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Formalize prompt-mode semantics across API and UI so per-image prompt editing and auto-fill have explicit, testable behavior.

## Deliverables
- Prompt mode model and mapping rules in backend/frontend contract docs and code.
- Submission mapping for each mode to payload shape (`params` vs `per_file_params`).
- `per-image auto` sub-state contract:
  - captions generated
  - motion prompts generated
  - edited prompts ready for apply
- Split workflow semantics:
  - `per-image auto` may produce N stage prompts per image
  - `manual` and `per-image manual` require explicit handling for N stage fields when selected workflow is split
- Validation rules for invalid mode/state combinations.

## Acceptance Criteria
- [x] Mode semantics are explicit and consistent between UI state and API payloads.
- [x] Invalid mode transitions return clear user-facing errors.
- [x] Mode defaults preserve current manual flow for existing users.
- [x] `per-image auto` supports Stage 2 re-run without forcing Stage 1 re-run.
- [x] Prompt mode behavior remains coherent for both standard and split-prompt workflows.

## Comprehensive Testing Requirements
- [x] Contract tests for each mode and payload mapping.
- [x] Negative tests for invalid mode + missing required per-image prompt data.
- [x] Contract tests for auto-mode transitions across caption-only, motion-only, and full pipeline.
- [x] Contract tests for split-workflow mode transitions with multi-stage prompt payloads.

---

## Task T45: UI Two-Stage Auto-Prompt Panel
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Add the operator-facing UI for the two-stage workflow: caption images, convert to motion prompts, iterate quickly, and apply per-file prompts.

## Deliverables
- Submit-panel auto-prompt controls:
  - generate captions (Stage 1)
  - generate motion prompts from captions (Stage 2)
  - regenerate motion prompts (Stage 2-only)
  - apply all
  - clear all
- Per-image rows showing caption + editable motion prompt tied to source files.
- Split-workflow rendering mode showing editable Clip 1..N prompts per image.
- Progress display for each stage.

## Acceptance Criteria
- [x] Operators can run Stage 1 and Stage 2 independently from the UI.
- [x] Operators can edit motion prompts inline before apply/submit.
- [x] Applying prompts produces per-file submission payloads that match edited values.
- [x] UI remains responsive during generation and surfaces stage-specific failures clearly.
- [x] Motion regeneration can run repeatedly from existing captions without reprocessing images.
- [x] For split-prompt workflows, UI allows per-image editing/regeneration across all generated stage prompts.

## Comprehensive Testing Requirements
- [x] Frontend tests for control visibility, state transitions, and editing behavior.
- [x] Integration tests validating payload generated from edited prompt list.
- [x] Integration tests for Stage 1-only, Stage 2-only, and full-stage UI flows.
- [x] UI tests for split-prompt workflows validate Clip 1..N display and payload mapping.
- [x] UI tests assert split-prompt labels use `Clip N` terminology (not `Stage N`) in user-facing rows.
- [x] Regression tests ensuring manual-only submission path remains intact.

---

## Task T46: Auto-Prompt Test Matrix (unit + integration + regression)
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Establish comprehensive test coverage for auto-prompt features and guard against regressions in existing queue behavior.

## Deliverables
- Test plan and implemented cases covering backend and frontend auto-prompt paths.
- Dedicated regression coverage for core non-auto submit and queue workflows.

## Acceptance Criteria
- [x] All new auto-prompt code paths have deterministic automated tests.
- [x] Existing baseline submit/queue tests continue to pass.
- [x] Failure paths (LM Studio unavailable, bad paths, stage errors) are covered.
- [x] Caching and stage-specific rerun behaviors are covered.
- [x] Split-prompt generation/parsing/mapping behaviors are covered.
- [x] Timestamp correctness coverage includes 81-frame/24fps expected markers (`1.5s`, `3s`) and workflow-derived alternatives.

## Comprehensive Testing Requirements
- [x] Unit tests for generator wrapper, connectivity gates, cache behavior, and prompt-merge utilities.
- [x] API integration tests for endpoint behavior and per-file submit behavior.
- [x] Frontend integration tests for mode switching and payload assembly.
- [x] API/frontend tests for `stage=caption`, `stage=motion`, and `stage=both` scenarios.
- [x] End-to-end tests for split workflows (`wan-context-2stage-split-prompts`, `wan-context-3stage-split-prompts`) are included.
- [x] Regression suite run for legacy and V2 submit/queue actions.

---

## Task T47: Auto-Prompt Docs and Operator Runbook
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Document setup, runtime behavior, fallback modes, and operator workflow for auto-prompt usage.

## Deliverables
- README updates for feature overview and dependency installation.
- Operator runbook covering:
  - two-stage architecture overview (caption -> motion prompt)
  - Stage 1/Stage 2 model defaults and on-disk locations
  - LM Studio setup and base URL configuration
  - manual model swap workflow and optional future auto-swap workflow
  - `requests`-only dependency model
  - rapid iteration workflow (caption once, rerun Stage 2 many times)
  - split-prompt workflow behavior (2-stage/3-stage) and stage prompt mapping
  - workflow timing derivation and timestamp placeholder usage (`1.5s` / `3s` for 81/24 defaults)
  - terminology conventions: UI uses `Clip 1/2/3` labels for split prompts
  - troubleshooting and failure recovery
- API docs for `POST /api/auto-prompt` and `per_file_params`.

## Acceptance Criteria
- [x] Documentation includes clear prerequisites and opt-in usage flow.
- [x] Runbook includes LM Studio unavailable behavior and expected 503 responses.
- [x] Documentation states that Stage 1 and Stage 2 prompts are authored in-house for the two-stage flow.
- [x] Docs reflect current code behavior and payload contracts.

## Comprehensive Testing Requirements
- [x] Manual doc validation pass using commands and flows exactly as documented.
- [x] API docs/examples validated against live local endpoint behavior.

---

## Task T48: Auto-Prompt CLI Dev Harness for Prompt Iteration
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`done` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Create a lightweight local harness to rapidly iterate on system prompt quality outside full UI submit flows.

## Deliverables
- CLI/dev command to run stage-selectable auto-prompt generation on a folder/list of images.
- Output format suitable for quick review and comparison.
- Optional Stage 2 system prompt override support for experimentation.
- Cached-caption workflow for rapid Stage-2-only reruns.
- CLI inputs for:
  - `--stage caption|motion|both`
  - `--workflow-name` (required for timing/split behavior)
  - `--captions-file` (for Stage 2 reruns without image inference)
  - `--system-prompt-override` (Stage 2)

## Acceptance Criteria
- [x] Developers can run batch prompt generation from terminal with a single command.
- [x] Harness supports Stage 2-only reruns from previously generated captions.
- [x] Output captures caption + motion prompt mapping clearly for review.
- [x] Harness supports split-workflow output shape (Clip 1..N) and validates parseability.
- [x] Stage 2 prompt iteration loop is measurably faster than full two-stage reruns on the same sample set.

## Comprehensive Testing Requirements
- [x] CLI tests for argument parsing and happy-path execution with mocked generator.
- [x] Tests for empty directory/input and invalid path handling.
- [x] CLI tests for stage selection, captions-file input, and Stage 2 override behavior.
- [x] CLI tests for `--workflow-name` split/single behavior and multi-clip output parsing.

---

## Task T49: End-to-End Batch Acceptance and Quality Sign-off
## Repo
`video_queue` (`/home/cobra/video_queue`)

## Status
`in_progress` (worker updates this to `in_progress`, `blocked`, or `done` in `tasks.md`)

## Objective
Validate real-world usefulness of auto-prompt mode on representative 20-50 image Wan i2v batches before release.

## Deliverables
- End-to-end batch run report with:
  - stage-by-stage timing (caption stage, model swap, motion stage)
  - prompt quality observations
  - submit/execution validation
- Comparative quality section:
  - Stage 2 prompt variant A vs B using the same cached captions
  - quality effect of Stage 2-only regeneration loop
- Release recommendation (ship/iterate/block) with concrete follow-up actions if needed.

## Acceptance Criteria
- [ ] End-to-end run completes with per-image prompts applied in queued jobs.
- [ ] Quality and usability findings are documented with examples.
- [ ] Report demonstrates practical Stage 2 prompt iteration workflow without repeated Stage 1 runs.
- [ ] Report includes at least one split-prompt workflow run (2-stage or 3-stage) with correct per-stage prompt persistence.
- [ ] Remaining gaps are converted into explicit follow-up tasks.

## Comprehensive Testing Requirements
- [ ] Manual E2E validation checklist completed for at least one medium batch (20+) and one larger batch (40-50).
- [ ] Verification that prompt persistence and job payloads match reviewed/edited prompts.
- [ ] Post-run regression smoke for baseline manual submission mode.
- [ ] Acceptance checklist includes at least one Stage 2-only rerun cycle from cached captions.
- [ ] Acceptance checklist includes split-prompt stage mapping verification in persisted prompt JSON.

---

## Suggested Execution Order
1. Task T00
2. Task T01
3. Task T02
4. Task T03
5. Task T04
6. Task T05
7. Task T06
8. Task T07
9. Task T08
10. Task T09
11. Task T10
12. Task T11
13. Task T12
14. Task T13
15. Task T14
16. Task T15
17. Task T16
18. Task T17
19. Task T23
20. Task T24
21. Task T25
22. Task T26
23. Task T27
24. Task T28
25. Task T29
26. Task T30
27. Task T31
28. Task T32
29. Task T33
30. Task T34
31. Task T35
32. Task T36
33. Task T37
34. Task T38
35. Task T39
36. Task T40
37. Task T41
38. Task T42
39. Task T43
40. Task T48
41. Task T44
42. Task T45
43. Task T46
44. Task T47
45. Task T49

## Parallelizable Work Streams
- Stream A: Task T02 + Task T03
- Stream B: Task T04 + Task T05 + Task T15
- Stream C: Task T06 + Task T07
- Stream D: Task T08 + Task T09 + Task T13 + Task T14 + Task T16 + Task T17
- Stream E: Task T10 (after Streams A/B mature)
- Stream F: Task T23 (can run in parallel as research/spec track)
- Stream G: Task T24 (after T23 spec approval)
- Stream H: Task T25 + Task T26 (staging durability + upload naming)
- Stream I: Task T27 + Task T28 (policy/config + retention cleanup, after T25)
- Stream J: Task T29 (global UX refresh)
- Stream K: Task T30 (batch drop parity, after/drop shared with existing upload logic)
- Stream L: Task T31 (frontend state architecture extension)
- Stream M: Task T34 (V2 scaffold + mount)
- Stream N: Task T35 + Task T36 + Task T37 (sequential V2 feature track after T34)
- Stream O: Task T38 (parity/perf/a11y gate after T35-37)
- Stream P: Task T39 (cutover/rollback after T38)
- Stream Q: Task T40 + Task T41 + Task T42 (auto-prompt backend foundation)
- Stream R: Task T43 + Task T44 + Task T45 (per-file contract + UI integration after Stream Q)
- Stream S: Task T48 (independent dev harness track, can start after T40)
- Stream T: Task T46 + Task T47 + Task T49 (test/docs/acceptance after Streams R and S)

## Exit Criteria for Refactor Program
- All task acceptance criteria complete.
- Full regression gate passes.
- Operational docs and rollback playbooks are complete.
