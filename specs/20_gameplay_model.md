# Gameplay Model

## Intent

The generated prototype should feel like a minimal retro shooter vertical slice, not like a generic tech demo.

The player should perceive:
- immediate responsiveness
- pressure while moving
- a clear hostile space
- simple combat
- a clear objective

## Core Gameplay Loop

explore -> encounter threat -> attack or evade -> survive -> reach exit

## Required Gameplay Features

### Player Movement
The player must be able to:
- move forward and backward
- turn left and right
- strafe left and right

Movement uses a momentum-based physics model. See [21_player_movement.md](21_player_movement.md) for detailed mechanics.

### World Collision
The player must not be able to walk through walls.

### Combat

The player has one ranged weapon (pistol). Combat uses hitscan (instant ray trace) -- there is no projectile travel time.

**Firing:**
- Player presses fire input
- A ray is traced from the player's position in the player's facing direction
- If the ray intersects an enemy within weapon range, that enemy takes damage
- The weapon cannot fire again until the fire cycle time elapses (0.54 seconds)

**Damage:**
- Each shot produces one of a small set of discrete damage values (not a smooth range)
- The specific values are defined in `25_game_tuning.md`
- The discrete outcomes create "lucky hit" and "weak hit" moments

**Accuracy (implemented):**
- First shot after `IDLE_THRESHOLD_SEC` idle: perfectly accurate (zero angular spread)
- Sustained fire: random angular offset applied as `(rand - rand) * PISTOL_REFIRE_SPREAD_RAD` — triangular distribution, +/- 5.6 degrees max
- Triangular distribution = difference of two uniform random values (most shots near center, outliers rare)
- Both the first-shot accuracy rule and triangular spread are fully implemented in `weapon_system::fire`

**Pain/Stagger:**
- When an enemy takes damage, there is a chance it enters a pain state
- During pain, the enemy's current action (moving, attacking) is interrupted
- Pain chance is checked per hit and is defined per enemy type
- High pain chance on basic enemies means sustained fire can interrupt their attacks

**Visual Feedback:**

Combat actions trigger short-lived visual effects (muzzle flash, hit-scan tracer, wall puff, blood splat, enemy pain flash, player damage tint, enemy death fade and corpse). Effects are layered on top of existing combat behavior and do not change combat outcomes. See [`40_visual_feedback.md`](40_visual_feedback.md) for behaviors and [`25_game_tuning.md`](25_game_tuning.md#visual-feedback) for constants.

The existing console messages from `weapon_system.rs` ("Hit for X! ...") and `enemy_logic.rs` ("Enemy hit player for X! ...") are *supplemented* by visual feedback, not replaced. Their fate is a separate Coder decision once visual feedback ships.

### Enemy

One enemy archetype exists: a basic hitscan trooper (low HP, single hitscan attack, high pain chance).

#### Current Implementation

The enemy currently uses a simplified AI:
- Detects player immediately (no line-of-sight check)
- Waits a reaction delay (0.23s) before first attack
- Moves toward player using smooth vector movement
- Deals contact damage (3-15 random) when within melee range
- Enters pain state on hit (78% chance, 0.17s duration)
- Dies at 0 HP

AI states: Idle → Chase → Pain → Death (no separate Attack state).

#### Target Behavior (from knowledge)

The full AI from knowledge/enemy_types.md is significantly more complex. The following are extracted behaviors that are **not yet implemented** but documented for future generation:

**Hitscan ranged attack**: Enemy should fire hitscan shots at range (up to 2048 map units) with +/- 22 degree spread, not contact damage. Attack sequence takes 0.74 seconds (wind-up, fire, cooldown).

**Distance-based fire probability**: At close range, almost always fires. At long range, probability drops (~22% at max distance). If just hit, always retaliates immediately. No double attack (must take at least one chase step between shots).

**Line-of-sight detection**: Enemy should only react when it can see the player. No distance limit — if LOS exists, enemy reacts.

**8-directional grid movement**: Prefers diagonal paths, tries cardinal directions if blocked. Random 0-15 steps before re-evaluating direction. Never voluntarily reverses.

**Idle scanning**: 0.57s scan cycle before detection. 180-degree forward arc.

**Chase timing**: 0.91s per animation cycle (8 frames). Active sound chance 1.2% per frame.

**Target persistence**: 2.86s threshold of stubborn pursuit after acquiring target.

**Death drops**: Ammo clip on death. Gib death below -20 HP.

**Full state machine**:
```
Idle --[player detected]--> Chase
Chase --[attack check passed]--> Attack
Chase --[damaged, pain check passed]--> Pain
Attack --[attack sequence complete]--> Chase
Pain --[pain duration elapsed]--> Chase
Any --[health <= 0]--> Death
```

### Level
The level must:
- contain walls and walkable space
- contain a player spawn
- contain at least one enemy
- contain at least one clear objective or exit

### HUD

A persistent heads-up display reports the player's current health (numeric value + proportional bar) and ammo (icon + digits) in the top-left corner. The HUD is read-only — it draws on top of the gameplay layers but does not change combat outcomes. See [`50_hud.md`](50_hud.md) for behaviors, [`25_game_tuning.md`](25_game_tuning.md#hud) for constants, and [`knowledge/hud.md`](../knowledge/hud.md) for the knowledge basis (numeric widget rules) and the prototype's deviations from it (top-left layout, proportional bar, per-band coloring, color-distinguished ammo pane in lieu of distinct fonts).

### Pickups and Ammo

Two pickup types exist in the level: health and ammo. Walking the player onto a pickup tile consumes it once, applies its effect (clamped to caps), and deactivates the pickup. The pickup is **refused** (left active for later) if the player is already at cap. The pistol consumes ammo per shot — when ammo reaches zero, the trigger is a no-op (no muzzle flash, no tracer, no shot) until ammo is replenished. Pickups are placed statically in `level_data::build_default`. See [`60_pickups.md`](60_pickups.md) for behaviors, [`25_game_tuning.md`](25_game_tuning.md#pickups) for constants, and [`knowledge/pickups.md`](../knowledge/pickups.md) for the knowledge basis (touch detection, refused-at-cap rule, ammo-gating-firing) and the prototype's scope reductions (single ammo category, no over-cap heals, no skill multiplier, no enemy drops).

### Game Over Flow

**Interactive mode (no `--autopilot` flag).** When the player either reaches the exit (`won = true`) or dies (`alive = false`), the engine MUST continue to render for at least `GAME_OVER_HOLD_SEC` seconds before exiting the main loop. The game-over colored border (green for win, red for lose; spec/50 § Render Order Update) and the HUD remain visible during the hold. The implementation MUST NOT exit on the same tick that the win/lose state is detected — that produces a zero-frame render of the game-over overlay and the player never sees the outcome.

Concretely, this requires the loop-exit *decision* and the loop-exit *action* to be separated:
- The decision (game over reached) flips a "game_over since" timestamp in the game state.
- The main loop continues to render frames until the elapsed time since the timestamp exceeds `GAME_OVER_HOLD_SEC`.
- After the hold elapses, the loop exits.

`GAME_OVER_HOLD_SEC` is defined in [`25_game_tuning.md`](25_game_tuning.md#visual). After the hold elapses the loop may exit immediately or wait for player input — the latter is **deferred**.

(Rationale: an earlier generated game flipped `running = false` on the same tick that the win/lose flag was set, then the `while window.is_open() && game.running` loop in `main.rs` exited before the next `draw()` call. The colored border rendered for zero frames. The fix is the decision/action separation described above.)

**Autopilot mode (`--autopilot <path>`).** The bot's `BotProgress::AllObjectivesComplete` signal terminates the loop on the next iteration, per `ir/contracts/_shared.yaml § main_cli`. The colored game-over border therefore renders for one frame in autopilot recordings — short enough that no human-perceptible hold occurs, which is intentional: specs/35 § Tooling Contract caps demo length below the 2-second hold duration so demo GIFs stay under the recording-time budget. The decision/action separation above still applies inside `game_loop::update`, but `main.rs`'s autopilot branch flips `running = false` on `AllObjectivesComplete` regardless of `game_over_at`, overriding the hold for this mode only.

## Implementation Status

**Implemented:**
- Player movement (forward/backward/strafe) with thrust+friction momentum model (see [`21_player_movement.md`](21_player_movement.md)).
- World collision — player cannot walk through walls; axis-aligned wall sliding.
- Combat — hitscan pistol: fire cycle, discrete damage (5/10/15), triangular spread, first-shot accuracy, pain/stagger system.
- Enemy basic trooper — AI states Idle/Chase/Pain/Dead; contact damage; reaction delay before first attack; pain flash visual.
- Level — walls, walkable space, player spawn, enemy spawn, exit objective.
- HUD — health bar + digits + ammo pane (see [`50_hud.md`](50_hud.md)).
- Pickups — health and ammo pickups; refused-at-cap rule; ammo gates firing (see [`60_pickups.md`](60_pickups.md)).
- Visual feedback — muzzle flash, hit-scan tracer, wall puff, blood splat, enemy pain flash, enemy death fade + corpse, player damage tint (see [`40_visual_feedback.md`](40_visual_feedback.md)).
- Game Over Flow — decision/action separation; GAME_OVER_HOLD_SEC hold before exit; colored border on win/lose.
- Demo mode — `--autopilot` and `--record-frames` CLI flags; deterministic replay (see [`35_demo_mode.md`](35_demo_mode.md)).

**Deferred:**
- See § Deferred Features below for the full list.

## Deferred Features

- Multiple weapons (shotgun, chaingun, fist, super shotgun)
- Projectile-based enemy attacks (fireball with travel time, dodging)
- Multiple enemy types (shotgun trooper, rapid-hitscan trooper, ranged-melee hybrid, melee-only beast, invisible melee-only beast, floating projectile mid-tier, kamikaze flyer, mid-tier melee+projectile boss, heavy melee+projectile boss, homing-missile boss, triple-projectile boss, rapid-plasma boss, area-attack boss with corpse-resurrect, rocket-launcher mega-boss, super-chaingun mega-boss)
- Armor and damage reduction system
- Full ammo economy (multiple categories, scarcity pressure, dropped-from-enemy pickups, backpack/cap expander)
- Difficulty levels (damage scaling)
- Auto-aim / vertical targeting
- Advanced enemy coordination
- Sound-based enemy alert propagation (sound propagates through connected sectors, blocked by closed doors)
- Melee attacks for enemies (beast bite, hybrid claw)
- Enemy infighting (enemies damaging each other, target switching)
- Enemy resurrection (area-attack boss reviving corpses)
- Deaf/ambush enemy flag (sight-only detection, ignores sound)
- Gib death prevention of resurrection
- Cutscenes
- Inventory UI
- Dialogue
- Stealth systems
- Multiplayer
- Procedural generation
