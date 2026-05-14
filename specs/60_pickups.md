# Pickups Specification

## Overview

This specification defines static pickup entities placed in the level: items the player consumes by walking over them. Four kinds ship in the prototype:

- **Health pickup** — restores `PICKUP_HEALTH_AMOUNT` HP, clamped to `PLAYER_MAX_HEALTH`.
- **Ammo pickup** — restores `PICKUP_AMMO_AMOUNT` rounds, clamped to `PLAYER_AMMO_MAX`.
- **Armor (green) pickup** — overwrites the player's armor pool to `PICKUP_ARMOR_GREEN_TARGET_POINTS` (100) and tier to `ArmorTier::Green`. Refused if `player.armor >= PICKUP_ARMOR_GREEN_TARGET_POINTS`.
- **Armor (blue) pickup** — overwrites the player's armor pool to `PICKUP_ARMOR_BLUE_TARGET_POINTS` (200) and tier to `ArmorTier::Blue`. Refused if `player.armor >= PICKUP_ARMOR_BLUE_TARGET_POINTS`.

This workflow also activates the **ammo system**: the player has a finite ammunition pool. The pistol decrements ammo by one per fired shot and is gated on `ammo > 0`. Out of ammo, the trigger is a no-op (no muzzle flash, no tracer, no shot, no cooldown reset).

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

### Ammo Pickup Consumption

**Trigger:** Same per-frame pickup check, for a `PickupKind::Ammo` pickup. Active pickup AND `player.ammo < PLAYER_AMMO_MAX`.

**Effect:** The pickup's `active` flag is set to `false`. Player ammo increases by `PICKUP_AMMO_AMOUNT`, clamped to `PLAYER_AMMO_MAX`.

**Rules:**
- Same "refused at cap" rule as health pickups. *(Knowledge: § Cap Behavior.)*
- Same "leave in list, just deactivate" rule.
- Auto-weapon-switch on zero→nonzero ammo (knowledge § Ammo Pickup Tiers, "auto-switch to best owned weapon") is **deferred** — the prototype has only one weapon, no switch is meaningful.

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

**Effect:** Exactly one `Pickup { kind: PickupKind::Ammo, pos: enemy.pos, active: true }` is appended to `Level::pickups` at the trooper's death position. The pickup is collectible by the existing per-frame pickup check on the next frame.

**Rules:**
- The drop is gated by an `Enemy.ammo_drop_spawned: bool` latch: initialized `false`, flipped to `true` after the push so the scan never double-spawns. *(Knowledge: § Drop on Kill — "deterministic per enemy kind, no random roll".)*
- The push happens in the dedicated drop-spawn step of `game_loop::update`'s frame-update order (`ir/contracts/_shared.yaml § frame_update_order`), AFTER the enemy update loop AND AFTER `weapon_system::fire`. This ensures a same-frame kill (player hitscan kills the trooper this tick) drops the pickup this tick rather than next tick. The drop is NOT pushed inside `enemy_logic::take_damage` because that call site only holds `&Level`, not `&mut Level::pickups` — pushing into the level requires the orchestration borrow that only `game_loop::update` owns. *(Service-emit decision recorded in `ir/contracts/_shared.yaml § service_emit_decisions § game_loop drop-spawn scan`.)*
- The pickup uses the existing `PickupKind::Ammo` and `PICKUP_AMMO_AMOUNT = 10` rounds — the half-clip "dropped" flag from knowledge (5 rounds for the basic trooper) is **deferred** to the richer-pickup-model slice. The prototype's single-amount ammo pickup means the drop grants the same rounds as a placed ammo box, which makes enemy-farming slightly more rewarding than the reference; tracked in `25_game_tuning.md § Enemy § Deferred from knowledge`.
- Because the drop appears in `Level::pickups` only AFTER the per-frame pickup check has already run this frame, the player cannot collect the drop on the same frame it is created — earliest collection is the NEXT frame. This is a one-frame delay (16 ms at 60 FPS), imperceptible.
- The drop respects the existing "refused at cap" rule: if the player is at `PLAYER_AMMO_MAX` when they walk over the dropped pickup, the pickup stays active and is collected later when there is room.
- The drop position is the trooper's `pos` at the moment of death — not the enemy's spawn position, not snapped to a tile. The renderer draws the dropped pickup at this floating-point position via the same code path that draws placed pickups.

*(Knowledge: § Drop on Kill — "spawns one pickup at the enemy's feet"; § Cap Behavior — "refused, pickup remains in world".)*

### Per-Frame Pickup Check

**Trigger:** Once per frame, in `game_loop::update`, after player movement (`apply_input`) and before enemy updates.

**Effect:** Each active pickup is tested against the player's current position. The first active pickup whose `pos.distance_to(player.pos) < PICKUP_RADIUS_TILES` AND whose acceptance condition holds is consumed. Per-kind acceptance conditions:

| Kind | Acceptance condition |
|------|----------------------|
| `Health` | `player.health < PLAYER_MAX_HEALTH` |
| `Ammo`   | `player.ammo < PLAYER_AMMO_MAX` |
| `ArmorGreen` | `player.armor < PICKUP_ARMOR_GREEN_TARGET_POINTS` (100) |
| `ArmorBlue`  | `player.armor < PICKUP_ARMOR_BLUE_TARGET_POINTS` (200) |

**Rules:**
- Single pickup per frame is sufficient — pickups are not stacked at the same tile. *(Generation default — the reference iterates ALL overlapping pickups in the same tick. For our 2 placed pickups in one level, single-per-frame is fine.)*
- If multiple pickups overlap the player at the same frame, the iteration order of `Level::pickups` decides the winner; the rest wait for subsequent frames.
- The check uses **circle distance** (`Vec2::distance_to`), not AABB. *(Knowledge says reference uses sum-of-radii Chebyshev/AABB; we use circle distance because all our other collision checks (player↔wall, weapon↔enemy) are circle-based — switching paradigms for one check would be inconsistent. The two are within ~25% of each other at typical pickup geometries; not a meaningful gameplay difference.)*
- The check runs even if the player is not alive; consuming a pickup post-mortem has no observable effect because health/ammo updates on a dead player don't re-arm anything.

### Ammo-Gated Firing

**Trigger:** `weapon_system::fire` is called by `game_loop::update`.

**Effect:** Before any other side effect (cooldown gate, muzzle flash, tracer, ray-march, damage), `fire` checks `player.ammo > 0`. If the check fails, `fire` returns immediately with **no** state change.

**Rules:**
- The cooldown gate (`time_since_fire >= PISTOL_FIRE_CYCLE`) runs first. The two gates compose: a shot fires only if both pass. *(Knowledge: § Ammo Gating of Firing — the reference's `check_ammo` is a pre-fire gate; ordering with other gates is implementation-internal.)*
- An out-of-ammo `fire()` MUST NOT reset `player.time_since_fire` — the player's first-shot accuracy budget is preserved across the dry trigger pull. *(Generation default — knowledge does not directly specify what happens to the refire timer on a dry pull; this rule is a UX choice.)*
- After all the existing fire-side effects complete (muzzle flash, tracer, ray-march, damage), `player.ammo -= 1`. *(Knowledge: § Ammo Gating of Firing — "ammo decrement happens at shot-spawn, not trigger". Our shot is hitscan with no projectile spawn, so "after all fire-side effects" is the closest analogue.)*

### Pickup Rendering

**Trigger:** Every frame, between Step 2 (exit + corpses) and Step 3 (blood + puffs) of the existing render order — on top of the floor/walls but below combat effects.

**Effect:** Each active pickup is drawn at its world position:

- **Health pickup:** a `PICKUP_HEALTH_SIZE_PX × PICKUP_HEALTH_SIZE_PX` filled square in `PICKUP_HEALTH_OUTER_COLOR`, with a centered horizontal+vertical cross of `PICKUP_HEALTH_INNER_THICKNESS_PX` width in `PICKUP_HEALTH_INNER_COLOR`.
- **Ammo pickup:** a `PICKUP_AMMO_SIZE_PX × PICKUP_AMMO_SIZE_PX` filled square in `PICKUP_AMMO_COLOR`, no inner detail.
- **Armor (green) pickup:** a `PICKUP_ARMOR_SIZE_PX × PICKUP_ARMOR_SIZE_PX` filled square in `PICKUP_ARMOR_GREEN_COLOR`, no inner detail.
- **Armor (blue) pickup:** a `PICKUP_ARMOR_SIZE_PX × PICKUP_ARMOR_SIZE_PX` filled square in `PICKUP_ARMOR_BLUE_COLOR`, no inner detail.

**Rules:**
- Inactive pickups draw nothing.
- Pickups draw under combat effects so a wall puff or blood splat covers them visually if both are at the same pixel — combat priority over loot.
- The render order list in `renderer::draw`'s docstring is updated.

*(Generation default: shapes and colors are not knowledge-backed — the reference uses sprite assets we don't have. The cross-on-square (medkit) and yellow-square (ammo box) shapes are common-knowledge retro UI conventions; the spec marks them as defaults and parking-lots them for asset-aware re-extraction.)*

### HUD Ammo Pane (extends spec/50)

**Trigger:** Every frame, in the same `draw_hud` call that draws the health pane.

**Effect:** A second pane is drawn directly below the health pane:
- A `HUD_AMMO_ICON_PX × HUD_AMMO_ICON_PX` filled square in `HUD_AMMO_COLOR` (mirrors the on-map ammo pickup color so the connection reads at a glance).
- Immediately to the right of the icon (gap `HUD_DIGIT_GAP_PX`), the player's `ammo` value drawn with the same bitmap font as health digits, color `HUD_AMMO_COLOR`. Vertical baseline centered against the icon. Right-justified, no leading zeros, zero special-cased per the same knowledge-backed rules used in spec/50 § Numeric Widget.

**Rules:**
- Pane origin: `(HUD_MARGIN_PX, HUD_MARGIN_PX + HUD_HEALTH_BAR_HEIGHT_PX + HUD_PANE_GAP_PX)`.
- No background bar (icon + digits only).
- Single color (yellow). Low-ammo warning color is **deferred**.
- Drawn whether ammo is zero or not.

*(Generation default: the layout / icon-shape / yellow choice are not knowledge-backed. Knowledge § Color / State Encoding tells us the reference uses two distinct fonts for primary vs secondary readouts, not color shifts; we substitute color for font-size since our font is monolithic.)*

## State

### Pickup Entity (in `Level::pickups`)
- **Type:** `Pickup { kind: PickupKind, pos: Vec2, active: bool }`.
- **Initial:** `level_data::build_default()` seeds five pickups (two health, one ammo, one green armor, one blue armor) at the positions in `25_game_tuning.md § Pickups § Default Level Placement`.
- **Transitions:** `active` flips from `true` to `false` exactly once when the player consumes the pickup. Never flips back within a run.

### Player Ammo (`Player.ammo`)
- **Type:** `i32`.
- **Initial:** `PLAYER_AMMO_INITIAL` set by `player_state::new`.
- **Transitions:** Decremented by 1 per fired shot in `weapon_system::fire`. Incremented by `PICKUP_AMMO_AMOUNT` (clamped) on ammo pickup consumption. Never goes negative — the ammo gate prevents firing the last shot of a zero pool.

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
- `player_state::new` initializes `ammo = PLAYER_AMMO_INITIAL`, `armor = PLAYER_ARMOR_INITIAL` (= 0), `armor_type = ArmorTier::None`.
- `player_state::take_health_pickup(player, amount)` — increments `health`, clamps to `PLAYER_MAX_HEALTH`. Does not touch `damage_count` or `alive`.
- `player_state::take_ammo_pickup(player, amount)` — increments `ammo`, clamps to `PLAYER_AMMO_MAX`.
- `player_state::take_armor_pickup(player, tier)` — overwrites `armor` to the tier's target pool (`PICKUP_ARMOR_GREEN_TARGET_POINTS` or `PICKUP_ARMOR_BLUE_TARGET_POINTS`) and `armor_type` to `tier`. Caller (game_loop) is responsible for flipping the Pickup's active flag and for the refused-at-pool guard.
- `player_state::take_damage(player, amount)` consumes `armor`/`armor_type` via the armor-first routing rule (specs/25 § Armor Damage Routing).

### With Weapon System
- `weapon_system::fire` adds a single ammo gate at the top: `if player.ammo == 0 { return; }`. Decrements `player.ammo -= 1` after the existing side effects.
- Ordering relative to the cooldown gate: cooldown first (so a dry-pull while still in cooldown is a single no-op, not a double-evaluation). Then ammo. Then everything else.

### With Game Loop
- `game_loop::update` adds Step 2.5 between `apply_input` (Step 2) and the enemy update (Step 3): scan `state.level.pickups` for the first active pickup within `PICKUP_RADIUS_TILES` of `state.player.pos` whose acceptance condition holds, and consume it.
- `game_loop::update` adds the drop-spawn step AFTER the enemy update loop AND AFTER `weapon_system::fire`: scan `state.enemies` for trooper deaths and push `Pickup { kind: PickupKind::Ammo, pos: enemy.pos, active: true }` into `state.level.pickups` (gated by `Enemy.ammo_drop_spawned`). See § Enemy Ammo Drops above.
- The frame-update-order list in `ir/contracts/_shared.yaml § frame_update_order` gains both steps.

### With Renderer
- `renderer::draw` adds Step 2.5 (between exit/corpses and blood/puffs) drawing active pickups.
- `draw_hud` (from spec/50) gets a second pane drawing call after the health pane.

### With Visual Effects
- On pickup consumption, `game_loop` calls `visual_effects::increment_pickup_tint(&mut state.fx)`, which adds `PICKUP_TINT_PER_PICKUP` to `VisualEffects.pickup_tint_count` (clamped to `PICKUP_TINT_CAP`).
- The golden-yellow screen-tint flash is fully specified in `specs/40_visual_feedback.md § Pickup Tint Screen Flash`. This spec does not duplicate those rules; it only documents the trigger point (pickup consumption) and the API call.

## Constraints

### Invariants
- `0 <= player.ammo <= PLAYER_AMMO_MAX` — enforced by the `take_ammo_pickup` clamp and the `fire`-time ammo gate.
- `0 <= player.health <= PLAYER_MAX_HEALTH` after a health pickup — enforced by the `take_health_pickup` clamp. (Below-zero health remains possible *before* clamp on lethal damage; the clamp at `take_damage` already snaps to zero.)
- `0 <= player.armor <= 200` — enforced implicitly by the armor pool's target-pool overwrite values (the two `PICKUP_ARMOR_*_TARGET_POINTS` constants are 100 and 200, and pickup-side acceptance overwrites the pool rather than adding) and by the `take_damage` clamp (`saved = min(armor, ...)` prevents negative). The ceiling has no named runtime constant — see [`ir/contracts/player_state.yaml § public_constants`](../ir/contracts/player_state.yaml) for the rationale (spec/80 § API Surface forbids dead `pub` exports, and no in-crate caller needs to read the ceiling at runtime).
- `(player.armor == 0) == (player.armor_type == ArmorTier::None)` is NOT an invariant in general: a fresh green pickup sets both `(armor=100, type=Green)` simultaneously; depleting armor via damage clears both to `(0, None)` simultaneously. But *between* those events the player can transiently carry a non-zero armor pool whose type matches the tier — that is the steady state. The implication is just that armor depletion via damage clears the type to None (specs/25 § Armor Damage Routing rule 3); the type does not silently desync from the pool.
- A pickup's `active` flag is monotonic: once `false`, never `true` again within a run.
- An out-of-ammo `fire` invocation is observationally a no-op: no field of `player`, no entry in `fx.effects`, and no enemy `health` changes.
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
- **Backpack / capacity expansion** — fixed `PLAYER_AMMO_MAX`.
- **Half-clip "dropped" flag** — knowledge § Drop on Kill + § Ammo Pickup Tiers say a basic-trooper drop yields 5 rounds (half a clip) vs the placed-pickup 10 rounds. The prototype's single-amount `PICKUP_AMMO_AMOUNT = 10` ignores the dropped/placed distinction. The trooper death-time drop itself is **implemented** in the 2026-05-13 combat slice (see § Enemy Ammo Drops above) — only the half-amount flag is deferred.
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

### Ammo Pickup
1. With player at the ammo pickup's position and `ammo < PLAYER_AMMO_MAX`, after one tick `player.ammo` increased by `PICKUP_AMMO_AMOUNT` (or clamped) and pickup `active == false`.
2. With player at the ammo pickup's position and `ammo == PLAYER_AMMO_MAX`, after one tick the pickup's `active == true` (refused) and `player.ammo` unchanged.

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

### Ammo-Gated Firing
1. Set `player.ammo = 0`, hold fire input, run one tick: no muzzle flash spawned, no tracer spawned, no enemy damage, `player.time_since_fire` does NOT reset to 0.
2. Set `player.ammo = 1`, fire once with cooldown ready: a muzzle flash spawns and `player.ammo` becomes 0.
3. Each successful shot decrements `player.ammo` by exactly 1.

### Per-Frame Pickup Check
1. With the player positioned `> PICKUP_RADIUS_TILES` from any active pickup, no pickup state changes after one tick.
2. With the player positioned exactly at the boundary (`= PICKUP_RADIUS_TILES`), the pickup is **not** consumed (strict `<` comparison).
3. With the player positioned just inside the boundary AND below cap, the pickup is consumed in one tick.

### Pickup Rendering
1. After `draw()`, sample a pixel at the health pickup's expected on-screen center: it matches `PICKUP_HEALTH_INNER_COLOR` (the cross center).
2. After `draw()`, sample a pixel at the ammo pickup's center: it matches `PICKUP_AMMO_COLOR`.
3. After consuming a pickup (`active = false`), sampling the same pixel returns the floor color (pickup not drawn).

### HUD Ammo Pane
1. With `player.ammo = 12`, after `draw()`, sample a pixel inside the ammo icon's footprint: it matches `HUD_AMMO_COLOR`.
2. With `player.ammo = 0`, the ammo pane still renders the digit `0` in `HUD_AMMO_COLOR`.

## Implementation Status

**Implemented:**
- `Pickup` and `PickupKind` types homed in `level_data`. `PickupKind` carries variants `Health`, `Ammo`, `ArmorGreen`, `ArmorBlue` (armor variants added in the 2026-05-14 armor slice).
- `ArmorTier` enum (`None | Green | Blue`) on `Player`, homed in `player_state`.
- `Level::pickups` field populated by `build_default` with two health, one ammo, one green armor, and one blue armor pickup at fixed positions (spec/25 § Pickups § Default Level Placement). Demo levels (`level_generator`) seed their own `Vec<Pickup>` per the layout pinned in `specs/15_level_generator.md`.
- `Player.ammo`, `Player.armor`, and `Player.armor_type` fields, initialized to `PLAYER_AMMO_INITIAL` / `PLAYER_ARMOR_INITIAL` / `ArmorTier::None` by `player_state::new`.
- `player_state::take_health_pickup`, `player_state::take_ammo_pickup`, and `player_state::take_armor_pickup(player, tier)` (clamped to caps; armor overwrites tier + pool).
- `player_state::take_damage` applies the armor-first routing rule (specs/25 § Armor Damage Routing).
- `weapon_system::fire` ammo gate (top of function, after cooldown gate) and per-shot decrement.
- `game_loop::update` Step 2.5 per-frame pickup check (refused-at-cap / refused-at-pool rule applied per the per-kind acceptance table above).
- `game_loop::update` drop-spawn scan after the enemy update + weapon-fire steps (specs/60 § Enemy Ammo Drops): pushes one `Pickup { kind: Ammo, pos: enemy.pos, active: true }` per dead trooper, gated by `Enemy.ammo_drop_spawned`.
- Renderer pickup layer (between exit/corpses and blood/puffs); armor pickups draw as flat-color squares.
- HUD ammo pane (icon + digits, below the health pane).
- HUD armor pane (icon + digits, below the ammo pane in topdown HUD; between ammo and weapon icon in the raycaster bottom strip). Color reflects `armor_type` (gray / green / blue).
- Pickup tint flash: `visual_effects::increment_pickup_tint` called on consumption (all four pickup kinds use the SAME flash; no per-kind variant — knowledge `pickups.md § Single-use Consumption` "Pickup-flash counter add per pickup: a small fixed increment ... every pickup contributes the same flash amount"); golden-yellow overlay spec in `specs/40 § Pickup Tint Screen Flash`.

**Deferred** (also listed above):
- Multiple weapon ammo pools.
- Ammo cap expander.
- Over-cap health pickups.
- Auto-weapon-switch on zero→nonzero ammo.
- Pickup respawn.
- Pickup audio.
- Backpack / capacity expansion.
- Half-clip "dropped" flag (knowledge says basic-trooper drops yield 5 rounds vs the placed-pickup 10 rounds; the prototype's single-amount `PICKUP_AMMO_AMOUNT = 10` ignores the dropped/placed distinction). Promotes when a richer pickup model lands.
- Skill multiplier (knowledge `combat_balance.md § Damage to Player` lists a 0.5× pre-armor halving on the easiest skill; deferred — single difficulty band).
- Tiny over-cap +1 armor bonus pickup.
- Pickup categories beyond health/ammo/armor.
- HUD low-ammo warning color.
- HUD pickup notification text.
- Pickup glow / animation.
