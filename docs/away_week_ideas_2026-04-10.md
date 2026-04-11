# Week-Away Build Ideas

Date: 2026-04-10

Purpose: capture the highest-leverage autonomous work to spend on while subscription capacity is underused and the owner is away for about a week.

## Best Big Bets

### 1. Upscale Eval Lab

Build a proper experiment system around the Qwen upscale flow.

Return state:
- parameter sweep runner for `cfg`, `denoise`, `steps`, mode, and prompt-hint variants
- saved comparison grids per source image
- provenance metadata for every generated output
- lightweight scoring workflow to mark winners and classify failures
- recommended presets by image type:
  - portrait
  - low-light
  - fabric-detail
  - tiny image
  - group shot

Why this is strong:
- turns subjective tuning into a repeatable process
- gives long-term value every time upscale settings change
- directly addresses the current "hard to tell what I prefer" problem

### 2. Production Hardening Pass

Make `video_queue + photoquery + ComfyUI` operationally boring.

Return state:
- real coverage reporting
- missing regression tests for:
  - prompt injection
  - restart behavior
  - stale server code vs workflow reload
  - live prompt provenance
- helpers that detect already-running services instead of failing noisily
- better logs and health checks
- tighter queue recovery and restart behavior

Why this is strong:
- reduces future debugging churn
- attacks the exact class of issues already hit during this tuning cycle

### 3. PhotoQuery Review Workflow

Turn PhotoQuery into a real review/selection surface for upscale results.

Return state:
- source/output side-by-side review
- rerun with modified preset from review screen
- exact sent prompt/settings shown in review UI
- failure labeling:
  - good
  - oversmooth
  - beige
  - drift
  - crop
- bulk retry flows based on failure class

Why this is strong:
- closes the loop between submission and evaluation
- makes the stack feel more like a product than a manual toolchain

## Secondary Bets

### 4. Auto-Preset Intelligence

Teach PQ/VQ to choose better defaults automatically.

Return state:
- heuristic or classifier-based preset selection
- special handling for:
  - tiny images
  - tall crops
  - low-light images
  - fabric-detail shots
  - group photos
- escalation logic such as:
  - `light -> heavy`
  - `detail -> creative`
  - `1x -> 1.5x` only when justified

### 5. Swarm Companion Integration

Make SwarmUI genuinely useful as a sidecar tool.

Return state:
- clean launcher/status integration
- shared model/config sanity checks
- optional helper-node integration if worth it
- workflow handoff path between Swarm experiments and VQ production presets

Why this is lower priority:
- useful for experimentation
- less leverage than eval tooling, hardening, and review workflow

## Recommended Package

If doing the most ambitious version, combine:
- Upscale Eval Lab
- Production Hardening Pass
- PhotoQuery Review Workflow

That combination gives the best "leave for a week, return to something materially better" outcome.
