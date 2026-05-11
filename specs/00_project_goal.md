# Project Goal

## Vision

Build a spec-driven pipeline that generates a classic retro shooter from structured specifications.

The specifications are derived from reference material through research and extraction. The generated game should feel authentic to the genre — the community should recognize the inspiration.

## Why

The project explores whether a game can be reconstructed as a family of design constraints and implementation rules rather than as a single codebase.

The deeper objective is to separate:
- design knowledge (specs)
- implementation strategy (generation rules)
- generated artifacts (disposable code)

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

Generation is human-driven: a maintainer triggers code generation in a Claude Code session using specs and IR as context, verifies results, and commits.

### Iterative Development

During development, prefer efficiency:
- Repair over regeneration
- Incremental module updates
- Preserve working code

### Release Generation

Each tagged release must:
- Regenerate all code from scratch
- Produce a "generated sample" — a playable artifact
- Prove that specs alone are sufficient

The `generated/` folder is always disposable. A release proves reproducibility.

### Reconcile

After generation, reconcile code with specs: capture invented constants into `specs/25_game_tuning.md`, mark unimplemented features as deferred, and document design decisions.

### Automation

Generation automation (LLM executor, CI-based regeneration) is not a current priority. The focus is on spec quality and knowledge depth. Automation becomes worthwhile when the project outgrows manual generation.

## Current Scope

The generated game should have:

- Player movement and collision
- Game loop with real-time input
- At least one weapon
- At least one enemy type
- Win/exit condition
- Graphical rendering (2D top-down or raycasting)

Scope evolves with the specs. See git history for changes.

## Non-goals

The project is explicitly not trying to do:

- Advanced AI behaviors
- Multiple weapon types
- Procedural level generation
- Graphical fidelity beyond functional
- One-shot perfect generation

These may become goals later. Non-goals evolve with the project.

## Source of Truth

The source of truth for the system is:
1. spec files in `specs/`
2. IR files in `ir/`

Reference material informs spec creation but is not the operational source of truth. Specs should be self-sufficient for generation.

## Versioning

Versions are git tags, not document sections. The docs describe current state; git history shows evolution.

Tag naming follows the `yyyy.vv` scheme: `yyyy` is the calendar year of the release, `vv` is a zero-padded sequence number within that year (e.g. `2026.01` for the first release of 2026, `2026.02` for the second). Sequence numbers do not reset across years on the same date — they reset only when the year changes.
