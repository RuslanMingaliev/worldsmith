# Project Goal

## Vision

Build a source-of-truth-driven pipeline that generates a classic retro shooter from structured, versioned artifacts.

For generated game code, the operational source of truth is mechanics knowledge, human-readable specs, and per-module IR contracts derived from reference material through research and extraction. The generated game should feel authentic to the genre — the community should recognize the inspiration without the public artifacts leaking source-game identifiers or private reference content.

## Why

The project explores whether a game can be reconstructed as a family of source-of-truth artifacts and generation rules rather than as a single hand-maintained codebase.

The deeper objective is to separate:
- extracted mechanics knowledge (`knowledge/`)
- design and generation constraints (`specs/`)
- machine-oriented module contracts (`ir/`)
- implementation strategy (generation rules)
- generated artifacts (disposable code)
- run feedback (Reconciler and PostMortem updates that close the loop)

## Project Phases

### Phase 1: Faithful Recreation (Current)

Generate a retro shooter that captures the essence of classic FPS games:
- Authentic gameplay feel
- Core mechanics faithful to the genre
- Specs derived from reference research

The production renderer is a column-based first-person raycaster that matches the reference engine's projection model (knowledge/raycaster_renderer.md). Within Phase 1, a six-slice migration replaced the prior 2D top-down view (specs/25 § Visual) incrementally so each slice was reviewable in isolation: slice 1 introduced the raycaster module, the spec, and a `--render-mode={topdown|raycaster}` CLI scaffold defaulting to `topdown` (specs/45); slices 2–4 added sprites, first-person effects, and the FPS-specific HUD layout; slice 5 flipped the default from `topdown` to `raycaster` — `cargo run` with no flag, every existing autopilot scenario, and the canonical PR-preview GIF all render the raycaster view. Slice 6 (this slice) is the terminal slice and re-frames the migration: the top-down view is permanently retained as a **debug-only alternate mode** invoked via `--render-mode=topdown`. It is no longer scheduled for removal — it stays in the codebase as a development aid (grok-at-a-glance debugging of pathfinding, sprite positions, level geometry, and autopilot decisions). The `RenderMode` enum, the `--render-mode` flag, the topdown world-draw path, the topdown HUD, and the topdown game-over border all remain callable.

### Phase 2: Extensibility (Future)

Add plugin/skill architecture for spec modifications:
- Skills like `/add-unicorn-skin` modify specs
- Community can extend the game through spec changes
- Generated code adapts to spec changes

## Generation Model

Generation is pipeline-driven with a human maintainer in the loop. Gameplay and spec deltas normally enter through an issue/PR flow (`agent-intake.yml` → `pr.yml`) that runs the relevant agents, performs partial regeneration against the latest `generated-snapshot` baseline, builds/tests the generated game, records a demo GIF, and surfaces Reconciler/PostMortem edits for maintainer review.

Manual generation in a Claude Code session remains supported for ad-hoc exploration, but it is no longer the primary operating model.

### Iterative Development

During development, prefer efficiency while keeping the source-of-truth chain explicit:
- repair hand-written tooling directly when generation is not involved
- use partial regeneration for source-of-truth PRs
- preserve unaffected generated modules by baselining from `generated-snapshot`
- capture any generated drift back into specs and IR contracts

### Release Generation

Each tagged release must:
- Regenerate all code from scratch
- Produce a "generated sample" — a playable artifact
- Publish the generated source alongside the binary
- Record release notes and run feedback as first-class outputs
- Prove that the source-of-truth pack is sufficient

The `generated/` folder is always disposable. A release proves reproducibility.

### Reconcile

After generation, reconcile code with the source-of-truth pack: capture invented constants into `specs/25_game_tuning.md`, update per-module `ir/contracts/` when contract shape drifted, mark unimplemented features as deferred, and document design decisions or agent-prompt fixes when a run exposes a repeated process failure.

### Automation

Automation is now part of what the project is testing. The priority is not to maximize automation for its own sake; it is to make the automated path auditable enough that a maintainer can trust the artifacts it produces. CI generation, partial-regeneration planning, post-merge snapshots, release composition, and agent prompt updates are therefore source-of-truth-adjacent work, not chores outside the experiment.

## Current Scope

The generated game should have:

- Player movement and collision
- Game loop with real-time input
- At least one weapon
- At least one enemy type
- Win/exit condition
- First-person column-based raycaster as the default renderer
- Top-down renderer retained as a debug-only alternate mode

Scope evolves with the specs. See git history for changes.

## Non-goals

The project is explicitly not trying to do:

- Advanced enemy AI behaviors
- Multiple weapon types
- Procedural level generation
- Graphical fidelity beyond the current flat-color raycaster
- One-shot perfect generation

These may become goals later. Non-goals evolve with the project.

## Source of Truth

The source of truth for generated game code is:
1. spec files in `specs/`
2. IR files and per-module contracts in `ir/`
3. sanitized mechanics knowledge in `knowledge/`

Reference material informs spec creation but is not the operational source of truth. The public source-of-truth pack should be self-sufficient for generation.

This does not imply that every future domain must be forced into specs. If a domain cannot be faithfully reproduced from prose constraints and numeric contracts, it needs its own explicit source-of-truth form and drift checks rather than pretending it fits the game-code generation model.

## Versioning

Versions are git tags, not document sections. The docs describe current state; git history shows evolution.

Tag naming follows the `yyyy.vv` scheme: `yyyy` is the calendar year of the release, `vv` is a zero-padded sequence number within that year (e.g. `2026.01` for the first release of 2026, `2026.02` for the second). Sequence numbers do not reset across years on the same date — they reset only when the year changes.
