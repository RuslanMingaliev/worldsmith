# Public Design Decisions

This file records design decisions whose rationale belongs alongside the public spec corpus — primarily decisions made during code generation that affect how readers should interpret the specs and the generated code.

For project-process and harness-level decisions (1–21) see `work/decisions.md`. ADR numbering continues across both files; new public ADRs should not reuse numbers from the private log.

Format:

```
## ADR N: Title
- Date: YYYY-MM-DD
- Status: Accepted / Superseded / Deprecated
- Context: Why this decision was needed
- Decision: What was decided
- Consequences: Implications and follow-up actions
```

---

## ADR 22: Ray-March for Wall Hit Detection in Hitscan

- Date: 2026-04-26
- Status: Accepted
- Context: To spawn a wall puff at the trace endpoint, `weapon_system::fire` needs the actual impact point against the level grid when the trace doesn't terminate on an enemy. A closed-form line-vs-grid intersection (DDA, slab method) would give an exact, branch-free hit point in `O(grid traversal)` time.
- Decision: Use a fixed-step ray march along the firing direction with `TRACE_STEP = 0.1` tile, querying `level.is_wall(probe)` until either a wall is hit or `RANGE` is exceeded. Each shot performs at most `RANGE / TRACE_STEP = 20480` iterations in the worst case, but the typical case (~10–15 tiles to a wall) terminates in ~100–150 iterations.
- Consequences: Implementation is short and unmistakably correct. Sub-tile accuracy is bounded by the step size (0.1 tile = 3.2 px), good enough for a top-down 2D puff. The puff position can land slightly past the wall surface but inside the same tile; visually indistinguishable. If we later need surface-aligned puffs (decals, normal-aware effects) or longer ranges, switching to a DDA traversal is a localized change inside `fire`.

---

## ADR 23: Spawn Corpse on the Tick After Death, Not Inside `take_damage`

- Date: 2026-04-26
- Status: Accepted
- Context: When the lethal hit lands, `weapon_system::fire` already holds `&mut VisualEffects` (to spawn the muzzle flash, tracer, and blood splat) and calls `enemy.take_damage(damage)`. Spawning the corpse synchronously inside `take_damage` would require `take_damage` to also receive `&mut VisualEffects`, which forces every caller of `take_damage` (current and future) into the same borrow shape and complicates the AI module's API.
- Decision: `take_damage` only flips a `just_died` flag on the enemy. The next call to `enemy.update(..., effects, dt)` consumes the flag and spawns the corpse via the visual-effects aggregate it already borrows. The first such `update` call is the one immediately following the lethal frame in `GameState::update`.
- Consequences: Borrow graph stays simple — `take_damage` keeps a small signature, and only `update` (which already takes `effects`) writes to the effects list. The cost is a single-frame delay (~16 ms at 60 FPS) between the lethal hit and the corpse appearing, well below the perceptual threshold and masked by the death-fade effect. Tests in `enemy_logic.rs` cover the spawn-on-update behavior.

---

## ADR 24: Software Alpha Blending for the Damage-Tint Overlay

- Date: 2026-04-26
- Status: Accepted
- Context: minifb's `update_with_buffer` takes a `&[u32]` in `0x00RRGGBB` format with no alpha channel — there is no native compositor or blend-state API. The damage-tint overlay needs to darken the frame toward red proportionally to a discrete tint level (1–8), and that effect must respect content underneath rather than fully painting it red.
- Decision: After all opaque draws complete (per the back-to-front order in `40_visual_feedback.md`), iterate the buffer once and replace each pixel with `out = out * (1 - a) + tint * a` per channel, where `a = (level / DAMAGE_TINT_LEVELS) * DAMAGE_TINT_MAX_ALPHA`. Implemented in `Renderer::apply_damage_tint`. Skipped entirely when `level == 0`.
- Consequences: One full pass over `WINDOW_WIDTH * WINDOW_HEIGHT = 307_200` pixels per frame when the tint is active. At 60 FPS this is ~18.4 M f32 multiplies/sec — negligible on any modern CPU and contained in a hot, cache-friendly loop. The overlay is the last visual layer (per render-order spec), so it tints corpses, effects, the player, and the exit marker uniformly. Skipping the pass entirely at level 0 means undamaged play has zero overhead.
