# Raycaster Renderer Specification

## Overview

This specification defines a column-based first-person renderer that draws walls, a flat floor, and a flat ceiling into the same `Vec<u32>` framebuffer used by the existing top-down renderer. It is the first step in a multi-slice migration that will eventually replace the top-down view with a first-person view authentic to the genre.

This slice (1 of 6) covers:
- A new `raycaster` module that owns the column-based projection math and a grid-DDA wall traversal over `level_data::Level`.
- A `--render-mode={topdown|raycaster}` CLI flag, defaulting to `topdown`, that selects which renderer the binary calls per frame.
- A floor-plus-ceiling split (two solid colors, one above the horizon and one below), no entities, no sprites.

Subsequent slices add: sprites and projectiles (slice 2), first-person muzzle/tracer/impact effects (slice 3), the FPS-specific HUD layout (slice 4), the default flip from `topdown` to `raycaster` (slice 5), and removal of the top-down code path (slice 6). Each slice is intentionally small so any single PR is easy to review and revert.

The HUD (top-left health bar + ammo pane, [`50_hud.md`](50_hud.md)) and the game-over border ([`25_game_tuning.md § Visual`](25_game_tuning.md#visual)) draw unchanged on top of the framebuffer in both modes; this spec does not touch their behavior.

Source: [`knowledge/raycaster_renderer.md`](../knowledge/raycaster_renderer.md). Per-row constants and color values are defined by name in [`25_game_tuning.md § Renderer (Raycaster)`](25_game_tuning.md#renderer-raycaster); this spec only refers to constants by name.

## Design Goals

- **Authentic projection.** The wall column heights come from a focal-length / perpendicular-distance formula with explicit fisheye correction, identical (up to fixed-point rounding) to the reference's column projection math (knowledge § Column Projection Model, § Perpendicular Distance, § Fisheye Correction). The pinhole-camera "looks-like-a-real-FPS" feel is preserved.
- **No new world representation.** The world is the existing `level_data::Level` — a `width × height` `Vec<Vec<Tile>>` grid where `Tile::Wall` is solid. The renderer walks this grid via DDA; no BSP tree, no portal data, no sector/sub-sector structures.
- **No new asset pipeline.** Walls are flat-color (NS/EW shading + distance attenuation), not textured. Floor and ceiling are flat colors split at the horizon. Texture mapping is deferred (knowledge § Deferred).
- **Default off.** The default CLI mode remains `topdown`. Every existing autopilot scenario and the canonical PR-preview GIF continue to render the top-down view byte-for-byte unchanged in this slice. Switching the default is slice 5; removing the top-down code path is slice 6.

## Generation Default Deviation: Grid-DDA in place of BSP Traversal

Knowledge § Wall Traversal Strategy describes the reference's binary space partition (BSP) tree as the canonical wall-traversal strategy. The same knowledge entry also describes the grid-DDA alternative as the natural choice for a tile-grid world (knowledge § Wall Traversal Strategy → "Alternative — grid-DDA"), explicitly noting that "both traversal strategies produce identical projection output up to per-pixel rounding".

**This spec uses grid-DDA, not BSP.** Rationale:

- The project's `level_data::Level` is a fixed `GRID_WIDTH × GRID_HEIGHT` (20 × 15) `Vec<Vec<Tile>>` (`level_data` contract § Level). It has no line-and-sector data, no precomputed BSP tree, no two-sided portal lines, and no varying floor / ceiling heights — all of the world-representation features that motivate BSP traversal in the reference are absent.
- Knowledge explicitly bounds the cost: "DDA cost: one step per tile boundary crossed, so cost per column is O(map diagonal) worst case; a 20×15 map has ≤ 35 steps per column. For 320 columns this is 11 200 steps per frame, trivial." (knowledge § Wall Traversal Strategy → Constants.)
- Adding a BSP precompute step would require either authoring it offline (no asset pipeline; spec/80 § Dependencies forbids new asset crates) or computing it at startup from the tile grid (a complete inversion of effort to recover the simpler representation we already have).

This is a deliberate generation-default deviation that cites [`knowledge/raycaster_renderer.md § Wall Traversal Strategy`](../knowledge/raycaster_renderer.md#wall-traversal-strategy). The projection math (§ Column Projection Model, § Perpendicular Distance, § Fisheye Correction) is preserved unchanged — only the traversal strategy is substituted, and the substitution is one of the two strategies knowledge explicitly endorses for the underlying world representation.

## Behaviors

### Render Mode Selection

**Trigger:** `main.rs` parses CLI flags via `std::env::args` ([`80_generation_rules.md § Dependencies`](80_generation_rules.md#dependencies)).

**Effect:** A `RenderMode` enum value is computed once at startup and used to dispatch each frame's draw call to either the top-down `renderer::draw` or the raycaster pipeline.

**Rules:**
- The flag is `--render-mode <mode>` where `<mode>` is `topdown` or `raycaster`. Order does not matter relative to `--autopilot` and `--record-frames`.
- Default (flag absent): `RenderMode::Topdown`. Every existing scenario, every existing autopilot replay, and the canonical PR-preview GIF must render byte-for-byte identically with the flag absent.
- Unknown value (e.g. `--render-mode foo`) or missing argument (`--render-mode` with no value) prints usage to stderr and exits with code `2`, matching the existing `--autopilot <path>` / `--record-frames <path>` failure mode (`ir/contracts/_shared.yaml § main_cli § argv_parser`).
- The flag has no effect on `game_loop::update`, on bot input, on RNG seeding, or on the simulation step. It selects only which draw pipeline runs after the per-frame update.

### Per-Frame Draw Dispatch (Raycaster Mode)

**Trigger:** Every frame in `--render-mode=raycaster`, after `game_loop::update` returns and before `window.update_with_buffer`.

**Effect:** The framebuffer is filled via `raycaster::draw(&mut framebuffer, &level, &player)`, then the existing HUD and game-over border draw on top.

**Rules:**
- `raycaster::draw` writes every pixel of the `WINDOW_WIDTH × WINDOW_HEIGHT` framebuffer (no read-modify-write of unaffected regions). The split is:
  - Above the horizon row (`y < HORIZON_Y`): solid `RAYCASTER_CEILING_COLOR`.
  - At and below the horizon row (`y >= HORIZON_Y`): solid `RAYCASTER_FLOOR_COLOR`, except where covered by a wall column.
- For each screen column `x in 0..WINDOW_WIDTH`, the raycaster computes:
  1. The per-column ray angle `theta = player.facing + column_angle_offset[x]`, where `column_angle_offset[x]` is derived from the FOV and column count (see § Column Projection below).
  2. A grid-DDA walk from `player.pos` along `theta` until the ray enters a tile where `level_data::is_wall` is true OR the per-column ray length reaches `RAYCASTER_MAX_DEPTH`.
  3. The perpendicular distance `perp_dist` (the axis-projected distance — knowledge § Perpendicular Distance, § Fisheye Correction "grid-walk implementation").
  4. A wall column height `column_h_px = (WALL_HEIGHT_TILES * focal_px) / perp_dist`, clamped to `[1, WINDOW_HEIGHT]`. Centered vertically on `HORIZON_Y` (no view-pitch — knowledge § FOV, Aspect, and the Implicit Pinhole Camera).
  5. A shaded wall color: starting from `RAYCASTER_WALL_COLOR_NEAR`, multiply each channel by `(1 - min(perp_dist / RAYCASTER_MAX_DEPTH, 1.0))` interpolated toward `RAYCASTER_WALL_COLOR_FAR`. If the ray entered the tile crossing a north-south boundary (an "EW wall" in knowledge § NS-vs-EW Wall Shading), the color is darkened by `RAYCASTER_NSEW_DARKEN_FACTOR`; otherwise it is left at the nominal shade. (Pick one axis convention and use it consistently — knowledge § NS-vs-EW Wall Shading allows either.)
  6. The framebuffer column is written: rows `[0, ceiling_top)` ← `RAYCASTER_CEILING_COLOR`, rows `[ceiling_top, floor_top)` ← shaded wall color, rows `[floor_top, WINDOW_HEIGHT)` ← `RAYCASTER_FLOOR_COLOR`. `ceiling_top = HORIZON_Y - column_h_px / 2`, `floor_top = HORIZON_Y + column_h_px / 2`, both clamped to `[0, WINDOW_HEIGHT]`.
- If the DDA walk reaches `RAYCASTER_MAX_DEPTH` without hitting a wall, the column is filled with ceiling above the horizon and floor below — no wall slice is drawn. This is the far-clip case (knowledge § Max Render Distance / Far Clipping).
- After `raycaster::draw` returns, the existing HUD draw path (`renderer::draw_hud` or its current equivalent) runs unchanged. The game-over border (if `game_over.is_some()`) also draws unchanged after the HUD.
- Sprites, projectiles, pickups, corpses, blood splats, wall puffs, muzzle flashes, tracers, the player damage tint, the pickup tint, the player disc, the direction line, and the exit marker are **not** rendered in this slice. These are added in slice 2 (entities/sprites), slice 3 (FPS-specific effects), and slice 4 (FPS HUD layout). The per-frame `VisualEffects` continues to tick (game_loop owns it; raycaster does not read it this slice).

### Column Projection

**Trigger:** Every column of every raycaster-mode frame; `column_angle_offset[x]` is precomputed once at startup.

**Effect:** Each screen column `x` corresponds to one ray direction sampled from the horizontal FOV (knowledge § Column Projection Model).

**Rules:**
- Horizontal FOV is `RAYCASTER_FOV_RADIANS`. The reference uses `pi/2` (90°) which is the fixed value pinned in spec/25; the projection math here works for any FOV ≤ `pi - epsilon` (knowledge § FOV, Aspect, and the Implicit Pinhole Camera).
- Per-column angle offset (derived once): `column_angle_offset[x] = atan2((x - WINDOW_WIDTH/2), focal_px) - 0` for `x in 0..WINDOW_WIDTH`. The center column has zero offset.
- Focal length: `focal_px = (WINDOW_WIDTH / 2) / tan(RAYCASTER_FOV_RADIANS / 2)`. At a 90° FOV this simplifies to `focal_px = WINDOW_WIDTH / 2` (knowledge § Column Projection Model).
- Column count is `WINDOW_WIDTH` (one ray per pixel column). Coarser per-column subsampling (e.g. one ray per N columns) is **deferred** — knowledge § Column Projection Model notes the linear cost / horizontal-resolution trade-off; we pick the simplest mapping for slice 1.
- Vertical FOV is implicit: `WINDOW_HEIGHT` rows fill whatever vertical world-angle the per-row geometry produces (knowledge § FOV, Aspect, and the Implicit Pinhole Camera). View pitch is not modeled — the horizon is always at `HORIZON_Y`.

### Perpendicular Distance and Fisheye Correction

**Trigger:** Every wall hit produced by the per-column DDA walk.

**Effect:** The distance value used to scale the wall column height is the perpendicular distance from the camera to the wall's infinite line — not the Euclidean distance from the camera to the column's particular hit point (knowledge § Perpendicular Distance, § Fisheye Correction).

**Rules:**
- In a grid-DDA walk over an axis-aligned tile world, the perpendicular distance is the axis-projected ray distance: the X-component of the ray's travel if the last tile boundary the ray crossed was a vertical (NS) boundary, else the Y-component (knowledge § Perpendicular Distance "grid-walk implementation"). This is computed by tracking per-axis cumulative `t` values during the DDA walk and reading the relevant one at the hit.
- Per-column wall height: `column_h_px = (WALL_HEIGHT_TILES * focal_px) / perp_dist`, clamped to `[1, WINDOW_HEIGHT]`. The clamp serves as both a near-plane (against extremely close walls) and a soft cap at extremely large heights (knowledge § Perpendicular Distance "Per-column scale is clamped").
- Naive Euclidean distance (`sqrt(dx*dx + dy*dy)`) is **forbidden** for wall column scaling — it produces the classic fisheye bow described in knowledge § Perpendicular Distance "Feel". Use only the axis-projected component.

### NS / EW Wall Shading (Fake Directional Light)

**Trigger:** Every wall column draw.

**Effect:** Wall faces hit on a horizontal tile boundary are drawn `RAYCASTER_NSEW_DARKEN_FACTOR` darker than wall faces hit on a vertical tile boundary (knowledge § NS-vs-EW Wall Shading).

**Rules:**
- The DDA walk records the axis on which the last tile boundary was crossed before entering the wall tile. By convention in this spec, vertical-boundary hits ("NS walls") render at the nominal shade; horizontal-boundary hits ("EW walls") render at the darkened shade. The opposite convention is equally valid (knowledge § NS-vs-EW Wall Shading "Either convention works") — the spec pins one for consistency.
- Darken is implemented as a per-channel multiply (`RAYCASTER_NSEW_DARKEN_FACTOR < 1.0`), then re-packed into the `0xRRGGBB` framebuffer word. No separate lighting pass.
- Shading and distance attenuation compose: the per-distance interpolation between `RAYCASTER_WALL_COLOR_NEAR` and `RAYCASTER_WALL_COLOR_FAR` is computed first, then the NS/EW factor multiplies the result. Order matters only because multiplication is commutative; the fixed order is documented for Coder-determinism.
- Sector light levels (knowledge § Distance Attenuation "16 discrete levels") are not implemented this slice — the level has no `light` field on tiles and no sector concept (`level_data` contract § Level). All tiles render at one nominal light level. Multi-light support is deferred.

### Distance Attenuation (Fog)

**Trigger:** Every wall column draw and every floor/ceiling row (in this slice, only walls — floor and ceiling are flat colors with no distance falloff).

**Effect:** Wall colors fade from `RAYCASTER_WALL_COLOR_NEAR` toward `RAYCASTER_WALL_COLOR_FAR` as the perpendicular distance approaches `RAYCASTER_MAX_DEPTH` (knowledge § Distance Attenuation).

**Rules:**
- The interpolation factor is `t = min(perp_dist / RAYCASTER_MAX_DEPTH, 1.0)`. Per-channel: `out = lerp(near, far, t)`.
- The reference's table-based 32-brightness-step colormap (knowledge § Distance Attenuation "32 brightness steps") is **simplified** to a continuous lerp here. The visual difference is imperceptible at our framebuffer's color depth and saves an asset pipeline; the substitution is a deliberate generation-default. Adding a colormap-style discrete-step palette is deferred to a future slice if and when palette assets are introduced.
- The `extra light` per-frame bias (knowledge § Distance Attenuation "extra light bias") is not implemented — we have no muzzle-pulse trigger in this slice (the FPS-specific muzzle-flash effect is slice 3).
- Floors and ceilings have no distance attenuation in this slice (flat colors, no per-row distance computation). Knowledge § Floor and Ceiling Treatment "Optional: still apply per-row distance attenuation to the flat colour for a 'fog' effect" is deferred.

### Floor and Ceiling Treatment

**Trigger:** Every column of every raycaster-mode frame.

**Effect:** Rows above `HORIZON_Y` are filled with `RAYCASTER_CEILING_COLOR`; rows at/below `HORIZON_Y` are filled with `RAYCASTER_FLOOR_COLOR`, except where covered by a wall column (knowledge § Floor and Ceiling Treatment "simplified flat-colour" alternative).

**Rules:**
- The horizon row is `HORIZON_Y = WINDOW_HEIGHT / 2` (no view pitch — knowledge § FOV, Aspect, and the Implicit Pinhole Camera).
- The reference's textured horizontal-span technique (knowledge § Floor and Ceiling Treatment "Rules — textured floor/ceiling") is **deferred**: we have no texture asset pipeline (spec/80 § Dependencies) and the simplified flat-colour alternative is explicitly endorsed as an equivalent (knowledge § Floor and Ceiling Treatment "Rules — simplified flat-colour").
- Floor and ceiling colors must be visually distinct from each other and from wall colors so the horizon line and the wall silhouettes both read at a glance. Spec/25 pins specific values; the rationale ("contrasting hues for floor vs ceiling so the horizon line is unambiguous" — knowledge § Floor and Ceiling Treatment "Feel") is captured there.

### Far Clipping

**Trigger:** A per-column DDA walk that does not hit a wall within `RAYCASTER_MAX_DEPTH`.

**Effect:** The column renders as floor + ceiling only; no wall slice (knowledge § Max Render Distance / Far Clipping).

**Rules:**
- `RAYCASTER_MAX_DEPTH` is in tile units. In the project's 20 × 15 grid, the diagonal is `sqrt(20² + 15²) ≈ 25` tiles, so a 32-tile far clip means the cap rarely fires for level interiors but bounds DDA cost in case a wall is missing or the player ends up outside the grid (`level_data::is_wall` returns `true` for out-of-bounds tiles, so this is defense-in-depth).
- The far clip is a hard upper bound on the DDA step count per column. Combined with the 20 × 15 grid bound (≤ ~35 steps per column at the worst diagonal), per-column DDA is `O(min(grid_diagonal, RAYCASTER_MAX_DEPTH))`. Per-frame cost is `WINDOW_WIDTH × O(grid_diagonal)`; knowledge § Wall Traversal Strategy bounds this at "trivial" for our grid size and column count.

## State

The raycaster is **stateless** — it owns no per-frame mutable state. Each call to `raycaster::draw` reads `level` and `player` (read-only borrows) and writes the framebuffer. The per-column angle-offset table is a private constant precomputed at compile time (or once at startup if floating-point trig prevents `const fn`).

The player's `pos` and `facing` are already tracked by `player_state::Player` (`player_state` contract § Player). No new field is added for raycaster mode — the existing top-down renderer reads exactly the same fields.

## Interactions

### With main.rs

- `main.rs` parses `--render-mode` from `std::env::args`, stores the result as `RenderMode`, and branches per-frame on the value.
- `main.rs` is the only consumer of `RenderMode`. The flag is not threaded through `game_loop::update`, `autopilot::bot_step`, or any per-frame gameplay path.

### With renderer (top-down)

- The top-down renderer (`renderer::draw`) is unchanged in this slice — its signature, its layer order, and its pixel output remain exactly as documented in `ir/contracts/renderer.yaml`. The `--render-mode=topdown` mode dispatches to it byte-for-byte unchanged.
- In `--render-mode=raycaster` mode, `renderer::draw` is **not called for the world layers**; the raycaster fills the framebuffer instead. The HUD and game-over border (currently invoked from inside `renderer::draw`) must remain reachable. Two equally valid implementation shapes (Coder degree of freedom):
  - (a) Split the existing `renderer::draw` into `renderer::draw_world` + `renderer::draw_hud` + `renderer::draw_game_over_border`, and `main.rs` composes them per mode.
  - (b) Keep `renderer::draw` monolithic for top-down mode, expose `renderer::draw_hud` + `renderer::draw_game_over_border` as separate public entry points, and have `main.rs` call those directly after `raycaster::draw`.
  Either shape preserves the contract that the HUD and game-over border draw last and identically in both modes.

### With level_data

- The raycaster reads `level.width`, `level.height`, and calls `level_data::is_wall(level, tile_x, tile_y)` for the DDA traversal. No new `level_data` API is added.
- Out-of-bounds tiles read as walls (`level_data::is_wall` boundary-safe contract), so a player who somehow exits the grid sees solid wall in every direction — the renderer terminates cleanly.

### With player_state

- The raycaster reads `player.pos` (`Vec2`, tile units) and `player.facing` (radians). No mutation. No new `player_state` API is added.
- `player.alive`, `player.health`, `player.ammo`, `player.damage_count`, etc. are not consumed by the raycaster — they remain consumed by the HUD and (in slice 3) the FPS effects.

### With game_loop, autopilot, weapon_system, enemy_logic, visual_effects, frame_recorder, input_controller, presentation

- Untouched in this slice. The raycaster runs entirely after `game_loop::update` returns; no per-frame gameplay path consults the renderer.
- `frame_recorder` continues to dump the raw BGRA framebuffer regardless of which renderer produced it (specs/35 § Frame Recording Format). Determinism follows from the raycaster being a pure function of `(level, player)` plus the precomputed angle-offset table.

## Constraints

### Invariants

- `--render-mode=topdown` (the default) is byte-for-byte identical to the pre-slice behavior. Every existing autopilot scenario, the canonical PR-preview GIF (`tests/level/local_chase_obstacle.yaml`, specs/35 § Test Scenario Suitability for Demo), and every regression scenario in `tests/**/*.yaml` produces an unchanged frame stream.
- `--render-mode=raycaster` produces a framebuffer in which every pixel is written exactly once per frame (no uninitialized regions). The HUD and game-over border (if active) draw on top.
- The raycaster does not allocate per frame. The angle-offset table is allocated once at startup. Per-column DDA state is stack-local.
- The raycaster does not read or modify `VisualEffects`, the `enemies` slice, the per-frame `frames` counter, or any other gameplay state. Only `level` and `player` are consumed.
- The `--render-mode` flag has no effect on RNG seeding, on simulation `dt`, on bot input, or on `game_loop::update`. The simulation is identical between modes; only the draw output differs.

### Determinism

The raycaster is a pure function of `(level, player)` plus compile-time constants. Demo recordings inherit determinism from the existing chain (specs/35 § Determinism): fixed `dt`, fixed RNG seeds, fixed framebuffer format. The raycaster adds no new sources of randomness.

The angle-offset table, if computed at startup via `f32::tan` / `f32::atan2`, must produce the same bit pattern across runs of the same binary on the same target. Floating-point trig in `core` is deterministic per IEEE-754 on the target architectures we ship to (x86-64 Linux, the only platform exercised by `pr.yml`). If a future port targets a platform where this is not true, the table can be precomputed at build time via `build.rs` and embedded as a `&'static [f32]`; this is **deferred** until needed.

### Aspect Ratio

The window is 640 × 480 (`WINDOW_WIDTH × WINDOW_HEIGHT`, presentation contract § public_constants), a 4:3 aspect with square pixels. Knowledge § FOV, Aspect, and the Implicit Pinhole Camera describes the reference's non-square 320 × 200 pixels; we pick square pixels because that is what minifb provides. The vertical FOV at 90° horizontal + 4:3 square pixels is approximately 75° (knowledge same § "Constants — Vertical FOV ≈ 75° at 4:3 with square pixels"). No deliberate squash to mimic the reference's non-square-pixel look — that would require scaling the per-row geometry and is deferred.

## Test Scenarios

This slice does NOT add a new autopilot fixture. The default `--render-mode=topdown` remains exercised by every existing fixture (`tests/combat/*.yaml`, `tests/level/*.yaml`); switching to `--render-mode=raycaster` does not change any scenario's pass/fail outcome (the bot drives the simulation, not the renderer). A smoke test for the `raycaster` mode at the binary level is the slice-1 manual verification step — `cargo run --release --manifest-path generated/game/Cargo.toml -- --render-mode=raycaster` should open a window showing flat-color walls + floor + ceiling with no panic.

A unit-test sketch lives in `ir/contracts/raycaster.yaml § notes`; the Coder may add `#[cfg(test)]` tests that:

1. Verify the column-angle-offset table has zero offset at the center column and symmetric magnitudes at edge columns.
2. Verify a single-tile-wide wall directly in front of the player produces a non-zero column at the center of the framebuffer and zero columns at the extreme edges (DDA traversal sanity).
3. Verify the perpendicular-distance computation matches `(player.pos - hit_pos).dot(camera_forward)` for a known camera angle (fisheye-correction sanity).

These are Coder-internal regression tests; they are not asserted by `autopilot::run_all_scenarios`.

## Implementation Status

**Implemented (after slice 1 lands):**
- `--render-mode={topdown|raycaster}` CLI flag parsed via `std::env::args`, default `topdown`.
- `raycaster` module with column-based DDA wall traversal over `level_data::Level`.
- Wall column projection with perpendicular distance and fisheye correction.
- NS / EW wall shading.
- Distance-attenuated wall color (continuous lerp between near and far).
- Flat-color floor and ceiling split at `HORIZON_Y = WINDOW_HEIGHT / 2`.
- Far-clip at `RAYCASTER_MAX_DEPTH`.
- HUD and game-over border draw on top of the raycaster framebuffer (delegating to the existing renderer's HUD path).
- `RenderMode` selection consumed only by `main.rs`; gameplay simulation unchanged.

**Deferred:**
- **Sprites and projectiles** in raycaster mode (slice 2). No live enemies, no corpses, no muzzle flashes, no tracers, no wall puffs, no blood splats, no pickups, no exit marker, no player disc, no direction line are drawn.
- **First-person muzzle/tracer/impact effects** (slice 3) — extra-light bias on muzzle discharge, world-brightness pulse, first-person-style impact sparks.
- **FPS-specific HUD layout** (slice 4) — bottom chrome strip, crosshair. The current top-left bar + digits HUD draws unchanged in both modes for slices 1–3.
- **Default flip from `topdown` to `raycaster`** (slice 5).
- **Removal of the top-down code path** (slice 6).
- **Textured walls** (knowledge § Deferred — Texture mapping for walls).
- **Textured floors and ceilings** (knowledge § Deferred — Texture mapping for floors and ceilings).
- **Sky as a special floor/ceiling case** (knowledge § Deferred).
- **Portal / window walls (two-sided lines)** (knowledge § Deferred — moot for our solid/empty tile world).
- **Sector light levels and the precomputed colormap table** (knowledge § Distance Attenuation 32-brightness-step palette) — replaced by a continuous lerp this slice; revisit when textures and palettes are introduced.
- **`extra light` per-frame bias** for muzzle-pulse brightening (knowledge § Distance Attenuation) — moves into slice 3 with the FPS effects.
- **View pitch / vertical look** (knowledge § FOV, Aspect, and the Implicit Pinhole Camera) — out of scope; would require Y-shearing or a true perspective Y projection.
- **Coarser per-column subsampling** (one ray per N columns) — knowledge § Column Projection Model notes the trade-off; the simplest (one ray per pixel column) is picked here.
- **Discrete-step color attenuation** (knowledge § Distance Attenuation 32 brightness steps) — revisit when palette assets are introduced.
- **Floor / ceiling distance attenuation** (knowledge § Floor and Ceiling Treatment "Optional: still apply per-row distance attenuation").
- **Non-square pixel aspect compensation** (knowledge § FOV, Aspect, and the Implicit Pinhole Camera) — we render at 4:3 square pixels.
- **Build-time precomputation of the angle-offset table** (`build.rs`) — only needed if cross-platform float-trig drift becomes observable.

## Related

- [`knowledge/raycaster_renderer.md`](../knowledge/raycaster_renderer.md) — knowledge basis for column projection, perpendicular distance, fisheye correction, NS/EW shading, distance attenuation, floor/ceiling treatment, FOV, far clipping, and traversal strategy.
- [`25_game_tuning.md § Renderer (Raycaster)`](25_game_tuning.md#renderer-raycaster) — numeric constants for FOV, max depth, NS/EW darken factor, near/far wall shade, floor/ceiling colors, horizon row, and the `--render-mode` flag default.
- [`10_system_model.md`](10_system_model.md) — system-level mention of the new `raycaster` module alongside `presentation` / `renderer`.
- [`80_generation_rules.md § Dependencies`](80_generation_rules.md#dependencies) — `std::env::args` constraint for CLI parsing; no new crates.
- [`ir/module_plan.yaml`](../ir/module_plan.yaml) — module-graph entry for `raycaster`.
- [`ir/contracts/raycaster.yaml`](../ir/contracts/raycaster.yaml) — public API of the raycaster module.
- [`ir/contracts/_shared.yaml § main_cli`](../ir/contracts/_shared.yaml) — `--render-mode` flag and per-mode dispatch behavior.
- [`ir/contracts/renderer.yaml`](../ir/contracts/renderer.yaml) — top-down renderer is gated by the new flag; HUD + game-over border draw on top in both modes.
- [`50_hud.md`](50_hud.md) — HUD layout (unchanged in this slice; renders on top of the raycaster framebuffer).
- [`35_demo_mode.md`](35_demo_mode.md) — demo mode and frame recording (unchanged; raycaster mode produces a deterministic frame stream just like topdown).
