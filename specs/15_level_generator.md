# Level Generator (Demo Scenarios)

## Intent

Some autopilot scenarios — particularly the one driving the PR-preview GIF — need a purpose-built level whose layout is chosen to demonstrate a specific gameplay behavior in a few seconds. The default level (`level_data::build_default`) is fine for general regression tests but is too cluttered to read at a glance: a short GIF of the bot wandering between an interior wall and a horizontal divider does not visually answer the question "did the enemy navigate around the obstacle?".

This spec defines a minimal `level_generator` module that produces a small, named, fully-deterministic `Level` for each demo scenario, and a tiny extension to the autopilot scenario YAML that lets a scenario opt into one of those levels by name.

The abstraction is deliberately small. There is no procedural generation, no template language, no DSL — each demo level is a hand-authored builder function that returns a `Level`. Adding a new demo level means adding one variant to an enum and one function, then naming the variant in a scenario YAML's `level:` field.

The knowledge basis is `knowledge/level_scenarios.md § Entity Placement Record` and § Key Insights ("a 'scenario' needs almost no new abstraction"). The reference treats a level as a tiny geometry plus a flat list of entity-placement records, processed by exactly the same code path that loads any other level. This spec mirrors that shape: the generator returns the same `Level` struct that `level_data::build_default` returns, and `game_loop` cannot tell which builder produced it.

## Architecture

```
specs/30 (autopilot)              specs/15 (this spec)
        │                                 │
        ▼                                 │
   parse_scenario  ◀─────── adds optional `level: <name>` key
        │                                 │
        │                                 │
   scenario.level.is_some()? ─yes─▶ level_generator::build(kind) ─▶ Level
                                  │
                                  └─no─▶ level_data::build_default() ─▶ Level

                 Level ─▶ game_loop::new(level) ─▶ GameState ─▶ render loop
```

The generator is consumed only by `main.rs` after CLI argument parsing (specs/35 § CLI). It is NOT called from `game_loop::update`, NOT from any per-frame path, and NOT during interactive play. Once `game_loop::new(level)` has built the `GameState`, the runtime treats a generated demo level as just another `Level` — the same struct, the same coordinate system, the same `is_wall` boundary check, the same tick loop.

## Demo Level Catalog

The generator owns a small `DemoLevelKind` enum. Each variant maps to one builder function that returns a fully-populated `Level`. The `Level` type itself is unchanged (`ir/contracts/level_data.yaml § Level`, `specs/25 § Level Layout`) — same struct, same fields, same `Vec<Vec<Tile>>` grid, same `Vec<Pickup>`.

| Variant | YAML name | Purpose | Implemented |
|---------|-----------|---------|-------------|
| `LocalChaseObstacle` | `local_chase_obstacle` | Demonstrates obstacle-aware enemy chase: one wall between player and enemy, valid path around. | yes |
| `KiteMelee` | `kite_melee` | Demonstrates the bot's kite policy: enemy spawns within `BOT_KITE_RANGE`, bot must back-pedal while firing (specs/30 § Bot Behavior). | yes |
| `RangedStandoff` | `ranged_standoff` | Demonstrates the basic trooper's ranged hitscan attack: open arena, enemy spawned ~8 tiles east of the player so the trooper can fire from outside `ENEMY_CONTACT_RANGE_TILES` while the bot waits stationary (specs/20 § Enemy, specs/25 § Enemy ranged hitscan rows). | yes |
| `ShotgunStandoff` | `shotgun_standoff` | Demonstrates the shotgun trooper's 3-pellet hitscan salvo: open arena, one shotgun trooper spawned 4 tiles east of the player so multiple pellets per salvo land on the player while the bot waits stationary (specs/20 § Enemy multi-archetype, specs/25 § Enemy § Per-archetype constants, specs/25 § Enemy § Pellet-loop salvo behavior). | yes |
| `ArmorAbsorption` | `armor_absorption` | Demonstrates armor's damage absorption: player spawns ON a green armor pickup so frame 1's pickup-check arms the player with `(armor=100, type=Green)`. A trooper 8 tiles east fires hitscans for the duration of a `wait:` objective; the armor pool absorbs 1/3 of every incoming hit (specs/25 § Armor / § Armor Damage Routing). The scenario asserts `player.armor < 100` — proving the absorption pipeline ran — and `player.armor > 0` — proving the absorption mechanic was not exhausted in one tick (knowledge/combat_balance.md § Damage to Player — "saved = damage/3 for green"). | yes |
| `ShellPickup` | `shell_pickup` | Demonstrates the bullets/shells pool independence: player spawns ON a single shell pickup in an otherwise-empty arena (no enemies). Frame 1's pickup-check consumes the shell, raising `player.shells` from 0 to `PICKUP_SHELLS_AMOUNT (4)` while leaving `player.bullets` unchanged at `PLAYER_BULLETS_INITIAL (50)`. The scenario asserts `player.bullets == 50` AND `player.shells == 4` — proving the pickup-to-category binding is one-to-one and the per-category pools are independent (specs/25 § Pickups § Player Ammo Pools, knowledge `combat_balance.md § Ammo Economy`). New in the 2026-05-18 ammo-split slice. | yes |

### LocalChaseObstacle

**Purpose.** A short, visually clear demonstration that the basic-trooper enemy can navigate around a static obstacle to reach the player. The level reduces all visual clutter (no pickups, no extra walls, no irrelevant geometry) so the GIF reader's eye is drawn directly to the chase path.

**Layout** (20 × 15 grid — same dimensions as the default level per `specs/25 § Level Layout`, so `GRID_WIDTH` / `GRID_HEIGHT` / `TILE_SIZE` from `level_data` apply unchanged):

- All edges are walls (border): tiles at `x = 0`, `x = 19`, `y = 0`, `y = 14`.
- Interior wall: a single vertical bar at `x = 10`, `y ∈ {4, 5, 6, 7, 8, 9, 10}` (7 tiles tall, vertically centered). This bar blocks the direct horizontal line between player and enemy.
- All other interior tiles are floor.

**Spawns** (tile units; same coordinate system as `level_data::Level::player_spawn` / `enemy_spawns` / `exit`):

| Entity | Position | Rationale |
|--------|----------|-----------|
| Player spawn | `(3.5, 7.5)` | Left side, vertically centered. Faces the obstacle along the horizontal axis. |
| Enemy spawn | `(16.5, 7.5)` | Right side, vertically centered. Mirrors the player so the obstacle sits exactly between them. |
| Exit | `(1.5, 1.5)` | Far top-left corner, well away from the action. The bot's `kill: enemy` objective never directs it toward the exit, so the win-condition check (`player.pos.distance_to(level.exit) < EXIT_RADIUS`) is not triggered during the demo. |
| Pickups | (none) | Empty `Vec<Pickup>`. Pickups would distract from the chase visualization. |

**Path geometry.** The 7-tile-tall obstacle leaves two gaps:

- A 3-tile-tall floor gap at the top: `y ∈ {1, 2, 3}` along the obstacle column (between the obstacle and the top border).
- A 3-tile-tall floor gap at the bottom: `y ∈ {11, 12, 13}` along the obstacle column (between the obstacle and the bottom border).

Either gap is wide enough for both the player (radius `0.4375` tile per `PLAYER_RADIUS_TILES`) and the enemy (radius `0.375` tile per `ENEMY_RADIUS_TILES`) to traverse with margin. The reference's chase routine (knowledge/level_scenarios.md § Obstacle-Aware Chase) prefers a direct diagonal toward the target; with the obstacle blocking that diagonal, the routine falls through to perpendicular alternates and then "continue old direction" — producing the characteristic "skim along the wall" path that this demo is meant to show.

**Visual reading of the GIF.** With both player and enemy moving toward each other, the enemy hits the obstacle first (because the bot stops when it reaches firing range, while the enemy continues to close to contact range). The enemy then takes a perpendicular along the wall, rounds the corner at one of the gaps, and resumes the chase. The bot, separately, navigates around the same obstacle to close the distance for `kill: enemy`. The chase path is visible for several seconds before the engagement begins.

### KiteMelee

**Purpose.** A short scenario that demonstrates the bot's kite policy (specs/30 § Bot Behavior). The enemy spawns inside `BOT_KITE_RANGE` of the player, so on the very first frame the bot enters kite mode (`forward = -1.0`) and back-pedals while continuing to fire. The level is otherwise empty so the back-pedal motion and falling enemy health are the only things on screen — the test verifies that the kite branch is wired up, not that the bot can also navigate.

**Layout** (20 × 15 grid — same dimensions and `TILE_SIZE` as the default level):

- All edges are walls (border): `x = 0`, `x = 19`, `y = 0`, `y = 14`.
- No interior walls. The room is one open rectangle.

**Spawns:**

| Entity | Position | Rationale |
|--------|----------|-----------|
| Player spawn | `(4.5, 7.5)` | West side, vertically centered. Player faces `+X` (default heading) so the enemy lies directly along the firing line. |
| Enemy spawn | `(6.0, 7.5)` | 1.5 tiles east of the player. Inside `BOT_KITE_RANGE` (2.0) so the bot enters kite mode on frame 1, but outside `ENEMY_CONTACT_RANGE_TILES` (0.8125) so kite-mode visual layout is preserved (the discs do not visibly overlap at spawn). With the 2026-05-13 combat slice replacing contact damage with the trooper's ranged hitscan attack, the kite buffer no longer protects against contact damage (which is retired) — it now protects against the trooper's near-melee hitscan, where the spread cone (±22°) at 1.5 tiles distance covers nearly the full forward arc, so a trooper that completes its 0.74s Attack sequence almost always hits. The bot must back-pedal AND fire fast enough to kill the trooper before the first Attack-state hitscan releases (the trooper's high pain-chance helps — sustained pistol fire tends to pain-lock the trooper before its windup-elapsed fire latch trips). |
| Exit | `(1.5, 1.5)` | Far top-left corner; the `kill: enemy` objective never directs the bot toward the exit, so the win-condition check is not triggered. |
| Pickups | (none) | Empty `Vec<Pickup>`. Pickups would distract from the kite visualization and would also let the bot recover health during the test, which would dilute the `player.health > 80` assertion. |

**Behavior to observe.** The bot starts inside kite range with the enemy directly east. On frame 1 the bot fires (LoS clear, `dist = 1.5 < BOT_FIRE_MAX_RANGE`, roughly facing) and emits `forward = -1.0` (kite mode). The bot retreats westward; the enemy chases at 2.0 tiles/sec. The pistol kills the enemy in 2–4 shots (mean 10 dmg vs 20 HP); during those ~1.0–2.0 seconds the bot may take 0–1 ranged hitscan hits from the trooper if a Pain-state interruption fails to stun-lock the trooper before its Attack windup elapses — `player.health > 80` should hold across the run because (a) first-shot accuracy lands the first hit, (b) 78% pain chance interrupts the trooper's Attack sequence frequently before the windup elapses, (c) the bot's max speed exceeds the enemy's 2.0 tiles/sec, and (d) even a successful trooper hitscan deals 3–15 (mean 9) damage — well below the 20-HP buffer. With the 2026-05-13 combat slice's contact-damage retirement, the trooper's ONLY harm vector here is the ranged hitscan; the assertion's robustness depends on pain-locking the trooper rather than out-running contact range.

### RangedStandoff

**Purpose.** A short scenario that exercises the basic trooper's ranged hitscan attack (specs/20 § Enemy, specs/25 § Enemy). The trooper spawns 8 tiles east of the player in an open arena. The bot's first objective is `wait: <frames>` so the player stands still while the trooper enters its Attack state and fires hitscan rounds from well outside `ENEMY_CONTACT_RANGE_TILES`. Subsequent objectives close the engagement so the scenario completes deterministically. The level is otherwise empty so the only damage source the assertion can attribute is the trooper's hitscan.

**Layout** (20 × 15 grid — same dimensions and `TILE_SIZE` as the default level):

- All edges are walls (border): `x = 0`, `x = 19`, `y = 0`, `y = 14`.
- No interior walls. The room is one open rectangle.

**Spawns:**

| Entity | Position | Rationale |
|--------|----------|-----------|
| Player spawn | `(4.5, 7.5)` | West side, vertically centered. Player faces `+X` (default heading) so the enemy lies directly along the firing line — trooper LoS to player and bot facing toward target both hold from frame 0. |
| Enemy spawn | `(12.5, 7.5)` | 8.0 tiles east of the player along the same horizontal line. Outside `BOT_KITE_RANGE` (2.0) so kite mode does not activate immediately. Outside `BOT_FIRE_MAX_RANGE`-minus-margin so the bot also takes a moment to engage. Inside `ENEMY_ATTACK_RANGE_TILES` (64.0) so the trooper can fire from spawn. Outside `ENEMY_CONTACT_RANGE_TILES` (0.8125) by ~10× so contact damage is impossible during the scripted wait window. |
| Exit | `(1.5, 1.5)` | Far top-left corner; `kill: enemy` and `wait:` objectives never direct the bot toward the exit, so the win-condition check is not triggered. |
| Pickups | (none) | Empty `Vec<Pickup>`. The dropped ammo clip from the trooper's death (specs/60 § Enemy Ammo Drops) is the only pickup that exists during the run; the level seeds none so the assertion can attribute any pre-kill damage exclusively to the trooper's hitscan. |

**Behavior to observe.** During the `wait:` objective the bot stands still and the trooper starts its state machine: Idle (reaction delay) → Chase (immediate, since LoS holds) → Attack (windup, fire, cooldown). Each Attack cycle resolves a hitscan trace at the player with `(rand_a − rand_b) * ENEMY_ATTACK_SPREAD_RAD` triangular spread. With the trooper at 4–8 tiles distance throughout the wait window (the enemy moves ~2.0 tiles/sec while in Chase between attacks), the player remains far outside contact range so any HP loss is provably from ranged hitscan. After the wait completes, `kill: enemy` engages: the bot turns toward the trooper, fires the pistol from path-follow distance, and the trooper dies in 2–4 shots (specs/25 § Damage Randomization). The dropped ammo clip lands at the trooper's death position (specs/60 § Enemy Ammo Drops); it is irrelevant to the assertions but exercises the death-time spawn hook.

### ShotgunStandoff

**Purpose.** A short scenario that exercises the shotgun trooper's 3-pellet hitscan salvo (specs/20 § Enemy multi-archetype, specs/25 § Enemy § Per-archetype constants, specs/25 § Enemy § Pellet-loop salvo behavior). The shotgun trooper spawns 4 tiles east of the player in an open arena — close enough that a meaningful number of pellets from each salvo land on the player at the trooper's ±22° per-pellet spread, far enough that the trooper cannot contact-damage the player from spawn. The bot's first objective is `wait: <frames>` so the player stands still through multiple salvos; subsequent objectives close the engagement so the scenario completes deterministically. The level is otherwise empty so the only damage source the assertion can attribute is the shotgun trooper's salvo.

**Layout** (20 × 15 grid — same dimensions and `TILE_SIZE` as the default level):

- All edges are walls (border): `x = 0`, `x = 19`, `y = 0`, `y = 14`.
- No interior walls. The room is one open rectangle.

**Spawns:**

| Entity | Position | Archetype | Rationale |
|--------|----------|-----------|-----------|
| Player spawn | `(4.5, 7.5)` | — | West side, vertically centered. Player faces `+X` (default heading) so the enemy lies directly along the firing line — trooper LoS to player and bot facing toward target both hold from frame 0. |
| Enemy spawn | `(8.5, 7.5)` | `Archetype::ShotgunTrooper` | 4.0 tiles east of the player along the same horizontal line. Outside `BOT_KITE_RANGE` (2.0) so kite mode does not activate immediately. Outside `ENEMY_CONTACT_RANGE_TILES` (0.8125) by ~5× so contact damage is impossible during the scripted wait window. Inside `ENEMY_ATTACK_RANGE_TILES` (64.0) so the trooper can fire from spawn. At 4 tiles the ±22° per-pellet horizontal spread cone has half-width ~1.6 tiles around the aim direction; the triangular distribution concentrates pellets near the aim center, so the typical 3-pellet salvo lands 1–2 pellets on a player-sized target. Closer placements (≤ 2 tiles) would trip kite mode; farther placements (≥ 8 tiles) make pellet hits too rare to assert against in a tight wait window. |
| Exit | `(1.5, 1.5)` | — | Far top-left corner; `kill: enemy` and `wait:` objectives never direct the bot toward the exit, so the win-condition check is not triggered. |
| Pickups | (none) | — | Empty `Vec<Pickup>`. The dropped ammo clip from the trooper's death (specs/60 § Enemy Ammo Drops) is the only pickup that exists during the run; the level seeds none so the assertion can attribute any pre-kill damage exclusively to the shotgun trooper's salvo. The shotgun trooper drops the same ammo clip as the basic trooper in this slice (specs/25 § Enemy § Drop-on-death (both archetypes)). |

**Behavior to observe.** During the `wait:` objective the bot stands still and the shotgun trooper starts its state machine: Idle (reaction delay, 0.23 s) → Chase (one tick — Attack gate satisfied immediately) → Attack (≈0.857 s sequence; 0.286 s wind-up then 3-pellet salvo fires). Per-archetype Attack-sequence duration: the shotgun trooper's 30-tick sequence is slightly slower than the basic trooper's 26-tick (knowledge/enemy_types.md § Shotgun Variant) — so over a 2-second wait the shotgun trooper fires roughly 2 salvos = 6 pellets total, of which ~3 land on the player at the 4-tile range. Each pellet rolls damage from `[3, 6, 9, 12, 15]` (mean 9), so the player typically loses 15–35 HP during the wait. After the wait completes, `kill: enemy` engages: the bot turns toward the shotgun trooper, fires the pistol from path-follow distance, and the trooper dies in 2–6 shots (specs/25 § Damage Randomization — pistol mean 10 damage × 30 HP shotgun ≈ 3 pistol shots). The dropped ammo clip lands at the trooper's death position (specs/60 § Enemy Ammo Drops); it is irrelevant to the assertions but exercises the death-time spawn hook.

The 4-tile distance is also outside `BOT_FIRE_MAX_RANGE` (10.0) − by definition the bot CAN fire from this distance if facing the enemy. With the bot's `wait:` objective active the bot does not fire (a `wait` produces `InputState::default()` per frame, no fire bit), so the trooper is uncontested during the wait window — exactly what the assertion needs to attribute damage to the salvo.

### ArmorAbsorption

**Purpose.** A short scenario that exercises the armor system end-to-end (specs/25 § Armor / § Armor Damage Routing; knowledge/combat_balance.md § Damage to Player; knowledge/pickups.md § Armor Pickup Tiers). The player spawns on a green armor pickup so the per-frame pickup check on frame 1 consumes it (armor set to 100, type set to Green). A basic trooper sits 8 tiles east in an open arena; the bot's first objective is `wait:` for ~3 seconds so the trooper fires several hitscans uncontested while the armor pool absorbs 1/3 of each hit. The bot then kills the trooper to complete the run deterministically.

**Layout** (20 × 15 grid — same dimensions and `TILE_SIZE` as the default level):

- All edges are walls (border): `x = 0`, `x = 19`, `y = 0`, `y = 14`.
- No interior walls. The room is one open rectangle.

**Spawns:**

| Entity | Position | Rationale |
|--------|----------|-----------|
| Player spawn | `(4.5, 7.5)` | West side, vertically centered. Player faces `+X` (default heading) so the enemy lies directly along the firing line — trooper LoS to player and bot facing toward target both hold from frame 0. |
| Enemy spawn | `(12.5, 7.5)` | 8.0 tiles east of the player along the same horizontal line. Same placement as `RangedStandoff` — outside `BOT_KITE_RANGE`, outside `ENEMY_CONTACT_RANGE_TILES` by ~10×, inside `ENEMY_ATTACK_RANGE_TILES`. Archetype `BasicTrooper` (the shotgun trooper's salvo would land too much damage per tick to leave the green armor pool partially depleted within the `wait:` window). |
| Exit | `(1.5, 1.5)` | Far top-left corner; `kill: enemy` and `wait:` objectives never direct the bot toward the exit, so the win-condition check is not triggered. |
| Pickups | one `Pickup { kind: PickupKind::ArmorGreen, pos: Vec2::new(4.5, 7.5), active: true }` | Green armor placed at the player's spawn position. The per-frame pickup check on frame 1 sees `distance_to(player.pos) == 0 < PICKUP_RADIUS_TILES (1.0)` and the acceptance condition `armor (0) < PICKUP_ARMOR_GREEN_TARGET_POINTS (100)` holds, so the pickup is consumed on frame 1: `armor = 100, armor_type = Green`. The "player spawns standing on the pickup" pattern guarantees frame-1 acquisition without requiring the bot to move. No other pickups — no ammo, no health — so the scenario can attribute every health-pool change exclusively to the trooper's hitscan stream and every armor-pool decrement exclusively to the absorption mechanic. |

**Behavior to observe.** Frame 1: `(armor=100, type=Green)` from the spawn-tile pickup. Frame 2 onward: bot's first objective is `wait:` for ~180 frames (3 seconds). Trooper state machine: Idle 0.23 s → Chase (no movement constraint along y; trooper closes toward player at 2.0 tiles/sec along x) → Attack 0.857 s sequence with 0.286 s wind-up + hitscan + cooldown. Over 3 seconds the trooper fires roughly 3–4 hitscans; at the ±22° spread cone over an 8 → 4 tile distance, ~50–70% of pellets typically land. Each landed hit rolls damage 3, 6, 9, 12, or 15 (mean 9); the armor pool absorbs `damage / 3` (integer division). Expected end-of-wait state: `armor ≈ 70–95`, `health ≈ 70–95`. After the wait completes, the bot's second objective is `kill: enemy` — the trooper dies in 2–4 pistol shots and the scenario ends. Determinism follows from fixed RNG seeds + fixed dt (specs/35 § Determinism) so the exact end-state values are reproducible across runs.

### ShellPickup

**Purpose.** A short scenario that exercises the bullets/shells pool independence (specs/25 § Pickups § Player Ammo Pools; specs/60 § Shell Pickup Consumption; knowledge `combat_balance.md § Ammo Economy` — "picking up shells never changes the bullets count, and vice versa"). The player spawns on a single shell pickup in an otherwise-empty arena. Frame 1's pickup-check consumes the shell, raising `player.shells` from `PLAYER_SHELLS_INITIAL = 0` to `PICKUP_SHELLS_AMOUNT = 4` while leaving `player.bullets` unchanged at `PLAYER_BULLETS_INITIAL = 50`. The scenario then `wait`s a few frames before the assertion check so no transient state is mid-flight when assertions run.

The scenario is enemy-free deliberately: with no enemies the bot does not fire (and even if it did, the pistol's gate reads `player.bullets > 0`, so a stray shot would decrement bullets — defeating the point of the assertion). The empty arena also means the only state-change source is the pickup-check on frame 1, which makes the assertion's pass/fail signal unambiguous.

**Layout** (20 × 15 grid — same dimensions and `TILE_SIZE` as the default level):

- All edges are walls (border): `x = 0`, `x = 19`, `y = 0`, `y = 14`.
- No interior walls. The room is one open rectangle.

**Spawns:**

| Entity | Position | Rationale |
|--------|----------|-----------|
| Player spawn | `(4.5, 7.5)` | West side, vertically centered. Same coordinate as the other smoke-test demo levels (`KiteMelee`, `RangedStandoff`, `ShotgunStandoff`, `ArmorAbsorption`) — keeps the player-spawn coordinate consistent across the demo-level catalog for ease of reading. Player faces `+X` (default heading) but the heading is irrelevant — no enemy exists, no firing happens. |
| Exit | `(1.5, 1.5)` | Far top-left corner; the scenario's `wait:` objective never directs the bot toward the exit, so the win-condition check is not triggered. Convention: every demo level seeds an exit even when not used so the `Level` struct is fully populated (specs/25 § Win/Lose). |
| Enemy spawns | (none) | Empty `Vec<EnemySpawn>`. No enemy means the bot does not fire, no Idle/Chase/Attack cycle runs, no `damage` accumulates — the only state change is the frame-1 pickup-check that consumes the shell. |
| Pickups | one `Pickup { kind: PickupKind::AmmoShells, pos: Vec2::new(4.5, 7.5), active: true }` | Shell pickup placed at the player's spawn position. The per-frame pickup-check on frame 1 sees `distance_to(player.pos) == 0 < PICKUP_RADIUS_TILES (1.0)` and the acceptance condition `shells (0) < PLAYER_SHELLS_MAX (50)` holds, so the pickup is consumed: `shells = 0 + PICKUP_SHELLS_AMOUNT (4) = 4`. The "player spawns standing on the pickup" pattern (mirroring `ArmorAbsorption`) guarantees frame-1 acquisition without requiring the bot to move. No other pickups so the scenario can attribute every `shells` change exclusively to this one consumption event. |

**Behavior to observe.** Frame 1: `shells = 4` (from the spawn-tile shell pickup; `bullets = 50`, unchanged). Frame 2 onward: bot's first objective is `wait: 30` (half a second at 60 FPS — plenty of margin for the frame-1 consumption to settle, and a margin against any first-frame initialization side effects). The bot emits `InputState::default()` per frame for the wait window. After the wait completes, the scenario ends and assertions are checked.

**Assertion strategy** for `tests/combat/shell_pickup.yaml`:
- `player.alive: true` — no enemy exists, so the player cannot have died.
- `player.bullets: "== 50"` — the starting bullets pool is `PLAYER_BULLETS_INITIAL = 50`; no firing happened (no enemy + `wait:` objective emits no fire input); no bullets-pickup was placed. This assertion proves the shell pickup did NOT spill into the bullets pool (the pool-independence invariant).
- `player.shells: "== 4"` — the starting shells pool is `PLAYER_SHELLS_INITIAL = 0`; the frame-1 pickup-check added `PICKUP_SHELLS_AMOUNT = 4`. No shotgun exists to decrement, so the value persists for the run. This assertion proves the shell pickup DID consumption-add to the shells pool.

Together the pair `(bullets == 50, shells == 4)` is the byte-level proof of pool independence: a single pickup raises only its category's pool.

**Assertion strategy** for `tests/combat/armor_absorbs_damage.yaml`:
- `player.alive: true` — the armor pool provided enough buffer that the player survives the wait.
- `enemy.alive: false` — the bot completes `kill: enemy` after the wait.
- `player.armor: "< 100"` — the armor pool was consumed by absorption; a value strictly less than the starting 100 proves the routing rule (specs/25 § Armor Damage Routing) ran. *(Without the armor pickup, every hit would have hit health directly and `armor` would remain at the starting value of `PLAYER_ARMOR_INITIAL = 0` — also `< 100`, so this assertion alone is not sufficient to discriminate. Paired with the next assertion it is.)*
- `player.armor: "> 0"` — the absorption was partial (armor was not fully exhausted in one mid-hit clamp). With armor at zero AND armor_type cleared to None (mid-hit depletion rule), the scenario would still pass `< 100` but fail `> 0`. The pair `0 < armor < 100` is the proof that the armor system absorbed damage, was non-zero before each hit, and retained pool after the test window.

The scenario does NOT directly assert against `player.health` because the assertion would need to encode a specific RNG-dependent damage trajectory that's harder to read at glance than the armor-pool assertions. The "strictly less HP damage with armor than without" acceptance criterion is satisfied by construction: with armor active, `saved` of the routing rule diverts a positive number of damage points per hit; without armor (e.g. if the armor pickup were removed), the same RNG-deterministic hits would land all damage on health, producing strictly lower `player.health`. The architectural proof is `player.armor < 100` (something was absorbed) — the corresponding HP delta is the mirror property by construction of the routing formula.

## Scenario YAML Extension

Scenarios opt into a non-default level by adding one optional key:

```yaml
scenario: local_chase_obstacle
description: Enemy chases player around a wall, demonstrating obstacle-aware chase behavior
level: local_chase_obstacle    # NEW — optional; absent = level_data::build_default()

objectives:
  - approach: enemy
  - kill: enemy

assertions:
  - player.alive: true
  - enemy.alive: false
```

**Field semantics:**

- `level:` (string, optional). If present, names a `DemoLevelKind` variant in `snake_case` form (e.g. `LocalChaseObstacle` → `local_chase_obstacle`). If absent or null, the runtime constructs the default level via `level_data::build_default()`. Unknown names are a hard parse error: `parse_scenario` panics with a clear message naming the unknown variant and the list of accepted values, per `specs/30 § Execution Rules` ("`.expect("valid scenario YAML")`").
- All existing fields (`scenario`, `description`, `objectives`, `assertions`) keep their existing semantics from `specs/30`.

**Backwards compatibility.** Every existing scenario YAML in `tests/**/*.yaml` continues to work without modification — the `level:` field defaults to absent, which falls back to `level_data::build_default()`. Specifically:

- `tests/combat/kill_enemy.yaml` — no `level:` field, uses default level.
- `tests/level/complete_level.yaml` — no `level:` field, uses default level.
- `tests/level/reach_exit.yaml` — no `level:` field, uses default level.
- `tests/level/scavenge_run.yaml` — no `level:` field, uses default level.
- `tests/combat/shotgun_trooper_salvo.yaml` — planned to use `level: shotgun_standoff`. **Deferred** — fixture file is not yet shipped on disk; the `ShotgunStandoff` demo level + `build_shotgun_standoff` builder + level_generator unit tests cover the geometry/archetype-construction path, but the autopilot end-to-end salvo damage scenario is not exercised until the fixture lands.

The parser change is purely additive: the field is `#[serde(default)]` on `Scenario` and the matching enum derives `serde::Deserialize` with `#[serde(rename_all = "snake_case")]`.

## Module Boundaries

The `level_generator` module sits between `level_data` (whose `Level` type it returns) and `main.rs` (its only consumer):

- **Depends on:** `level_data` (for the `Level`, `Tile`, `Vec2`, `Pickup`, `PickupKind` types).
- **Consumed by:** `main.rs` (loads the requested level when `--autopilot` mode parses a scenario with a `level:` field), and `autopilot` (the `DemoLevelKind` enum is a public type referenced by `Scenario.level: Option<DemoLevelKind>`). No other module references the generator.
- **Not consumed by:** anything in the per-frame update path. Generation runs once, at startup, before the render loop begins. `game_loop::update`, `autopilot::bot_step`, `enemy_logic::update`, etc. never reference `level_generator`.

This keeps the generator out of gameplay runtime logic per the issue's "Generator must not be part of gameplay runtime logic" constraint.

### `game_loop::new` constructor signature

To let `main.rs` choose between `level_data::build_default()` and `level_generator::build(kind)` without duplicating GameState construction logic, `game_loop::new()` is generalized to take a `Level` argument:

```rust
// before (specs/30 era):
pub fn new() -> GameState                 // builds default level internally

// after (this spec):
pub fn new(level: Level) -> GameState     // caller chooses the level
```

`main.rs` is the sole caller; it picks the level based on `--autopilot` mode and the parsed scenario:

```rust
let level = match autopilot_scenario.as_ref().and_then(|s| s.level) {
    Some(kind) => level_generator::build(kind),
    None       => level_data::build_default(),
};
let mut game = game_loop::new(level);
```

Interactive play (no `--autopilot`) always passes `level_data::build_default()` — the `level:` scenario field has no effect on interactive play because no scenario is loaded. The combined `--autopilot --record-frames` invocation (the canonical PR-preview path) goes through the same `match` and picks the generated level when the scenario asks for it.

## Determinism

Determinism follows entirely from the rules already established in `specs/35 § Determinism`. The generator itself uses no randomness — each builder function is a pure function from `DemoLevelKind` to `Level`, so repeated calls return byte-equal `Level` structs. With:

1. The fixed BGRA framebuffer recording (`specs/35 § Frame Recording Format`),
2. The fixed `dt = 1/60` simulation step (`specs/35 § Determinism`),
3. The fixed module-private RNG seeds in `--autopilot` mode (`specs/35 § Determinism`), and
4. The pure-function builder defined here,

a `--autopilot tests/level/local_chase_obstacle.yaml --record-frames out.raw` invocation produces a byte-identical `out.raw` across runs. This is the same property `specs/35 § Acceptance Criteria` already requires; this spec adds nothing to the determinism contract beyond "the builder is pure".

## PR Preview Integration

`tests/level/local_chase_obstacle.yaml` is the canonical PR-preview scenario. The split is:

| Use case | Scenario | Level |
|----------|----------|-------|
| PR-preview GIF (visual demo) | `tests/level/local_chase_obstacle.yaml` | `local_chase_obstacle` (this spec) |
| Regression `cargo test` runs | `tests/combat/*.yaml`, `tests/level/{complete_level,reach_exit,scavenge_run}.yaml` | default (`level_data::build_default`) |

The default level (no `level:` field) remains the right choice for regression-style scenarios — they exercise the canonical level layout, the canonical pickup placements, and the canonical exit-reachability path. The demo level is purpose-built for visual clarity and would be a poor regression target (no pickups, single obstacle) but a strong PR-preview target.

The spec asserts that the PR workflow's "Record gameplay GIF" step (`.github/workflows/pr.yml`) and `tooling/record_autopilot.sh`'s default scenario should both name `tests/level/local_chase_obstacle.yaml`. Updating those files is a workflow concern; see `work/pipeline_run_2026-05-03.md § Run-level follow-ups` for the maintainer task list (the agent-intake commit scope does not cover `.github/` or `tooling/` outside `tooling/agents/`, so the workflow swap ships separately).

## Variant policy

When `level_generator::DemoLevelKind` gains a new variant, the same PR
(or a linked agent-task issue created before merge) MUST either:

1. Land a paired `tests/<category>/<variant>.yaml` scenario that exercises
   the variant end-to-end via `autopilot::run_all_scenarios`, OR
2. Mark the variant in this spec's § Implementation Status table as
   `Deferred — YAML follow-up: <issue link>`. The issue link is required
   (not just the literal word "Deferred") so the follow-up is trackable
   rather than silently carried.

**Rationale.** A `DemoLevelKind` variant without an end-to-end fixture
ships dead-code-shaped public API: the builder function compiles and
the enum variant exists, but no `tests/**/*.yaml` exercises the resulting
`Level`. The next regen pass cannot detect drift because no scenario
asserts on the variant's behavior. Worse, if the variant is added with
the intent of being used as a future demo target, a maintainer reading
the catalog has no way to tell which variants are wired through the
autopilot path and which are awaiting fixtures.

Captured from PR #25 PostMortem run 2: when `KiteMelee` was first added,
its builder shipped without a paired `tests/combat/kite_enemy.yaml` and
the variant was effectively unreachable from `run_all_scenarios` until a
follow-up commit (`6aa25e8` — "tests: author tests/combat/kite_enemy.yaml
end-to-end fixture") landed the missing fixture. The commit gap was a
silent regression-coverage hole in the intervening days. This policy
prevents the same shape of gap recurring.

**Enforcement.** The policy is editorial — neither `tooling/validate_specs.py`
nor `cargo test` mechanically checks that every `DemoLevelKind` variant
has a fixture (`run_all_scenarios` only iterates the existing fixtures, so
an orphan variant simply doesn't get exercised — no error fires). The
Architect agent is responsible for upholding the policy when proposing a
new variant, and the Reconciler agent is responsible for flagging an
orphan variant in the post-Coder review pass. Reviewers (human or
ultrareview-bot) should reject a PR that adds a variant without one of
the two outcomes above.

**Fixture authoring.** When the policy chooses outcome (1), the fixture
file is part of the spec — the Architect authors it alongside the spec
edit (per `tooling/agents/architect.md` § Output: "Test-fixture YAML files
under `tests/` when a spec references them by filename"). The Coder does
not author fixtures (its scope is `generated/`). The agent-intake
workflow's `git add` scope (`specs knowledge ir tooling/agents`) does NOT
include `tests/`, so a fixture authored during agent-intake must ship in
a follow-up maintainer commit — same workflow gap as the demo-GIF swap
described in § PR Preview Integration.

## Constraints

- **No procedural generation.** Each demo level is a hand-written builder function. No grammar, no PCG seed, no algorithmic placement. Adding a new demo level means adding one enum variant and one function.
- **`Level` representation is unchanged.** The generator returns the same `Level` struct that `level_data::build_default` returns. No new fields, no new tile types, no new entity records. (`ir/contracts/level_data.yaml § Level` is unmodified.)
- **Generator is not part of gameplay runtime.** The only call sites are `main.rs` (once at startup) and the public `DemoLevelKind` type referenced by `autopilot::Scenario.level`. Per-frame paths never reference `level_generator`.
- **Pure builder functions.** Each builder is a `fn(...) -> Level` with no I/O, no randomness, no global state. Repeated calls return byte-equal `Level` structs.
- **Backwards compatible.** Scenarios without a `level:` field continue to use `level_data::build_default`. No existing test fixture is modified.

## Implementation Status

**Implemented:**
- Spec defines the `DemoLevelKind` enum, the `level_generator::build` function, and two variants: `LocalChaseObstacle` and `KiteMelee`.
- Spec defines the `level:` scenario YAML field and its fall-back semantics.
- Spec defines the `game_loop::new(level: Level)` signature change and `main.rs`'s call-site decision.
- Test fixture `tests/level/local_chase_obstacle.yaml` exists on disk and uses the `level: local_chase_obstacle` field plus the `approach: enemy` / `kill: enemy` objectives.
- `KiteMelee` is exercised by `level_generator` unit tests (`test_kite_melee_*` in `src/level_generator.rs`) which cover dimensions, spawn placement, the open-arena layout, the no-pickup invariant, and the within-`BOT_KITE_RANGE` distance assertion.
- Test fixture `tests/combat/kite_enemy.yaml` exists on disk and uses the `level: kite_melee` field, the `kill: enemy` objective, and the `player.health > 80` assertion. `autopilot::run_all_scenarios` exercises the kite policy end-to-end alongside the unit tests above.
- Test fixture `tests/combat/trooper_ranged_hits.yaml` — **deferred**. The `RangedStandoff` level + `build_ranged_standoff` builder + level_generator unit tests cover the geometry/archetype-construction path, but the autopilot end-to-end "ranged hitscan damages player from outside contact range" scenario is not exercised until the fixture (planned: `level: ranged_standoff`, `wait` then `kill: enemy`, `player.health < 100` assertion) lands on disk.
- `ShotgunStandoff` variant added with `build_shotgun_standoff` builder in `level_generator`. Test fixture `tests/combat/shotgun_trooper_salvo.yaml` — **deferred**. The shotgun-archetype constants in `enemy_logic::archetype_stats` and the `level_generator` unit test (`test_build_shotgun_standoff`) cover the static archetype/level construction path, but the autopilot end-to-end "3-pellet salvo damages the player from outside `ENEMY_CONTACT_RANGE_TILES`" scenario (planned: `level: shotgun_standoff`, `wait` then `kill: enemy`, `player.health < 100` assertion) is not run until the fixture lands on disk.
- `ArmorAbsorption` variant added with `build_armor_absorption` builder in `level_generator`. Test fixture `tests/combat/armor_absorbs_damage.yaml` exists on disk and uses `level: armor_absorption`, `wait: 180` then `kill: enemy` objectives, and the paired `player.armor: "< 100"` + `player.armor: "> 0"` assertions (plus `player.alive: true` + `enemy.alive: false`) per `### ArmorAbsorption § Assertion strategy`. `autopilot::get_field_value` resolves `"player.armor" -> AssertValue::Number(state.player.armor as f32)` per `ir/contracts/autopilot.yaml § run_scenario § Field-value resolver`. `autopilot::run_all_scenarios` exercises the armor-first damage routing pipeline (specs/25 § Armor Damage Routing) end-to-end alongside the level_generator unit test (`test_build_armor_absorption`).
- `ShellPickup` variant added with `build_shell_pickup` builder in `level_generator`. Test fixture `tests/combat/shell_pickup.yaml` exists on disk and uses `level: shell_pickup`, `wait: 30` objective, and the paired `player.bullets: "== 50"` + `player.shells: "== 4"` assertions (plus `player.alive: true`) per `### ShellPickup § Assertion strategy`. `autopilot::get_field_value` resolves `"player.bullets" -> AssertValue::Number(state.player.bullets as f32)` and `"player.shells" -> AssertValue::Number(state.player.shells as f32)` per `ir/contracts/autopilot.yaml § run_scenario § Field-value resolver`. `autopilot::run_all_scenarios` exercises the per-category pool independence end-to-end (specs/25 § Pickups § Player Ammo Pools, specs/60 § Shell Pickup Consumption).
- IR module `level_generator` is added to `ir/module_plan.yaml` (universal-sink rule applied: `main.depends_on` lists `level_generator`).
- IR contract for `level_generator` and the autopilot / `game_loop` extensions live in `ir/contracts/level_generator.yaml`, `ir/contracts/autopilot.yaml`, and `ir/contracts/game_loop.yaml`.
- `.github/workflows/pr.yml` and `.github/workflows/release.yml` record the demo GIF using `tests/level/local_chase_obstacle.yaml` as the canonical PR-preview scenario.

**Deferred:**
- Additional demo level variants beyond `LocalChaseObstacle` and `KiteMelee` (e.g. corridor chase, multi-enemy fan-out, pickup-scavenge tutorial). Add a variant to `DemoLevelKind` and a builder function as the need arises.
- Authoring fixtures for additional demo levels.
- Allowing scenarios to override the default level's *contents* (e.g. a scenario that uses the default geometry but adds an extra enemy) — this would require either splitting `Level` into geometry-vs-entities or adding a separate "scenario overlay" concept. Not needed for the current PR-preview goal.

## Related

- `specs/30_test_framework.md` — autopilot scenario YAML format (this spec extends it with the optional `level:` field).
- `specs/35_demo_mode.md` — `--autopilot` CLI mode and frame recording (this spec is consumed during scenario load in that mode).
- `specs/25_game_tuning.md § Level Layout` — the default level's dimensions and layout (kept for backwards compatibility; this spec adds an alternative builder, not a replacement).
- `knowledge/level_scenarios.md` — knowledge basis for "scenario = tiny geometry + entity list, hand-authored, no procedural generation" and the obstacle-aware chase behavior the demo level is designed to expose.
- `ir/module_plan.yaml` — module-graph entry for `level_generator`.
- `ir/contracts/level_generator.yaml` — the public API of the generator; `ir/contracts/autopilot.yaml` — the extended `Scenario` shape; `ir/contracts/game_loop.yaml` — the new `new(level)` signature.
