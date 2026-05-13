# Pickups Specification

## Overview

This specification defines static pickup entities placed in the level: items the player consumes by walking over them. Two kinds ship in the prototype:

- **Health pickup** — restores `PICKUP_HEALTH_AMOUNT` HP, clamped to `PLAYER_MAX_HEALTH`.
- **Ammo pickup** — restores `PICKUP_AMMO_AMOUNT` rounds, clamped to `PLAYER_AMMO_MAX`.

This workflow also activates the **ammo system**: the player has a finite ammunition pool. The pistol decrements ammo by one per fired shot and is gated on `ammo > 0`. Out of ammo, the trigger is a no-op (no muzzle flash, no tracer, no shot, no cooldown reset).

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

**Effect:** Each active pickup is tested against the player's current position. The first active pickup whose `pos.distance_to(player.pos) < PICKUP_RADIUS_TILES` AND whose acceptance condition holds (health < cap for health pickups, ammo < cap for ammo pickups) is consumed.

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
- **Initial:** `level_data::build_default()` seeds two pickups (one health, one ammo) at the positions in `25_game_tuning.md § Pickups § Default Level Placement`.
- **Transitions:** `active` flips from `true` to `false` exactly once when the player consumes the pickup. Never flips back within a run.

### Player Ammo (`Player.ammo`)
- **Type:** `i32`.
- **Initial:** `PLAYER_AMMO_INITIAL` set by `player_state::new`.
- **Transitions:** Decremented by 1 per fired shot in `weapon_system::fire`. Incremented by `PICKUP_AMMO_AMOUNT` (clamped) on ammo pickup consumption. Never goes negative — the ammo gate prevents firing the last shot of a zero pool.

## Interactions

### With Level Data
- `level_data::build_default` populates `Level::pickups` with the default placement.
- `Pickup` and `PickupKind` are homed in `level_data` (alongside `Tile` and `Vec2`).

### With Player State
- `player_state::new` initializes `ammo = PLAYER_AMMO_INITIAL`.
- `player_state::take_health_pickup(player, amount)` — increments `health`, clamps to `PLAYER_MAX_HEALTH`. Does not touch `damage_count` or `alive`.
- `player_state::take_ammo_pickup(player, amount)` — increments `ammo`, clamps to `PLAYER_AMMO_MAX`.

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
- A pickup's `active` flag is monotonic: once `false`, never `true` again within a run.
- An out-of-ammo `fire` invocation is observationally a no-op: no field of `player`, no entry in `fx.effects`, and no enemy `health` changes.
- The "refused at cap" rule means no pickup is consumed when its effect would be wasted.

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
- **Pickup categories beyond health/ammo** — armor, keycards, all powerups. Knowledge mentions them; deferred.
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
- `Pickup` and `PickupKind` types homed in `level_data`.
- `Level::pickups` field populated by `build_default` with one health and one ammo pickup at fixed positions (spec/25 § Pickups § Default Level Placement). Demo levels (`level_generator`) seed their own `Vec<Pickup>` per the layout pinned in `specs/15_level_generator.md`.
- `Player.ammo` field, initialized to `PLAYER_AMMO_INITIAL` by `player_state::new`.
- `player_state::take_health_pickup` and `player_state::take_ammo_pickup` (clamped to caps).
- `weapon_system::fire` ammo gate (top of function, after cooldown gate) and per-shot decrement.
- `game_loop::update` Step 2.5 per-frame pickup check (refused-at-cap rule applied).
- `game_loop::update` drop-spawn scan after the enemy update + weapon-fire steps (specs/60 § Enemy Ammo Drops): pushes one `Pickup { kind: Ammo, pos: enemy.pos, active: true }` per dead trooper, gated by `Enemy.ammo_drop_spawned`.
- Renderer pickup layer (between exit/corpses and blood/puffs).
- HUD ammo pane (icon + digits, below the health pane).
- Pickup tint flash: `visual_effects::increment_pickup_tint` called on consumption; golden-yellow overlay spec in `specs/40 § Pickup Tint Screen Flash`.

**Deferred** (also listed above):
- Multiple weapon ammo pools.
- Ammo cap expander.
- Over-cap health pickups.
- Auto-weapon-switch on zero→nonzero ammo.
- Pickup respawn.
- Pickup audio.
- Backpack / capacity expansion.
- Half-clip "dropped" flag (knowledge says basic-trooper drops yield 5 rounds vs the placed-pickup 10 rounds; the prototype's single-amount `PICKUP_AMMO_AMOUNT = 10` ignores the dropped/placed distinction). Promotes when a richer pickup model lands.
- Skill multiplier.
- Pickup categories beyond health/ammo.
- HUD low-ammo warning color.
- HUD pickup notification text.
- Pickup glow / animation.
