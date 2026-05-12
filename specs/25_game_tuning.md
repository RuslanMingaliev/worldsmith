# Game Tuning

## Intent

This spec captures all gameplay balance constants, visual parameters, and level layout values. Values are derived from knowledge extraction (see `knowledge/combat_balance.md`, `knowledge/enemy_types.md`, `knowledge/player_movement.md`), not invented.

## Reconcile-pass row format (for new entries)

When the Reconciler captures a new constant during a regen pass, the canonical row in this file holds **only** the value plus a ≤1-sentence rationale, and ends with `(see reconcile_log#<anchor>)`. The full audit trail — where the constant was inlined in code, what alternatives were considered, prior incarnations, the run that captured it — lives in `work/reconcile_history.md` (gitignored, accumulated locally and surfaced through PostMortem's run journal).

This split exists so this file stays *stable across a regen pass*: downstream phases (Coder, PostMortem, release_editor) re-read it on every Coder invocation, and provenance prose written by an earlier phase invalidates the prompt cache for everyone after it. See `tooling/agents/reconciler.md § Step 1` for the writer-side rule and `tooling/orchestrator_run.py § FROZEN_CONTEXT_FILES` for the cache-stability rationale.

Existing rows below this point predate the convention and are kept verbatim — they are stable and cached. The split applies to new captures from this point forward.

## Player

| Constant | Value | Source |
|----------|-------|--------|
| Health | 100 | knowledge/combat_balance.md § Damage to Player (Armor and Damage Reduction) |
| Movement model | thrust + friction | Constants (THRUST_FACTOR, FRICTION, MAX_SPEED, STOP_THRESHOLD) defined in `specs/21_player_movement.md` |
| Turn speed | 2.0 rad/sec | Tuned for 60 FPS (original was 35 ticks/sec) |
| PLAYER_RADIUS_TILES | 0.4375 | Derived from player visual radius 14 px / `TILE_SIZE` (32). Used by `player_state::collides` to size the four-corner overlap test against `level_data::is_wall`, and referenced by name in `specs/15_level_generator.md § LocalChaseObstacle` to verify gap traversability. Captured during reconcile pass — the IR contract already cited `specs/25 § Visual` as its source but no named row existed. |

## Enemy (Basic Hitscan Trooper)

### Implemented

| Constant | Value | Source |
|----------|-------|--------|
| Health | 20 | knowledge/combat_balance.md |
| Speed | 2.0 units/sec | Adapted from reference (slower than player) |
| Detection | Immediate (simplified) | Target: line of sight, no distance limit |
| Reaction delay | 0.23 seconds | Time before first attack after spotting player |
| Attack type | Contact damage | Target: hitscan at range |
| Attack damage | 3, 6, 9, 12, or 15 per hit | Formula: `(random(0..4) + 1) * 3`, mean ~9 |
| Attack cooldown | 0.54 seconds | Time between contact hits |
| ENEMY_RADIUS_TILES | 0.375 | Derived from enemy visual radius 12 px / TILE_SIZE (32). Used for collision detection in `enemy_logic.rs` and implicitly by `ENEMY_CONTACT_RANGE_TILES`. Captured during reconcile pass — was present in code but not named in spec. |
| ENEMY_CONTACT_RANGE_TILES | 0.8125 tile (= 26 px) | Derived from player + enemy visual radii in `## Visual` (14 px + 12 px) divided by `TILE_SIZE`. Specs/20 says "contact damage when within melee range" without naming a value; this range fires the hit exactly when the two discs visually touch. Captured during a reconcile pass (was inlined as a derived constant in `enemy_logic.rs`). |
| Pain chance | 78% (200/255) | Chance to enter pain/stagger state when hit |
| Pain duration | 0.17 seconds | Duration of pain stagger animation |
| AI states | Idle, Chase, Pain, Death | Target adds: Attack |

### Target (from knowledge, not yet implemented)

| Constant | Value | Source |
|----------|-------|--------|
| Attack type | Hitscan at range | knowledge/enemy_types.md |
| Attack range | 2048 map units | Same as player weapon range |
| Attack spread | +/- 22 degrees max | Triangular distribution |
| Attack sequence | 0.74 seconds | Wind-up, fire, cooldown |
| Detection | Line of sight | No distance limit |
| Idle scan period | 0.57 seconds per cycle | Two frames at 0.29s each |
| Chase cycle time | 0.91 seconds | Eight frames at ~0.11s each |
| Movement | 8-directional grid | Prefers diagonal toward player |
| Target threshold | 2.86 seconds | Stubborn pursuit duration |
| Move count | 0--15 steps | Steps before re-evaluating direction |
| Active sound chance | 1.2% per chase frame | Ambient sound |
| Radius | 20 map units | Collision size |
| Height | 56 map units | Vertical extent |
| Mass | 100 | Knockback resistance factor |
| Gib threshold | -20 HP | Extreme death on overkill |
| Drop on death | Ammo clip | Item dropped when killed |

## Weapon (Pistol -- starting weapon)

| Constant | Value | Source |
|----------|-------|--------|
| Damage | 5, 10, or 15 per shot | Formula: `5 * (random(0..2) + 1)`, mean ~10 |
| Range | 2048 map units | Effectively unlimited indoors |
| PISTOL_RANGE_TILES | 64.0 tiles | Derived from `Range` (2048 map units) at 32 px/tile (`TILE_SIZE`). The reference engine uses 32 px per tile, so 2048 / 32 = 64 tiles. Captured during a reconcile pass (was inlined as `PISTOL_RANGE_TILES` in `weapon_system.rs`); mirrors the existing `ENEMY_CONTACT_RANGE_TILES` derivation note. |
| Fire cycle | 0.54 seconds | ~1.84 shots/sec (knowledge/combat_balance.md) |
| Hit detection | Hitscan (instant) | Line trace, no projectile travel time |
| First-shot accuracy | Perfect (no spread) | First shot after pause has zero angular offset |
| IDLE_THRESHOLD_SEC | 1.0 seconds | Generation default — promotes deliberate paused single-shot to first-shot accuracy. No reference value: holding fire at the 0.54s cycle never resets to perfect aim, but a deliberate pause does. Captured during a reconcile pass (was inlined as `IDLE_THRESHOLD_SEC` in `weapon_system.rs`). |
| Refire spread | +/- 5.6 degrees max | Triangular distribution centered on aim direction |
| Melee range | 64 map units | Relevant for future melee weapons (deferred) |

### Damage Randomization

All damage uses discrete random outcomes, not a smooth curve. The pattern is `constant * (random(0..N) + 1)`, producing a small number of equally-likely damage values. This creates memorable "lucky hit" / "weak hit" moments.

For the pistol: 3 possible outcomes (5, 10, 15). Against a 20 HP enemy, this means 2-4 shots to kill with most encounters taking 2 shots. The variance keeps repeated fights from feeling mechanical.

### Accuracy Model

Accuracy uses a triangular distribution (difference of two uniform random values). Most shots cluster near the aim point, with outliers being rare. This feels more natural than uniform random spread.

- **First shot after idle**: perfectly accurate (zero spread)
- **Sustained fire (refire)**: spread applied as angular offset, +/- 5.6 degrees max for player
- **Enemy fire**: same model but with +/- 22 degrees max spread (4x wider than player)

The first-shot accuracy bonus rewards deliberate, aimed single shots over holding down fire.

### Pain/Stagger System

When a target takes damage, there is a percentage chance it enters a brief pain state (stagger). During pain, the target's current action is interrupted.

- Pain chance is checked per hit: `random(0..255) < pain_threshold`
- Basic enemy pain chance: 200/255 (~78%)
- At 78%, sustained pistol fire can effectively stun-lock basic enemies
- This gives even the weakest weapon crowd control utility

## Win/Lose

| Constant | Value |
|----------|-------|
| Exit radius | 1.0 units |
| Player dies at | 0 HP |

## Level Layout

| Property | Value |
|----------|-------|
| Grid size | 20 x 15 tiles |
| Tile size | 32 px |
| Player spawn | (2.5, 2.5) |
| Exit position | (17.5, 2.5) |
| Border | All edges are walls |

### Enemy spawns

`level_data::build_default()` populates two basic-trooper enemies (`Vec<Vec2>` order is the deterministic tie-breaker for `Scenario` targets — per `specs/30 § Targets` "enemy" resolves to the *nearest* alive enemy with ties broken by index in `enemy_spawns`):

| Order | Position (tile coords) | Rationale |
|-------|------------------------|-----------|
| 1 | (17.5, 12.5) | Existing SE-corner spawn. Kept first so it wins index-tie-breaks when both enemies are equidistant; in single-enemy fixtures (`tests/combat/kill_enemy.yaml` etc.) it is the only candidate so the resolved target is unambiguous. Generation default — no knowledge backing. |
| 2 | (4.5, 11.5) | SW spawn — geographically isolated from the spawn → enemy 1 → ammo → exit corridor used by `scavenge_run.yaml`, so it does not chase down the primary trajectory. Provides multi-enemy combat in `tests/level/local_chase_obstacle.yaml`-equivalents that target this position explicitly, and gives the recorded demo a second engagement. Generation default — no knowledge backing. |

### Interior walls

| Segment | Coordinates | Rationale |
|---------|-------------|-----------|
| Central divider (north half) | x=10, y=3..8 | Existing. Forces NS traversal in the upper half via columns 1-9 at y<3 OR columns 11-18 at y<3. |
| Mid-left horizontal | y=7, x=4..9 | Existing. Separates the lower-left pocket (around the SW health pickup) from the upper region; bot must go around via x<4 or x>9. |
| SE pocket cover | y=10, x=13..15 (Rust half-open: x=13, 14) | Two-tile horizontal cover north of the SE enemy. The bot's BFS path approaches the SE enemy from the east via column 15+ (open) rather than a straight diagonal, giving the demo a visible "round the corner" beat without changing the column-1-to-19 connectivity. Generation default — no knowledge backing. |

## Visual

| Property | Value | Color |
|----------|-------|-------|
| Window | 640 x 480 px | — |
| Wall tile | 32x32 | #404040 dark gray |
| Floor tile | 32x32 | #808080 medium gray |
| Player | radius 14px | #00FF00 green |
| Enemy | radius 12px | #FF0000 red |
| Exit marker | X shape, 20px | #00FFFF cyan |
| Direction line | 20px length | #FFFF00 yellow |
| Game over border | 10px | green tint (win) / red tint (lose) |
| GAME_OVER_BORDER_WIN_COLOR | inlined as `0x00FF80u32` in `renderer::draw` game-over arm | #00FF80 spring green — generation default. Spec described "green tint" qualitatively; this row pins the specific shade. Distinct from `COLOR_PLAYER` (`#00FF00`) and `HUD_HEALTH_COLOR_HIGH` (`#00C000`) so the border reads as a discrete UI band rather than as a player tile or HUD element. (see reconcile_log#GAME_OVER_BORDER_COLORS) |
| GAME_OVER_BORDER_LOSE_COLOR | inlined as `0xFF4040u32` in `renderer::draw` game-over arm | #FF4040 tomato red — generation default. Spec described "red tint" qualitatively; this row pins the specific shade. Lighter than `COLOR_ENEMY` (`#FF0000`) and `HUD_HEALTH_COLOR_LOW` (`#C00000`) so the lose border does not visually merge with a low-health HUD or with on-screen enemies. (see reconcile_log#GAME_OVER_BORDER_COLORS) |
| GAME_OVER_HOLD_SEC | 2.0 sec | Generation default — minimum visibility budget for the player to register the win/lose outcome before the loop exits. Rationale: without an explicit hold, the main-loop exits on the same tick the game-over flag is set, so the colored border renders for zero frames. 2 seconds is the standard retro-shooter hold; revisit if user feedback says it's too short or too long. See specs/20 § Game Over Flow. |

### Visual Feedback

Behavior spec: [`40_visual_feedback.md`](40_visual_feedback.md).
Source: `knowledge/visual_feedback.md`. Reference durations were given in 35-tick/sec ticks; values below are converted to seconds and rounded to two decimals.

#### Muzzle Flash

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| MUZZLE_FLASH_DURATION | 0.10 s | — | Adapted from pistol flash 7 tics (~0.20 s); halved for crisper top-down feel |
| MUZZLE_FLASH_COLOR | — | #FFFF80 pale yellow | Bright "full-bright" muzzle color |
| MUZZLE_FLASH_RADIUS | 6 px | — | Small filled disc at muzzle |
| MUZZLE_OFFSET | 0.5 tile (16 px at 32 px/tile) | — | Offset from player center along facing direction; expressed in world (tile) units to match weapon-system math |

#### Hit-Scan Tracer

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| TRACER_DURATION | 0.06 s | — | Short single-frame line; 2D substitute for impact spark |
| TRACER_COLOR | — | #FFFFC0 near-white | Distinct from muzzle flash, brighter |
| TRACER_THICKNESS | 1 px | — | Single-pixel line |

#### Impact: Wall Puff

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| PUFF_DURATION | 0.30 s | — | Adapted from 16 tics (~0.46 s); shortened for top-down |
| PUFF_COLOR | — | #B0B0B0 light gray | Distinct from blood, similar to wall material |
| PUFF_RADIUS | 4 px | — | Small particle |

#### Impact: Blood Splat

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| BLOOD_DURATION | 0.50 s | — | Adapted from 24 tics (~0.69 s); shortened for top-down |
| BLOOD_COLOR | — | #C00000 deep red | Visibly different hue from enemy body color |
| BLOOD_RADIUS | 6 px | — | Larger than puff, single tier (damage-tiered blood deferred) |

#### Enemy Pain Flash

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| ENEMY_PAIN_FLASH_DURATION | 0.10 s | — | Adapted from 6 tics (~0.17 s); slightly shorter than full pain duration |
| ENEMY_PAIN_FLASH_COLOR | — | #FFFFFF white | Bright tint replacing normal enemy red while flashing |

#### Player Damage Tint

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| DAMAGE_TINT_CAP | 100 | — | Mirrors reference cap (max ~100 tics @ 35 tics/sec) |
| DAMAGE_TINT_DECAY_PER_SEC | 35 units/sec | — | Linear; reference uses 1 unit/tic at 35 tics/sec |
| DAMAGE_TINT_LEVELS | 8 | — | Discrete alpha levels (0 = no overlay) |
| DAMAGE_TINT_COLOR | — | #FF0000 red | Overlay hue; alpha varies by level |
| DAMAGE_TINT_MAX_ALPHA | ~50% | — | Alpha at level 8; intermediate levels interpolate down to 0 |

Mapping: `level = ceil(damage_count * DAMAGE_TINT_LEVELS / DAMAGE_TINT_CAP)`, clamped to `[0, DAMAGE_TINT_LEVELS]`.

#### Pickup Tint

Behavior spec: [`40_visual_feedback.md § Pickup Tint Screen Flash`](40_visual_feedback.md).

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| PICKUP_TINT_PER_PICKUP | 6 | — | knowledge/visual_feedback.md § Player Damage Screen Tint (pickup-tint accumulation: +6 per pickup) |
| PICKUP_TINT_LEVEL_COUNT | 4 | — | knowledge/visual_feedback.md § Player Damage Screen Tint (pickup-tint level count: 4) |
| COLOR_PICKUP_TINT | — | #FFCC00 golden-yellow | Generation default — no knowledge backing. Knowledge describes "golden-yellow" qualitatively; hex value is a generation default chosen to be visually distinct from the ammo-pickup color (`#FFFF00`) and the muzzle-flash color (`#FFFF80`). |
| PICKUP_TINT_CAP | 6.0 | — | Generation default — one pickup fills the counter to its cap (matches PICKUP_TINT_PER_PICKUP). Knowledge does not specify the cap beyond the per-pickup accumulation. |
| PICKUP_TINT_DECAY_PER_SEC | 35 units/sec | — | Generation default — same 1-unit-per-reference-tick decay rate used by the damage tint (knowledge/visual_feedback.md § Player Damage Screen Tint: "decay by 1 per tick at 35 ticks/sec"). |
| PICKUP_TINT_MAX_ALPHA | ~30% | — | Generation default — gentler than the damage tint max (50%) to signal a positive event rather than harm. |

Mapping: `level = ceil(pickup_tint_count * PICKUP_TINT_LEVEL_COUNT / PICKUP_TINT_CAP)`, clamped to `[0, PICKUP_TINT_LEVEL_COUNT]`. Level zero means no overlay.

#### Enemy Death Visual

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| ENEMY_DEATH_FADE_DURATION | 0.40 s | — | Adapted from 25 tics (~0.71 s); shortened for snappier feel |
| ENEMY_CORPSE_COLOR | — | #602020 dark red-brown | Faded version of enemy color |
| ENEMY_CORPSE_RADIUS | 8 px | — | Smaller than live enemy (12 px); ~2/3 size, mirrors "height collapses to 1/4" intent |
| CORPSE_PERSISTENCE | until level reset | — | Permanent within a run; reference uses -1 frame duration |

#### Effect List

| Constant | Value | Source |
|----------|-------|--------|
| EFFECT_LIST_INITIAL_CAPACITY | 16 | Pre-allocation hint; not a hard cap |
| EFFECT_LIST_MAX | (none) | Effect-count culling deferred |
| PERSISTENT_LIFETIME | `f32::INFINITY` | Sentinel `lifetime_remaining` value used by corpses to mean "never expire on age"; lifetime ticking skips non-finite values |

#### Wall Hit Trace

| Constant | Value | Source |
|----------|-------|--------|
| TRACE_STEP | 0.1 tile | Ray-march step size used by `weapon_system::fire` to find a wall impact when the trace doesn't hit an enemy. Sub-tile resolution puts the puff close to the wall surface; a smaller step trades CPU for accuracy. Closed-form line-vs-grid intersection deferred (see `work/decisions.md` § Decision 22, private log; gitignored). |

## Pickups

Behavior spec: [`60_pickups.md`](60_pickups.md). Knowledge: [`knowledge/pickups.md`](../knowledge/pickups.md). Some values are knowledge-backed (the reference engine grants exactly this amount); others are scaled-down generation defaults sized for our one-enemy prototype level.

### Player Ammo Pool

| Constant | Value | Source |
|----------|-------|--------|
| PLAYER_AMMO_INITIAL | 12 | Generation default — no knowledge backing. Knowledge § Ammo Pickup Tiers gives reference starting ammo as 50 bullets (Category A pistol/clip ammo cap is 200). At our level scale (1 enemy needing 1–4 shots), 50 is irrelevant abundance and 12 makes the ammo pickup visibly meaningful. |
| PLAYER_AMMO_MAX | 30 | Generation default — no knowledge backing. Knowledge § Ammo Pickup Tiers gives reference Category A cap as 200. Scaled down 6.7× to match our level density. |

### Pickup Effects

| Constant | Value | Source |
|----------|-------|--------|
| PICKUP_HEALTH_AMOUNT | 25 | Knowledge § Health Pickup Tiers — "large health pickup → +25 HP, clamps at normal_max, refused at full". Direct match. |
| PICKUP_AMMO_AMOUNT | 10 | Knowledge § Ammo Pickup Tiers — "Small pickup: 1 clip-load granted" × `clip_size = 10` for Category A (primary clip ammo). Direct knowledge value. |
| PICKUP_RADIUS_TILES | 1.0 | Knowledge § Pickup Touch Detection — "AABB sum-of-radii: `r_player + r_thing` = 16+16 = 32 world units = 1 tile at 32 px/tile". Translation note: knowledge value is AABB Chebyshev; we use circle distance for consistency with our other collision checks (see spec/60 § Per-Frame Pickup Check); the magnitude (1 tile) carries over. |

### Default Level Placement

Three pickups in `level_data::build_default()`:

| Pickup | Position (tile coords) | Rationale |
|--------|------------------------|-----------|
| Health | (5.5, 12.5) | Generation default — south corridor, off the direct path from spawn → enemy → exit. Rationale: rewards exploration; player must detour from the optimal kill-then-exit path to find it. Tests the refused-at-cap rule because at full health the player can intentionally skip it. |
| Health | (12.5, 4.5) | Generation default — north of the central wall divider, on the natural BFS path between spawn and the SE enemy at (17.5, 12.5). With two enemies in the default level the bot is more likely to take damage during the run; this pickup sits on a low-detour line so `BOT_HEALTH_PICKUP_THRESHOLD`-triggered routing fires when HP drops below 50%. Generation default — no knowledge backing. |
| Ammo | (15.5, 7.5) | Generation default — east of the interior horizontal wall, on a natural approach line toward the enemy at (17.5, 12.5). Rationale: lies on the path the player will most likely take; reinforces the "ammo replenish before combat" loop. Sized so a player who fired wastefully on the way still has ammo for the encounter. |

### Sprite Visual

All sprite constants are `Generation default — no knowledge backing`. Knowledge does not extract pixel sprite shapes (the reference uses bitmap sprite assets we don't have). Shapes are common-knowledge retro UI conventions; colors chosen for distinction.

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| PICKUP_HEALTH_SIZE_PX | 12 | — | Generation default. Rationale: half the enemy diameter (24 px) so it does not visually compete with an enemy at the same distance, but large enough that the player can target it on a fast pass-through. |
| PICKUP_HEALTH_OUTER_COLOR | — | #FFFFFF white | Generation default. Rationale: white background is unique among all in-game colors (walls/floor/player/enemy all use saturated colors) so the pickup pops out without needing animation. |
| PICKUP_HEALTH_INNER_COLOR | — | #FF2020 red | Generation default. Rationale: red cross on white is the universal medical/health icon. Slightly orange-leaning red (`#FF2020`) so it is distinguishable from `COLOR_ENEMY` (pure `#FF0000`) and `HUD_HEALTH_COLOR_LOW` (`#C00000`) at a glance. |
| PICKUP_HEALTH_INNER_THICKNESS_PX | 4 | — | Generation default. Rationale: 1/3 of the pickup width — the cross arms are bold enough to read at a distance but leave white space on either side so the pickup still reads as "white square + cross", not "red mass". |
| PICKUP_AMMO_SIZE_PX | 10 | — | Generation default. Rationale: smaller than the health pickup (12 px) — visual hierarchy: health is the more "rare and valuable" pickup, gets the larger silhouette. |
| PICKUP_AMMO_COLOR | — | #FFFF00 yellow | Generation default. Rationale: pure yellow is the universal "ammo / pickup" color and is reused for the HUD ammo pane (`HUD_AMMO_COLOR`) so the two visually link. Distinct from `COLOR_MUZZLE_FLASH` (`#FFFF80` pale yellow) so the static pickup does not look like a transient effect. |

### HUD Ammo Pane (extends [`50_hud.md`](50_hud.md))

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| HUD_PANE_GAP_PX | 4 | — | Generation default. Rationale: half the digit on-screen height (~10 px) — wide enough that the two panes read as separate fields, narrow enough that they read as one HUD cluster. |
| HUD_AMMO_ICON_PX | 8 | — | Generation default. Rationale: matches the digit on-screen height (8 ≈ HUD_DIGIT_HEIGHT_PX × HUD_DIGIT_PIXEL_SIZE = 10) so icon + digits visually align as one row. |
| HUD_AMMO_COLOR | — | #FFFF00 yellow | Generation default — same yellow as the on-map ammo pickup so the player's eye links them. Knowledge § Color / State Encoding shows the reference uses *different fonts* (tall vs short) for primary vs secondary readouts; we substitute color since our font is monolithic. |

## HUD

Behavior spec: [`50_hud.md`](50_hud.md). Knowledge: [`knowledge/hud.md`](../knowledge/hud.md). Constants below mix knowledge-backed values with explicit generation defaults; the Source column is honest about which is which.

### Layout

| Constant | Value | Source |
|----------|-------|--------|
| HUD_MARGIN | 4 | Generation default — no knowledge backing (revised from initial design value of 8 to match generated code; code constant is `HUD_MARGIN`, not `HUD_MARGIN_PX`). Knowledge/hud.md § Status Bar Layout describes a bottom-anchored full-width chrome strip; we use a top-left corner pane instead. Margin sized for visual breathing room. |
| HUD_HEALTH_BAR_WIDTH_PX | 100 | Generation default — no knowledge backing. The reference uses digits-only without a proportional bar (knowledge § Color / State Encoding: digits inherit global palette tint instead). The bar substitutes for the missing palette channel; width is wide enough to read 1% increments. |
| HUD_HEALTH_BAR_HEIGHT_PX | 10 | Generation default — no knowledge backing. Rationale: ~10% of bar width (100 px) — thick enough to be visible at a glance from the corner of the eye, thin enough not to overwhelm the digits next to it. Aspect ratio 10:1 borrowed from typical retro HUD bars. |
| HUD_DIGIT_KERN_PX | 1 | Generation default — no knowledge backing. Rationale: minimum non-zero kerning so adjacent digits never visually merge, while still keeping the field compact. Knowledge § Numeric Widget describes fixed-width glyph advancement but does not specify kerning — the reference's glyphs include their own padding in the bitmap. Note: the bar→digits horizontal gap and the icon→digits horizontal gap both reuse `HUD_PANE_GAP_PX = 4` (§ HUD Ammo Pane), so a separate `HUD_DIGIT_GAP_PX` constant does not exist in the codebase. |

### Bitmap Font

Knowledge basis: [`knowledge/hud.md`](../knowledge/hud.md) § Numeric Widget and § Font / Glyph Data — fixed-width bitmap glyphs, 10 patches indexed by digit value `0..9`, glyph dimensions defined per font. Specific dimensions below are generation defaults because the reference reads dimensions at runtime from asset patch metadata; we have no asset pipeline.

| Constant | Value | Source |
|----------|-------|--------|
| HUD_DIGIT_WIDTH_PX | 3 | Generation default — narrow 3×5 retro font; reference dimensions not statically extractable. Rationale: 3×5 is the smallest grid that produces visually distinct digits 0–9; further compression makes 6 vs 8 vs 9 ambiguous. Public-domain 3×5 bitmap fonts exist for reference. |
| HUD_DIGIT_HEIGHT_PX | 5 | Generation default — narrow 3×5 retro font. Rationale: see HUD_DIGIT_WIDTH_PX. |
| HUD_DIGIT_PIXEL_SIZE | 2 | Generation default — each glyph pixel renders as a 2×2 block; on-screen digit is `HUD_DIGIT_WIDTH_PX*HUD_DIGIT_PIXEL_SIZE` × `HUD_DIGIT_HEIGHT_PX*HUD_DIGIT_PIXEL_SIZE` (6×10 px). Rationale: 1× scale renders 3×5 px digits — too small to read at 640×480 window distance. 2× brings them to 6×10 — comparable to typical legible HUD glyphs at this resolution. Higher scales would crowd the bar pane. |

The 10-entry glyph table (`HUD_DIGIT_GLYPHS`) is a renderer-private compile-time constant, not a tuning constant.

Knowledge-grounded numeric-widget rules (encoded in renderer behavior, not as constants):
- Right-justified anchoring (knowledge § Numeric Widget) — **deferred**: code renders digits left-to-right from a fixed x offset (`digits_x`); field width is variable, not padded to a fixed column. Digits are not right-justified in the current prototype.
- No leading zeros — value 7 in a 3-digit slot renders as `7`, not `007` (knowledge § Numeric Widget). **Implemented** via `n.to_string()`.
- Zero special-cased — `0` renders as the `0` glyph, not blank (knowledge § Numeric Widget). **Implemented**.

### Health Bands

| Constant | Value | Source |
|----------|-------|--------|
| HUD_HEALTH_BAND_HIGH_THRESHOLD | 0.66 | Generation default — no knowledge backing. Knowledge § Color / State Encoding: the reference does NOT color-shift digits by value (uses global palette shift instead). The band system is a prototype substitute for the missing palette channel. Top third = "healthy". |
| HUD_HEALTH_BAND_LOW_THRESHOLD | 0.33 | Generation default — same rationale as above. Bottom third = "critical"; middle band is implied. |

### Colors

All five HUD colors are generation defaults — no knowledge backing. Reasoning: knowledge § Color / State Encoding shows the reference does not apply per-element color to status bar digits; coloring is the prototype substitute (see § Health Bands rationale).

| Constant | Color | Source |
|----------|-------|--------|
| HUD_FRAME_COLOR | #C0C0C0 light gray | Generation default — bar outline (deferred). Rationale: distinguishable from both wall (`#404040`) and floor (`#808080`) tiles so the bar reads as UI not as a tile. Note: the 1 px outline around the health bar is not drawn in current code — `renderer::draw_hud` draws only the background fill and foreground fill. Bar outline is tracked as deferred in specs/50. |
| HUD_HEALTH_BAR_BG_COLOR | #303030 dark gray | Generation default — empty-bar fill. Rationale: darker than the wall color (`#404040`) so the empty portion of the bar reads as "drained" rather than as part of the level chrome. |
| HUD_HEALTH_COLOR_HIGH | #00C000 green | Generation default — full/healthy state. Rationale: pure green is the universal "OK / safe" signal; matches the player disc color (`COLOR_PLAYER` `#00FF00`) so player and full-health bar visually agree. |
| HUD_HEALTH_COLOR_MID | #C0C000 yellow | Generation default — middle band. Rationale: standard yellow caution; sits between green and red on the hue circle so the band transition is monotonic and intuitive. |
| HUD_HEALTH_COLOR_LOW | #C00000 red | Generation default — critical band. Rationale: matches the enemy color (`COLOR_ENEMY` `#FF0000`) and damage tint (`COLOR_DAMAGE_TINT`) so "low health" thematically links to "the enemy is winning". |

## RNG Seeds (Determinism)

Fixed seeds used when `--autopilot` flag is passed (specs/35 § Determinism). Seed values are generation defaults captured during reconcile pass — was noted in specs/35 as "Coder choice; document in work/decisions.md".

| Constant | Value | Module | Source |
|----------|-------|--------|--------|
| WEAPON_RNG_SEED | `0xDEAD_BEEF_1234_5678` | module-private const in `game_loop`; `game_loop::new` passes it unconditionally to `player_state::new`, which stores it on `Player.weapon_rng` (player_state contract § Player) | Generation default — arbitrary distinctive hex value. Seeds weapon damage RNG for deterministic demo recording. RNG state lives on `Player` so `weapon_system::fire` advances it through the existing `&mut Player` borrow — no module-private `static mut`, no `unsafe` (spec/80 § Safety). The seed is passed unconditionally regardless of `--autopilot`; `_shared.yaml § main_cli § rng_seeding` permits either always-fixed or mode-switched plumbing. |
| ENEMY_RNG_SEED | `0xCAFE_BABE_8765_4321` | `enemy_logic` (module-private const `ENEMY_RNG_SEED`, embedded in every `Enemy::rng` field at construction) | Generation default — arbitrary distinctive hex value. Seeds enemy pain-check and attack-damage RNG. The Coder dropped the per-enemy seed-injection API in this regen because every enemy initialises from the same fixed seed; the in-code identifier matches this row's canonical name. (see reconcile_log#ENEMY_RNG_SEED) |
| BOT_RNG_SEED | `0x00C0_FFEE` | `autopilot` | Generation default — "coffee" mnemonic. Seeds `BotState::rng` (LCG, module-private). Currently consumed by stuck-detection strafe-direction selection: when `stuck_strafe_remaining` decays to 0 the bot picks the next strafe direction via `rng.next_f32() > 0.5`. Per `coder_degrees_of_freedom`, both RNG-seeded picks and a deterministic toggle (`strafe_dir = -strafe_dir`) satisfy specs/35 § Determinism — the current Coder picked the RNG-seeded form. (see reconcile_log#BOT_RNG_SEED) |

## Autopilot (Bot Tuning)

The autopilot bot in `src/autopilot.rs` exposes a per-frame API always compiled, with a batch test-driver gated behind `#[cfg(test)]`. Behavior is described in `specs/30_test_framework.md` § Bot Behavior; the constants below are the bot's tuning knobs.

| Constant | Value | Source |
|----------|-------|--------|
| BOT_FRAME_TIME | 1/60 s | specs/30 § Execution Rules (60 FPS) |
| BOT_MAX_FRAMES | 18000 | 300 game-seconds at 60 FPS. Raised from the original 3600 (60 sec) so two-enemy fixtures across the central divider have time to navigate around the obstacle, fire, and reach the exit; single-enemy fixtures continue to finish in well under 3600 frames. (see reconcile_log#BOT_MAX_FRAMES) |
| BOT_REACH_DISTANCE | 1.0 tile | specs/30 § Objectives (`reach: distance < 1.0`) |
| BOT_APPROACH_DISTANCE | 8.0 tiles | specs/30 § Objectives (`approach: distance < 8.0`) |
| BOT_STUCK_FRAMES | 30 | specs/30 § Stuck Detection |
| BOT_REVERSE_STRAFE_FRAMES | 60 | specs/30 § Stuck Detection |
| ~~BOT_KILL_MIN_RANGE~~ | ~~6.0 tiles~~ | **Superseded** — the hold-and-fire-from-6-tiles policy was replaced by BFS path-follow + kite mode (this section's `BOT_FIRE_MAX_RANGE` and `BOT_KITE_RANGE` rows). The constant is no longer present in `src/autopilot.rs`. Row retained for history; do not reintroduce. (see reconcile_log#BOT_KILL_MIN_RANGE) |
| BOT_FACING_THRESHOLD | 0.3 rad | Generation default — captured during a reconcile pass (was inlined as `BOT_FACING_THRESHOLD` in `autopilot.rs`). Defines "roughly facing" the target (specs/30 § Bot Behavior point 2): if `\|delta_angle\| < BOT_FACING_THRESHOLD`, the bot moves forward. ~17 degrees keeps the bot from swerving while still firing only when meaningfully aligned. |
| BOT_TURN_THRESHOLD | 0.05 rad | Generation default — captured during a reconcile pass (was inlined as `BOT_TURN_THRESHOLD` in `autopilot.rs`). Below this angular delta the bot emits `turn = 0`, preventing oscillation around the target heading at high turn speed. ~3 degrees is one-frame-of-overshoot at `PLAYER_TURN_SPEED = 2.0 rad/sec` and 60 FPS. |
| BOT_KITE_RANGE | 2.0 tiles | Generation default — no knowledge backing. Distance below which the bot enters kite mode (back-pedal) when its objective targets an enemy. Sized comfortably above `ENEMY_CONTACT_RANGE_TILES` (0.8125) so the bot has ~1.2 tiles of buffer to retreat before contact damage triggers, and below `BOT_APPROACH_DISTANCE` (8.0) so kiting only activates after the bot has already closed via path-follow mode. Decreasing toward contact range gives the enemy a chance to land hits; increasing past ~3 tiles makes the bot retreat preemptively from non-threatening engagements. |
| BOT_FIRE_MAX_RANGE | 10.0 tiles | Generation default — no knowledge backing. Maximum distance at which the bot will pull the trigger on a `kill:` objective. Must be greater than `BOT_APPROACH_DISTANCE` (8.0) so the bot fires the moment the `approach:` objective completes; well below `PISTOL_RANGE_TILES` (64) since long-range pistol shots are spread-affected and waste ammo. 10 tiles also clears the typical 13-tile inter-spawn distance in `local_chase_obstacle` once the bot has rounded the obstacle. |
| BOT_FIRE_LOS_RAY_STEP | 0.1 tile | Generation default — no knowledge backing. Step size for the tile-grid ray-cast in `has_line_of_sight`. Mirrors `TRACE_STEP` (`weapon_system.rs`); sub-tile resolution so a one-tile-wide gap reads as transparent at oblique angles. A closed-form 2D DDA is permitted in lieu of stepping (`coder_degrees_of_freedom`); the constant becomes a documentation marker if the Coder picks DDA. |
| BOT_PATH_REPLAN_FRAMES | 30 frames | Generation default — no knowledge backing. The bot recomputes its BFS path no more often than every 30 frames (~0.5 s at 60 FPS) when the objective target hasn't shifted by more than one tile. Per-frame replanning is wasteful (BFS over the 20×15 grid is cheap but allocates). 30 frames is short enough that a moving enemy doesn't drift more than ~1 tile between plans at the basic trooper's 2.0 tiles/sec speed. The replan-on-target-move rule (move > 1 tile) is the dominant trigger in practice; the frame cadence is a floor that keeps the planner reactive when the target tile hasn't changed but the geometry has. |
| BOT_HEALTH_PICKUP_THRESHOLD | 0.5 (50% of `PLAYER_MAX_HEALTH`, i.e. 50 HP) | Generation default — no knowledge backing. HP fraction below which the bot's next path-replan routes via the nearest active health pickup before resuming the current objective. 50% sits comfortably above the lethal range (a single basic-trooper hit at the 15-damage tier from 50 HP leaves the player at 35 HP, still survivable for one more hit) but high enough that the detour fires before the engagement turns critical. Below ~30% the bot would already be one bad hit from death and the detour is too late; above ~70% the bot detours unnecessarily on minor scratches. Project-internal tuning — bot is autopilot tooling, not reference-derived gameplay AI. |
| BOT_PICKUP_DETOUR_BUDGET | 4 tiles | Generation default — no knowledge backing. Maximum extra path tiles the bot will detour to grab an opportunistic ammo pickup. The detour cost is computed as `path_via_pickup_length - direct_path_length` over the BFS graph. If the detour exceeds 4 tiles the pickup is skipped. 4 tiles is roughly two seconds of additional travel at the player's nominal speed and one BFS-path's worth of "round one corner to grab an item" — small enough that the demo doesn't visibly stall, large enough that an ammo pickup adjacent to the path is always taken. Project-internal tuning. |
| BOT_WAYPOINT_REACHED_TILES | 0.7 tile | Generation default — no knowledge backing. Distance threshold under which the bot consumes the next BFS waypoint and steers toward the one after. Both tile-equality (`bot.path[0] == floor(player.pos)`) and a distance threshold satisfy the spec (`coder_degrees_of_freedom § "waypoint-consume distance"`); the current Coder picked the threshold form. 0.7 sits comfortably below the 1.0-tile waypoint spacing so the bot consumes a waypoint before reaching the next, while above the per-frame movement step (~0.005 tile @ MAX_SPEED * dt) so a single frame does not skip multiple waypoints. (see reconcile_log#BOT_WAYPOINT_REACHED_TILES) |
| BOT_STUCK_MOVE_EPSILON | 0.02 tile/frame | Generation default — no knowledge backing. Per-frame movement threshold below which the bot's stuck-counter increments toward `BOT_STUCK_FRAMES`; inlined as a literal in `autopilot::bot_step` stuck-detect block. Spec/30 pins the frame counts but not the movement threshold (Coder degree of freedom under `stuck-detect`). 0.02 sits above f32 noise from collision slides and below the typical friction-tail velocity, so genuine stops trigger and floating-point jitter does not. (see reconcile_log#BOT_STUCK_MOVE_EPSILON) |

## Renderer (Raycaster)

Behavior spec: [`45_raycaster_renderer.md`](45_raycaster_renderer.md). Knowledge: [`knowledge/raycaster_renderer.md`](../knowledge/raycaster_renderer.md). Constants below define the column-based first-person renderer. As of slice 5 it is the default mode (`cargo run` with no flag); `--render-mode=topdown` is permanently retained as a debug-only alternate mode for development use (specs/00 § Phase 1).

### Pipeline Selection

| Constant | Value | Source |
|----------|-------|--------|
| RENDER_MODE_DEFAULT | `raycaster` | Generation default — no knowledge backing. Flipped from `topdown` to `raycaster` in slice 5 of the migration so `cargo run` (no flag) and the canonical PR-preview GIF render the first-person view by default. `--render-mode=topdown` remains available as a debug visualization (permanently retained per specs/00 § Phase 1). The flag values themselves (`topdown`, `raycaster`) are project-internal CLI vocabulary, not reference-derived. |

### Projection

| Constant | Value | Source |
|----------|-------|--------|
| RAYCASTER_FOV_RADIANS | `std::f32::consts::FRAC_PI_2` (90°) | knowledge/raycaster_renderer.md § Column Projection Model — "Horizontal FOV: 90°" (also § FOV, Aspect, and the Implicit Pinhole Camera "Horizontal FOV: 90° (fixed)"). |
| RAYCASTER_COLUMN_COUNT | `WINDOW_WIDTH` (640) | Generation default — no knowledge backing. Knowledge § Column Projection Model notes "doubling or halving the column count trades horizontal resolution against fill cost linearly"; we pick one ray per pixel column for the simplest mapping. Coarser subsampling is deferred (specs/45 § Deferred). |
| HORIZON_Y | `(WINDOW_HEIGHT - RAYCASTER_HUD_STRIP_HEIGHT_PX) / 2` | knowledge/raycaster_renderer.md § Floor and Ceiling Treatment — "Status-bar carve-out: full screen height minus a fixed bottom strip … is the actual render viewport; **centerY is half the viewport height**." The horizon belongs in the viewport's center, not the framebuffer's center; when the HUD claims a bottom strip the carve-out shifts the horizon upward. `RAYCASTER_HUD_STRIP_HEIGHT_PX` is `0` in any slice that has no bottom strip (so HORIZON_Y collapses to `WINDOW_HEIGHT / 2`) and is the strip's pixel height in slices that do (defined in specs/50). |
| WALL_HEIGHT_TILES | 1.0 | Generation default — no knowledge backing. The reference uses sector-relative wall heights driven by the world-format's per-sector floor/ceiling Z values; our `level_data::Tile` has no height field, so all walls are unit-height in tile units. Treating walls as cube-shaped (1 tile wide × 1 tile tall) keeps the projection focal-length math (`column_h_px = WALL_HEIGHT_TILES * focal_px / perp_dist`) using the same unit basis as the floor/ceiling split. Per-tile height is deferred (specs/45 § Deferred — Sector light levels and the precomputed colormap table). |
| EYE_HEIGHT_FRACTION | `41.0 / 128.0` (≈0.32) | knowledge/player_movement.md "View height \| 41 units \| Player eye height" pins the 41-unit numerator. The 128 denominator approximates a typical reference-engine room height — canonical room height is not yet in knowledge (Generation default — backing for the 128 denominator pending an Extractor pass that formalizes a canonical room-height citation). The ratio places the camera at the same wall-relative height the reference engine produces inside a typical 128-tall room: ~32% of `WALL_HEIGHT_TILES` above the floor, ~68% below the ceiling. Drives the asymmetric vertical wall split (specs/45 § Column Projection) and the sprite floor anchor (specs/45 § Sprite Vertical Anchor). |

### Far Clipping

| Constant | Value | Source |
|----------|-------|--------|
| RAYCASTER_MAX_DEPTH | 32.0 tiles | knowledge/raycaster_renderer.md § Max Render Distance / Far Clipping — "Reasonable far-clip for a 20×15 tile world: 32 tiles is more than the diagonal, so the cap rarely fires; smaller worlds (≤ 16×16) can use 16 tiles safely." Direct knowledge value. |

### Wall Shading

All wall colors are generation defaults — no knowledge backing. Knowledge § NS-vs-EW Wall Shading and § Distance Attenuation describe the *mechanism* (per-segment integer light-step adjustment + colormap-table lookup); the actual hex values come from per-asset palette data we don't have. Hex values pinned here so the Coder doesn't reinvent them.

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| RAYCASTER_WALL_COLOR_NEAR | — | #C0C0C0 light gray | Generation default — no knowledge backing. Bright neutral gray at zero distance; reads as "close stone wall" without competing for hue with the floor or ceiling. |
| RAYCASTER_WALL_COLOR_FAR | — | #101010 near-black | Generation default — no knowledge backing. Effectively black at `RAYCASTER_MAX_DEPTH`; matches the reference's saturated-darkest behavior at the colormap's last row (knowledge § Distance Attenuation "the colormap table saturates at its last (darkest) entry"). |
| RAYCASTER_NSEW_DARKEN_FACTOR | 0.75 | — | knowledge/raycaster_renderer.md § NS-vs-EW Wall Shading — "One light-level step difference between 'darker axis' and nominal". Translation: the reference's discrete-step colormap maps one step to roughly a 25% reduction at typical light levels; 0.75 (per-channel multiply) is the closest continuous equivalent in our colormap-less pipeline. The exact factor is a generation default within that spirit — increase toward 1.0 to reduce the directional-light effect, decrease to amplify it. |

### Floor / Ceiling

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| RAYCASTER_FLOOR_COLOR | — | #404040 dark gray | Generation default — no knowledge backing. Knowledge § Floor and Ceiling Treatment "Feel" recommends "contrasting hues for floor vs ceiling so the horizon line is unambiguous"; dark gray below contrasts with mid gray above. Re-uses the existing top-down `COLOR_WALL` palette band so both renderers share a visual identity. |
| RAYCASTER_CEILING_COLOR | — | #202020 darker gray | Generation default — no knowledge backing. Slightly darker than the floor so the horizon line reads downward (player's eye drops to "ground"); same § Floor and Ceiling Treatment "Feel" rationale. Distinct from `RAYCASTER_WALL_COLOR_FAR` (`#101010`) so a far wall does not visually merge with the ceiling. |

### Sprites and Billboards

Behavior spec: [`45_raycaster_renderer.md § Sprites and Billboards`](45_raycaster_renderer.md). Knowledge: [`knowledge/raycaster_sprites.md`](../knowledge/raycaster_sprites.md). The sprite pass projects entity-list elements into screen-aligned billboards drawn as flat-color rectangles **floor-anchored at sprite distance** (specs/45 § Sprite Vertical Anchor — `screen_y_center = HORIZON_Y + (EYE_HEIGHT_FRACTION − world_half_height) × xscale`), with per-column z-test against the wall pass's depth array.

The constants below are sized for the raycaster slice 2 sprite pass. The per-entity world half-extents are derived from existing visual constants — the raycaster module imports those values rather than redefining them, so this section pins only the genuinely new tuning knobs.

| Constant | Value | Source |
|----------|-------|--------|
| RAYCASTER_SPRITE_NEAR_PLANE | 0.1 tiles | knowledge/raycaster_sprites.md § World → Camera-Space Transform — "MINZ" rationale. Reference engine pins MINZ at 4 reference world units (= 4 / 32 = 0.125 tiles at our scale); rounded to 0.1 tiles. Below this forward-distance the projection scale would diverge; sprites at or below `forward_dist = RAYCASTER_SPRITE_NEAR_PLANE` are dropped from rendering for the frame. The chosen value sits well below `ENEMY_CONTACT_RANGE_TILES` (0.8125), so an enemy in melee range never trips the near-plane reject. |
| RAYCASTER_SPRITE_SIDE_CONE_FACTOR | 4.0 | knowledge/raycaster_sprites.md § World → Camera-Space Transform — "Side-cone reject". At 90° FOV the precise edge is `\|right_offset\| = forward_dist`; the reference uses ×4 slack as a coarse early-out before the per-column screen-x clip path runs. Coder degree of freedom — falling back to the always-clip form (no early-out) is correctness-equivalent and lets the constant remain a documentation marker. |
| RAYCASTER_SPRITE_VERTICAL_ANCHOR | floor-anchored | knowledge/raycaster_sprites.md § Per-Sprite Scale and Screen-Space X-Range — "anchor offset"; knowledge/player_movement.md "View height \| 41 units \| Player eye height" (drives `EYE_HEIGHT_FRACTION`). Sprites are anchored so the bottom edge meets the floor at the sprite's distance, mirroring the reference engine's "entity world Y equals the floor of the room it occupies" convention (specs/45 § Sprite Vertical Anchor). The y-center formula uses `EYE_HEIGHT_FRACTION` and the sprite's `world_half_height` (defined in specs/45 § Sprite Vertical Anchor and reused by every billboard candidate). Pins the anchor convention as a spec-level commitment so the Coder does not silently switch between "center on horizon" and "anchor at floor"; the choice affects every billboard's y1/y2 calculation. The earlier slice-2 horizon-centered simplification has been retired. Entity vertical-Z (non-zero height-above-floor — e.g. a flying enemy) remains deferred (specs/45 § Deferred). |
| RAYCASTER_SPRITE_DEPTH_FADE_FACTOR | 0.7 | knowledge/raycaster_sprites.md § Flat-Color vs Textured Choice — "Distance attenuation is optional — if applied, it follows the same lerp-toward-far convention as the wall pass". Knowledge permits the attenuation; this spec opts in. Generation default — value sized so a sprite at `RAYCASTER_MAX_DEPTH` retains 30% of its source-color luminance (still recognisable as enemy/pickup/blood) while a sprite partially occluded by a near-shaded wall does not visually clash with the wall's deep-shade band. The shade lerp uses `sprite_shade_t = (forward_dist / RAYCASTER_MAX_DEPTH).clamp(0.0, 1.0) * RAYCASTER_SPRITE_DEPTH_FADE_FACTOR`, then `lerp_rgb(sprite.color, RAYCASTER_WALL_COLOR_FAR, sprite_shade_t)`. |
| RAYCASTER_SPRITE_MIN_PROJ_DIST | 1.0 tile | Generation default — caps the maximum projected screen extent of a sprite so a near-camera billboard (live enemy at melee range, corpse the player walks over, pickup right at the player's feet) does not monopolize the framebuffer. Knowledge has no analogue: `raycaster_sprites.md` § Per-Sprite Scale only mentions an *implicit* "vertical-FOV cap" produced by the column-renderer's pixel-stepping when a too-close sprite would exceed the viewport — flat-color rectangles without that pixel-stepping geometry will, without an explicit cap, render as a screen-blocking solid block at melee range. The clamp is `xscale = focal_px / forward_dist.max(RAYCASTER_SPRITE_MIN_PROJ_DIST)`. Value chosen so a player-radius enemy (`ENEMY_RADIUS_TILES = 0.375 tile`) at `forward_dist <= MIN_PROJ_DIST` projects to ~120 px half-width at 640 px viewport (≈ 37% of screen width) — recognisable "in-your-face" feel without visual blackout. The unclamped `forward_dist` is still used for the per-column z-test against `wall_depth[x]`; the clamp only affects projection. The near-plane reject `RAYCASTER_SPRITE_NEAR_PLANE = 0.1 tile` continues to drop sprites below that threshold; `MIN_PROJ_DIST` shapes how the surviving close-range sprites are sized. |

#### Per-Entity Billboard Half-Extents (derived, not new constants)

The raycaster's sprite pass reads existing visual constants for each entity type's world half-width / half-height (in tile units). Listed here for cross-reference; **not new constants** — defined in the modules cited.

| Entity | Half-extent | Source |
|--------|-------------|--------|
| Live enemy | `ENEMY_RADIUS_TILES` (0.375 tile) | specs/25 § Enemy. Imported from `enemy_logic`. |
| Dying enemy (death-fade Effect) | `lerp(ENEMY_RADIUS_TILES, ENEMY_CORPSE_RADIUS / TILE_SIZE, fade_t)` where `fade_t = 1.0 - lifetime_remaining / ENEMY_DEATH_FADE_DURATION` (0.375 → 0.25 tile over the fade) | Shrinks from live-enemy size to corpse size as the fade progresses — the same `fade_t` drives both color and size, so the visual reads as a single "settle" beat. At `fade_t == 1.0`, both extent and color match the corpse spawned next, eliminating the discontinuity that existed when the death-fade rendered at full live-enemy extent right up until the corpse replaced it. |
| Persistent corpse Effect | `ENEMY_CORPSE_RADIUS / TILE_SIZE` (0.25 tile, 8 px / 32 px) | specs/25 § Enemy Death Visual. Imported from `visual_effects` (px) and `level_data` (TILE_SIZE). |
| Blood splat Effect | `BLOOD_RADIUS / TILE_SIZE` (0.1875 tile, 6 px / 32 px) | specs/25 § Blood Splat. Imported from `visual_effects` (px) and `level_data` (TILE_SIZE). |
| Health pickup | `PICKUP_HEALTH_SIZE_PX / 2.0 / TILE_SIZE` (0.1875 tile, 12 px / 32 px / 2) | specs/25 § Pickups § Sprite Visual. Imported from `renderer` (px) and `level_data` (TILE_SIZE). |
| Ammo pickup | `PICKUP_AMMO_SIZE_PX / 2.0 / TILE_SIZE` (0.15625 tile, 10 px / 32 px / 2) | specs/25 § Pickups § Sprite Visual. Imported from `renderer` (px) and `level_data` (TILE_SIZE). |

#### Per-Entity Billboard Color (derived, not new constants)

The raycaster's sprite pass reads existing color constants for each entity type. Listed here for cross-reference; **not new constants** — defined in the modules cited.

| Entity | Color | Source |
|--------|-------|--------|
| Live enemy (no pain) | `COLOR_ENEMY` (#FF0000) | specs/25 § Visual. Imported from `renderer`. |
| Live enemy (`pain_flash_remaining > 0`) | `COLOR_PAIN_FLASH` (#FFFFFF) | specs/25 § Enemy Pain Flash. Imported from `renderer`. |
| Dying enemy (death-fade Effect) | `lerp(COLOR_ENEMY, COLOR_CORPSE, 1.0 - lifetime_remaining / ENEMY_DEATH_FADE_DURATION)` | specs/25 § Enemy Death Visual. Imported color constants from `renderer`; duration constant from `visual_effects`. |
| Persistent corpse Effect | `COLOR_CORPSE` (#602020) | specs/25 § Enemy Death Visual. Imported from `renderer`. |
| Blood splat Effect | `COLOR_BLOOD` (#C00000) | specs/25 § Blood Splat. Imported from `renderer`. |
| Health pickup | `PICKUP_HEALTH_OUTER_COLOR` (#FFFFFF) | specs/25 § Pickups § Sprite Visual. Imported from `renderer`. The inner red cross overlay is **deferred** (specs/45 § Deferred — Inner-detail multi-layer sprites). |
| Ammo pickup | `PICKUP_AMMO_COLOR` (#FFFF00) | specs/25 § Pickups § Sprite Visual. Imported from `renderer`. |

### First-Person Effects

Behavior spec: [`45_raycaster_renderer.md § First-Person Effects`](45_raycaster_renderer.md#first-person-effects). Knowledge: [`knowledge/raycaster_effects.md`](../knowledge/raycaster_effects.md). Constants below pin the slice-3 first-person effects: the screen-space muzzle-flash overlay, the world-space tracer line, the wall-puff billboard's full-bright phase, and the extra-light bias on wall and sprite shading during the firing window.

The trigger durations (`MUZZLE_FLASH_DURATION = 0.10s`, `TRACER_DURATION = 0.06s`, `PUFF_DURATION = 0.30s`) and the effect colors (`COLOR_MUZZLE_FLASH = #FFFF80`, `COLOR_TRACER = #FFFFC0`, `COLOR_PUFF = #B0B0B0`, `COLOR_BLOOD = #C00000`, `COLOR_DAMAGE_TINT = #FF0000`, `COLOR_PICKUP_TINT = #FFCC00`) are reused unchanged from the topdown effect set (§ Visual Feedback) — the raycaster imports them via `visual_effects` (durations) and `renderer` (colors). The constants below are the genuinely new values for the first-person projection.

| Constant | Value | Source |
|----------|-------|--------|
| RAYCASTER_EXTRA_LIGHT_SHADE_DELTA | 0.0625 (≈ 1/16 ramp step) | [`knowledge/raycaster_effects.md § Extra-Light Bias`](../knowledge/raycaster_effects.md#extra-light-bias-global-brightness-pulse) — "The world's light-table is structured as a 16-step ramp ... The renderer adds the extra-light counter to this index ... 1 ramp-step ≈ 6.25%". The continuous-lerp pipeline approximates the discrete-step bias by subtracting 0.0625 from the shading-lerp parameter `shade_t` during the firing flash window. Reference uses 1 step for "small/rapid weapons" (handgun); pistol is small/rapid. The 2-step bias for heavy weapons is **deferred** (specs/45 § Deferred — 2-step extra-light bias for heavy weapons). The clamp `(shade_t - DELTA).clamp(0.0, 1.0)` ensures a near-zero `shade_t` (very close wall) does not wrap negative. |
| RAYCASTER_MUZZLE_FLASH_CENTER_X | `WINDOW_WIDTH / 2` (= 320) | Generation default — knowledge `raycaster_effects.md` § Held-Weapon View Sprite confirms a fixed screen-space anchor ("a fixed offset from the top of the reference 200-row vertical space") but does not pin pixel coordinates (those come from per-asset sprite dimensions, which we don't have). Centered horizontally because the player's gun is held centered in first-person view. Tied to `WINDOW_WIDTH` so the anchor scales correctly if the window dimensions ever change. |
| RAYCASTER_MUZZLE_FLASH_CENTER_Y | `WINDOW_HEIGHT * 3 / 4` (= 360) | Generation default — knowledge has no pixel value (asset-driven in the reference). Three-quarters down places the flash where the muzzle of a held pistol would exit the bottom of the frame; sits above the top-left HUD pane (which extends down only ~30 px from the top edge — specs/50) with comfortable margin so the flash and HUD never overlap. The held-weapon body sprite (the gun itself, on which the flash visually anchors) is **deferred** to slice 4 with the FPS HUD layout (specs/45 § Deferred — Held-weapon body sprite); slice 3 ships the flash as an unattached bright disc. |
| RAYCASTER_MUZZLE_FLASH_RADIUS_PX | 24 | Generation default — knowledge has no pixel value (asset-driven). Sized larger than topdown's `MUZZLE_FLASH_RADIUS = 6 px` so the flash reads as a held-weapon flash at screen scale (the topdown flash sits at the player's world position projected to screen, while the raycaster flash is a screen-space overlay at the gun anchor — different scale basis). Bounded so the flash does not occlude the central viewport: at 24 px radius the flash covers ~7.5% of the 640 px screen width and ~10% of the 480 px height, visible without obscuring the player's view of nearby walls / enemies during the 0.10s flash. |
| RAYCASTER_TRACER_THICKNESS_PX | 1 | Generation default — knowledge `raycaster_effects.md` § Hitscan Trace Endpoint: NO Tracer Line explicitly notes the reference does NOT render a tracer; the tracer in raycaster mode is a deliberate genre-style departure for visual parity with the topdown renderer (specs/45 § Generation Default Deviation: Tracer Line). 1 px matches the topdown `TRACER_THICKNESS`; thicker tracers would visually compete with the muzzle flash overlay. |
| RAYCASTER_PUFF_FULL_BRIGHT_FRACTION | 0.5 | [`knowledge/raycaster_effects.md § Wall-Hit Impact Puff`](../knowledge/raycaster_effects.md#wall-hit-impact-puff-world-space-billboard) — "First frame uses the full-bright flag: drawn at the brightest colormap regardless of distance/sector light. Subsequent frames use normal distance-attenuated shading". The reference's 4-frame puff is collapsed to "full-bright for the first half of the lifetime, distance-attenuated for the second half" in our 1-Effect model. 0.5 ties at the midpoint; tunable upward (more full-bright) if puffs against far walls do not pop, or downward if they overstay. |

#### Per-Frame Bias Detection (derived, not a new constant)

The "firing window active" gate referenced by both the wall pass and the sprite pass is derived from the per-frame state, not pinned as a constant:

```rust
let firing_active = fx.effects.iter()
    .any(|e| e.kind == EffectKind::MuzzleFlash && e.lifetime_remaining > 0.0);
```

This expression is computed once at the start of `raycaster::draw` and cached for the frame. Knowledge `raycaster_effects.md` § Effect Pass Ordering — "the renderer caches the player's extra-light counter into a frame-scoped shading offset" — pins this once-per-frame compute as a contract requirement; it is not a constant.

#### Per-Effect Half-Extents and Colors (derived, not new constants)

The slice-3 wall puff sprite-pass billboard derives its half-extent from the existing `PUFF_RADIUS` constant in `visual_effects` and uses the existing `COLOR_PUFF` constant in `renderer`:

| Entity | Half-extent | Color | Source |
|--------|-------------|-------|--------|
| Wall puff Effect | `PUFF_RADIUS / TILE_SIZE` (0.125 tile, 4 px / 32 px) | `COLOR_PUFF` (#B0B0B0) | specs/25 § Visual Feedback / Wall Puff. Imported from `visual_effects` (px) and `level_data` (TILE_SIZE); color from `renderer`. The puff's full-bright phase override is keyed off `lifetime_remaining / PUFF_DURATION > RAYCASTER_PUFF_FULL_BRIGHT_FRACTION`. |

The screen-space muzzle flash overlay reuses `COLOR_MUZZLE_FLASH` (`#FFFF80`) from `renderer`. The tracer line reuses `COLOR_TRACER` (`#FFFFC0`) from `renderer`. The damage tint overlay reuses `COLOR_DAMAGE_TINT`, `DAMAGE_TINT_CAP`, `DAMAGE_TINT_LEVELS`, and `DAMAGE_TINT_MAX_ALPHA_PCT`. The pickup tint overlay reuses `COLOR_PICKUP_TINT`, `PICKUP_TINT_CAP`, `PICKUP_TINT_LEVEL_COUNT`, and `PICKUP_TINT_MAX_ALPHA_PCT`. None are new constants.

### FPS HUD Layout

Behavior spec: [`45_raycaster_renderer.md § FPS HUD Layout`](45_raycaster_renderer.md#fps-hud-layout). Knowledge: [`knowledge/raycaster_hud.md`](../knowledge/raycaster_hud.md). Constants below pin the slice-4 first-person HUD: a bottom chrome strip showing health, ammo, and weapon panes. The strip is drawn ONLY in `--render-mode=raycaster`; the `--render-mode=topdown` path keeps the existing top-left text HUD (specs/50) byte-for-byte unchanged. **No on-view crosshair is drawn** — the reference engine renders none in its first-person view (knowledge `raycaster_hud.md` § On-View Crosshair — Absent in the Reference's First-Person View), and slice 4 follows the reference; see specs/45 § Reference-Faithful No-Crosshair Choice.

The reference engine's HUD is bitmap-asset-driven (320 × 32 chrome bitmap blitted into rows 168..199 of a 320 × 200 framebuffer; widget anchors at hard-coded pixel positions reading two pre-loaded digit fonts; weapons-owned subpanel showing slots 2..7 as small colored digits — knowledge `raycaster_hud.md` § Bottom Chrome Strip — Static Background Bitmap, § Widget Layout Within the Strip, § Bottom-Strip Font Treatment). We have no asset pipeline (specs/80 § Dependencies) and only one weapon (`ir/game_ir.yaml § combat`). Constants below adapt the reference's geometry to our 640 × 480 framebuffer at 2× scale and substitute a flat-color strip for the chrome bitmap.

#### Strip

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| RAYCASTER_HUD_STRIP_HEIGHT_PX | 80 | — | Generation default — no knowledge backing for the absolute pixel value (the reference's 32-row strip is asset-bitmap-sized). The reference strip occupies 16% of vertical space (32 / 200); 80 / 480 ≈ 16.7%, the closest 2× scale that preserves that proportion at our 640 × 480 framebuffer (knowledge `raycaster_hud.md` § Viewport-to-HUD Vertical Partition — "The strip's height is a fixed bitmap-height constant ... rows 168..199 ... leaving rows 0..167 for the world view"). 80 also gives the digit pane comfortable vertical breathing room at our digit pixel size (below). |
| RAYCASTER_HUD_STRIP_COLOR | — | #585050 chrome warm-gray | knowledge/raycaster_hud.md § Bottom-Strip Palette Reference — "Chrome warm-gray: a desaturated warm gray, roughly (90, 80, 80)". `#585050` ≈ (88, 80, 80) — the closest 8-bit-per-channel value to the knowledge-suggested chrome. |
| RAYCASTER_HUD_STRIP_TOP_Y | `WINDOW_HEIGHT - RAYCASTER_HUD_STRIP_HEIGHT_PX` (= 400) | — | Derived. The strip is anchored to the bottom of the framebuffer (knowledge same § — "The strip's vertical origin is `(framebuffer_height - strip_height)`"). |

The world-view region is rows `0..RAYCASTER_HUD_STRIP_TOP_Y` (= 0..400). The wall pass, sprite pass, and effects pass write the entire framebuffer (rows 0..480) — the strip is drawn on top of those layers and overwrites the bottom 80 rows. World-region pixels above the strip remain visible. (The world's bottom 80 rows DO get computed; they're just covered by the strip. Knowledge `raycaster_hud.md` § Viewport-to-HUD Vertical Partition notes the reference avoids the wasted compute by limiting `view_height` to 168 rows; we do not — the strip overlay is simpler and the wasted compute on 80 × 640 = 51 200 pixels is negligible at our scenario complexity.)

#### Per-Pane Layout (Within the Strip)

Knowledge `raycaster_hud.md` § Widget Layout Within the Strip pins the reference's hard-coded absolute widget pixel positions (ammo at x=44, health at x=90, weapons subpanel at x=104, etc.). Our 2× scale-up + single-weapon substitution makes the reference positions inapplicable verbatim. The constants below pin a left-to-right "health → ammo → weapon" reading order (knowledge same § — "The layout reads left-to-right as a sentence"), with explicit anchors so the Coder does not reinvent positions across regens.

| Constant | Value | Source |
|----------|-------|--------|
| RAYCASTER_HUD_DIGIT_PIXEL_SIZE | 4 | Generation default — no knowledge backing for the exact value (reference fonts are asset-bitmap-driven). 4× scale on the existing 3 × 5 digit font (specs/25 § Bitmap Font) produces 12 × 20 px digits — closest analogue to the reference's "tall-digit" font (~14 × 16 px, knowledge `raycaster_hud.md` § Bottom-Strip Font Treatment) at our framebuffer size. The topdown HUD uses 2× scale (6 × 10 digits); the FPS strip's bigger panes need bigger digits to read across the player's "instrument panel" attention span. |
| RAYCASTER_HUD_PANE_X_HEALTH | 32 | Generation default — no knowledge backing. Left padding for the health pane. The reference's tall-digit health % anchors at x=90 in the 320-wide strip (knowledge `raycaster_hud.md` § Widget Layout Within the Strip); 32 in our 640-wide strip is the same fractional position (~10% in from the left edge) accounting for the absence of the reference's ammo pane to the left of health. |
| RAYCASTER_HUD_PANE_X_AMMO | 256 | Generation default — no knowledge backing. Middle pane anchor; sized to clear the health digits (max width = 3 digits × 12 px + 2 × 1 px kern = ~38 px from the health icon at x≈40) with comfortable margin. |
| RAYCASTER_HUD_PANE_X_WEAPON | 480 | Generation default — no knowledge backing. Right pane anchor; sized to fit a weapon icon (~80 px wide, see below) inside the strip without overlapping the framebuffer right edge. |
| RAYCASTER_HUD_PANE_TEXT_Y | `RAYCASTER_HUD_STRIP_TOP_Y + (RAYCASTER_HUD_STRIP_HEIGHT_PX - RAYCASTER_HUD_DIGIT_PIXEL_SIZE * HUD_DIGIT_HEIGHT_PX) / 2` (= 400 + (80 - 20) / 2 = 430) | Vertically centers the digits inside the strip. Derived from the strip dimensions and digit size. |

#### Pane Colors and Glyphs

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| RAYCASTER_HUD_HEALTH_COLOR | — | #D00000 saturated red | knowledge/raycaster_hud.md § Bottom-Strip Palette Reference — "Tall-digit red: a saturated red roughly in the (200, 0, 0) – (220, 0, 0) range". `#D00000` ≈ (208, 0, 0). Distinct from the topdown HUD's `HUD_HEALTH_COLOR_LOW` (`#C00000`) so a topdown→raycaster mode switch reads as deliberately different rather than an accidental color drift. |
| RAYCASTER_HUD_AMMO_COLOR | reuse `HUD_AMMO_COLOR` (`#FFFF00`) | #FFFF00 yellow | knowledge/raycaster_hud.md § Bottom-Strip Palette Reference — "Short-digit yellow (active weapons-owned): a saturated yellow roughly (220, 220, 0)". `#FFFF00` is the closest 8-bit value and reuses the existing topdown `HUD_AMMO_COLOR` (specs/25 § HUD Ammo Pane) so the on-map ammo pickup, the topdown HUD ammo pane, and the FPS HUD ammo pane all share one yellow. The reference uses two distinct font weights for primary vs secondary readouts; with our monolithic font we substitute pane position (separate strip slot) instead of a separate font (knowledge `raycaster_hud.md` § Bottom-Strip Font Treatment + § Widget Layout). |
| RAYCASTER_HUD_WEAPON_COLOR | — | #B0B0B0 mid-gray | Generation default — no knowledge backing for a single-weapon icon (reference shows a 6-slot weapons-owned subpanel, knowledge `raycaster_hud.md` § Widget Layout Within the Strip — "Weapons-owned indicators: 6 slots ... gray = unowned, yellow = owned"; we have one weapon and do not need the slot-based representation). Mid-gray reads as "tool / equipment", distinct from the alarm-panel red (health) and the ammo yellow. |

#### Health Icon (Left of Health Digits)

The HUD strip's health pane composes a small icon glyph + the player's health digits, mirroring the topdown HUD's "icon + digits" pattern (specs/25 § HUD Ammo Pane). We have no alphabet font (only digits 0..9), so the pane uses a glyph icon instead of a textual "HEALTH" label.

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| RAYCASTER_HUD_HEALTH_ICON_PX | 16 | — | Generation default — no knowledge backing. ~80% of the digit on-screen height (`HUD_DIGIT_HEIGHT_PX × RAYCASTER_HUD_DIGIT_PIXEL_SIZE = 20`) so the icon sits comfortably alongside the digits. Reuses the red-cross convention from the on-map health pickup (specs/25 § Pickups § Sprite Visual). |
| RAYCASTER_HUD_HEALTH_ICON_THICKNESS_PX | 4 | — | Generation default — same 1/4-of-icon-width ratio as the on-map health pickup's `PICKUP_HEALTH_INNER_THICKNESS_PX`. |
| (icon background) | — | reuse `RAYCASTER_HUD_HEALTH_COLOR` | The icon is a simple red plus-cross (no white background) so it composes onto the chrome strip without a second color band. |

#### Ammo Icon (Left of Ammo Digits)

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| RAYCASTER_HUD_AMMO_ICON_PX | 16 | — | Generation default — same size as the health icon for visual symmetry. Reuses the yellow-square convention from the topdown HUD (`HUD_AMMO_ICON_PX = 8` at topdown's 2× digit scale; ours is 16 at the strip's 4× digit scale, preserving the same "icon ≈ digit height" ratio). |
| (icon color) | — | reuse `RAYCASTER_HUD_AMMO_COLOR` | Single solid yellow square. |

#### Weapon Icon (Right Pane)

The reference's weapons-owned subpanel is a 2-row × 3-column grid of small digit slots showing weapons 2..7 (knowledge `raycaster_hud.md` § Widget Layout Within the Strip). With one weapon (the pistol — slot 1, which the reference renders implicitly), our analogue is a single static icon representing the active weapon.

| Constant | Value | Color | Source |
|----------|-------|-------|--------|
| RAYCASTER_HUD_WEAPON_ICON_W_PX | 48 | — | Generation default — no knowledge backing. Sized to read as "the weapon" at the strip's scale — wider than tall to suggest a horizontal pistol silhouette. |
| RAYCASTER_HUD_WEAPON_ICON_H_PX | 16 | — | Generation default — same height as the health/ammo icons for visual symmetry. |

The exact silhouette (single filled rectangle, T-shape with grip, two-rectangle "barrel + grip" pistol) is a Coder degree of freedom (`ir/contracts/renderer.yaml § coder_degrees_of_freedom`). The simplest shape — a single filled rectangle in `RAYCASTER_HUD_WEAPON_COLOR` at the size above — is the obvious starting point; future iterations may elaborate to a multi-rect silhouette without spec change.

#### Effect Composition

The HUD strip draws **on top of** the world layers and effect overlays (matching knowledge's "two HUD surfaces compose without interaction" — § Key Insights). Concretely, after the slice-3 effects pass returns:

1. Bottom HUD strip (chrome + health pane + ammo pane + weapon icon)
2. Game-over border (if `game_over.is_some()`) — unchanged from slice 3

The HUD strip is **full-bright** — no distance attenuation, no extra-light-bias modulation, no z-test against `wall_depth[]`.

## Frame Rate

| Property | Value |
|----------|-------|
| Target FPS | 60 |
| Delta time cap | 0.1s |

## Design Notes (derived from knowledge)

- Enemy killed in 2 pistol shots (20 HP / avg 10 damage) -- snappy encounters
- Player killed by ~11 enemy shots (100 HP / avg 9 damage) -- forgiving for single enemies
- Damage variance (5/10/15 per shot) keeps repeated fights from feeling mechanical
- High pain chance (78%) rewards aggressive play -- sustained fire can stun-lock enemies
- First-shot accuracy rewards deliberate aim; refire spread punishes spray
- Asymmetric accuracy (player 5.6 deg vs enemy 22 deg) compensates for enemies always facing player
- No chase range limit -- if enemy sees you, it reacts
- Sound propagation alerts nearby enemies (deferred)

## Time Model

All timing constants in this spec use seconds. The game uses delta_time for frame-rate-independent updates. Constants were derived from the reference game's tick-based timings (35 ticks/sec) converted to seconds:

- Reference fire cycle: 19 ticks at 35 ticks/sec = 0.54 seconds
- Reference reaction delay: 8 ticks at 35 ticks/sec = 0.23 seconds

The game's rendering frame rate (60 FPS) does not affect gameplay timing because all updates are delta_time-scaled.

## Deferred Combat Features

The following are documented in knowledge but out of current scope (one weapon, one enemy type):

- Multiple weapons (shotgun, chaingun, fist, super shotgun)
- Projectile-based attacks (hybrid fireball, travel time, dodging)
- Multiple enemy types -- see knowledge/enemy_types.md for full roster:
  - Shotgun trooper (30 HP, hitscan x3, 66% pain chance)
  - Rapid-hitscan trooper (70 HP, rapid hitscan, 66% pain chance)
  - Ranged-melee hybrid (60 HP, melee + projectile, 78% pain chance)
  - Melee-only beast (150 HP, melee only, 70% pain chance)
  - Floating projectile mid-tier (400 HP, projectile, 50% pain chance)
  - Heavy melee+projectile boss (1000 HP, melee + projectile, 20% pain chance)
  - Rocket-launcher mega-boss (4000 HP, rockets, 8% pain chance)
  - And others (see knowledge/enemy_types.md)
- Armor system (green 33% absorption, blue 50% absorption)
- Ammo economy (ammo types, pickups, scarcity pressure)
- Difficulty-based damage scaling (easy = 0.5x incoming damage)
- Auto-aim / vertical targeting assistance
- Berserk power-up (10x melee damage)
- Deterministic PRNG (256-entry lookup table for demo replay)
