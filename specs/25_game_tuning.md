# Game Tuning

## Intent

This spec captures all gameplay balance constants, visual parameters, and level layout values. Values are derived from knowledge extraction (see `knowledge/combat_balance.md`, `knowledge/enemy_types.md`, `knowledge/player_movement.md`), not invented.

## Player

| Constant | Value | Source |
|----------|-------|--------|
| Health | 100 | knowledge/player_movement.md |
| Movement model | thrust + friction | Constants (THRUST_FACTOR, FRICTION, MAX_SPEED, STOP_THRESHOLD) defined in `specs/21_player_movement.md` |
| Turn speed | 2.0 rad/sec | Tuned for 60 FPS (original was 35 ticks/sec) |

## Enemy (Basic Ranged -- "Former Human" archetype)

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
| ENEMY_CONTACT_RANGE_TILES | 0.8125 tile (= 26 px) | Derived from player + enemy visual radii in `## Visual` (14 px + 12 px) divided by `TILE_SIZE`. Specs/20 says "contact damage when within melee range" without naming a value; this range fires the hit exactly when the two discs visually touch. Captured during reconcile of full regen 2026-04-26 (was inlined as derived constant in `enemy_logic.rs`). |
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
| Fire cycle | 0.54 seconds | ~1.84 shots/sec (knowledge/combat_balance.md) |
| Hit detection | Hitscan (instant) | Line trace, no projectile travel time |
| First-shot accuracy | Perfect (no spread) | First shot after pause has zero angular offset |
| IDLE_THRESHOLD_SEC | 1.0 seconds | Generation default — promotes deliberate paused single-shot to first-shot accuracy. No reference value: holding fire at the 0.54s cycle never resets to perfect aim, but a deliberate pause does. Captured during reconcile of full regen 2026-04-26 (was inlined as `IDLE_THRESHOLD_SEC` in `weapon_system.rs`). |
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
- Projectile-based attacks (imp fireball, travel time, dodging)
- Multiple enemy types -- see knowledge/enemy_types.md for full roster:
  - Shotgun Guy (30 HP, hitscan x3, 66% pain chance)
  - Chaingunner (70 HP, rapid hitscan, 66% pain chance)
  - Imp (60 HP, melee + projectile, 78% pain chance)
  - Demon (150 HP, melee only, 70% pain chance)
  - Cacodemon (400 HP, projectile, 50% pain chance)
  - Baron of Hell (1000 HP, melee + projectile, 20% pain chance)
  - Cyberdemon (4000 HP, rockets, 8% pain chance)
  - And others (see knowledge/enemy_types.md)
- Armor system (green 33% absorption, blue 50% absorption)
- Ammo economy (ammo types, pickups, scarcity pressure)
- Difficulty-based damage scaling (easy = 0.5x incoming damage)
- Auto-aim / vertical targeting assistance
- Berserk power-up (10x melee damage)
- Deterministic PRNG (256-entry lookup table for demo replay)
