# Game Tuning

## Intent

This spec captures all gameplay balance constants, visual parameters, and level layout values. Values are derived from knowledge extraction (see `knowledge/combat_balance.md`, `knowledge/enemy_types.md`, `knowledge/player_movement.md`), not invented.

## Player

| Constant | Value | Source |
|----------|-------|--------|
| Health | 100 | knowledge/player_movement.md |
| Movement model | thrust + friction | Constants (THRUST_FACTOR, FRICTION, MAX_SPEED, STOP_THRESHOLD) defined in `specs/21_player_movement.md` |
| Turn speed | 2.0 rad/sec | Tuned for 60 FPS (original was 35 ticks/sec) |

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
| Enemy spawn | (17.5, 12.5) |
| Exit position | (17.5, 2.5) |
| Border | All edges are walls |
| Interior walls | Vertical segment x=10, y=3..8; horizontal y=7, x=4..9 |

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
| TRACE_STEP | 0.1 tile | Ray-march step size used by `weapon_system::fire` to find a wall impact when the trace doesn't hit an enemy. Sub-tile resolution puts the puff close to the wall surface; a smaller step trades CPU for accuracy. Closed-form line-vs-grid intersection deferred (see ADR 22). |

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

Two pickups in `level_data::build_default()`:

| Pickup | Position (tile coords) | Rationale |
|--------|------------------------|-----------|
| Health | (5.5, 12.5) | Generation default — south corridor, off the direct path from spawn → enemy → exit. Rationale: rewards exploration; player must detour from the optimal kill-then-exit path to find it. Tests the refused-at-cap rule because at full health the player can intentionally skip it. |
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
| WEAPON_RNG_SEED | `0xDEAD_BEEF_1234_5678` | `weapon_system` | Generation default — arbitrary distinctive hex value. Seeds weapon damage RNG for deterministic demo recording. |
| ENEMY_RNG_SEED | `0xCAFE_BABE_8765_4321` | `enemy_logic` | Generation default — arbitrary distinctive hex value. Seeds enemy pain-check and attack-damage RNG. |
| BOT_RNG_SEED | `0x00C0_FFEE` | `autopilot` | Generation default — "coffee" mnemonic. Seeds bot stuck-detection strafe-direction RNG. |

## Autopilot (Bot Tuning)

The autopilot bot in `src/autopilot.rs` exposes a per-frame API always compiled, with a batch test-driver gated behind `#[cfg(test)]`. Behavior is described in `specs/30_test_framework.md` § Bot Behavior; the constants below are the bot's tuning knobs.

| Constant | Value | Source |
|----------|-------|--------|
| BOT_FRAME_TIME | 1/60 s | specs/30 § Execution Rules (60 FPS) |
| BOT_MAX_FRAMES | 3600 | specs/30 § Execution Rules (60 sec max) |
| BOT_REACH_DISTANCE | 1.0 tile | specs/30 § Objectives (`reach: distance < 1.0`) |
| BOT_APPROACH_DISTANCE | 8.0 tiles | specs/30 § Objectives (`approach: distance < 8.0`) |
| BOT_STUCK_FRAMES | 30 | specs/30 § Stuck Detection |
| BOT_REVERSE_STRAFE_FRAMES | 60 | specs/30 § Stuck Detection |
| BOT_FACING_THRESHOLD | 0.3 rad | Generation default — captured during a reconcile pass (was inlined as `BOT_FACING_THRESHOLD` in `autopilot.rs`). Defines "roughly facing" the target (specs/30 § Bot Behavior point 2): if `\|delta_angle\| < BOT_FACING_THRESHOLD`, the bot moves forward. ~17 degrees keeps the bot from swerving while still firing only when meaningfully aligned. |
| BOT_TURN_THRESHOLD | 0.05 rad | Generation default — captured during a reconcile pass (was inlined as `BOT_TURN_THRESHOLD` in `autopilot.rs`). Below this angular delta the bot emits `turn = 0`, preventing oscillation around the target heading at high turn speed. ~3 degrees is one-frame-of-overshoot at `PLAYER_TURN_SPEED = 2.0 rad/sec` and 60 FPS. |

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
