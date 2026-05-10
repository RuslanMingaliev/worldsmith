# Raycaster Renderer Specification

## Overview

This specification defines a column-based first-person renderer that draws walls, a flat floor, a flat ceiling, and screen-aligned billboards for world entities (live enemies, dying enemies, persistent corpses, blood splats, pickups) into the same `Vec<u32>` framebuffer used by the existing top-down renderer. It is the first step in a multi-slice migration that will eventually replace the top-down view with a first-person view authentic to the genre.

This slice (2 of 6) covers:
- A `raycaster` module that owns the column-based projection math, a grid-DDA wall traversal over `level_data::Level`, a per-column wall-depth (z-buffer-equivalent) array written during the wall pass, and a back-to-front sprite pass that consults that array for per-column occlusion (knowledge: `raycaster_sprites.md` § Per-Column Wall Depth (Z-Buffer Equivalent), § Sort Order: Back-to-Front).
- The slice-1 `--render-mode={topdown|raycaster}` CLI flag is unchanged; default remains `topdown`.
- The slice-1 floor-plus-ceiling split is unchanged.
- A new sprite pass that projects the entity lists owned by `game_loop::GameState` (live enemies, the persistent `VisualEffects` entries — `EnemyDeathFade`, `EnemyCorpse`, `BloodSplat` — and active `Level::pickups`) into screen-aligned billboards, draws them as flat-color rectangles centered on the horizon, and clips each sprite column against the per-column wall-depth array (knowledge: `raycaster_sprites.md` § Per-Sprite Scale and Screen-Space X-Range, § Per-Column Height and Vertical Clip, § Flat-Color vs Textured Choice).

Subsequent slices add: first-person muzzle/tracer/impact effects (slice 3), the FPS-specific HUD layout (slice 4), the default flip from `topdown` to `raycaster` (slice 5), and removal of the top-down code path (slice 6). Each slice is intentionally small so any single PR is easy to review and revert.

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

**Effect:** The framebuffer is filled via `raycaster::draw(&mut framebuffer, &level, &player, &enemies, &fx)` (full signature in `ir/contracts/raycaster.yaml`), then the existing HUD and game-over border draw on top.

**Rules:**
- `raycaster::draw` writes every pixel of the `WINDOW_WIDTH × WINDOW_HEIGHT` framebuffer (no read-modify-write of unaffected regions). The split is:
  - Above the horizon row (`y < HORIZON_Y`): solid `RAYCASTER_CEILING_COLOR`.
  - At and below the horizon row (`y >= HORIZON_Y`): solid `RAYCASTER_FLOOR_COLOR`, except where covered by a wall column.
- The raycaster runs in two passes per frame, in this order:
  1. **Wall pass** — fills the framebuffer with ceiling, walls, and floor, AND populates a per-column wall-depth array `wall_depth: [f32; WINDOW_WIDTH]` (see § Sprites and Billboards → Per-Column Wall Depth Z-Buffer below).
  2. **Sprite pass** — projects the entity lists (live enemies, the persistent VisualEffects sprite-class entries — `EnemyDeathFade`, `EnemyCorpse`, `BloodSplat` — and active `level.pickups`) into screen-aligned billboards, sorts them back-to-front by forward distance, and overwrites framebuffer pixels per column where the sprite's forward distance is strictly less than that column's `wall_depth[x]` (see § Sprites and Billboards below).
- For each screen column `x in 0..WINDOW_WIDTH`, the wall pass computes:
  1. The per-column ray angle `theta = player.facing + column_angle_offset[x]`, where `column_angle_offset[x]` is derived from the FOV and column count (see § Column Projection below).
  2. A grid-DDA walk from `player.pos` along `theta` until the ray enters a tile where `level_data::is_wall` is true OR the per-column ray length reaches `RAYCASTER_MAX_DEPTH`.
  3. The perpendicular distance `perp_dist` (the axis-projected distance — knowledge § Perpendicular Distance, § Fisheye Correction "grid-walk implementation").
  4. A wall column height `column_h_px = (WALL_HEIGHT_TILES * focal_px) / perp_dist`, clamped to `[1, WINDOW_HEIGHT]`. Centered vertically on `HORIZON_Y` (no view-pitch — knowledge § FOV, Aspect, and the Implicit Pinhole Camera).
  5. A shaded wall color: starting from `RAYCASTER_WALL_COLOR_NEAR`, multiply each channel by `(1 - min(perp_dist / RAYCASTER_MAX_DEPTH, 1.0))` interpolated toward `RAYCASTER_WALL_COLOR_FAR`. If the ray entered the tile crossing a north-south boundary (an "EW wall" in knowledge § NS-vs-EW Wall Shading), the color is darkened by `RAYCASTER_NSEW_DARKEN_FACTOR`; otherwise it is left at the nominal shade. (Pick one axis convention and use it consistently — knowledge § NS-vs-EW Wall Shading allows either.)
  6. The framebuffer column is written: rows `[0, ceiling_top)` ← `RAYCASTER_CEILING_COLOR`, rows `[ceiling_top, floor_top)` ← shaded wall color, rows `[floor_top, WINDOW_HEIGHT)` ← `RAYCASTER_FLOOR_COLOR`. `ceiling_top = HORIZON_Y - column_h_px / 2`, `floor_top = HORIZON_Y + column_h_px / 2`, both clamped to `[0, WINDOW_HEIGHT]`.
  7. `wall_depth[x] = perp_dist` (knowledge: `raycaster_sprites.md` § Per-Column Wall Depth (Z-Buffer Equivalent)).
- If the DDA walk reaches `RAYCASTER_MAX_DEPTH` without hitting a wall, the column is filled with ceiling above the horizon and floor below — no wall slice is drawn — and `wall_depth[x] = RAYCASTER_MAX_DEPTH` (the far-clip sentinel; sprites at that distance or beyond do not draw, sprites closer than the far clip draw normally). This is the far-clip case (knowledge § Max Render Distance / Far Clipping; knowledge: `raycaster_sprites.md` § Per-Column Wall Depth — Initialization sentinel).
- After the wall pass, the sprite pass runs (§ Sprites and Billboards). After both passes, `raycaster::draw` returns and the existing HUD draw path (`renderer::draw_hud`) runs unchanged. The game-over border (if `game_over.is_some()`) also draws unchanged after the HUD.
- Wall puffs, muzzle flashes, tracers, the player damage tint, the pickup tint, the player disc, the direction line, and the exit marker are **not** rendered in this slice. These are added in slice 3 (FPS-specific effects) and slice 4 (FPS HUD layout). Pickup inner-detail (the red cross overlay on health pickups) is also deferred — slice 2 draws each pickup as a single flat-color rectangle.

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
- The perpendicular distance is the camera-forward projection of the ray's travel to the wall hit, i.e. `perp_dist = dot(hit_pos - player.pos, camera_forward)` where `camera_forward = (cos(player.facing), sin(player.facing))`. Equivalently, if `t` is the parametric distance from camera to hit along the ray and `angle_offset = column_angle_offset[x]` is the column's angle relative to the camera-forward direction, then `perp_dist = t * cos(angle_offset)` (knowledge § Perpendicular Distance, § Fisheye Correction).
- The choice of how `t` is recovered from the DDA walk depends on the ray parameterization. Two equivalent options:
  - **Option A (unit-direction ray):** Cast `ray_dir = (cos(player.facing + angle_offset), sin(player.facing + angle_offset))`. The DDA's matched `side_dist` value is the Euclidean distance to the hit, so the spec rule becomes `perp_dist = side_dist * cos(angle_offset)`. The `cos(angle_offset)` multiplication MUST appear explicitly in the implementation.
  - **Option B (camera-plane ray):** Cast `ray_dir = camera_forward + camera_plane * camera_x` where `camera_plane` is perpendicular to `camera_forward` with length `tan(RAYCASTER_FOV_RADIANS / 2)` and `camera_x = (2*x - WINDOW_WIDTH) / WINDOW_WIDTH ∈ [-1, 1]`. With this non-unit ray, the DDA's matched `side_dist` value equals the camera-forward projected distance directly, so `perp_dist = side_dist` with no further trig (knowledge § Perpendicular Distance "grid-walk implementation").
- Per-column wall height: `column_h_px = (WALL_HEIGHT_TILES * focal_px) / perp_dist`, clamped to `[1, WINDOW_HEIGHT]`. The clamp serves as both a near-plane (against extremely close walls) and a soft cap at extremely large heights (knowledge § Perpendicular Distance "Per-column scale is clamped").
- Naive Euclidean distance to the wall (`sqrt(dx*dx + dy*dy)` from camera to hit, equivalently `t` for a unit-direction ray with no `cos(angle_offset)` correction) is **forbidden** for wall column scaling — it produces the classic fisheye bow described in knowledge § Perpendicular Distance "Feel". The implementation must visibly apply either Option A's `cos(angle_offset)` multiplication or Option B's camera-plane ray construction; raw DDA `side_dist` from a unit-direction ray must not flow into `column_h_px` unmodified.

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

### Sprites and Billboards

**Trigger:** Every raycaster-mode frame, after the wall pass populates `wall_depth[]` and writes the wall + floor + ceiling layers.

**Effect:** Each world-space entity from the per-frame entity lists (live enemies, dying-enemy fade `Effect`s, persistent corpse `Effect`s, blood-splat `Effect`s, and active `Pickup`s) is projected into a screen-aligned billboard and drawn as a flat-color rectangle, with per-column occlusion against the wall pass's depth array and back-to-front compositing among sprites (knowledge: `raycaster_sprites.md` § Per-Sprite Scale and Screen-Space X-Range, § Per-Column Wall Depth (Z-Buffer Equivalent), § Sort Order: Back-to-Front, § Flat-Color vs Textured Choice).

**Rules:**

#### Sprite Sources

The raycaster reads the following entity collections from the function arguments — none are added or mutated. Each enumerated below as `(source, predicate, world half-width, world half-height, color)`:

1. **Live enemies** — iterate `enemies: &[Enemy]`; include entries where `enemy.alive` is true. World half-extent is `ENEMY_RADIUS_TILES` (specs/25 § Enemy). Color is `COLOR_PAIN_FLASH` if `enemy.pain_flash_remaining > 0.0`, else `COLOR_ENEMY` (specs/25 § Visual + § Enemy Pain Flash; matches the topdown renderer's pain-flash override per `ir/contracts/renderer.yaml`).
2. **Dying-enemy death fade** — iterate `fx.effects`; include entries where `kind == EffectKind::EnemyDeathFade`. World half-extent is `ENEMY_RADIUS_TILES`. Color is interpolated from `COLOR_ENEMY` toward `COLOR_CORPSE` by `1.0 - (eff.lifetime_remaining / ENEMY_DEATH_FADE_DURATION)` (so a fresh effect renders at `COLOR_ENEMY` and fades to `COLOR_CORPSE` as it expires, matching the topdown renderer's death-fade pipeline per `ir/contracts/renderer.yaml`).
3. **Enemy corpses** — iterate `fx.effects`; include entries where `kind == EffectKind::EnemyCorpse`. World half-extent is `ENEMY_CORPSE_RADIUS / TILE_SIZE` (specs/25 § Enemy Death Visual; px-to-tile conversion). Color is `COLOR_CORPSE`.
4. **Blood splats** — iterate `fx.effects`; include entries where `kind == EffectKind::BloodSplat`. World half-extent is `BLOOD_RADIUS / TILE_SIZE` (specs/25 § Blood Splat). Color is `COLOR_BLOOD`.
5. **Active pickups** — iterate `level.pickups`; include entries where `pickup.active` is true. World half-extent is `PICKUP_HEALTH_SIZE_PX / 2.0 / TILE_SIZE` for `PickupKind::Health`, `PICKUP_AMMO_SIZE_PX / 2.0 / TILE_SIZE` for `PickupKind::Ammo` (specs/25 § Pickups § Sprite Visual; px-to-tile conversion). Color is `PICKUP_HEALTH_OUTER_COLOR` (Health) or `PICKUP_AMMO_COLOR` (Ammo). The inner red cross of the topdown health pickup is **deferred** — slice 2 draws a single flat-color rectangle per pickup.

The constants `COLOR_ENEMY`, `COLOR_PAIN_FLASH`, `COLOR_CORPSE`, `COLOR_BLOOD`, `PICKUP_HEALTH_OUTER_COLOR`, `PICKUP_AMMO_COLOR`, `ENEMY_CORPSE_RADIUS`, `BLOOD_RADIUS`, `PICKUP_HEALTH_SIZE_PX`, and `PICKUP_AMMO_SIZE_PX` already exist in their owning modules (renderer / visual_effects / specs/25); the raycaster imports them rather than redefining them. `ENEMY_RADIUS_TILES` is imported from `enemy_logic`. `TILE_SIZE` is imported from `level_data`. The Coder may inline the px-to-tile arithmetic or precompute it as a module-private const — both shapes meet the spec.

#### Camera-Space Transform

For each candidate sprite (knowledge: `raycaster_sprites.md` § World → Camera-Space Transform):

- `tr = sprite.pos - player.pos`.
- `forward_dist = tr.x * cos(player.facing) + tr.y * sin(player.facing)`.
- `right_offset = tr.x * sin(player.facing) - tr.y * cos(player.facing)`. Positive `right_offset` maps to the right half of the screen.
- **Near-plane reject:** if `forward_dist < RAYCASTER_SPRITE_NEAR_PLANE`, drop the sprite (knowledge: `raycaster_sprites.md` § World → Camera-Space Transform — MINZ rationale).
- **Side-cone reject (optional fast path):** if `|right_offset| > RAYCASTER_SPRITE_SIDE_CONE_FACTOR * forward_dist`, drop the sprite. The factor is sized so any sprite on-screen passes the test; obvious off-screen sprites short-circuit the more expensive screen-x clip path. Coder degree of freedom — falling back to the full screen-x clip without the early-out is correctness-equivalent (and the side-cone constant becomes a documentation marker if the Coder picks the always-clip form).

#### Per-Sprite Scale and Screen-Space X-Range

For each sprite that survives the camera-space rejects (knowledge: `raycaster_sprites.md` § Per-Sprite Scale and Screen-Space X-Range):

- `xscale = focal_px / forward_dist`. (Same `focal_px` as the wall pass — § Column Projection.)
- `screen_x_center = (WINDOW_WIDTH as f32 / 2.0) + right_offset * xscale`.
- `half_width_px = sprite.world_half_width * xscale`.
- `half_height_px = sprite.world_half_height * xscale`.
- `x1 = (screen_x_center - half_width_px).round().clamp(0, WINDOW_WIDTH as i32 - 1) as usize`.
- `x2 = (screen_x_center + half_width_px).round().clamp(0, WINDOW_WIDTH as i32 - 1) as usize`. If `x2 < x1` after the clamp (sprite fully off-screen), the sprite is skipped.
- Vertical extent is centered on the horizon (no entity world-Z this slice — all entities are treated as standing at the camera's eye level; knowledge: `raycaster_sprites.md` § Per-Sprite Scale and Screen-Space X-Range "anchor offset"):
  - `y1 = (HORIZON_Y as f32 - half_height_px).round().clamp(0, WINDOW_HEIGHT as i32) as usize`.
  - `y2 = (HORIZON_Y as f32 + half_height_px).round().clamp(0, WINDOW_HEIGHT as i32) as usize`.
- For each column `x in x1..=x2` and the sprite's `forward_dist`, compare against `wall_depth[x]`. If `forward_dist < wall_depth[x]`, paint pixels in rows `y1..y2` with the sprite's color; otherwise skip the column (knowledge: `raycaster_sprites.md` § Per-Column Wall Depth (Z-Buffer Equivalent) — strict-less-than comparison; § Per-Column Height and Vertical Clip).

The vertical-anchor decision (center on horizon vs. floor-anchor) is a deliberate slice-2 simplification: the topdown renderer treats entities as floor-plane discs with no vertical extent, and the simplest first-person analogue is "billboard at eye level". Floor-anchored sprites (with the bottom edge sitting on the horizon for a 1-tile-tall sprite) are deferred to a future slice once entity vertical-Z is modeled (knowledge: `raycaster_sprites.md` § Open Questions — Entity vertical motion).

#### Per-Column Wall Depth Z-Buffer

A single `wall_depth: [f32; WINDOW_WIDTH]` array is the in-memory equivalent of the reference's drawseg-and-clip-array machinery for our grid-DDA traversal (knowledge: `raycaster_sprites.md` § Per-Column Wall Depth (Z-Buffer Equivalent)).

**Rules:**
- The array lives module-private inside `raycaster`. Storage is one float per column; allocation strategy is a Coder degree of freedom (`OnceLock`, lazy_static-style, or a stack-local `[f32; WINDOW_WIDTH]` rebuilt per call all satisfy the no-per-frame-Vec-allocation invariant).
- The wall pass writes `wall_depth[x] = perp_dist` after computing the wall slice for column `x`. Far-clip columns (no wall hit within `RAYCASTER_MAX_DEPTH`) write `wall_depth[x] = RAYCASTER_MAX_DEPTH`.
- The sprite pass reads `wall_depth[x]` and uses strict-less-than (`<`) comparison: at exact equality the wall wins (knowledge: § Per-Column Wall Depth — Comparison rule).
- The array is not read or modified outside the raycaster module. No public API exposes it.

#### Sort Order

Sprites are drawn back-to-front so closer billboards composite over farther ones via paint order (knowledge: `raycaster_sprites.md` § Sort Order: Back-to-Front).

**Rules:**
- After all candidates are collected (and camera-space rejects applied), sort the surviving list by `forward_dist` descending (equivalently, by `xscale` ascending — smallest xscale = farthest = drawn first).
- Walk the sorted list head-to-tail, drawing each sprite via the per-column write described above.
- A stable sort is not required (knowledge: § Sort Order — "the sort key alone is a total order on visible sprites"). The active entity count is bounded above by `2 enemies + 3 pickups + ENEMY_DEATH_FADE_DURATION × max_kill_rate corpses + BLOOD_DURATION × max_hit_rate blood splats`; for our scenarios this is well under 32 sprites/frame, so an `O(n²)` selection sort or an `O(n log n)` `Vec::sort_by` are both fine. Coder degree of freedom on sort algorithm.
- The visible-sprite cap (`MAXVISSPRITES = 128` in the reference) is not enforced as a hard limit in slice 2 — the active entity count never approaches it. If it is exceeded in a future scenario, the Coder may either grow the cap or fall back to a fixed-size buffer per `coder_degrees_of_freedom`.

#### Distance Attenuation (Sprites)

Sprite colors do **not** distance-attenuate this slice (knowledge: `raycaster_sprites.md` § Flat-Color vs Textured Choice — "Distance attenuation is optional"). Sprites paint at full saturation regardless of forward distance, so the player can identify enemies, pickups, and blood at a glance against the distance-faded wall background. Adding a sprite-fading lerp to match the wall pass is deferred to a later slice (likely paired with the sprite-texturing work in the Phase 2 asset-pipeline expansion).

#### Multi-Layer Sprite Detail

The topdown renderer draws an inner red cross overlay on health pickups (PICKUP_HEALTH_INNER_COLOR / PICKUP_HEALTH_INNER_THICKNESS_PX). The raycaster slice-2 simplification draws a single flat-color rectangle per sprite — multi-layer sprite detail is **deferred** until either (a) a per-entity-type texture asset is introduced, or (b) a parallel "draw the inner detail as a second smaller billboard" path is added. Both options are out-of-scope for slice 2; the simplification is acceptable because the white outer rectangle is already visually distinct from every other entity color in the level.

## State

The raycaster is **stateless across frames** — it owns no per-frame data that persists between `raycaster::draw` calls. Each call reads `level`, `player`, `enemies`, and `fx` (all read-only borrows) and writes the framebuffer. The per-column angle-offset table is a private constant precomputed once on first call (or at compile time if `const fn` trig becomes available). The per-column wall-depth array `wall_depth: [f32; WINDOW_WIDTH]` is module-private and is rewritten end-to-end during the wall pass of every frame; it never carries state between frames. Storage strategy for the depth array (stack-local, `OnceLock`-backed, or a lazily-initialized fixed-size array reused across calls) is a Coder degree of freedom (`ir/contracts/raycaster.yaml § notes`).

The player's `pos` and `facing` are already tracked by `player_state::Player` (`player_state` contract § Player). The enemy slice is owned by `game_loop::GameState::enemies`. The visual-effect list and pickup-tint counter are owned by `game_loop::GameState::fx`. The pickups list is owned by `level.pickups`. No new field is added in any consumer module for raycaster mode — the raycaster reads exactly the data the topdown renderer already reads.

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

### With enemy_logic

- The raycaster reads `enemy.pos`, `enemy.alive`, and `enemy.pain_flash_remaining` from each `Enemy` in the slice. No mutation. No new `enemy_logic` API is added — these are the same fields the topdown renderer already reads.
- The dying-enemy fade interpolation reads from `VisualEffects::EnemyDeathFade` entries, NOT from `enemy.death_fade_remaining`, matching the topdown renderer's pipeline (`ir/contracts/renderer.yaml § public_methods § draw notes`). Both timers tick at `dt` in lockstep so the visual result matches.
- `ENEMY_RADIUS_TILES` is imported from `enemy_logic` for the live-enemy and death-fade billboard half-extent.

### With visual_effects

- The raycaster reads `fx.effects` (a `&[Effect]` slice) and inspects each entry's `kind`, `pos`, and `lifetime_remaining`. The raycaster filters this slice for the three sprite-class effect kinds (`EnemyDeathFade`, `EnemyCorpse`, `BloodSplat`) and ignores `MuzzleFlash` / `Tracer` / `WallPuff` — those FPS-specific impact effects are deferred to slice 3.
- `fx.pickup_tint_count` is **not** read by the raycaster this slice. The pickup-tint overlay is part of the slice-3 FPS-effects work.
- `ENEMY_DEATH_FADE_DURATION`, `ENEMY_CORPSE_RADIUS`, and `BLOOD_RADIUS` are imported from `visual_effects` for the death-fade interpolation divisor and the corpse / blood-splat billboard half-extents.
- The raycaster does NOT spawn or mutate any `Effect` — it only reads them. `visual_effects::tick` continues to run from `game_loop::update` as before; the raycaster runs after that update phase per `ir/contracts/_shared.yaml § frame_update_order`.

### With renderer (color constants)

- The raycaster imports the entity color constants `COLOR_ENEMY`, `COLOR_PAIN_FLASH`, `COLOR_CORPSE`, `COLOR_BLOOD`, `PICKUP_HEALTH_OUTER_COLOR`, and `PICKUP_AMMO_COLOR` from the `renderer` module. Per `ir/contracts/_shared.yaml § intentionally_unspecified` the renderer is the canonical home for the project's RGB palette; raycaster shares the palette via constant import (a spec/80 § API Surface "constant import is fine; struct import is not" pattern).
- The raycaster does NOT consume `renderer::draw`, `renderer::draw_world`, or any other renderer entry point. The HUD layer (`renderer::draw_hud`) and game-over border (`renderer::draw_game_over_border`) are still composed by `main.rs` AFTER `raycaster::draw` returns; that dispatch shape is unchanged from slice 1.

### With level_data (additional reads from slice 1)

- In addition to the slice-1 `level.width`, `level.height`, and `level_data::is_wall(...)` traversal reads, slice 2 also reads `level.pickups` (`&[Pickup]`) for the active-pickup billboard sources, plus `TILE_SIZE` and `PICKUP_RADIUS_TILES` constants for px-to-tile conversion. No new `level_data` API is added.

### With game_loop, autopilot, weapon_system, frame_recorder, input_controller, presentation

- Untouched in this slice. The raycaster runs entirely after `game_loop::update` returns; no per-frame gameplay path consults the renderer.
- `game_loop::GameState::enemies` and `game_loop::GameState::fx` are passed by reference into `raycaster::draw` from `main.rs` — no mutation crosses back through this path.
- `frame_recorder` continues to dump the raw BGRA framebuffer regardless of which renderer produced it (specs/35 § Frame Recording Format). Determinism follows from the raycaster being a pure function of `(level, player, enemies, fx)` plus the precomputed angle-offset table.

## Constraints

### Invariants

- `--render-mode=topdown` (the default through slice 4) is byte-for-byte identical to the pre-slice behavior. Every existing autopilot scenario, the canonical PR-preview GIF (`tests/level/local_chase_obstacle.yaml`, specs/35 § Test Scenario Suitability for Demo), and every regression scenario in `tests/**/*.yaml` produces an unchanged frame stream. Slice 2 widens the raycaster's draw signature but does not change the topdown dispatch path.
- `--render-mode=raycaster` produces a framebuffer in which every pixel is written exactly once by the wall + sprite passes (sprite columns may overwrite wall pixels where the sprite is closer). The HUD and game-over border (if active) draw on top.
- The raycaster does not allocate per frame. The angle-offset table and the per-column wall-depth array are allocated once at startup (or on first call). Per-frame sprite-collection storage is either a stack-local fixed-size array (Coder degree of freedom — current per-frame entity count is bounded above by ~32) or a module-private `Vec` reused across calls; both shapes meet the no-per-frame-allocation invariant. Per-column DDA state is stack-local.
- The raycaster reads — but never mutates — `level`, `player`, `enemies`, and `fx`. It does NOT read `fx.pickup_tint_count`, the per-frame `frames` counter, `player.alive`, `player.health`, `player.ammo`, `player.damage_count`, `enemy.health`, `enemy.state`, or any other field outside the explicit sprite-source list above.
- The raycaster's sprite pass writes `wall_depth[]` exactly once per frame (during the wall pass) and reads it during the sprite pass. No external module reads or writes `wall_depth[]`.
- The `--render-mode` flag has no effect on RNG seeding, on simulation `dt`, on bot input, or on `game_loop::update`. The simulation is identical between modes; only the draw output differs. Slice 2 does not change this — adding sprite reads in `raycaster::draw` is a render-side change only.

### Determinism

The raycaster is a pure function of `(level, player, enemies, fx)` plus compile-time constants. Demo recordings inherit determinism from the existing chain (specs/35 § Determinism): fixed `dt`, fixed RNG seeds, fixed framebuffer format. The raycaster adds no new sources of randomness.

The angle-offset table, if computed at startup via `f32::tan` / `f32::atan2`, must produce the same bit pattern across runs of the same binary on the same target. Floating-point trig in `core` is deterministic per IEEE-754 on the target architectures we ship to (x86-64 Linux, the only platform exercised by `pr.yml`). If a future port targets a platform where this is not true, the table can be precomputed at build time via `build.rs` and embedded as a `&'static [f32]`; this is **deferred** until needed.

The sprite pass is order-deterministic only if the back-to-front sort is performed on a key that produces a total order on visible sprites for any input. The Coder may pick any sort function (`Vec::sort_by` over a `forward_dist`-keyed comparator with a stable secondary tie-breaker, or an `O(n²)` selection sort over the same key) — both produce identical pixel output as long as the comparator is total. If two sprites share the same `forward_dist` to the bit, the secondary tie-breaker must be deterministic (e.g. source-list index, which is itself deterministic given the upstream simulation determinism).

### Aspect Ratio

The window is 640 × 480 (`WINDOW_WIDTH × WINDOW_HEIGHT`, presentation contract § public_constants), a 4:3 aspect with square pixels. Knowledge § FOV, Aspect, and the Implicit Pinhole Camera describes the reference's non-square 320 × 200 pixels; we pick square pixels because that is what minifb provides. The vertical FOV at 90° horizontal + 4:3 square pixels is approximately 75° (knowledge same § "Constants — Vertical FOV ≈ 75° at 4:3 with square pixels"). No deliberate squash to mimic the reference's non-square-pixel look — that would require scaling the per-row geometry and is deferred.

## Test Scenarios

This slice does NOT add a new autopilot fixture. The default `--render-mode=topdown` (in effect through slice 4) remains exercised by every existing fixture (`tests/combat/*.yaml`, `tests/level/*.yaml`); switching to `--render-mode=raycaster` does not change any scenario's pass/fail outcome (the bot drives the simulation, not the renderer). A smoke test for the `raycaster` mode at the binary level is the slice manual verification step — `cargo run --release --manifest-path generated/game/Cargo.toml -- --render-mode=raycaster` should open a window showing flat-color walls + floor + ceiling AND visible flat-colored billboards (red enemy rectangles, white health pickups, yellow ammo pickup) correctly occluded by walls, with no panic.

The PR-preview demo GIF is recorded in `--render-mode=raycaster` per the slice-1 environment override (`WORLDSMITH_RENDER_MODE=raycaster` in `tooling/record_autopilot.sh` and `pr.yml`); the slice-2 acceptance criterion is that the GIF visibly shows enemy billboards. The demo scenario is `tests/level/local_chase_obstacle.yaml`, unchanged from the slice-1 baseline.

A unit-test sketch lives in `ir/contracts/raycaster.yaml § notes`. The Coder MUST keep the fisheye-correction regression test from slice 1 (item 3 below); items 1, 2, 4, and 5 are recommended but not required.

1. Verify the column-angle-offset table has zero offset at the center column and symmetric magnitudes at edge columns.
2. Verify a single-tile-wide wall directly in front of the player produces a non-zero column at the center of the framebuffer and zero columns at the extreme edges (DDA traversal sanity).
3. **(Required)** For a fixed test world with a single wall-line directly in front of the player (e.g. a horizontal wall row at known `y`), compute the wall hit point analytically for at least three non-center columns (spanning the FOV), then assert that the `perp_dist` value used internally by `raycaster::draw` for each of those columns equals `dot(hit_pos - player.pos, camera_forward)` to within a small epsilon (`1e-4`). This is the direct definitional check from § Perpendicular Distance and Fisheye Correction. A missing `cos(angle_offset)` correction (or equivalent) would make the Euclidean-distance values fail this assertion at non-center columns. The test may either expose `perp_dist` via a test-only helper function or recompute the projection from the same internal formula — but the identity itself must be asserted, not bypassed.
4. **Sprite-vs-wall occlusion sanity:** Place a wall at known `forward_dist`, then place a sprite at twice that distance behind the same column. Assert that the sprite-pass output for that column is byte-equal to the wall-pass output (sprite's per-column z-test should reject — wall wins). Then move the sprite to half the wall's distance and assert the sprite color writes through to that column.
5. **Back-to-front sort:** Project two sprites at known different `forward_dist` values whose screen-x ranges overlap; assert the closer one's color appears in the overlap region after `raycaster::draw` returns (the farther one was painted first, the closer one painted over).

These are Coder-internal regression tests; they are not asserted by `autopilot::run_all_scenarios`.

## Implementation Status

**Implemented (after slice 2 lands):**
- `--render-mode={topdown|raycaster}` CLI flag parsed via `std::env::args`, default `topdown`.
- `raycaster` module with column-based DDA wall traversal over `level_data::Level`.
- Wall column projection with perpendicular distance and fisheye correction.
- NS / EW wall shading.
- Distance-attenuated wall color (continuous lerp between near and far).
- Flat-color floor and ceiling split at `HORIZON_Y = WINDOW_HEIGHT / 2`.
- Far-clip at `RAYCASTER_MAX_DEPTH`.
- HUD and game-over border draw on top of the raycaster framebuffer (delegating to the existing renderer's HUD path).
- `RenderMode` selection consumed only by `main.rs`; gameplay simulation unchanged.
- **Per-column wall-depth z-buffer** (`wall_depth: [f32; WINDOW_WIDTH]`) populated during the wall pass, consulted during the sprite pass.
- **Screen-aligned billboard projection** for live enemies, dying-enemy death-fade effects, persistent corpses, blood splats, and active health/ammo pickups. Each entity is projected to a flat-color rectangle centered on the horizon, with per-column occlusion against `wall_depth[]` and back-to-front compositing among sprites.
- **Camera-space transform with near-plane reject** (`RAYCASTER_SPRITE_NEAR_PLANE`) for sprites.
- **Pain-flash color override** for live enemies whose `pain_flash_remaining > 0` (mirrors the topdown renderer's pain-flash treatment).
- **Death-fade color interpolation** from `COLOR_ENEMY` toward `COLOR_CORPSE` over the `EnemyDeathFade` effect lifetime.

**Deferred:**
- **Projectile sprites** — the current weapon system is hitscan-only (`ir/game_ir.yaml § combat.attack_type: hitscan`); no projectile entities exist in the world today. The sprite pass framework above is generic enough that adding a `&[Projectile]` source becomes a one-line change to the candidate-collection step when projectile combat is introduced.
- **Inner-detail multi-layer sprites** — the topdown health pickup's red cross overlay (PICKUP_HEALTH_INNER_COLOR / PICKUP_HEALTH_INNER_THICKNESS_PX) is not drawn in raycaster mode this slice; pickup billboards are single flat-color rectangles. Revisit when textured sprites are introduced.
- **Sprite distance attenuation** — sprites paint at full saturation; the wall-style lerp toward `RAYCASTER_WALL_COLOR_FAR` is not applied. Knowledge `raycaster_sprites.md` § Flat-Color vs Textured Choice flags this as "optional"; deferred until textured sprites land.
- **Floor-anchored / world-Z sprites** — sprites center vertically on the horizon (entities treated as eye-level billboards). True floor-anchoring requires an entity-vertical-Z field on `Enemy` / `Effect` / `Pickup`; deferred until any entity gains non-zero height-above-floor (knowledge `raycaster_sprites.md` § Open Questions — Entity vertical motion).
- **Eight-rotation sprite frames** — single-frame billboards only; deferred (knowledge `raycaster_sprites.md` § Sprite Rotational Frames — Generation default for a simplified renderer).
- **Sprite texturing** (column-major posts with transparent gaps) — replaced by flat-color rectangles; revisit when an asset pipeline exists.
- **First-person muzzle/tracer/impact effects** (slice 3) — extra-light bias on muzzle discharge, world-brightness pulse, first-person-style impact sparks. The `MuzzleFlash`, `Tracer`, and `WallPuff` effect kinds are explicitly skipped by the slice-2 sprite source filter.
- **Player damage tint and pickup tint overlays** (slice 3) — `player.damage_count` and `fx.pickup_tint_count` are not consumed by the raycaster this slice.
- **Player disc, direction line, and exit marker** — not rendered in first-person mode. Player position is implicit (camera origin); the exit is reachable via gameplay, not via an in-world marker. The exit-marker may return as a different visual treatment in a later slice (e.g. a colored billboard or floor decal).
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
- **Translucent / "fuzz" sprite rendering** (knowledge `raycaster_sprites.md` § Open Questions — Translucent sprite rendering) — flat-color sprites have no translucent path.
- **Per-sprite full-bright / damage-flash colormap selection** (knowledge `raycaster_sprites.md` § Deferred) — depends on the colormap-table form of distance attenuation.
- **Visible-sprite cap** (`MAXVISSPRITES = 128` in the reference) — the active entity count never approaches this in our scenarios; not enforced as a hard limit in slice 2.

## Related

- [`knowledge/raycaster_renderer.md`](../knowledge/raycaster_renderer.md) — knowledge basis for column projection, perpendicular distance, fisheye correction, NS/EW shading, distance attenuation, floor/ceiling treatment, FOV, far clipping, and traversal strategy.
- [`knowledge/raycaster_sprites.md`](../knowledge/raycaster_sprites.md) — knowledge basis for camera-space transform, per-sprite scale, screen-space x-range, per-column wall-depth z-buffer, per-column height and vertical clip, back-to-front sort, and the flat-color vs textured choice (slice 2).
- [`25_game_tuning.md § Renderer (Raycaster)`](25_game_tuning.md#renderer-raycaster) — numeric constants for FOV, max depth, NS/EW darken factor, near/far wall shade, floor/ceiling colors, horizon row, sprite near-plane, and the `--render-mode` flag default.
- [`10_system_model.md`](10_system_model.md) — system-level mention of the `raycaster` module alongside `presentation` / `renderer`.
- [`80_generation_rules.md § Dependencies`](80_generation_rules.md#dependencies) — `std::env::args` constraint for CLI parsing; no new crates.
- [`ir/module_plan.yaml`](../ir/module_plan.yaml) — module-graph entry for `raycaster`.
- [`ir/contracts/raycaster.yaml`](../ir/contracts/raycaster.yaml) — public API of the raycaster module.
- [`ir/contracts/_shared.yaml § main_cli`](../ir/contracts/_shared.yaml) — `--render-mode` flag and per-mode dispatch behavior.
- [`ir/contracts/renderer.yaml`](../ir/contracts/renderer.yaml) — top-down renderer is gated by the new flag; HUD + game-over border draw on top in both modes; raycaster reads its color constants from this module.
- [`ir/contracts/enemy_logic.yaml`](../ir/contracts/enemy_logic.yaml) — `Enemy` struct fields read by the raycaster sprite pass (pos, alive, pain_flash_remaining); `ENEMY_RADIUS_TILES` constant.
- [`ir/contracts/visual_effects.yaml`](../ir/contracts/visual_effects.yaml) — `VisualEffects`, `Effect`, `EffectKind` types read by the raycaster sprite pass; `ENEMY_DEATH_FADE_DURATION`, `ENEMY_CORPSE_RADIUS`, `BLOOD_RADIUS` constants.
- [`ir/contracts/level_data.yaml`](../ir/contracts/level_data.yaml) — `Pickup`, `PickupKind` types read by the raycaster sprite pass.
- [`50_hud.md`](50_hud.md) — HUD layout (unchanged in this slice; renders on top of the raycaster framebuffer).
- [`35_demo_mode.md`](35_demo_mode.md) — demo mode and frame recording (unchanged; raycaster mode produces a deterministic frame stream just like topdown).
