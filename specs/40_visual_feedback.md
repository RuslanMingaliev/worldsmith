# Visual Feedback Specification

## Overview

This specification defines the short-lived visual effects that confirm combat actions for the player: weapon firing, hits on walls vs. enemies, enemy reactions, player damage, and enemy death. Each effect is a transient sprite or color overlay with a fixed lifetime; together they create a layered "moment of impact" without changing core gameplay.

Scope is the current 2D top-down prototype. Effects intended for first-person rendering, tiered blood, gibs, pickups, and force feedback are deferred (see Deferred section).

All numeric durations, colors, and sizes referenced by name (e.g. `MUZZLE_FLASH_DURATION`) are defined in [`25_game_tuning.md`](25_game_tuning.md). The behavior spec only refers to constants by name.

Source: [`knowledge/visual_feedback.md`](../knowledge/visual_feedback.md).

## Design Goals

- **Discrimination over fidelity**: A wall puff (gray) and a blood splat (red) just need to look *different*. Photorealism is not a goal.
- **Short and overlapping**: Most effects last under one second. Layered short effects feel substantial; long individual effects feel sluggish.
- **Auto-cleanup**: Every effect has a fixed lifetime and despawns automatically. No manual reset.
- **Decoupled from game logic**: Effects are visual only. Damage, pain transitions, and death are owned by combat/AI specs; this spec only describes what the player sees.

## Behaviors

### Muzzle Flash

**Trigger:** Player weapon fires (one flash per shot).

**Effect:** A bright filled shape appears at the player's muzzle position (slightly forward of the player's center along the facing direction) for `MUZZLE_FLASH_DURATION`.

**Rules:**
- Position is recomputed at spawn time; the flash does not follow the player after it spawns.
- Spawning a new flash while one already exists is allowed — both render until each expires.
- The flash uses the muzzle color from tuning, distinct from the projectile tracer color.
- World-brightness pulse is **deferred** (no first-person renderer to brighten).

### Hit-Scan Tracer

**Trigger:** Player weapon fires (one tracer per shot, regardless of whether anything was hit).

**Effect:** A thin line is drawn from the player's muzzle position to the trace endpoint for `TRACER_DURATION`.

**Rules:**
- Endpoint is the impact position: the surface of an enemy if hit, otherwise the wall the trace stops at, otherwise the trace's max range.
- The tracer uses the tracer color from tuning.
- The tracer is a 2D-friendly substitute for first-person muzzle illumination + impact spark, communicating "the shot went *that* way" at a glance in top-down view.
- Tracer geometry is captured at spawn; it does not update if the player moves.

### Impact Effect (Wall Puff vs. Blood Splat)

**Trigger:** A weapon trace terminates at a wall (puff) or at a living enemy (blood). One impact effect per terminating trace.

**Effect:** A small short-lived sprite spawns at the trace endpoint:
- **Wall puff**: gray, `PUFF_DURATION`.
- **Blood splat**: red, `BLOOD_DURATION`, larger than the puff.

**Rules:**
- Effect type is selected by what the trace hit (wall vs. enemy). A trace that hits nothing produces no impact effect.
- Effects do not block gameplay, do not damage anything, and do not interact with collision.
- Effects do not pulse or move; they fade out (or display flat) for their lifetime then despawn.
- Damage-tiered blood (small/medium/large by damage value) is **deferred**: a single splat size is used for now.

### Enemy Pain Flash

**Trigger:** An enemy enters its existing Pain state (defined in [`20_gameplay_model.md`](20_gameplay_model.md)). The pain *transition* is owned by enemy logic; this spec only adds the *visual* layered on top.

**Effect:** For `ENEMY_PAIN_FLASH_DURATION`, the enemy is drawn with the pain-flash color instead of its normal body color.

**Rules:**
- The flash duration may be shorter than the underlying Pain state duration (`PAIN_DURATION` from `25_game_tuning.md`); the visual only highlights the moment of being hit.
- The flash timer is (re)set whenever the enemy enters the Pain state. Because Pain entry is gated by the per-hit pain check (78% chance), a re-hit that fails the pain check does not refresh the flash. This is acceptable: rapid pistol fire trips the pain check often enough to keep the flash alive in practice.
- The flash applies to the enemy's existing draw position and shape — no new entity is spawned.

### Player Damage Tint

**Trigger:** Player takes damage (any amount, any source).

**Effect:** A semi-transparent red overlay covers the play area. Overlay alpha scales with the player's accumulated damage count.

**Rules:**
- The player has a `damage_count` accumulator. On damage, `damage_count += damage_value` (after any future armor reduction), clamped to `DAMAGE_TINT_CAP`.
- Each tick, `damage_count` decays by `DAMAGE_TINT_DECAY_PER_SEC * delta_time`. Accumulator is clamped at zero.
- `damage_count` is mapped to one of `DAMAGE_TINT_LEVELS` discrete alpha levels for the overlay; level zero means the overlay is not drawn at all.
- The mapping is roughly even across the cap (e.g. for 8 levels and cap 100, each level covers ~12.5 units of damage).
- The accumulator is *cumulative*: many small hits chain into a sustained red without per-hit logic.
- "Faster decay when facing attacker" rule from the source is **deferred** for the prototype (the prototype has only one enemy and no concept of "facing the attacker").
- Pickup tint (gold flash on item pickup) is **deferred** (no pickups exist yet).

### Enemy Death Visual

**Trigger:** Enemy health reaches 0 (existing Death transition, owned by enemy logic).

**Effect:** Two phases:
1. **Death fade**: For `ENEMY_DEATH_FADE_DURATION`, the enemy sprite shrinks and/or recolors toward the corpse color.
2. **Corpse marker**: After the fade, a static corpse sprite is drawn at the death position. The corpse persists until level reset.

**Rules:**
- Once a corpse marker exists, it is drawn under all live entities (non-blocking, walkable visually).
- The corpse uses the corpse color from tuning, smaller than the live enemy sprite.
- The corpse is purely visual: it does not collide, take damage, or interact with the player.
- Gib (extreme death) animation is **deferred**: only the normal fade-and-corpse path exists.
- The death visual must not block the existing Death state transition or any other game logic — it runs alongside, not instead of.
- Implementation note: the corpse marker is spawned by `enemy.update()` rather than synchronously inside `take_damage()`. This is a borrow-graph simplification (the weapon system already holds `&mut VisualEffects` while calling `take_damage`); spawning is delayed to the tick on which the death-fade timer reaches zero.

### Effect Layering

**Trigger:** Multiple effects active simultaneously.

**Effect:** All active effects render in the same frame without conflict.

**Rules:**
- Each effect runs on its own lifetime timer.
- Render order (back to front): corpses, blood splats, wall puffs, tracers, muzzle flashes, enemies, player, damage tint overlay.
- Effect lifetimes are independent: a tracer expiring does not affect a still-active blood splat from the same shot.
- All effects auto-despawn when their lifetime reaches zero. There is no manual cleanup.

## State

### Active Effects List
- **Type:** A list of transient visual effect entities.
- **Initial:** Empty.
- **Transitions:** New effects are appended on triggers (firing, hitting, dying). Each tick, every effect's remaining lifetime is decreased by `delta_time`. Effects with lifetime <= 0 are removed, except corpses which persist.

### Effect Entity
Each effect carries:
- **Kind:** muzzle flash, tracer, wall puff, blood splat, or corpse.
- **Position:** World-space coordinates (or a pair of coordinates for tracer endpoints).
- **Lifetime remaining:** Seconds until despawn (corpses use a sentinel meaning "persistent").

### Player Damage Accumulator
- **Type:** Float, scalar.
- **Initial:** 0.0.
- **Transitions:** Increased on player damage (clamped to cap), decayed each tick. Owned by player state (or the visual-feedback module if cleaner) — implementation choice deferred to Coder.

### Enemy Pain Flash Timer
- **Type:** Float, per enemy (only one enemy exists today).
- **Initial:** 0.0.
- **Transitions:** Set to full duration when enemy enters Pain state. Decreased each tick. Drives whether the enemy renders with the flash color this frame.

## Interactions

### With Weapon System
- On `fire`, the weapon system spawns one muzzle flash and one hit-scan tracer with the appropriate endpoint.
- On a successful enemy hit, the weapon system additionally spawns a blood splat at the impact point.
- On a wall hit (trace terminates at a wall), the weapon system spawns a wall puff at the impact point.
- The weapon system does not need to know how effects render — only that it requests a spawn.

### With Enemy Logic
- On entering Pain state, enemy logic raises the pain-flash visual.
- On entering Death state, enemy logic triggers the death visual (fade + corpse spawn).

### With Player State
- On `take_damage`, the player damage accumulator is increased.
- The damage accumulator decays as part of normal frame updates.

### With Renderer
- The renderer reads the active effects list, the pain-flash state on each enemy, and the player damage accumulator each frame.
- The renderer does not modify any effect state — it only draws.
- Existing stdout messages from the weapon system and enemy logic ("Hit for X! ...", "Enemy hit player for X! ...") remain in place; visual feedback supplements, not replaces them. Their removal is a separate Coder decision later.

### With Game Loop
- The game loop owns the active effects list (or a `VisualEffects` aggregate).
- Each frame, the game loop calls a tick/update on the effects list to age and prune them.
- Effect spawn requests from weapon system and enemy logic are appended to this list during their respective updates.

## Constraints

### Invariants
- Effect lifetimes are non-negative; effects with lifetime <= 0 (other than corpses) must be pruned within one frame.
- Effects do not affect gameplay state (no damage, no collision, no state machine transitions).
- The player damage accumulator is bounded: `0 <= damage_count <= DAMAGE_TINT_CAP`.
- Spawning an effect must succeed even if dozens of effects are already active. Effect-list capping is **deferred** (acceptable for the prototype's single-enemy combat).

### Determinism
- Effect spawn position is a deterministic function of weapon/enemy state at the time of the trigger. No random jitter is required for the prototype (the source's anti-lockstep jitter is **deferred** because simultaneous effects are rare with one enemy).

## Deferred

The following are documented in `knowledge/visual_feedback.md` but are out of scope for the current 2D top-down prototype:

- **World-brightness pulse from muzzle flash** — requires first-person rendering.
- **Damage-tiered blood sprites** — single splat size for now; will be revisited when the weapon roster expands.
- **Gib (extreme death) animation** — single death visual path; will be revisited when overkill thresholds matter.
- **Pickup tint** (yellow flash on item pickup) — no pickups exist yet.
- **Force feedback / rumble** on damage — not applicable to keyboard input.
- **"Faster decay when facing attacker"** for damage tint — single-enemy prototype.
- **Anti-lockstep random jitter** on effect first-frame durations — only meaningful with many simultaneous effects.
- **Effect-count cap / culling** — only meaningful in long sustained combat.
- **Vertical jitter / upward drift** on impact effects — fade-out alone is sufficient in top-down view.
- **Different puff variant for melee vs. ranged** — only one weapon exists.
- **Corpse-position drop items** — pickups not implemented.

## Test Scenarios

### Muzzle Flash and Tracer
1. Firing the weapon spawns one muzzle flash at the player's muzzle position.
2. Firing the weapon spawns one tracer originating at the player's muzzle position.
3. After `MUZZLE_FLASH_DURATION` elapses, the muzzle flash is no longer drawn.
4. After `TRACER_DURATION` elapses, the tracer is no longer drawn.

### Wall vs. Enemy Hit Discrimination
1. Firing toward a wall produces exactly one wall puff (gray) at the wall, no blood.
2. Firing toward and hitting an enemy produces exactly one blood splat (red) at the enemy, no puff.
3. A trace that hits nothing within range produces no impact effect.

### Enemy Pain Flash
1. When an enemy enters the Pain state, it renders with the pain-flash color for `ENEMY_PAIN_FLASH_DURATION`.
2. After `ENEMY_PAIN_FLASH_DURATION` elapses, the enemy renders with its normal color (regardless of whether the Pain state itself has ended).
3. A subsequent hit that itself triggers Pain (passes the pain check) re-arms the flash timer to full duration.

### Player Damage Tint
1. Player taking 10 damage increases `damage_count` by 10 (clamped to cap).
2. With `damage_count` at the cap, the overlay renders at maximum alpha level.
3. With `damage_count` at zero, no overlay is rendered.
4. After taking damage and waiting `DAMAGE_TINT_CAP / DAMAGE_TINT_DECAY_PER_SEC` seconds with no further damage, `damage_count` decays back to zero.

### Enemy Death Visual
1. When an enemy reaches 0 HP, the death-fade visual begins.
2. After `ENEMY_DEATH_FADE_DURATION` elapses, a corpse marker is drawn at the death position.
3. The corpse persists across subsequent frames until level reset.
4. The corpse does not block player movement (no collision change introduced by this spec).

## Implementation Status

**Implemented:**
- Muzzle flash on every player shot.
- Hit-scan tracer line from muzzle to trace endpoint, including misses.
- Wall puff vs. blood splat impact discrimination.
- Enemy pain-flash tint replacing the body color for `ENEMY_PAIN_FLASH_DURATION`.
- Enemy death fade (sprite shrinks and recolors toward corpse color over `ENEMY_DEATH_FADE_DURATION`) followed by a persistent corpse marker.
- Player damage tint accumulator with discrete-level alpha overlay and per-tick decay.
- Independent per-effect lifetimes with auto-despawn.

**Deferred** (also listed in the Deferred section above, restated here so future Reconciler runs can compare line-by-line):
- World-brightness pulse from muzzle flash.
- Damage-tiered blood sprites.
- Gib (extreme death) animation.
- Pickup tint (gold flash on item pickup).
- Force feedback / rumble on damage.
- "Faster decay when facing attacker" rule for damage tint.
- Anti-lockstep random jitter on first-frame durations.
- Effect-list cap / culling.
- Vertical jitter / upward drift on impact effects.
- Per-weapon puff variants.
- Corpse-position drop items.
