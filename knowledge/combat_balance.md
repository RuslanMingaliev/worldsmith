# Finding: Combat Balance

## Summary

The reference game uses a deterministic pseudo-random number generator (a fixed 256-entry lookup table returning 0-255) that drives all damage rolls, accuracy spread, and pain chance checks. Weapon damage follows a pattern of multiplying a random roll by a fixed constant, producing a small range of discrete outcomes. Hitscan weapons are instant-hit with auto-aim assistance, and accuracy degrades on sustained fire, rewarding deliberate single shots.

## Observed Mechanics

### Hitscan Damage Formula

- **Behavior**: Bullet weapons deal damage computed as `constant * (random_roll % N + 1)`, producing a small set of discrete outcomes rather than a smooth curve
- **Rules**: Each bullet is a single instant-hit trace (hitscan) from the shooter through the world. If it intersects a shootable target, the damage value is applied directly
- **Constants**:
  - Pistol / chaingun: `5 * (rnd%3 + 1)` = 5, 10, or 15 per shot (mean ~10)
  - Shotgun: 7 pellets, each using the pistol formula, total 35-105 (mean ~70)
  - Super shotgun: 20 pellets, each `5 * (rnd%3 + 1)`, total 100-300 (mean ~200)
  - Fist: `(rnd%10 + 1) * 2` = 2-20 (mean ~11); melee strength powerup multiplies by 10 = 20-200
  - Enemy hitscan (basic grunt): `((rnd%5) + 1) * 3` = 3-15 per shot (mean ~9)
  - Enemy shotgun grunt: salvo of 3 hitscan pellets, each rolling `((rnd%5) + 1) * 3` independently for both spread and damage; per-pellet range 3-15 (mean ~9), salvo total range 9-45 (mean ~27). The face-target and auto-aim slope are computed once *before* the pellet loop, so all pellets share the same base angle and vertical slope; only the horizontal spread offset and damage roll vary per pellet.
- **Feel**: The discrete damage tiers (5/10/15 for pistol) create a subtle "lucky hit" / "weak hit" dynamic. Most shots cluster around the mean but occasionally spike or dip

### Accuracy and Spread

- **Behavior**: The first pistol/chaingun shot is perfectly accurate (no angular offset). Subsequent shots while holding fire add random angular spread, making sustained fire less precise
- **Rules**: Spread is applied as `(rnd_a - rnd_b) << shift` added to the firing angle, where rnd_a and rnd_b are independent 0-255 random values. The subtraction creates a triangular distribution centered on zero (most shots near center, fewer at extremes)
- **Constants**:
  - Player pistol/chaingun refire: shift = 18, max spread ~5.6 degrees each side
  - Enemy basic grunt: shift = 20, max spread ~22 degrees each side (much less accurate)
  - Enemy shotgun grunt: each pellet in the 3-pellet salvo rolls `(rnd_a - rnd_b) << 20` independently — same shift (20) and same per-pellet max spread (~22 degrees each side) as the basic grunt. The base angle and vertical slope are shared by all pellets in the salvo (computed once before the pellet loop); only the horizontal spread roll is per-pellet. No first-shot accuracy bonus — every pellet of every salvo rolls full spread.
  - Player shotgun pellets: always use full spread (never "accurate"), shift = 18
  - Super shotgun: shift = 19 (~11 degrees), plus vertical spread via `(rnd-rnd)<<5` on the slope
  - Full angle circle = 2^32 units. 45 degrees = 0x20000000
- **Feel**: The triangular distribution is key. Most refire shots still land close to center, so sustained fire feels "sloppy but usable" rather than completely random. The first-shot accuracy bonus rewards tap-firing

### Auto-Aim (Vertical Targeting)

- **Behavior**: Before firing, the engine traces a ray to find a target, sweeping vertically within a view cone. If no target is found on the center line, it checks two additional angles offset horizontally
- **Rules**: The bullet slope (vertical angle) is set by the auto-aim slope helper, which attempts auto-aim at the aimed direction, then tries +5.6 degrees and -5.6 degrees horizontally. The vertical aiming window is approximately +/- 32 degrees (slope of 100/160)
- **Constants**:
  - Auto-aim search range: 1024 world units (the reference engine's coordinate unit) (16 * 64)
  - Horizontal auto-aim sweep: ~5.6 degrees each side (1<<26 angle units)
  - Vertical aim window: atan(100/160) ~= 32 degrees up and down
- **Feel**: Auto-aim makes the game forgiving on vertical alignment. Players only need to face roughly toward enemies horizontally. The horizontal sweep means the engine can "find" nearby targets even when not perfectly aimed

### Weapon Fire Rate

- **Behavior**: Each weapon has a state cycle defined in ticks (the reference engine runs at 35 ticks/sec) (1 tick = 1/35 second). The fire animation plays through several states, and the weapon cannot fire again until it returns to the ready state or reaches a refire check
- **Rules**: State durations are defined in tick counts. The total fire cycle is the sum of all state ticks from attack start back to ready/refire
- **Constants**:
  - Pistol: 4 + 6 + 4 + 5 = 19 ticks (~0.54 seconds, ~1.84 shots/sec)
  - Shotgun: 3 + 7 + 5 + 5 + 4 + 5 + 5 + 3 + 7 = 44 ticks (~1.26 sec, ~0.80 shots/sec)
  - Chaingun: 4 + 4 + 0 = 8 ticks per pair (~0.23 sec, ~4.38 shots/sec, fires 2 per cycle)
  - Fist: 4 + 4 + 5 + 4 + 5 = 22 ticks (~0.63 sec)
  - Tick rate: 35 ticks per second
- **Feel**: The pistol is deliberately slow for a starting weapon. The chaingun fires the same bullets at roughly 4x the rate, making it a clear upgrade. The shotgun's long pump animation creates a vulnerable window but higher burst damage

### Range and Hit Detection

- **Behavior**: Bullet weapons are pure hitscan (instant ray trace). They have no travel time or drop. Projectile weapons fire physical objects that travel through the world
- **Rules**: Hitscan traces a line from the shooter through the map, checking for intersections with walls and things. Projectiles are spawned as moving objects with defined speed
- **Constants**:
  - Hitscan maximum range (MISSILERANGE): 2048 world units (32 * 64)
  - Melee range (MELEERANGE): 64 world units
  - Melee check distance: MELEERANGE - 20 + target radius (so ~64 world units for standard enemies with radius 20)
  - Player radius: 16 world units
  - Standard enemy radius: 20 world units
  - For reference: a standard door is 64 units wide, a corridor is typically 128-256 units
- **Feel**: Hitscan range is generous enough that in most indoor environments, if you can see it, you can hit it. Melee range requires getting very close, which creates risk

### Projectile Damage

- **Behavior**: Enemy projectiles are physical objects that travel through the world and deal damage on contact. The damage on impact uses a formula similar to hitscan but with a different random multiplier
- **Rules**: Projectile impact damage = `(rnd%8 + 1) * missile_damage_constant`. The damage constant is defined per projectile type in the object data
- **Constants**:
  - Ranged-melee hybrid fireball: `(rnd%8 + 1) * 3` = 3-24 damage (mean ~13.5)
  - Floating projectile mid-tier fireball: `(rnd%8 + 1) * 5` = 5-40 damage (mean ~22.5)
  - Ranged-melee hybrid fireball speed: 10 world units per tick (~350 units/sec)
- **Feel**: Projectile damage is more variable than hitscan (8 possible values vs 3-5), making individual hits feel more "swingy." The travel time makes them dodgeable, which is the core of the gameplay loop for ranged enemies

### Damage to Player (Armor and Damage Reduction)

- **Behavior**: When the player takes damage, armor absorbs a fraction of it. Skill level also affects damage taken
- **Rules**: Green armor (type 1) absorbs 1/3 of damage. Blue armor (type 2) absorbs 1/2 of damage. Absorbed damage is subtracted from armor points. When armor is depleted mid-hit, only the remaining armor points are absorbed. On the easiest skill, all damage is halved (right shift by 1)
- **Constants**:
  - Player starting health: 100
  - Maximum normal health: 100 (powerups can push to 200)
  - Green armor absorption: 33% (damage/3)
  - Blue armor absorption: 50% (damage/2)
  - Green armor points: 100 (absorbs ~33 HP worth of damage)
  - Blue armor points: 200 (absorbs ~100 HP worth of damage)
  - Easy skill damage multiplier: 0.5x
  - Damage screen flash cap: 100 (clamped regardless of actual damage)
- **Feel**: Green armor extends effective health from 100 to ~150. Blue armor extends it to ~200. The fractional absorption means armor is always useful but never makes the player invincible

### Pain and Stagger

- **Behavior**: When a target takes damage, there is a random chance it enters a pain state (brief stagger animation). This interrupts whatever the enemy was doing
- **Rules**: After applying damage, the engine rolls the gameplay PRNG (256-entry table, deterministic for replay) against the enemy's pain chance. If the roll is less than the pain chance, the target enters its pain state animation. Pain chance is defined per enemy type as a value from 0-255
- **Constants**:
  - Basic hitscan trooper (low HP): painchance 200 (~78% chance per hit)
  - Shotgun trooper (3-pellet hitscan): painchance 170 (~67%)
  - Ranged-melee hybrid (claw + projectile): painchance 200 (~78%)
  - Melee-only beast: painchance 180 (~71%)
- **Feel**: High pain chances on basic enemies mean the pistol can effectively "stun-lock" them with sustained fire, giving even the weakest weapon crowd control utility. This is a crucial balance lever

### Enemy Health Tiers

- **Behavior**: Enemies are organized into clear health tiers that determine how many shots from each weapon are needed to kill them
- **Rules**: Health is a flat integer value. Enemies die when health reaches 0 or below
- **Constants**:
  - Basic hitscan trooper (low HP): 20 HP (1-4 pistol shots, mean ~2)
  - Shotgun trooper (3-pellet hitscan): 30 HP (2-6 pistol shots, mean ~3)
  - Ranged-melee hybrid (claw + projectile): 60 HP (4-12 pistol shots, mean ~6)
  - Melee-only beast: 150 HP (10-30 pistol shots, mean ~15)
- **Feel**: The basic trooper is designed to die in 1-2 pistol shots, making the player feel competent immediately. The ranged-melee hybrid is the first real test, requiring sustained fire. The melee-only beast is clearly not a "pistol enemy," pushing the player toward better weapons

### Ammo Economy

- **Behavior**: The player starts with a pistol and limited ammunition. Ammo pickups restore fixed amounts
- **Rules**: Each weapon consumes a defined amount of ammo per shot from its ammo pool. Pistol and chaingun share the "clip" ammo type
- **Constants**:
  - Starting ammo: 50 bullets (clip type)
  - Clip pickup: 10 bullets (half = 5 from dropped clips)
  - Box of bullets: 50
  - Max ammo (bullets): 200 (400 with ammo capacity expander)
  - Pistol: 1 bullet per shot
  - Chaingun: 1 bullet per shot (but fires 2 per cycle)
  - Shotgun: 1 shell per shot
  - Max ammo (shells): 50 (100 with ammo capacity expander)
- **Feel**: Starting with 50 bullets means ~25 basic troopers worth of ammo at average damage, or only ~8 ranged-melee hybrids. This creates early scarcity pressure that drives exploration and weapon acquisition

### Damage Randomization System

- **Behavior**: All damage uses a deterministic pseudo-random number generator based on a fixed 256-entry lookup table
- **Rules**: The gameplay PRNG (256-entry table, deterministic for replay) increments an index into the table and returns the byte value (0-255). The same sequence is used for all gameplay randomness (damage, spread, pain checks, AI decisions). This makes the game fully deterministic given the same inputs (important for demo recording/playback)
- **Constants**:
  - Table size: 256 entries
  - Value range: 0-255
  - Separate index for gameplay vs cosmetic (the cosmetic PRNG is a separate stream so visuals don't perturb gameplay seed)
- **Feel**: The fixed table means damage is pseudo-random but repeatable. In practice, the sequence feels random to the player. The separation of gameplay and cosmetic random generators ensures visual effects never desync gameplay determinism

## Key Insights

1. **The "multiply random by constant" pattern** is used everywhere. It produces a small number of discrete damage values (3 or 5 or 8 possible outcomes) rather than a smooth distribution. This creates memorable moments ("I one-shot that hybrid!") without requiring complex math.

2. **First-shot accuracy is a core design pillar.** The pistol and chaingun reward careful, aimed single shots with perfect accuracy. Holding down fire trades precision for speed. This gives the player a meaningful choice even with the simplest weapon.

3. **The triangular spread distribution** (random minus random) is an elegant solution. Most shots cluster near center, with outliers being rare. This feels better than uniform random spread because "mostly accurate with occasional wild shots" matches player intuition.

4. **Pain chance as a balance lever** is underappreciated. The ~78% pain chance on basic enemies means the pistol can interrupt most attacks, making it viable for survival even when outgunned. Without this, the pistol would feel useless against anything.

5. **Damage is deliberately "swingy"** at the low end. A pistol shot can do 5 or 15 damage -- a 3x variance. Against a 20 HP basic trooper, this means 1-4 shots to kill. This variance keeps early combat from feeling mechanical even when fighting the same enemy repeatedly.

6. **Enemy hitscan vs player hitscan uses asymmetric accuracy.** Enemies use a wider spread angle (shift 20 vs 18, so 4x wider spread), making their shots miss more often. This compensates for the fact that enemies always face the player before shooting.

7. **Weapon tiers create clear "zones of effectiveness."** The pistol kills basic troopers efficiently, struggles with ranged-melee hybrids, and is nearly useless against melee-only beasts. Each weapon tier opens up a new class of enemy that feels manageable. This drives the player's sense of progression.

## Combat Constants Summary

| Parameter | Value | Notes |
|---|---|---|
| Tick rate | 35/sec | All timings in ticks |
| Player health | 100 | Max 200 with powerups |
| Pistol damage | 5/10/15 | Per shot, uniform random |
| Pistol fire cycle | 19 ticks (~0.54s) | ~1.84 shots/sec |
| Pistol accuracy (first shot) | Perfect | No spread on first shot |
| Pistol accuracy (refire) | +/- ~5.6 deg max | Triangular distribution |
| Shotgun damage | 35-105 (7 pellets) | Mean ~70 |
| Shotgun fire cycle | 44 ticks (~1.26s) | ~0.80 shots/sec |
| Chaingun fire cycle | 8 ticks (~0.23s) | 2 shots per cycle |
| Fist damage | 2-20 | Melee strength powerup: 20-200 |
| Hitscan range | 2048 world units | Effectively infinite indoors |
| Melee range | 64 world units | Very close |
| Auto-aim range | 1024 world units | For bullet slope |
| Basic trooper HP | 20 | 1-4 pistol shots |
| Shotgun trooper HP | 30 | 2-6 pistol shots |
| Ranged-melee hybrid HP | 60 | 4-12 pistol shots |
| Melee-only beast HP | 150 | 10-30 pistol shots |
| Basic trooper attack damage | 3-15 | Per shot |
| Ranged-melee hybrid fireball damage | 3-24 | Dodgeable projectile |
| Ranged-melee hybrid melee damage | 3-24 | Same formula |
| Melee-only beast bite damage | 4-40 | Melee only |
| Green armor absorption | 33% | Type 1 |
| Blue armor absorption | 50% | Type 2 |
| Starting ammo (bullets) | 50 | ~25 basic trooper kills |
| Clip pickup | 10 bullets | Half from drops |
| Max bullets | 200 | 400 with ammo capacity expander |
| Enemy spread (grunt) | +/- ~22 deg max | 4x wider than player |
| Pain chance (basic trooper) | 200/256 (~78%) | High stagger rate |
| Pain chance (ranged-melee hybrid) | 200/256 (~78%) | High stagger rate |
| Easy skill damage | 0.5x | Halved incoming damage |

## Open Questions

- How does the sound alert system (noise-propagation alert routine) affect enemy activation range and combat pacing?
- What is the exact behavior of the reactiontime counter and how does it create the delay before enemies first attack?
- How does the target threshold system (BASETHRESHOLD = 100 ticks) affect enemy target switching in multi-enemy encounters?
- What are the movement speeds of enemies relative to the player, and how does this affect kiting/retreat strategies?
- How does the line-of-sight check interact with partial cover and what role does the reject matrix play in large-scale combat?
