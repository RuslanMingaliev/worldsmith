# Pickups Specification

## Overview

This specification defines static pickup entities placed in the level: items the player consumes by walking over them. Five kinds ship in the prototype:

- **Health pickup** — restores `PICKUP_HEALTH_AMOUNT` HP, clamped to `PLAYER_MAX_HEALTH`.
- **Bullet pickup (`AmmoBullets`)** — restores `PICKUP_BULLETS_AMOUNT` rounds into the **bullets** pool, clamped to `PLAYER_BULLETS_MAX`. Consumed by the pistol.
- **Shell pickup (`AmmoShells`)** — restores `PICKUP_SHELLS_AMOUNT` rounds into the **shells** pool, clamped to `PLAYER_SHELLS_MAX`. New in the 2026-05-18 ammo-split slice; consumed by the deferred shotgun (specs/25 § Deferred Combat Features — Multiple weapons). The pool exists with no consumer in this slice, so taking a shell pickup raises `player.shells` from 0 toward `PLAYER_SHELLS_MAX = 50` but no weapon decrements it.
- **Armor (green) pickup** — overwrites the player's armor pool to `PICKUP_ARMOR_GREEN_TARGET_POINTS` (100) and tier to `ArmorTier::Green`. Refused if `player.armor >= PICKUP_ARMOR_GREEN_TARGET_POINTS`.
- **Armor (blue) pickup** — overwrites the player's armor pool to `PICKUP_ARMOR_BLUE_TARGET_POINTS` (200) and tier to `ArmorTier::Blue`. Refused if `player.armor >= PICKUP_ARMOR_BLUE_TARGET_POINTS`.

This workflow also activates the **per-category ammo system**: the player has two independent pools (bullets and shells) addressed by an `AmmoCategory` enum on `Player`. Each weapon's definition pins the category it consumes (`weapon_system::PISTOL_AMMO_CATEGORY = AmmoCategory::Bullets`). The pistol decrements the bullets pool by one per fired shot and is gated on `player.bullets > 0`. Out of bullets, the trigger is a no-op (no muzzle flash, no tracer, no shot, no cooldown reset). The shells pool has no consumer this slice — picking up shells raises the count without altering bullets, and vice versa (knowledge `combat_balance.md § Ammo Economy` — "picking up shells never changes the bullets count, and vice versa.").

And the **armor system**: armor absorbs a fraction of incoming damage before it reaches `Player.health` (specs/25 § Armor / § Armor Damage Routing). Two tiers ship (green at 1/3 absorption, blue at 1/2 absorption); the over-cap +1 bonus armor pickup is deferred.

All numeric amounts, sprite sizes, colors, and pickup positions referenced by name are defined in [`25_game_tuning.md`](25_game_tuning.md#pickups). The behavior spec only refers to constants by name.

Source: [`knowledge/pickups.md`](../knowledge/pickups.md). Spec values that are NOT directly grounded in knowledge are marked `Generation default — no knowledge backing` in spec/25.

## Design Goals

- **Walk-over consumption.** No prompt, no inventory key, no manual confirm. Knowledge: § Pickup Touch Detection — the reference engine's pickup is a side-effect of the per-tick collision pass.
- **Single-use, leave-in-world-but-inactive.** A consumed pickup stays in `Level::pickups` with `active = false` rather than being removed. Knowledge: § Single-use Consumption — the reference removes the entity entirely; we keep the slot for stable iteration order in our `Vec`-based world.
- **Refused at cap.** Picking up at full health (or full ammo) does NOT consume the pickup — it stays active for later. Knowledge: § Cap Behavior — this is the reference's "refused if at cap" rule; it is a quietly important design choice (lets the player save a heal for when it matters).
- **Ammo gates firing.** Out-of-ammo trigger is a no-op. Knowledge: § Ammo Gating of Firing — the reference's `check_ammo` runs before any other side effect.
- **Deterministic placement.** Pickups are placed statically in `level_data::build_default()`. No spawners, no random drops in this round.

## Behaviors

### Health Pickup Consumption

**Trigger:** During the per-frame pickup check, the player's position is within `PICKUP_RADIUS_TILES` of a `PickupKind::Health` pickup that is still active (`active == true`) AND `player.health < PLAYER_MAX_HEALTH`.

**Effect:** The pickup's `active` flag is set to `false`. Player health increases by `PICKUP_HEALTH_AMOUNT`, clamped to `PLAYER_MAX_HEALTH`.

**Rules:**
- The "refused at cap" rule is enforced by the trigger condition: at full health the pickup is NOT consumed and stays active. *(Knowledge: § Cap Behavior — "Normal-cap health … refused, pickup remains in world".)*
- The pickup is not removed from `Level::pickups`; the `active` flag flips to `false`. The renderer and the per-frame check skip inactive pickups. *(Generation default — knowledge says reference removes entirely; we use stable iteration order for the prototype.)*
- A pickup that has been deactivated is never re-armed within a run.

### Bullet Pickup Consumption (`PickupKind::AmmoBullets`)

**Trigger:** Same per-frame pickup check, for a `PickupKind::AmmoBullets` pickup. Active pickup AND `player.bullets < PLAYER_BULLETS_MAX`.

**Effect:** The pickup's `active` flag is set to `false`. The player's **bullets** pool increases by `PICKUP_BULLETS_AMOUNT`, clamped to `PLAYER_BULLETS_MAX`. The shells pool is **not** touched (knowledge `combat_balance.md § Ammo Economy` — "picking up shells never changes the bullets count, and vice versa.").

**Rules:**
- Same "refused at cap" rule as health pickups, but the cap check reads only the bullets pool. *(Knowledge `pickups.md § Cap Behavior` — "the cap check reads only that category's count — a player at the bullets cap can still pick up a shell pickup if shells are below the shells cap, and vice versa.")*
- Same "leave in list, just deactivate" rule.
- The pickup-to-category binding is fixed by variant: `PickupKind::AmmoBullets` writes only `player.bullets` and touches nothing else. The `game_loop::update` pickup-check step dispatches on `pickup.kind` and calls `player_state::take_ammo_pickup(player, AmmoCategory::Bullets, PICKUP_BULLETS_AMOUNT)`. *(Knowledge `pickups.md § Ammo Pickup Tiers` — "Pickup-to-category binding is one-to-one and fixed by pickup kind.")*
- Auto-weapon-switch on zero→nonzero bullets (knowledge `pickups.md § Ammo Pickup Tiers`) is **deferred** — the pistol is the only bullets-consuming weapon, so the switch would no-op.
- Large bullet pickup (box, 50 bullets; knowledge `combat_balance.md § Ammo Economy`) is **deferred**.

### Shell Pickup Consumption (`PickupKind::AmmoShells`)

**Trigger:** Same per-frame pickup check, for a `PickupKind::AmmoShells` pickup. Active pickup AND `player.shells < PLAYER_SHELLS_MAX`.

**Effect:** The pickup's `active` flag is set to `false`. The player's **shells** pool increases by `PICKUP_SHELLS_AMOUNT`, clamped to `PLAYER_SHELLS_MAX`. The bullets pool is **not** touched.

**Rules:**
- Same "refused at cap" rule as health pickups, but the cap check reads only the shells pool.
- Same "leave in list, just deactivate" rule.
- The pickup-to-category binding is fixed by variant: `PickupKind::AmmoShells` writes only `player.shells` and touches nothing else. The `game_loop::update` pickup-check step dispatches on `pickup.kind` and calls `player_state::take_ammo_pickup(player, AmmoCategory::Shells, PICKUP_SHELLS_AMOUNT)`.
- **No consumer this slice.** No weapon currently decrements `player.shells`. The shotgun is **deferred** to the next slice (specs/25 § Deferred Combat Features). Picking up a shell pickup raises `player.shells` from its starting value (`PLAYER_SHELLS_INITIAL = 0`) toward the cap (`PLAYER_SHELLS_MAX = 50`); the value persists for the run but no in-game effect reads it beyond the HUD pane (and the HUD pane is bound to the equipped weapon's category, which is bullets for the pistol — so picking up shells does NOT change the displayed HUD pane value when the pistol is equipped).
- Auto-weapon-switch on zero→nonzero shells (knowledge `pickups.md § Ammo Pickup Tiers` — "the first shell pickup the player ever finds auto-equips the shotgun (if owned)") is **deferred** — no shotgun exists yet, so the switch would no-op.
- Large shell pickup (shell box, 20 shells; knowledge `combat_balance.md § Ammo Economy`) is **deferred**.

### Armor (Green) Pickup Consumption

**Trigger:** Same per-frame pickup check, for a `PickupKind::ArmorGreen` pickup. Active pickup AND `player.armor < PICKUP_ARMOR_GREEN_TARGET_POINTS` (100).

**Effect:** The pickup's `active` flag is set to `false`. The player's armor pool is **overwritten** to `PICKUP_ARMOR_GREEN_TARGET_POINTS` and the armor type is **overwritten** to `ArmorTier::Green`.

**Rules:**
- "Refused at pool" rule: pickup is consumed only when `player.armor < PICKUP_ARMOR_GREEN_TARGET_POINTS`. At or above 100 points (regardless of current tier — including a partially-depleted blue at >100 points), the pickup stays active and is left in the world. *(Knowledge: § Armor Pickup Tiers — "refused if current armor points >= 100 ... the refusal compares raw points, not value, so a partially-depleted blue at >100 points blocks a fresh green".)*
- **Overwrite semantics**: knowledge § Armor Pickup Tiers — "overwrites *both* the armor type and the armor points with the new tier and its target pool". A green pickup grabbed while the player carries 50 green sets both fields back to (Green, 100); it does NOT add 100 to the existing 50.
- Asymmetric upgrade: a green pickup grabbed while the player carries blue armor with `armor < 100` is **accepted** and overwrites the player back to (Green, 100). This downgrades the tier even though it raises the points to the green cap. Knowledge § Armor Pickup Tiers notes this is the reference's behavior — "the refusal compares raw points, not value" — and we mirror it. *(In practice, the green pool's 100 is below blue's 200 cap, so blue armor at `armor >= 100` blocks the green pickup; the downgrade only fires when the blue pool has been depleted below 100.)*
- Same "leave in list, just deactivate" rule as health/ammo (specs/60 § Health Pickup Consumption).
- The over-cap +1 bonus armor pickup (knowledge § Armor Pickup Tiers — "tiny over-cap bonus pickup") is **deferred**; this slice ships only the two tiered pickups.

### Armor (Blue) Pickup Consumption

**Trigger:** Same per-frame pickup check, for a `PickupKind::ArmorBlue` pickup. Active pickup AND `player.armor < PICKUP_ARMOR_BLUE_TARGET_POINTS` (200).

**Effect:** The pickup's `active` flag is set to `false`. The player's armor pool is **overwritten** to `PICKUP_ARMOR_BLUE_TARGET_POINTS` and the armor type is **overwritten** to `ArmorTier::Blue`.

**Rules:**
- Same refusal/overwrite semantics as green, scaled to the blue tier (refused at `armor >= 200`; sets `armor = 200`, `armor_type = Blue` on accept).
- Blue overwrites green unconditionally (green's pool ≤ 100 < 200, so blue always sets a strictly larger pool). Knowledge § Armor Pickup Tiers — "Picking up the large-tier (blue) armor when the player has 100 green overwrites to 200 blue — the new tier and its full pool both apply".
- Same "leave in list, just deactivate" rule as health/ammo.

### Enemy Ammo Drops

**Trigger:** During the per-frame `game_loop::update` sequence, an enemy's `alive` flag transitions from `true` to `false` (via `enemy_logic::take_damage` from a player hitscan that drops the trooper to ≤ 0 HP).

**Effect:** Exactly one `Pickup { kind: PickupKind::AmmoBullets, pos: enemy.pos, active: true }` is appended to `Level::pickups` at the trooper's death position. The dropped category is "bullets" because the basic trooper drops a bullet clip per knowledge `enemy_types.md § Death and Item Drops` ("The basic hitscan trooper drops a clip (bullet ammo) on death"); the variant name reflects this since the 2026-05-18 ammo-split slice (previously the variant was `PickupKind::Ammo`, which the slice renamed to `AmmoBullets` to make the category explicit). The pickup is collectible by the existing per-frame pickup check on the next frame.

**Rules:**
- The drop is gated by an `Enemy.ammo_drop_spawned: bool` latch: initialized `false`, flipped to `true` after the push so the scan never double-spawns. *(Knowledge: § Drop on Kill — "deterministic per enemy kind, no random roll".)*
- The push happens in the dedicated drop-spawn step of `game_loop::update`'s frame-update order (`ir/contracts/_shared.yaml § frame_update_order`), AFTER the enemy update loop AND AFTER `weapon_system::fire`. This ensures a same-frame kill (player hitscan kills the trooper this tick) drops the pickup this tick rather than next tick. The drop is NOT pushed inside `enemy_logic::take_damage` because that call site only holds `&Level`, not `&mut Level::pickups` — pushing into the level requires the orchestration borrow that only `game_loop::update` owns. *(Service-emit decision recorded in `ir/contracts/_shared.yaml § service_emit_decisions § game_loop drop-spawn scan`.)*
- The pickup uses `PickupKind::AmmoBullets` and `PICKUP_BULLETS_AMOUNT = 10` rounds — the half-clip "dropped" flag from knowledge (5 rounds for the basic trooper) is **deferred** to the richer-pickup-model slice. The prototype's single-amount bullet pickup means the drop grants the same rounds as a placed bullet pickup, which makes enemy-farming slightly more rewarding than the reference; tracked in `25_game_tuning.md § Enemy § Deferred from knowledge`.
- Because the drop appears in `Level::pickups` only AFTER the per-frame pickup check has already run this frame, the player cannot collect the drop on the same frame it is created — earliest collection is the NEXT frame. This is a one-frame delay (16 ms at 60 FPS), imperceptible.
- The drop respects the existing "refused at cap" rule: if the player is at `PLAYER_BULLETS_MAX` when they walk over the dropped pickup, the pickup stays active and is collected later when there is room.
- The drop position is the trooper's `pos` at the moment of death — not the enemy's spawn position, not snapped to a tile. The renderer draws the dropped pickup at this floating-point position via the same code path that draws placed pickups.

*(Knowledge: § Drop on Kill — "spawns one pickup at the enemy's feet"; § Cap Behavior — "refused, pickup remains in world".)*

### Per-Frame Pickup Check

**Trigger:** Once per frame, in `game_loop::update`, after player movement (`apply_input`) and before enemy updates.

**Effect:** Each active pickup is tested against the player's current position. The first active pickup whose `pos.distance_to(player.pos) < PICKUP_RADIUS_TILES` AND whose acceptance condition holds is consumed. Per-kind acceptance conditions:

| Kind | Acceptance condition |
|------|----------------------|
| `Health`      | `player.health < PLAYER_MAX_HEALTH` |
| `AmmoBullets` | `player.bullets < PLAYER_BULLETS_MAX` |
| `AmmoShells`  | `player.shells < PLAYER_SHELLS_MAX` |
| `ArmorGreen`  | `player.armor < PICKUP_ARMOR_GREEN_TARGET_POINTS` (100) |
| `ArmorBlue`   | `player.armor < PICKUP_ARMOR_BLUE_TARGET_POINTS` (200) |

**Rules:**
- Single pickup per frame is sufficient — pickups are not stacked at the same tile. *(Generation default — the reference iterates ALL overlapping pickups in the same tick. For our 2 placed pickups in one level, single-per-frame is fine.)*
- If multiple pickups overlap the player at the same frame, the iteration order of `Level::pickups` decides the winner; the rest wait for subsequent frames.
- The check uses **circle distance** (`Vec2::distance_to`), not AABB. *(Knowledge says reference uses sum-of-radii Chebyshev/AABB; we use circle distance because all our other collision checks (player↔wall, weapon↔enemy) are circle-based — switching paradigms for one check would be inconsistent. The two are within ~25% of each other at typical pickup geometries; not a meaningful gameplay difference.)*
- The check runs even if the player is not alive; consuming a pickup post-mortem has no observable effect because health/ammo updates on a dead player don't re-arm anything.

### Ammo-Gated Firing

**Trigger:** `weapon_system::fire` is called by `game_loop::update`.

**Effect:** Before any other side effect (cooldown gate, muzzle flash, tracer, ray-march, damage), `fire` checks the equipped weapon's ammo pool. For the pistol (`PISTOL_AMMO_CATEGORY = AmmoCategory::Bullets`) the check is `player.bullets > 0`. If the check fails, `fire` returns immediately with **no** state change.

**Rules:**
- The cooldown gate (`time_since_fire >= PISTOL_FIRE_CYCLE`) runs first. The two gates compose: a shot fires only if both pass. *(Knowledge: § Ammo Gating of Firing — the reference's `check_ammo` is a pre-fire gate; ordering with other gates is implementation-internal.)*
- An out-of-ammo `fire()` MUST NOT reset `player.time_since_fire` — the player's first-shot accuracy budget is preserved across the dry trigger pull. *(Generation default — knowledge does not directly specify what happens to the refire timer on a dry pull; this rule is a UX choice.)*
- After all the existing fire-side effects complete (muzzle flash, tracer, ray-march, damage), the equipped weapon's pool is decremented by the weapon's per-shot cost. For the pistol that is `player.bullets -= 1` (knowledge `combat_balance.md § Ammo Economy` — "Pistol: 1 bullet per shot"). *(Knowledge: § Ammo Gating of Firing — "ammo decrement happens at shot-spawn, not trigger". Our shot is hitscan with no projectile spawn, so "after all fire-side effects" is the closest analogue.)*
- The dispatch is keyed on the weapon's `ammo_category` field (knowledge `combat_balance.md § Ammo Economy` — "Each weapon definition carries an `ammo_category` field"). With the pistol as the only weapon the dispatch is constant; when the deferred shotgun ships it adds a second arm decrementing `player.shells` by its per-shot cost (knowledge — "Shotgun: 1 shell per shot").

### Pickup Rendering

**Trigger:** Every frame, between Step 2 (exit + corpses) and Step 3 (blood + puffs) of the existing render order — on top of the floor/walls but below combat effects.

**Effect:** Each active pickup is drawn at its world position:

- **Health pickup:** a `PICKUP_HEALTH_SIZE_PX × PICKUP_HEALTH_SIZE_PX` filled square in `PICKUP_HEALTH_OUTER_COLOR`, with a centered horizontal+vertical cross of `PICKUP_HEALTH_INNER_THICKNESS_PX` width in `PICKUP_HEALTH_INNER_COLOR`.
- **Bullet pickup (`AmmoBullets`):** a `PICKUP_AMMO_SIZE_PX × PICKUP_AMMO_SIZE_PX` filled square in `PICKUP_AMMO_COLOR` (yellow), no inner detail.
- **Shell pickup (`AmmoShells`):** a `PICKUP_SHELL_SIZE_PX × PICKUP_SHELL_SIZE_PX` filled square in `PICKUP_SHELL_COLOR` (warm orange), no inner detail. New in the 2026-05-18 ammo-split slice. The distinct hue (orange vs yellow) lets the player tell which ammo category a pickup grants at a glance — knowledge `pickups.md § Ammo Pickup Tiers` notes pickups are "marked" per category in the reference's sprite assets; we substitute a per-category color since we have no sprite assets.
- **Armor (green) pickup:** a `PICKUP_ARMOR_SIZE_PX × PICKUP_ARMOR_SIZE_PX` filled square in `PICKUP_ARMOR_GREEN_COLOR`, no inner detail.
- **Armor (blue) pickup:** a `PICKUP_ARMOR_SIZE_PX × PICKUP_ARMOR_SIZE_PX` filled square in `PICKUP_ARMOR_BLUE_COLOR`, no inner detail.

**Rules:**
- Inactive pickups draw nothing.
- Pickups draw under combat effects so a wall puff or blood splat covers them visually if both are at the same pixel — combat priority over loot.
- The render order list in `renderer::draw`'s docstring is updated.

*(Generation default: shapes and colors are not knowledge-backed — the reference uses sprite assets we don't have. The cross-on-square (medkit) and yellow-square (ammo box) shapes are common-knowledge retro UI conventions; the spec marks them as defaults and parking-lots them for asset-aware re-extraction.)*

### HUD Ammo Pane (extends spec/50)

**Trigger:** Every frame, in the same `draw_hud` call that draws the health pane.

**Effect:** A second pane is drawn directly below the health pane. The pane is **weapon-aware**: it displays the count for the equipped weapon's ammo category (specs/25 § HUD Ammo Pane; knowledge `hud.md § Numeric Widget § Weapon-aware source rebinding (primary ammo widget only)` — "the active weapon's ammo-category field from the weapon definition table" is the dispatch input):

1. The renderer reads the equipped weapon's `ammo_category` (a `weapon_system::AmmoCategory` constant — see `ir/contracts/weapon_system.yaml § PISTOL_AMMO_CATEGORY`).
2. The pane reads the matching pool from `Player` (`AmmoCategory::Bullets → player.bullets`, `AmmoCategory::Shells → player.shells`).
3. The pane icon is a `HUD_AMMO_ICON_PX × HUD_AMMO_ICON_PX` filled square in the matching color (`HUD_AMMO_COLOR` yellow for bullets; a future `HUD_SHELL_COLOR` for shells is deferred to the shotgun-shipping slice).
4. Immediately to the right of the icon (gap `HUD_PANE_GAP_PX`), the matched pool value is drawn with the same bitmap font as health digits in the matching color. Vertical baseline centered against the icon. No leading zeros, zero special-cased per the same knowledge-backed rules used in spec/50 § Numeric Widget.

With pistol as the only weapon in this slice, the dispatch is constant (`Bullets → player.bullets → HUD_AMMO_COLOR`), so the visual output is identical to the pre-slice HUD ammo pane. The slice introduces the dispatch *machinery* (read the weapon's category, look up the pool); the data it dispatches over is currently a one-element table.

**Rules:**
- Pane origin: `(HUD_MARGIN_PX, HUD_MARGIN_PX + HUD_HEALTH_BAR_HEIGHT_PX + HUD_PANE_GAP_PX)`. Unchanged.
- No background bar (icon + digits only). Unchanged.
- Single color per frame, dispatched from the equipped weapon's category. Currently always `HUD_AMMO_COLOR` (yellow). Low-ammo warning color is **deferred**.
- Drawn whether the dispatched pool is zero or not.
- Shell-pool changes are **invisible to this pane while the pistol is equipped** — picking up a shell pickup while holding the pistol raises `player.shells` but the pane keeps showing `player.bullets`. This matches knowledge `hud.md § Numeric Widget § Weapon-aware source rebinding` — "the secondaries are bound once at init" — except the prototype omits the secondary readouts entirely (single-pane HUD), so a shell pickup with the pistol equipped has no on-screen indication in this slice. A "low-priority shell pickup notification" or per-category secondary readout is **deferred** (knowledge — "four per-category secondary widgets").

*(Generation default: the layout / icon-shape / yellow choice are not knowledge-backed. Knowledge § Color / State Encoding tells us the reference uses two distinct fonts for primary vs secondary readouts, not color shifts; we substitute color for font-size since our font is monolithic. The weapon-aware dispatch itself IS knowledge-backed — see knowledge `hud.md § Numeric Widget § Weapon-aware source rebinding`.)*

## State

### Pickup Entity (in `Level::pickups`)
- **Type:** `Pickup { kind: PickupKind, pos: Vec2, active: bool }`.
- **Initial:** `level_data::build_default()` seeds five pickups (two health, one bullet — `AmmoBullets`, one green armor, one blue armor) at the positions in `25_game_tuning.md § Pickups § Default Level Placement`. No shell pickup is seeded in the default level; the shell pickup is exercised only via the `ShellPickup` demo level + `tests/combat/shell_pickup.yaml`.
- **Transitions:** `active` flips from `true` to `false` exactly once when the player consumes the pickup. Never flips back within a run.

### Player Ammo Pools (`Player.bullets`, `Player.shells`)
- **Type:** Two `i32` fields on `Player`, one per category. Indexed semantically by `AmmoCategory::{Bullets, Shells}` (the enum lives in `player_state`; see `ir/contracts/player_state.yaml § AmmoCategory`).
- **Initial:** `bullets = PLAYER_BULLETS_INITIAL` (50), `shells = PLAYER_SHELLS_INITIAL` (0). Set by `player_state::new`.
- **Transitions:**
  - `bullets`: decremented by 1 per fired pistol shot in `weapon_system::fire` (after side effects). Incremented by `PICKUP_BULLETS_AMOUNT` (clamped to `PLAYER_BULLETS_MAX`) on bullet pickup consumption. Never goes negative — the bullets-pool fire gate prevents firing the last shot of a zero pool.
  - `shells`: incremented by `PICKUP_SHELLS_AMOUNT` (clamped to `PLAYER_SHELLS_MAX`) on shell pickup consumption. No consumer in this slice — the value monotonically increases until cap. When the deferred shotgun ships, it adds the shells-decrement and the shells-pool fire gate symmetrically.
- **Independence:** A write to one pool never reads or modifies the other (knowledge `combat_balance.md § Ammo Economy` — "The two categories are stored as independent integers ... picking up shells never changes the bullets count, and vice versa.").

### Player Armor (`Player.armor` and `Player.armor_type`)
- **Type:** `armor: u8` (0..=200) and `armor_type: ArmorTier` enum with variants `None`, `Green`, `Blue`.
- **Initial:** `armor = PLAYER_ARMOR_INITIAL` (= 0) and `armor_type = ArmorTier::None`, set by `player_state::new`.
- **Transitions:**
  - On green armor pickup consumption: `armor = PICKUP_ARMOR_GREEN_TARGET_POINTS`, `armor_type = ArmorTier::Green` (overwrite, not add).
  - On blue armor pickup consumption: `armor = PICKUP_ARMOR_BLUE_TARGET_POINTS`, `armor_type = ArmorTier::Blue` (overwrite).
  - On `take_damage(dmg)` with non-None armor: `armor -= saved` where `saved = min(armor, dmg * absorb_num / absorb_den)`. If `saved == armor` (pool exhausted by this hit), `armor_type = ArmorTier::None`. See specs/25 § Armor Damage Routing for the routing algorithm.
  - Never goes negative — the clamp in step 3 of the routing rule prevents underflow.

## Interactions

### With Level Data
- `level_data::build_default` populates `Level::pickups` with the default placement.
- `Pickup` and `PickupKind` are homed in `level_data` (alongside `Tile` and `Vec2`).

### With Player State
- `player_state::new` initializes `bullets = PLAYER_BULLETS_INITIAL`, `shells = PLAYER_SHELLS_INITIAL`, `armor = PLAYER_ARMOR_INITIAL` (= 0), `armor_type = ArmorTier::None`.
- `player_state::take_health_pickup(player, amount)` — increments `health`, clamps to `PLAYER_MAX_HEALTH`. Does not touch `damage_count` or `alive`.
- `player_state::take_ammo_pickup(player, category, amount)` — dispatches on `category`: for `AmmoCategory::Bullets` increments `player.bullets` and clamps to `PLAYER_BULLETS_MAX`; for `AmmoCategory::Shells` increments `player.shells` and clamps to `PLAYER_SHELLS_MAX`. Caller (game_loop) is responsible for flipping the Pickup's active flag and for the refused-at-cap guard against the matching pool.
- `player_state::take_armor_pickup(player, tier)` — overwrites `armor` to the tier's target pool (`PICKUP_ARMOR_GREEN_TARGET_POINTS` or `PICKUP_ARMOR_BLUE_TARGET_POINTS`) and `armor_type` to `tier`. Caller (game_loop) is responsible for flipping the Pickup's active flag and for the refused-at-pool guard.
- `player_state::take_damage(player, amount)` consumes `armor`/`armor_type` via the armor-first routing rule (specs/25 § Armor Damage Routing).

### With Weapon System
- `weapon_system::fire` reads the equipped weapon's `AmmoCategory` (for the pistol: `PISTOL_AMMO_CATEGORY = AmmoCategory::Bullets`) and:
  - Gates at the top: `if player_ammo_pool(player, category) == 0 { return; }` — i.e. `player.bullets == 0` for the pistol.
  - Decrements that pool by the weapon's per-shot cost (1 for the pistol) AFTER the existing side effects — i.e. `player.bullets -= 1` for the pistol. The decrement amount is the weapon's "per-shot cost" (knowledge `combat_balance.md § Ammo Economy`); for the pistol that is 1, and for the deferred double-barrel shotgun variant it would be 2.
- Ordering relative to the cooldown gate: cooldown first (so a dry-pull while still in cooldown is a single no-op, not a double-evaluation). Then ammo. Then everything else.
- The dispatch on `AmmoCategory` is single-armed in this slice (only the pistol exists). When the shotgun ships, the dispatch grows a second arm; the gate and decrement shapes stay the same with `player.shells` substituted.

### With Game Loop
- `game_loop::update` adds Step 2.5 between `apply_input` (Step 2) and the enemy update (Step 3): scan `state.level.pickups` for the first active pickup within `PICKUP_RADIUS_TILES` of `state.player.pos` whose acceptance condition holds, and consume it.
- `game_loop::update` adds the drop-spawn step AFTER the enemy update loop AND AFTER `weapon_system::fire`: scan `state.enemies` for trooper deaths and push `Pickup { kind: PickupKind::AmmoBullets, pos: enemy.pos, active: true }` into `state.level.pickups` (gated by `Enemy.ammo_drop_spawned`). The variant is `AmmoBullets` (was `Ammo` pre-2026-05-18 ammo-split slice) because the basic trooper drops a bullet clip per knowledge `enemy_types.md § Death and Item Drops`. See § Enemy Ammo Drops above.
- The frame-update-order list in `ir/contracts/_shared.yaml § frame_update_order` gains both steps.

### With Renderer
- `renderer::draw` adds Step 2.5 (between exit/corpses and blood/puffs) drawing active pickups.
- `draw_hud` (from spec/50) gets a second pane drawing call after the health pane.

### With Visual Effects
- On pickup consumption, `game_loop` calls `visual_effects::increment_pickup_tint(&mut state.fx)`, which adds `PICKUP_TINT_PER_PICKUP` to `VisualEffects.pickup_tint_count` (clamped to `PICKUP_TINT_CAP`).
- The golden-yellow screen-tint flash is fully specified in `specs/40_visual_feedback.md § Pickup Tint Screen Flash`. This spec does not duplicate those rules; it only documents the trigger point (pickup consumption) and the API call.

## Constraints

### Invariants
- `0 <= player.bullets <= PLAYER_BULLETS_MAX` — enforced by the `take_ammo_pickup` clamp (with `AmmoCategory::Bullets`) and the pistol's `fire`-time ammo gate.
- `0 <= player.shells <= PLAYER_SHELLS_MAX` — enforced by the `take_ammo_pickup` clamp (with `AmmoCategory::Shells`). The "never negative" half of the invariant is vacuously satisfied this slice because no weapon decrements the shells pool yet; it will become a real constraint when the shotgun ships.
- The two pools are independent: a write to `player.bullets` never reads or modifies `player.shells`, and vice versa.
- `0 <= player.health <= PLAYER_MAX_HEALTH` after a health pickup — enforced by the `take_health_pickup` clamp. (Below-zero health remains possible *before* clamp on lethal damage; the clamp at `take_damage` already snaps to zero.)
- `0 <= player.armor <= 200` — enforced implicitly by the armor pool's target-pool overwrite values (the two `PICKUP_ARMOR_*_TARGET_POINTS` constants are 100 and 200, and pickup-side acceptance overwrites the pool rather than adding) and by the `take_damage` clamp (`saved = min(armor, ...)` prevents negative). The ceiling has no named runtime constant — see [`ir/contracts/player_state.yaml § public_constants`](../ir/contracts/player_state.yaml) for the rationale (spec/80 § API Surface forbids dead `pub` exports, and no in-crate caller needs to read the ceiling at runtime).
- `(player.armor == 0) == (player.armor_type == ArmorTier::None)` is NOT an invariant in general: a fresh green pickup sets both `(armor=100, type=Green)` simultaneously; depleting armor via damage clears both to `(0, None)` simultaneously. But *between* those events the player can transiently carry a non-zero armor pool whose type matches the tier — that is the steady state. The implication is just that armor depletion via damage clears the type to None (specs/25 § Armor Damage Routing rule 3); the type does not silently desync from the pool.
- A pickup's `active` flag is monotonic: once `false`, never `true` again within a run.
- An out-of-bullets `fire` invocation is observationally a no-op: no field of `player`, no entry in `fx.effects`, and no enemy `health` changes.
- The "refused at cap / refused at pool" rule means no pickup is consumed when its effect would be wasted.

### Determinism
- Pickup placement is hardcoded.
- Pickup consumption is deterministic in `Level::pickups` iteration order.
- Ammo decrement is deterministic (one per fired shot).

## Deferred

The following are intentionally out of scope for the prototype:

- **Multiple weapon ammo pools** — pistol/clip is the only weapon. Knowledge documents 4 categories (A/B/C/D); we use a single `ammo` field.
- **Ammo cap expander** — the inventory-expander pickup that doubles every cap (knowledge § Ammo Pickup Tiers). Single-cap prototype.
- **Over-cap health pickups** — the +1 / +100 / set-200 tier (knowledge § Health Pickup Tiers). Single-cap prototype, normal_max only.
- **Auto-weapon-switch on zero→nonzero ammo** — knowledge § Ammo Pickup Tiers. Only one weapon exists.
- **Pickup respawn** — single-use within a run.
- **Pickup pickup sound / dry-fire "click"** — no audio system in the prototype.
- **Backpack / capacity expansion** — fixed `PLAYER_BULLETS_MAX` and `PLAYER_SHELLS_MAX`; the inventory-expander pickup that doubles every cap (knowledge `pickups.md § Ammo Pickup Tiers`) is deferred.
- **Half-clip "dropped" flag** — knowledge § Drop on Kill + § Ammo Pickup Tiers say a basic-trooper drop yields 5 rounds (half a clip) vs the placed-pickup 10 rounds. The prototype's single-amount `PICKUP_BULLETS_AMOUNT = 10` (was `PICKUP_AMMO_AMOUNT` pre-2026-05-18 ammo-split slice) ignores the dropped/placed distinction. The trooper death-time drop itself is **implemented** in the 2026-05-13 combat slice (see § Enemy Ammo Drops above) — only the half-amount flag is deferred.
- **Skill multiplier (2× ammo on easiest/hardest)** — knowledge § Difficulty / Skill Multipliers. No skill system in the prototype.
- **Pickup categories beyond health/ammo/armor** — keycards, all powerups. Knowledge mentions them; deferred. (Armor green + blue land in the 2026-05-14 armor slice — see § Armor (Green) Pickup Consumption and § Armor (Blue) Pickup Consumption.)
- **Tiny over-cap armor bonus pickup** — knowledge `pickups.md § Armor Pickup Tiers` describes a +1 bonus pickup parallel to the tiny health bonus, never refused, clamped at 200, defaults armor_type to Green when picked up at type None. Deferred to keep the armor slice scope tight; the two tiered pickups (green, blue) ship this slice.
- **Armor downgrade refusal at high points** — see § Armor (Green) Pickup Consumption: a green pickup grabbed while the player has blue armor at `armor < 100` is *accepted* (mirrors the reference behavior per knowledge § Armor Pickup Tiers — "the refusal compares raw points, not value"). A future "preserve tier on downgrade" rule could mark this acceptance as undesirable UX; not in this slice.
- **HUD low-ammo warning color** — ammo digits are single-color (yellow).
- **HUD pickup notification text** — already deferred in spec/50 § Deferred.
- **Pickup glow / animation** — static colored squares only.

## Test Scenarios

### Health Pickup
1. With player at the health pickup's position and `health < PLAYER_MAX_HEALTH`, after one `update` tick the pickup's `active == false` and `player.health` increased by `PICKUP_HEALTH_AMOUNT` (or clamped to max).
2. With player at the health pickup's position and `health == PLAYER_MAX_HEALTH`, after one tick the pickup's `active` is **still `true`** and `player.health` unchanged. *(Knowledge § Cap Behavior: "refused, pickup remains in world".)*
3. After the pickup is consumed (active = false), walking off and back on does not change `player.health` further.

### Bullet Pickup
1. With player at the bullet pickup's position and `bullets < PLAYER_BULLETS_MAX`, after one tick `player.bullets` increased by `PICKUP_BULLETS_AMOUNT` (or clamped) and pickup `active == false`. `player.shells` is unchanged.
2. With player at the bullet pickup's position and `bullets == PLAYER_BULLETS_MAX`, after one tick the pickup's `active == true` (refused) and `player.bullets` unchanged. `player.shells` is unchanged.

### Shell Pickup
1. With player at the shell pickup's position and `shells < PLAYER_SHELLS_MAX`, after one tick `player.shells` increased by `PICKUP_SHELLS_AMOUNT` (or clamped) and pickup `active == false`. `player.bullets` is unchanged — this is the pool-independence invariant. *(Knowledge `combat_balance.md § Ammo Economy`.)*
2. With player at the shell pickup's position and `shells == PLAYER_SHELLS_MAX`, after one tick the pickup's `active == true` (refused) and `player.shells` unchanged. `player.bullets` is unchanged. The "refused at cap" rule checks only the shells pool — a player at `bullets == PLAYER_BULLETS_MAX` can still pick up a shell as long as `shells < PLAYER_SHELLS_MAX`.
3. Starting from `(bullets = PLAYER_BULLETS_INITIAL = 50, shells = 0)`, after walking over a shell pickup once: `bullets == 50` (unchanged) AND `shells == PICKUP_SHELLS_AMOUNT == 4`. This is the byte-identical pool-independence assertion exercised by `tests/combat/shell_pickup.yaml` (specs/15 § ShellPickup).

### Armor Pickup
1. With player at the green armor pickup's position and `armor < PICKUP_ARMOR_GREEN_TARGET_POINTS`, after one tick `player.armor == PICKUP_ARMOR_GREEN_TARGET_POINTS`, `player.armor_type == ArmorTier::Green`, pickup `active == false`.
2. With player at the green armor pickup's position and `armor >= PICKUP_ARMOR_GREEN_TARGET_POINTS`, after one tick the pickup is **refused**: `active == true`, `armor` / `armor_type` unchanged.
3. With player at the blue armor pickup's position and `armor < PICKUP_ARMOR_BLUE_TARGET_POINTS`, after one tick `player.armor == PICKUP_ARMOR_BLUE_TARGET_POINTS`, `player.armor_type == ArmorTier::Blue`, pickup `active == false`.
4. Overwrite semantics: with `(armor=50, type=Green)` and standing on the blue pickup, after one tick `armor == 200`, `armor_type == Blue` (overwrite, not add).

### Armor Damage Absorption
1. Set `(armor=100, type=Green)`, `health = 100`. Apply `take_damage(12)`: `saved = 12 / 3 = 4`, `armor = 96`, `health = 88`, `armor_type` unchanged.
2. Set `(armor=10, type=Green)`, `health = 100`. Apply `take_damage(60)`: candidate `saved = 60 / 3 = 20`; clamp to `armor (10)`; `armor = 0`, `armor_type = ArmorTier::None`, `health = 100 - 50 = 50`. Subsequent `take_damage(15)` absorbs zero (`armor_type == None`): `health = 50 - 15 = 35`, demonstrating the "mid-hit depletion clears type" rule.
3. Set `(armor=100, type=Blue)`, `health = 100`. Apply `take_damage(20)`: `saved = 20 / 2 = 10`, `armor = 90`, `health = 90`. (Blue absorbs 1/2, not 1/3.)
4. Comparative: two runs of the same scenario, one with `(armor=100, type=Green)` set before the trooper fires and one without armor, must show the armored run's final `player.health` strictly greater than the un-armored run's. (See `tests/combat/armor_absorbs_damage.yaml`.)

### Ammo-Gated Firing (Pistol → Bullets)
1. Set `player.bullets = 0`, hold fire input, run one tick: no muzzle flash spawned, no tracer spawned, no enemy damage, `player.time_since_fire` does NOT reset to 0. `player.shells` is irrelevant — the pistol's gate reads only the bullets pool.
2. Set `player.bullets = 1`, fire once with cooldown ready: a muzzle flash spawns and `player.bullets` becomes 0. `player.shells` is unchanged.
3. Each successful pistol shot decrements `player.bullets` by exactly 1 and leaves `player.shells` unchanged.

### Per-Frame Pickup Check
1. With the player positioned `> PICKUP_RADIUS_TILES` from any active pickup, no pickup state changes after one tick.
2. With the player positioned exactly at the boundary (`= PICKUP_RADIUS_TILES`), the pickup is **not** consumed (strict `<` comparison).
3. With the player positioned just inside the boundary AND below cap, the pickup is consumed in one tick.

### Pickup Rendering
1. After `draw()`, sample a pixel at the health pickup's expected on-screen center: it matches `PICKUP_HEALTH_INNER_COLOR` (the cross center).
2. After `draw()`, sample a pixel at the ammo pickup's center: it matches `PICKUP_AMMO_COLOR`.
3. After consuming a pickup (`active = false`), sampling the same pixel returns the floor color (pickup not drawn).

### HUD Ammo Pane
1. With `player.bullets = 12` and pistol equipped (always, this slice), after `draw()`, sample a pixel inside the ammo icon's footprint: it matches `HUD_AMMO_COLOR`.
2. With `player.bullets = 0` and pistol equipped, the ammo pane still renders the digit `0` in `HUD_AMMO_COLOR`.
3. With `player.bullets = 50` and `player.shells = 4` and pistol equipped, the pane displays `50` (bullets), NOT `4` (shells). The dispatch is keyed on the equipped weapon's category. *(This will flip to displaying shells when the deferred shotgun is equipped — same dispatch, different category.)*

## Implementation Status

**Implemented:**
- `Pickup` and `PickupKind` types homed in `level_data`. `PickupKind` carries variants `Health`, `AmmoBullets`, `AmmoShells`, `ArmorGreen`, `ArmorBlue` (`AmmoBullets` is the renamed slice-3 `Ammo` variant; `AmmoShells` is new in the 2026-05-18 ammo-split slice — see specs/25 § Pickups § Default Level Placement).
- `AmmoCategory` enum (`Bullets | Shells`) homed in `player_state`. Consumed by `weapon_system::fire` (via `PISTOL_AMMO_CATEGORY`), `game_loop::update` (pickup-check dispatch from `PickupKind::AmmoBullets/AmmoShells` to `take_ammo_pickup(player, category, amount)`), and renderer (HUD ammo pane weapon-aware dispatch).
- `ArmorTier` enum (`None | Green | Blue`) on `Player`, homed in `player_state`.
- `Level::pickups` field populated by `build_default` with two health, one bullet pickup, one green armor, and one blue armor pickup at fixed positions (spec/25 § Pickups § Default Level Placement). Demo levels (`level_generator`) seed their own `Vec<Pickup>` per the layout pinned in `specs/15_level_generator.md`. The new `ShellPickup` demo level seeds a single shell pickup at the player's spawn (specs/15 § ShellPickup).
- `Player.bullets`, `Player.shells`, `Player.armor`, and `Player.armor_type` fields, initialized to `PLAYER_BULLETS_INITIAL = 50` / `PLAYER_SHELLS_INITIAL = 0` / `PLAYER_ARMOR_INITIAL = 0` / `ArmorTier::None` by `player_state::new`.
- `player_state::take_health_pickup`, `player_state::take_ammo_pickup(player, category, amount)` (dispatches on `category` — `Bullets` → `player.bullets`, `Shells` → `player.shells`; clamps to the matching cap), and `player_state::take_armor_pickup(player, tier)` (clamped to caps; armor overwrites tier + pool).
- `player_state::take_damage` applies the armor-first routing rule (specs/25 § Armor Damage Routing).
- `weapon_system::PISTOL_AMMO_CATEGORY = AmmoCategory::Bullets`. `weapon_system::fire` reads the constant to gate (`player.bullets > 0`) and decrement (`player.bullets -= 1`).
- `game_loop::update` Step 2.5 per-frame pickup check (refused-at-cap / refused-at-pool rule applied per the per-kind acceptance table above; bullets vs shells caps checked independently).
- `game_loop::update` drop-spawn scan after the enemy update + weapon-fire steps (specs/60 § Enemy Ammo Drops): pushes one `Pickup { kind: AmmoBullets, pos: enemy.pos, active: true }` per dead trooper, gated by `Enemy.ammo_drop_spawned`. (The variant name changed from `Ammo` to `AmmoBullets` in this slice; the dropped category remains "bullets" because the basic trooper drops a bullet clip per knowledge `enemy_types.md § Death and Item Drops`.)
- Renderer pickup layer (between exit/corpses and blood/puffs); bullet pickups draw as yellow squares, shell pickups draw as warm-orange squares, armor pickups draw as flat-color squares.
- HUD ammo pane (icon + digits, below the health pane) is **weapon-aware**: dispatched from `PISTOL_AMMO_CATEGORY` to `player.bullets` with `HUD_AMMO_COLOR` (yellow). Visually identical to pre-slice HUD because pistol is the only weapon. The FPS HUD strip's ammo pane uses the same dispatch.
- HUD armor pane (icon + digits, below the ammo pane in topdown HUD; between ammo and weapon icon in the raycaster bottom strip). Color reflects `armor_type` (gray / green / blue).
- Pickup tint flash: `visual_effects::increment_pickup_tint` called on consumption (all five pickup kinds — Health, AmmoBullets, AmmoShells, ArmorGreen, ArmorBlue — use the SAME flash; no per-kind variant — knowledge `pickups.md § Single-use Consumption` "Pickup-flash counter add per pickup: a small fixed increment ... every pickup contributes the same flash amount"); golden-yellow overlay spec in `specs/40 § Pickup Tint Screen Flash`.
- Bullets pool / shells pool per-category split exercised by `tests/combat/shell_pickup.yaml`: starts at `(bullets = 50, shells = 0)`, picks up one shell, ends at `(bullets = 50, shells = 4)`. Exercises the pool-independence invariant + the per-category cap acceptance + the new `AmmoShells` variant + `level_generator::build_shell_pickup`.

**Deferred** (also listed above):
- Shotgun + shells consumer (next slice, per the issue's stated scope — the shells pool exists but has no consumer this slice).
- Auto-weapon-switch on zero→nonzero ammo (knowledge `pickups.md § Ammo Pickup Tiers` — bullets: pistol-only so meaningless; shells: no shotgun yet so meaningless). Promotes when the shotgun ships and a third bullets-consuming weapon ships.
- Energy-cell and explosive-missile categories (knowledge `combat_balance.md § Ammo Economy` lists four categories total; this slice ships two).
- Ammo cap expander (knowledge — "doubles cap on every category"; relies on multi-category accounting).
- Large pickups (bullet box 50, shell box 20 — knowledge `combat_balance.md § Ammo Economy`; this slice ships only the small variants).
- Over-cap health pickups.
- Pickup respawn.
- Pickup audio.
- Backpack / capacity expansion.
- Half-clip "dropped" flag — applies to BOTH bullets (knowledge says basic-trooper drops yield 5 rounds vs the placed-pickup 10 rounds; the prototype's single-amount `PICKUP_BULLETS_AMOUNT = 10` ignores the distinction) AND shells (knowledge — "half = 2 from a dropped-on-kill shell pickup"; no shotgun-trooper drop yet either way). Promotes when a richer pickup model lands.
- Skill multiplier (knowledge `combat_balance.md § Damage to Player` lists a 0.5× pre-armor halving on the easiest skill; deferred — single difficulty band).
- Tiny over-cap +1 armor bonus pickup.
- Pickup categories beyond health/ammo/armor (key cards, all powerups).
- HUD low-ammo warning color (per-category — bullets and shells would each get their own threshold once consumers exist).
- HUD secondary per-category ammo readouts (knowledge `hud.md § Status Bar Layout` — "one *secondary* readout per ammo category (2-digit short numerics, stacked in a small panel to the right)"). The primary readout is implemented (weapon-aware); the secondaries are deferred. Visible symptom: a shell pickup taken while the pistol is equipped has no on-screen indication.
- HUD pickup notification text.
- Pickup glow / animation.
