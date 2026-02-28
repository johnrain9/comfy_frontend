# T31 Design: Multi-Tab Workspaces for Queue Control Panel

## Problem
Switching between workflows/modes currently overwrites one shared form state. Users lose context and must reconfigure settings repeatedly.

## Goals
- Keep multiple independent submit workspaces open at once.
- Make tab switching instant and lossless.
- Persist tabs across refresh/restart.
- Keep queue behavior unchanged.

## Non-Goals
- No backend DB changes for tab state (client-side only).
- No collaborative/shared tabs between users.
- No queue-tab coupling (tabs are submit-side only).

## UX Design

### Tab Bar (Submit Panel Top)
- Horizontal tab strip above existing submit controls.
- Each tab shows:
  - tab name
  - active state
  - close control
- Actions:
  - `+ New Tab`
  - rename active tab (inline edit)
  - close active/non-active tab

### Default Behavior
- First launch creates one tab: `Workspace 1`.
- Creating a tab clones the active tab (faster branching).
- Closing active tab activates nearest right tab, else left.
- Last tab cannot be removed; close resets it to defaults.

### Context Indicators
- Active tab is visually prominent.
- Optional dirty marker (`*`) when current DOM differs from last saved snapshot.

## State Model

## Storage Keys
- Keep existing key: `video_queue_ui_state_v1`.
- Add version bump: `video_queue_ui_state_v2`.

## Shape
```json
{
  "version": 2,
  "active_tab_id": "ws_1700000000000_a1",
  "workspaces": [
    {
      "id": "ws_1700000000000_a1",
      "name": "Workspace 1",
      "state": {
        "global": {
          "active_mode": "batch",
          "workflow_name": "wan-context-2stage",
          "resolution_preset": "640x1136",
          "flip_orientation": false,
          "move_processed": false,
          "input_dir": "",
          "single_image": "",
          "job_name": ""
        },
        "workflow_params": {
          "wan-context-2stage": { "...": "..." }
        },
        "drop_state": {
          "batch_input_dir": "",
          "upscale_images_input_dir": ""
        },
        "preset_state": {
          "prompt_preset_name": "",
          "settings_preset_name": ""
        }
      }
    }
  ]
}
```

## Persistence Rules
- Save on:
  - field input/change
  - tab switch
  - tab create/rename/close
- Debounce writes (100–200ms) to avoid localStorage churn.

## Runtime Architecture

### Core Functions
- `getActiveWorkspace()`
- `setActiveWorkspace(id)`
- `createWorkspace({ cloneFromActive: true })`
- `renameWorkspace(id, name)`
- `closeWorkspace(id)`
- `loadWorkspaceStateIntoDom(workspace)`
- `syncDomIntoActiveWorkspace()`

### Integration with Existing Form Logic
- Existing `syncGlobalStateFromForm()` and `saveCurrentWorkflowParams()` become workspace-scoped.
- Existing `uiState.global` / `uiState.workflow_params` accessors are replaced with `activeWorkspace.state.*`.
- Existing drop-state variables remain runtime globals but mirrored into active workspace snapshot.

## Submission Semantics
- Submit always uses active workspace only.
- No multi-tab bulk submit action in this iteration.
- Queue/API payload shape unchanged.

## Edge Cases
- Workflow removed after reload:
  - keep saved name in workspace state
  - fallback to first available workflow on render
  - show inline warning in submit message
- Invalid tab name:
  - trim, max 40 chars, fallback to default
- Corrupt storage:
  - reset to fresh v2 state with one workspace

## Migration Plan
- On load:
  - if `v2` exists -> use directly
  - if `v1` exists -> migrate single state to one workspace
  - else -> initialize fresh
- Keep migration function idempotent.

## Accessibility
- Tab strip uses button semantics with clear active state.
- Keyboard:
  - left/right cycles tabs
  - enter activates focused tab
  - delete closes focused tab (except last)

## Test Plan
- Unit/integration frontend tests:
  - create/switch/close/rename tabs
  - per-tab isolation of workflow/mode/params
  - persistence and restore
  - submit uses active tab values only
- Regression:
  - existing queue, presets, drag/drop flows unaffected

## Rollout
1. Add tab state architecture + migration.
2. Add tab bar UI (no behavior regressions).
3. Wire submit and preset interactions.
4. Add keyboard/accessibility polish.

---

## Self-Critique

### Weakness 1: State Complexity
This design increases client state complexity significantly and risks subtle desync between DOM and active workspace snapshot.

Improvement:
- Centralize writes through one reducer-like function instead of direct mutation in many handlers.

### Weakness 2: Drop-State Coupling
Dropped batch/upscale temporary directories are session-specific but persisted in design. Persisting them may restore stale paths after restart.

Improvement:
- Persist only metadata for dropped state (display), but clear staged-path tokens on load.

### Weakness 3: Preset Selection Ambiguity
The design stores preset names per workspace, but preset lists are mode-scoped and can change.

Improvement:
- Persist both preset name and resolved prompt/settings text snapshot for robust restore fallback.

### Weakness 4: Tab Proliferation
Unlimited tabs may create clutter and performance issues.

Improvement:
- Cap tabs (e.g., 8) with explicit message when limit reached.

### Weakness 5: Keyboard Scope
Keyboard shortcuts can conflict with text input focus.

Improvement:
- Enable tab hotkeys only when focus is outside text inputs/textarea.

### Recommendation Before Build
Adopt a small internal state manager abstraction first (workspace store + subscribe/render) before attaching UI controls. That reduces regression risk and simplifies testability.
