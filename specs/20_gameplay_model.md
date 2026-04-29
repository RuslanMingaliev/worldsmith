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

**Accuracy (current):**
- The first shot after a pause uses a tighter alignment check (more likely to hit)
- Sustained fire uses a slightly looser alignment check
- This is a simplification — see Target Accuracy below

**Accuracy (target, from knowledge):**
- First shot: perfectly accurate (zero angular spread)
- Sustained fire: random angular offset +/- 5.6 degrees, triangular distribution
- Triangular distribution = difference of two uniform random values (most shots near center, outliers rare)
- Not yet implemented — current code approximates via dot-product threshold adjustment

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

## Deferred Features

- Multiple weapons (shotgun, chaingun, fist, super shotgun)
- Projectile-based enemy attacks (fireball with travel time, dodging)
- Multiple enemy types (shotgun trooper, rapid-hitscan trooper, ranged-melee hybrid, melee-only beast, invisible melee-only beast, floating projectile mid-tier, kamikaze flyer, mid-tier melee+projectile boss, heavy melee+projectile boss, homing-missile boss, triple-projectile boss, rapid-plasma boss, area-attack boss with corpse-resurrect, rocket-launcher mega-boss, super-chaingun mega-boss)
- Armor and damage reduction system
- Ammo economy and pickups
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
