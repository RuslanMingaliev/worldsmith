# Finding: Enemy Types

## Summary

Enemies in the classic reference FPS share a common AI framework built around a state machine (idle, chase, attack, pain, death) and a set of modular behavior functions. The simplest enemy — the basic humanoid trooper — serves as the archetype: low health, hitscan attack, high pain chance, and slow movement. Enemy differentiation comes primarily from tuning constants (health, speed, pain chance, attack type) rather than fundamentally different AI logic. The system is elegant because the same core chase/attack loop produces wildly different gameplay encounters through just a few parameter changes.

## Observed Mechanics

### State Machine

- **Behavior**: Every enemy has a set of states forming a finite state machine. Each state specifies a sprite frame, a duration in tics (at 35 tics/second), an optional action function, and the next state. The enemy transitions automatically when a state's timer expires, and can be forced into a different state by external events (being damaged, spotting a player).
- **Rules**:
  - **Idle (Spawn)**: Two frames alternating with 10-tic durations. Each frame calls the "look" function to scan for players. The enemy stands in place, cycling between two frames, until it spots a target.
  - **Chase (See)**: Eight frames cycling with 4-tic durations. Each frame calls the "chase" function, which handles movement toward the player, attack checks, and direction changes. A full animation cycle is 32 tics (~0.91 seconds).
  - **Attack (Missile)**: Three frames — a 10-tic wind-up (face target), an 8-tic fire frame (deal damage), and an 8-tic cooldown. Total attack duration is 26 tics (~0.74 seconds). After attacking, returns to chase.
  - **Pain**: Two frames of 3 tics each (6 tics total, ~0.17 seconds). The pain interruption is brief, making enemies recover quickly.
  - **Death**: Five frames of 5 tics each. On frame 3, the enemy becomes non-solid (walkable). The final frame has a duration of -1, meaning it persists forever as a corpse.
  - **Gib Death (Extreme)**: Nine frames of 5 tics each. Triggered when damage overkills by more than the enemy's spawn health. A more dramatic death animation.
  - **Resurrection**: Four frames of 5 tics each, playing the death animation in reverse. Returns to chase state. Only possible if the enemy type has a raise state defined.
- **Constants**:
  - Tic rate: 35 per second
  - Idle frame duration: 10 tics (~0.29 seconds per frame)
  - Chase frame duration: 4 tics (~0.11 seconds per frame)
  - Attack total duration: 26 tics (~0.74 seconds)
  - Pain total duration: 6 tics (~0.17 seconds)
  - Death frame duration: 5 tics each
- **Feel**: The relatively long idle scan (20 tics per cycle) gives a relaxed, patrolling feel. Once alerted, the fast 4-tic chase frames make enemies feel urgent and aggressive. The very short pain duration means stun-locking weak enemies is possible with rapid fire but not trivially easy.

### Detection and Alerting (A_Look)

- **Behavior**: While idle, enemies scan for players each frame using two methods: checking if their sector has been tagged by sound propagation, or performing a direct visual scan. Once a target is found, the enemy transitions to its chase/see state and plays an alert sound.
- **Rules**:
  - Sound-based detection: When any monster or player fires a weapon, sound propagates through connected sectors recursively. Sound crosses open two-sided lines freely but is blocked by closed doors (zero-height openings). Sound-blocking lines (a special map flag) allow sound to pass once but not twice, creating a two-tier propagation system. Each sector stores a reference to the sound source, which idle enemies check.
  - Deaf/ambush enemies (a map editor flag): These ignore sound-based detection entirely. They only activate when they have direct line of sight to a player, making them useful for positioning surprise encounters.
  - Visual scan: The look function cycles through players (up to 4 in multiplayer) checking for line of sight. In the default (non-allaround) mode, it only looks in a 180-degree forward arc. Enemies farther than melee range who are behind the enemy are ignored. Line of sight uses the map's reject table for fast elimination, then traces a line checking for solid geometry.
  - Alert sound: The basic trooper randomly selects from three alert sounds, adding variety to encounters.
- **Constants**:
  - Sound propagation: Unlimited range through connected open sectors
  - Sound-blocking lines: Permit one level of propagation (so sound can cross one sound-blocking line but not two in sequence)
  - Visual arc: 180 degrees forward (ANG90 each side) during idle scanning
  - Players checked per look: Up to 2 before giving up
- **Feel**: Sound propagation creates a cascading alert effect — firing a weapon in a connected area wakes up every enemy that can "hear" it. This punishes reckless shooting and rewards careful play. The ambush flag lets level designers place enemies that only react to sight, creating trap encounters.

### Chase Behavior (A_Chase)

- **Behavior**: The core pursuit loop that runs each chase frame. Handles reaction time countdown, target validation, attack decisions, movement toward the player, and idle sounds.
- **Rules**:
  - **Reaction time**: On each chase frame, the reaction time counter decrements by 1. While reaction time is non-zero, the enemy will not attack (but will still chase). The basic trooper starts with 8 tics of reaction time, giving the player a brief grace period after being spotted.
  - **Target threshold**: After acquiring a target (especially by being shot), the enemy tracks a "threshold" counter that decrements each chase tic. While the threshold is active, the enemy stubbornly pursues its current target even if shot by something else. The threshold is set to 100 when a new target is acquired from damage.
  - **No double attack**: After attacking, the enemy sets a flag preventing it from attacking on the very next chase frame. On non-nightmare difficulty, it instead picks a new direction, giving the player a brief window.
  - **Melee check**: Performed first but the basic trooper has no melee state, so this is skipped.
  - **Ranged attack check**: The enemy will attempt a ranged attack if: (a) on Nightmare difficulty or movecount is zero, (b) it has line of sight to the target, (c) it passes the missile range probability check. After attacking, sets a flag to prevent immediate re-attack.
  - **Movement**: The enemy moves toward the player using an 8-direction grid (N, NE, E, SE, S, SW, W, NW). Movement speed is multiplied by pre-computed direction vectors. After moving a random number of steps (0-15, set each time a new direction is chosen), a new direction is calculated. If movement is blocked, the enemy picks a new direction immediately.
  - **Direction selection**: Prefers diagonal movement toward the player. If that fails, tries the two cardinal directions, with a random chance of swapping their priority. If all preferred directions fail, tries the old direction, then scans all eight directions randomly. Never reverses direction (turnaround) unless all other options are exhausted.
  - **Active sounds**: Each chase frame has a 3/256 (~1.2%) chance of playing an ambient idle sound.
  - **Turning**: The enemy's visual angle snaps toward its movement direction in 45-degree increments each frame, creating a visible turning animation.
- **Constants**:
  - Reaction time: 8 tics for the basic trooper (~0.23 seconds)
  - Target threshold: 100 tics (~2.86 seconds of stubborn pursuit)
  - Move count: Random 0-15 steps before re-evaluating direction
  - Active sound chance: 3/256 per chase frame
  - Movement directions: 8 cardinal + diagonal
  - Speed: 8 map units per movement step (basic trooper)
- **Feel**: The reaction time gives a satisfying "spotted!" moment where the player has a brief chance to react. The threshold system prevents enemies from being easily confused by crossfire. The random direction evaluation with diagonal preference creates naturalistic zig-zagging pursuit paths that feel organic rather than robotic.

### Ranged Attack Check (P_CheckMissileRange)

- **Behavior**: A probability-based check that determines whether an enemy should fire. Enemies at close range almost always fire, while distant enemies fire less often. This creates natural attack patterns without explicit timers.
- **Rules**:
  - Requires line of sight to the target
  - If the target just hit the enemy (MF_JUSTHIT flag), always fire (fight back immediately)
  - If reaction time is non-zero, never fire
  - Base distance is the approximate distance to the target minus 64 units
  - For enemies with no melee attack (like the basic trooper), subtract an additional 128 units from the distance, making them fire more aggressively at range
  - Distance is then converted from fixed-point to integer (shift right by 16)
  - Distance is capped at 200 (some specific enemy types have different caps or halvings)
  - A random number 0-255 is compared to the distance; if the random number is less than the distance, the attack is skipped
  - The basic trooper has no special distance modifiers (those are reserved for specific enemy types)
- **Constants**:
  - Base distance offset: -64 units
  - No-melee bonus: -128 additional units
  - Maximum probability cap: 200/256 (~78% chance of NOT firing at maximum distance)
  - Minimum effective range: At point-blank, the adjusted distance approaches 0, meaning the enemy almost always fires
- **Feel**: Close enemies are extremely dangerous because they fire almost every chase frame. Distant enemies fire sporadically, creating pressure without overwhelming the player. The "fight back" flag ensures enemies always retaliate when hit, making every encounter feel reactive.

### Hitscan Attack (A_PosAttack)

- **Behavior**: The basic trooper fires a single hitscan (instant-hit) projectile, similar to the player's pistol. The attack has random spread and variable damage.
- **Rules**:
  - Faces the target before firing
  - Uses auto-aim to find the vertical slope to the target (within the standard missile range)
  - Adds horizontal spread: a random offset of approximately +/- 5.6 degrees (the random spread uses two P_Random calls subtracted from each other, shifted left by 20 bits in angle space)
  - Damage is calculated as (random 1-5) * 3, giving a range of 3-15 damage per shot
  - The attack is an instant hitscan trace, not a projectile — it cannot be dodged once fired
  - Plays the pistol sound effect
- **Constants**:
  - Damage range: 3-15 per shot (average 9)
  - Damage formula: (P_Random() % 5 + 1) * 3
  - Horizontal spread: approximately +/- 5.6 degrees
  - Attack range: 2048 units (32 * 64, the standard missile range)
  - Attack type: Hitscan (instant)
- **Feel**: The variable damage (3-15) creates unpredictable threat levels. Sometimes a trooper barely scratches you; sometimes it deals significant damage. The spread means the attack can miss at range, making distance a valid defensive strategy against hitscan enemies. At close range, the spread is negligible and damage is very reliable.

### Shotgun Variant (A_SPosAttack)

- **Behavior**: The shotgun-wielding variant fires three hitscan pellets instead of one, each with independent spread and damage rolls. Otherwise uses the same core logic.
- **Rules**:
  - Fires 3 pellets, each with independent random spread
  - Each pellet deals (random 1-5) * 3 damage (same formula as single-shot)
  - Same horizontal spread per pellet as the basic attack
  - Maximum potential damage: 45 (3 pellets * 15 each)
- **Constants**:
  - Pellet count: 3
  - Damage per pellet: 3-15 (average 9)
  - Total damage range: 9-45 (average 27)
- **Feel**: Much more dangerous than the basic trooper at close range. The three independent pellets make the shotgunner a high-priority target. The per-pellet spread means some pellets can miss at range, making the damage fall off naturally with distance.

### Pain System

- **Behavior**: When damaged, an enemy has a chance to enter its pain state, interrupting whatever it was doing. The pain chance varies by enemy type and is a core balancing lever.
- **Rules**:
  - On each damage event, a random number 0-255 is compared to the enemy's pain chance
  - If the random number is less than the pain chance, the enemy enters its pain state
  - The pain state sets MF_JUSTHIT, causing the enemy to retaliate immediately on recovery
  - Pain state duration is very short (6 tics for the basic trooper)
  - Being damaged also sets reaction time to 0 (immediate attack readiness)
  - If the enemy was idle (spawn state) when hit, it transitions to chase
  - Getting hit also sets the attacker as the new target with a fresh threshold of 100
- **Constants**:
  - Basic trooper pain chance: 200/256 (~78%)
  - Shotgun trooper pain chance: 170/256 (~66%)
  - Chaingun trooper pain chance: 170/256 (~66%)
  - Imp pain chance: 200/256 (~78%)
  - Demon pain chance: 180/256 (~70%)
  - Cacodemon pain chance: 128/256 (50%)
  - Baron pain chance: 50/256 (~20%)
  - Knight pain chance: 50/256 (~20%)
  - Cyberdemon pain chance: 20/256 (~8%)
  - Spider Mastermind pain chance: 40/256 (~16%)
  - Lost Soul pain chance: 256/256 (100%, always flinches)
- **Feel**: High pain chance on weak enemies (troopers, imps) means they can be effectively stun-locked with rapid fire, making them feel manageable individually. Low pain chance on bosses means they shrug off hits and keep attacking, feeling relentless. This single number dramatically changes the feel of each enemy encounter.

### Melee Range Detection

- **Behavior**: Determines if an enemy is close enough for a melee attack. The basic trooper has no melee attack, but this is used by demons, imps, and other melee-capable enemies.
- **Rules**:
  - Uses approximate distance (not true Euclidean — a fast estimate that takes the larger axis plus half the smaller)
  - Melee range is 64 units, minus 20 units, plus the target's radius
  - Requires line of sight
  - For a standard player (radius 16 units), effective melee range is 60 units
- **Constants**:
  - Base melee range: 64 units
  - Offset: -20 units
  - Standard effective range: ~60 units (with player radius 16)
- **Feel**: The tight melee range means enemies must get very close, giving the player opportunities to backpedal. The line-of-sight requirement prevents melee through walls.

### Death and Item Drops

- **Behavior**: When health reaches zero, the enemy enters its death state sequence. If overkill damage exceeds the enemy's spawn health, it enters a more dramatic "extreme death" (gib) state instead. The enemy becomes non-solid partway through the death animation and may drop items.
- **Rules**:
  - Normal death: Health reaches 0 or below
  - Gib/extreme death: Health drops below negative spawn health (e.g., below -20 for the basic trooper)
  - On death frame 3, the enemy loses MF_SOLID flag (A_Fall), becoming walkable
  - Height is quartered on death (for collision purposes during the animation)
  - The basic trooper drops a clip (bullet ammo) on death
  - The shotgun trooper drops a shotgun on death
  - Death animation tics are randomized slightly (subtract 0-3 tics from the first frame), adding visual variety
  - Corpses can be resurrected by the Archvile enemy type if they have a raise state
- **Constants**:
  - Gib threshold: -spawnhealth (e.g., -20 for basic trooper)
  - Basic trooper drop: Ammo clip
  - Shotgun trooper drop: Shotgun
  - Death tic randomization: 0-3 tics subtracted from first frame
- **Feel**: Item drops create a tactical incentive to kill enemies for resources, especially the shotgun trooper early in the game. The gib mechanic provides satisfying visual feedback for powerful weapons and also prevents resurrection (no raise state for gibbed enemies).

### Line of Sight

- **Behavior**: A two-phase check determines whether one entity can see another. First, a fast rejection using a precomputed lookup table eliminates impossible sightlines. Then, a precise ray trace checks for obstructing geometry.
- **Rules**:
  - Phase 1 (Reject table): A precomputed matrix stored in the map data indicates which sector pairs can never see each other. This is a fast bitfield lookup.
  - Phase 2 (Ray trace): A line is traced from the looker's eye height (3/4 of total height) to the target. The trace checks for intercepting two-sided lines (walls, doors) that block the view.
  - Eye height is calculated as: z + height - (height / 4), which equals 3/4 of total height from the floor
- **Constants**:
  - Eye height: 3/4 of entity height from the floor
  - Basic trooper eye height: 42 units (3/4 of 56)
- **Feel**: The reject table optimization means hundreds of enemies can exist without lag from sight checks. The 3/4 eye height means enemies peer over shorter obstacles realistically.

### Movement System

- **Behavior**: Enemies move in one of eight directions on a grid system. Movement speed is an integer multiplied by pre-computed direction vectors.
- **Rules**:
  - Eight directions: E, NE, N, NW, W, SW, S, SE
  - Speed is multiplied by direction unit vectors (using ~0.707 for diagonals: the value 47000 in fixed-point, where FRACUNIT is 65536)
  - Movement is checked for collision with walls and other entities
  - If blocked, the enemy tries to open doors (use special lines) and picks a new direction
  - Floating enemies (like cacodemons) adjust height when blocked vertically
  - On the ground, enemy z is snapped to floor height after each move
- **Constants**:
  - Basic trooper speed: 8 (map units per move step)
  - Diagonal factor: ~0.717 (47000/65536)
  - Direction count: 8 + "no direction"
- **Feel**: The 8-direction movement creates slightly rigid paths that are characteristic of the era. Enemies don't smoothly curve toward the player but instead take staircase-like paths. This is visually distinctive and subtly easier for players to predict.

## Key Insights

- **One AI fits all**: Nearly every enemy in the game uses the exact same A_Look/A_Chase/attack framework. The dramatic difference in feel between a lowly trooper and a Baron of Hell comes entirely from tuning numbers (health, speed, pain chance, damage, attack type). This is an extraordinarily efficient design.

- **Pain chance is the most important balancing knob**: A 78% pain chance makes troopers feel manageable (they flinch often). A 20% pain chance makes barons feel imposing (they almost never flinch). The Lost Soul at 100% always flinches but compensates with aggressive charge attacks. This single value shapes the entire feel of each enemy encounter.

- **Hitscan vs. projectile is a fundamental enemy design axis**: The basic trooper uses hitscan (instant, cannot be dodged after firing). This makes it dangerous despite low damage because the player cannot react after the shot is fired — only prevention (killing or interrupting before the attack) works. Contrast with projectile enemies where dodging is the primary counterplay.

- **Sound propagation creates emergent encounters**: Firing a weapon alerts enemies through connected sectors, turning isolated fights into chain reactions. This creates emergent difficulty scaling and makes sound a strategic consideration.

- **The "reaction time" grace period is essential**: The 8-tic delay before a newly alerted enemy can attack gives the player a critical window to react. Without it, turning a corner into enemies would be instant death. This is a subtle but vital design choice.

- **Distance-based attack probability replaces explicit cooldowns**: Instead of putting attacks on a timer, the game makes distant enemies probabilistically less likely to fire. This creates natural-feeling attack patterns that are dense up close and sparse at range, without any visible "reloading" behavior.

- **No double attack rule prevents stunlock**: The MF_JUSTATTACKED flag ensures an enemy always takes at least one chase step between attacks. On non-Nightmare difficulty, this means the enemy must also pick a new direction, creating visible wind-up before the next shot.

## Enemy Constants Summary

| Enemy | Health | Speed | Radius | Height | Pain Chance | Attack Type | Damage/Shot | Mass |
|---|---|---|---|---|---|---|---|---|
| Former Human | 20 | 8 | 20 | 56 | 200/256 (78%) | Hitscan x1 | 3-15 | 100 |
| Shotgun Guy | 30 | 8 | 20 | 56 | 170/256 (66%) | Hitscan x3 | 9-45 | 100 |
| Chaingunner | 70 | 8 | 20 | 56 | 170/256 (66%) | Hitscan x1 (rapid) | 3-15 | 100 |
| Imp | 60 | 8 | 20 | 56 | 200/256 (78%) | Melee + Projectile | 3-24 (melee) / 3-24 (fireball) | 100 |
| Demon | 150 | 10 | 30 | 56 | 180/256 (70%) | Melee only | 4-40 | 400 |
| Spectre | 150 | 10 | 30 | 56 | 180/256 (70%) | Melee only (invisible) | 4-40 | 400 |
| Cacodemon | 400 | 8 | 31 | 56 | 128/256 (50%) | Projectile | 5-40 (fireball) | 400 |
| Lost Soul | 100 | 8 | 16 | 56 | 256/256 (100%) | Charge (3 dmg) | 3 | 50 |
| Baron of Hell | 1000 | 8 | 24 | 64 | 50/256 (20%) | Melee + Projectile | 10-80 (melee) / 8 (fireball) | 1000 |
| Hell Knight | 500 | 8 | 24 | 64 | 50/256 (20%) | Melee + Projectile | 10-80 (melee) / 8 (fireball) | 1000 |
| Revenant | 300 | 10 | 20 | 56 | 100/256 (39%) | Melee + Homing missile | Varies | 500 |
| Mancubus | 600 | 8 | 48 | 64 | 80/256 (31%) | Projectile x3 | 8 per fireball | 1000 |
| Arachnotron | 500 | 12 | 64 | 64 | 128/256 (50%) | Rapid plasma | Varies | 600 |
| Arch-Vile | 700 | 15 | 20 | 56 | 10/256 (4%) | Area fire attack | 20+70 blast | 500 |
| Cyberdemon | 4000 | 16 | 40 | 110 | 20/256 (8%) | Rockets x3 | 20-160 per rocket | 1000 |
| Spider Mastermind | 3000 | 12 | 128 | 100 | 40/256 (16%) | Super chaingun | 3-15 per bullet | 1000 |

Notes on the table:
- Radius and height are in map units (before FRACUNIT conversion)
- Speed is in map units per movement step (not per second)
- Actual movement speed per second = speed * moves_per_second (varies with chase frame rate)
- All enemies share reaction time of 8 tics
- Damage for projectile enemies refers to the projectile's damage field, not direct attack damage

## Open Questions

- How exactly does the Revenant's homing missile tracking work? (Separate tracer logic in A_Tracer)
- What are the precise damage formulas for melee attacks on demons, barons, and imps? (A_SargAttack, A_BruisAttack, A_TroopAttack)
- How does infighting work when enemies damage each other? (Target switching, species-based exceptions)
- How does the Arch-Vile's resurrection mechanic select corpses and what are its constraints?
- What are the Nightmare difficulty modifiers for enemy behavior? (Faster attacks, respawning)
- How does the Pain Elemental's Lost Soul spawning work and what limits it?
