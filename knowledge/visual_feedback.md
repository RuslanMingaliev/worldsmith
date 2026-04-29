# Finding: Visual Feedback for Shooting and Damage

## Summary

Classic FPS reference games layer visual feedback on top of every combat action: a brief muzzle flash sprite confirms the shot, an impact effect at the trace endpoint discriminates wall hits (puff) from flesh hits (blood), enemies briefly play a stagger animation when they take damage, and the player sees a red screen tint scaled to the size of the hit. Each effect has a short fixed lifetime (a fraction of a second) and a small randomization on duration so repeated hits look organic. The pattern is portable to a top-down 2D prototype because each effect is essentially a short-lived sprite or color tint with a duration measured in tens of milliseconds.

## Observed Mechanics

### Muzzle Flash (Weapon Firing Confirmation)

- **Behavior**: The instant the player fires, a separate "flash" sprite layer is overlaid on top of the weapon sprite for a few ticks (the reference engine runs at 35 ticks/sec). The flash uses a full-bright color so it visually pops against the dimmer weapon sprite. After the flash sprite expires, the layer goes blank again.
- **Rules**:
  - The flash is rendered on its own sprite layer, independent of the weapon animation. The two layers share screen position but have independent state machines.
  - When a weapon's fire action runs, it directly sets the flash layer's state to a weapon-specific flash frame; the weapon and flash animations then play simultaneously.
  - The flash state has a side-effect that boosts the world's "extra light" level for the duration of the flash. This brightens the surrounding scene briefly, simulating illumination from the muzzle. Two stages exist: a brighter first frame and a slightly dimmer second frame as the flash fades.
  - Multi-frame flashes cycle automatically: the first flash state's "next state" points to the second flash state, which then transitions to a "light done" state that resets the extra light to zero.
  - For rapid-fire weapons (chaingun-style), the flash state used is randomized between two equivalent variants per shot, so consecutive frames don't look identical.
  - When a weapon is being fired multiple times via a refire action, each shot triggers a fresh flash.
- **Constants** (at 35 ticks/sec):
  - Pistol flash: single frame, 7 ticks (~0.20 s)
  - Single-barrel shotgun flash: 4 ticks + 3 ticks = 7 ticks total (~0.20 s)
  - Double-barrel shotgun flash: 5 ticks + 4 ticks = 9 ticks total (~0.26 s)
  - Chaingun flash: 5 ticks per frame (~0.14 s), randomly picks one of two variants per shot
  - Rocket launcher flash: 3 + 4 + 4 + 4 = 15 ticks (~0.43 s, longer because of the launch plume)
  - Plasma flash: 4 ticks, randomly picks one of two variants (~0.11 s)
  - Extra-light levels: 0 = none, 1 = bright (start of flash), 2 = brighter (mid flash for longer flashes)
- **Feel**: The flash is short — typically under a quarter second — but unmistakable. Because it's a separate layer, the weapon sprite continues its recoil/recovery animation independently, which makes the firing animation feel layered and lively. The brief world brightening implies that the muzzle is actually illuminating the room, even though it's just a global tint.

**Top-down 2D adaptation**: A small bright sprite or filled shape at the player's "muzzle" position (offset slightly forward of the player's center along the firing direction) for 5-7 frames at 60 FPS works well. Pair it with a brief world-wide brightness pulse if rendering supports it.

### Hitscan Impact: Wall Puff vs. Flesh Blood

- **Behavior**: When a hitscan trace terminates against a target, an effect spawns at the endpoint. Walls produce a small smoky puff. Living shootable creatures produce a blood splatter. Some creatures (mechanical / barrel-like) are flagged "no blood" and produce a puff instead.
- **Rules**:
  - The trace function walks intercepts in distance order. On the first wall it can't pass through, it computes a position slightly back from the actual hit point (a small fraction of the trace distance) and spawns a puff there. On the first valid creature hit, it spawns either a puff or blood depending on the target's flags, then applies damage and stops.
  - The puff/blood is positioned a few units short of the actual collision so the sprite doesn't z-fight or clip into the wall/target.
  - Both effects are spawned with a small random vertical jitter (a few units up or down from the impact height), so consecutive hits don't stack identically.
  - Both effects rise slowly (small upward velocity) over their lifetime, simulating dispersing smoke or floating blood drops.
  - Both effects have a small per-spawn random reduction (subtract 0-3) of the first frame's duration, so multiple impacts spawned the same tick don't desync into a marching-band animation.
  - Wall hits against a "sky" surface produce no puff (the trace just stops with no effect — important for outdoor levels).
  - Melee weapons reaching a wall get a different puff variant (no spark frame), since punches shouldn't visually spark on stone.
  - Blood color/sprite frame is selected by damage tier, giving heavier hits a chunkier visual:
    - Damage >= 13: full splatter (most dramatic)
    - Damage 9-12: medium spatter
    - Damage < 9: small drip
- **Constants** (at 35 ticks/sec):
  - Puff: 4 frames, 4 ticks each = 16 ticks total (~0.46 s)
  - Puff first frame is "full bright" so it stands out
  - Puff upward velocity: 1 unit per tick (slow rise)
  - Blood: 3 frames, 8 ticks each = 24 ticks total (~0.69 s)
  - Blood upward velocity: 2 units per tick (rises faster than puff)
  - Random duration jitter on first frame: subtract 0-3 ticks
  - Vertical jitter on spawn position: about +/- a few units (random dispersion)
  - Position offset from impact: ~4 units back for walls, ~10 units back for things
- **Feel**: The puff/blood discrimination is essential information. With sound alone, the player would not know whether a shot landed. The visual distinction tells the player "you hit the wall" vs. "you hit the enemy" instantly, even before damage numbers or enemy reactions appear. The damage-tiered blood makes powerful weapons feel more impactful than weak ones at the moment of impact.

**Top-down 2D adaptation**: A small grey particle or short-lived sprite at the impact point for walls; a red splash sprite for enemies, with size scaled by damage (small/medium/large variants). The brief upward drift can be approximated by a simple fade-out.

### Enemy Pain Animation

- **Behavior**: When an enemy takes damage and the pain check passes (random number < the enemy's pain chance), it briefly plays a flinch animation, interrupting whatever it was doing. The flinch is short — typically under 0.2 seconds — but it's a clear visual signal that the shot landed.
- **Rules**:
  - The pain state is a 2-frame animation that plays once and then returns the enemy to its chase state.
  - Each enemy type has its own pain sprite, but mechanically the system is uniform.
  - The first pain frame is silent; the second frame triggers a pain sound effect (audio feedback paired with the visual flinch).
  - The pain state sets a "just hit, fight back" flag that makes the enemy retaliate immediately on recovery, biasing combat toward escalation rather than stalemate.
  - During pain, the enemy's reaction-time counter is forced to zero, so it's ready to attack the moment pain ends.
  - The pain check is triggered every time the enemy takes damage, not just once per encounter, so rapid-fire weapons can chain pain animations on weak enemies.
  - Some enemies (skull-like flying chargers) have a 100% pain chance — they always flinch, but compensate with aggressive movement.
- **Constants** (at 35 ticks/sec):
  - Basic humanoid enemies (basic hitscan trooper / shotgun trooper): 2 frames at 3 ticks each = 6 ticks total (~0.17 s)
  - Ranged-melee hybrid / small melee enemy: 2 frames at 2 ticks each = 4 ticks total (~0.11 s)
  - Larger floating creature: 3 frames at 3-6 ticks = 12 ticks total (~0.34 s)
  - Pain sound plays on second frame (mid-flinch)
- **Feel**: Pain animations are deliberately short. Long pain animations would make enemies feel "stunned" rather than "hurt." The 0.1-0.2 second flinch is just enough to read as "I hit it" without being a tactical pause. Combined with high pain chances on weak enemies, sustained fire visibly stun-locks them, which is a satisfying expression of damage.

**Top-down 2D adaptation**: A 1-2 frame color flash on the enemy sprite (e.g., briefly tint white or brighten the enemy color) for 6-10 frames at 60 FPS. Optionally pair with a small knockback offset.

### Player Damage Screen Tint

- **Behavior**: When the player takes damage, the entire screen tints red for a brief moment. The intensity of the red and how long it lingers scale with the damage taken. Many small hits produce mild flashes; one big hit produces a strong red wash.
- **Rules**:
  - The player has a "damage count" counter that accumulates damage taken (after armor reduction) into a single pool.
  - Each tick, the damage count decays by 1, so the red tint naturally fades over time.
  - If the player is facing their attacker, the damage count decays slightly faster (interpreted as the player "acknowledging" the hit visually). Otherwise, normal decay.
  - The damage count is clamped to a maximum (catastrophic damage events don't produce infinite-duration red screens).
  - The current damage count is mapped to one of N discrete red-tint palette levels. Higher counts = stronger red.
  - The mapping is roughly logarithmic: small damage produces a brief mild flash; bigger damage steps up to a stronger flash that takes longer to fade.
  - A small "tactile feedback" pulse is also triggered (force feedback / rumble), proportional to the damage.
  - A separate counter controls a brief golden-yellow tint for picking up items (positive feedback). This shares the screen-tint mechanism but uses a different palette ramp.
- **Constants** (at 35 ticks/sec):
  - Damage count cap: 100 (so the strongest possible flash lasts about 100 ticks ~= 2.86 s before fully fading)
  - Decay rate: 1 unit per tick (linear)
  - Number of red-tint levels: 8
  - Mapping: tint level = floor((damage_count + 7) / 8), clamped to 8 levels
  - Pickup-tint accumulation: +6 per pickup
  - Pickup-tint level count: 4 (briefer, gentler than damage)
- **Feel**: The screen flash is one of the most visceral feedback channels in the genre. It tells the player "you got hit, badly" without UI changes, without numbers, without sound — just a wash of color. The fade-out gives the player a brief moment to feel hurt before normalcy returns. Crucially, the cap prevents instant-kill events from blacking out the screen with red, which would be disorienting.

**Top-down 2D adaptation**: A semi-transparent red overlay rectangle covering the play area, with alpha proportional to a decaying damage counter. Decay linearly, cap the counter, and the same code can drive a yellow tint for pickups.

### Enemy Death Animation

- **Behavior**: When an enemy reaches zero health, it transitions to a multi-frame death animation that ends with a "corpse" frame that persists indefinitely. If the killing blow was a major overkill (damage exceeded the enemy's spawn health, so health goes deeply negative), it uses a more dramatic "extreme death" / gib animation instead.
- **Rules**:
  - Normal death: 5-frame animation, 5 ticks per frame, ends with a corpse frame that has -1 duration (persists forever).
  - Extreme death (gib): 9-frame animation, 5 ticks per frame, ends with a different corpse frame. Triggered when health drops below the negative of the enemy's max health.
  - On entering death, the enemy's height collapses to a quarter of original (so the corpse is small and walkable over).
  - Partway through the death animation (typically frame 3), the enemy loses its "solid" flag and becomes walk-through.
  - On the second frame of death, a death sound plays (scream/groan). The extreme death plays a different "splat" sound on its second frame.
  - On the first frame, a small random reduction (0-3 ticks) is subtracted from the duration so simultaneous deaths don't all sync up.
  - Some enemy types drop pickup items at the moment of death (the basic hitscan grunt drops an ammo clip, the shotgun grunt drops a shotgun pickup). The drop spawns at the death location.
  - Gibbed enemies cannot be resurrected by certain enemy types — the gib death has no "raise" path. This makes gibbing tactically distinct from normal kills.
- **Constants** (at 35 ticks/sec):
  - Normal death: 5 frames * 5 ticks = 25 ticks (~0.71 s) + permanent corpse
  - Extreme death: 9 frames * 5 ticks = 45 ticks (~1.29 s) + permanent corpse
  - Solid-loss frame: typically the third frame (~0.29 s into the animation)
  - Height collapse: original height / 4
  - Gib threshold: damage exceeding spawn_health (e.g., 20 HP enemy gibs at -20 or worse)
  - Random first-frame jitter: subtract 0-3 ticks
- **Feel**: Death animations are paced to feel weighty. Three-quarters of a second of falling/twitching before settling tells the player "you killed it" with finality. The gib animation rewards powerful weapons or critical hits with a more dramatic visual, reinforcing the feel of overkill. Persistent corpses serve as visible records of recent combat — they tell the player at a glance "I came through here and cleared it."

**Top-down 2D adaptation**: A simple 3-5 frame fade-out / slump animation on the enemy sprite, transitioning to a static "corpse" sprite that remains. For gibs, a brief particle burst plus a different corpse sprite (or none, if gibbed enemies should fully vanish).

### Visual Feedback Layering

- **Behavior**: Multiple feedback channels stack simultaneously without conflict. A single fired-and-hit shot produces, in order: (1) muzzle flash on the player's view, (2) world brightness pulse, (3) puff or blood at impact point, (4) pain animation on the enemy, (5) pain sound, (6) hit sound (from the puff/blood spawn).
- **Rules**:
  - Each effect runs on its own state machine and timer, so they don't interfere.
  - The flash, puff/blood, and pain animation all start in the same tick that the hit is registered.
  - All effects auto-clean-up after their duration expires (no manual reset needed).
  - The screen damage tint is the only effect that is *cumulative* — each hit adds to the existing tint instead of replacing it.
- **Feel**: The simultaneous layering creates a strong "moment of impact" feel. A single well-aimed shot rewards the player with a small fireworks display: the gun flashes, the room briefly lights up, a small splatter appears at the target, the target flinches, sounds play. Even though each individual effect is short, the combination feels meaty.

## Key Insights

1. **Visual feedback is non-negotiable for "feel."** Without muzzle flash, blood/puff, and pain animations, the player has no way to tell whether shots landed except by enemy health bars or damage numbers — both of which feel like RPG abstractions, not action-game feedback. The genre's identity is built on these tiny instant signals.

2. **Discrimination is more important than fidelity.** A wall puff and a blood splatter don't need to be photoreal — they just need to look *different*. The player's brain reads "grey vs. red" instantly and updates their mental model of what they hit. A top-down 2D prototype can satisfy this with minimal art (one gray particle, one red particle).

3. **Effects are short and overlapping.** Almost every visual effect is under half a second. The art of the system is that *short* effects layered together feel substantial, while individual long effects would feel sluggish. The pain animation at 0.17 seconds is a particularly elegant example: too short to feel like a stagger, just long enough to register as a flinch.

4. **The damage tint is cumulative for a reason.** A linear-decay accumulator is the right data structure: it naturally produces strong flashes for big hits (high accumulation) and gentle pulses for small hits (low accumulation), and many small hits chain into a sustained red without needing per-hit logic.

5. **Damage-tiered blood adds free expressiveness.** Selecting blood frame by damage value is a tiny code change but it makes weapons feel different. A pistol producing small drips and a shotgun producing big splatters communicates weapon power purely through visuals.

6. **Effects use the same state-machine framework as enemies.** Puffs, blood, muzzle flashes, and corpses all are state machines with sprite/duration/next-state entries. The same engine that runs enemy AI runs visual effects. This is a very efficient design: if you have a state machine, you have a particle system.

7. **Random duration jitter prevents "marching" effects.** Subtracting 0-3 random ticks from the first frame of effects spawned simultaneously prevents them from animating in lockstep. The cost is one random number per spawn; the benefit is that crowds of effects look organic.

8. **Decoupled flash and weapon layers preserve animation independence.** The muzzle flash being on its own sprite layer means the weapon recoil/recovery animation doesn't have to be re-authored to include flash frames. Each can be tuned independently.

## Visual Feedback Constants Summary

| Effect | Duration | Notes |
|---|---|---|
| Muzzle flash (pistol) | ~0.20 s | Single bright frame |
| Muzzle flash (shotgun) | ~0.20 s | Two-stage fade |
| Muzzle flash (chaingun) | ~0.14 s per shot | Randomized between 2 variants |
| Muzzle flash (rocket) | ~0.43 s | Longer plume |
| Wall puff | ~0.46 s (4 frames) | First frame full-bright; slow rise |
| Blood splatter | ~0.69 s (3 frames) | Frame depends on damage tier |
| Blood (heavy hit, dmg >= 13) | Frame 1 sprite | Largest splatter |
| Blood (medium hit, dmg 9-12) | Frame 2 sprite | Medium spatter |
| Blood (light hit, dmg < 9) | Frame 3 sprite | Small drip |
| Enemy pain (small enemy) | ~0.11 s | Ranged-melee hybrid-tier |
| Enemy pain (basic humanoid) | ~0.17 s | Trooper-tier |
| Enemy pain (larger creature) | ~0.34 s | Floating creature |
| Player damage tint cap | 100 (~2.86 s max fade) | Cumulative, linear decay |
| Player damage tint levels | 8 | Discrete red palette ramp |
| Pickup tint cap | ~6 per pickup, 4 levels | Yellow ramp |
| Normal death animation | ~0.71 s + permanent corpse | 5 frames * 5 ticks |
| Gib death animation | ~1.29 s + permanent corpse | 9 frames * 5 ticks |
| Death first-frame jitter | -0 to -3 ticks (random) | Anti-lockstep |
| Solid-loss point in death | ~0.29 s in (frame 3) | Becomes walk-through |
| Corpse height | original / 4 | Walkable obstacle |

## Implementation Notes for Top-Down 2D

The reference's effect system is straightforward to port:

- **Particle / effect entity**: Use the same entity system as enemies, with a "lifetime" countdown component. When lifetime reaches zero, despawn.
- **Muzzle flash**: Spawn at player's position offset slightly forward in firing direction. Use a bright color (yellow/white). 100-200 ms lifetime. Optionally tint world brightness during flash.
- **Wall puff**: Spawn at hitscan endpoint when ray hits wall. Gray particle. ~450 ms lifetime. Slight upward (or "scale-down") drift.
- **Blood splash**: Spawn at hitscan endpoint when ray hits enemy. Red particle. Size scaled by damage value (3 tiers minimum: small/medium/large). ~700 ms lifetime.
- **Enemy pain flash**: When enemy takes damage and pain check passes, briefly tint enemy sprite white or scale up by 10% for 100-200 ms.
- **Player damage overlay**: Maintain a "damage count" float in player state. On damage, add the damage value (capped). Each frame, decay by ~30/sec. Render a translucent red rectangle over the play area with alpha proportional to count/cap.
- **Death animation**: A short fade or slump (3-5 frames at 60 FPS). Transition to a darker, smaller "corpse" sprite that persists.
- **Anti-lockstep jitter**: Add 0-3 frame random delay to spawn duration for simultaneous effects.

## Open Questions

- How does the reference handle effect culling for very long fights? (Are there caps on simultaneous puffs/blood entities?)
- Does the screen damage tint interact with other palette-based effects (radiation suit green tint, invulnerability inverse tint), and if so, what's the priority?
- Are there any visual feedback differences between the player taking damage from melee vs. hitscan vs. projectile attacks? (The damage count appears uniform.)
- Is there any visual feedback for "near miss" (a shot passing close by without hitting)? Sound only, or visual too?
- How do player-on-player damage effects (multiplayer / friendly fire) differ visually from enemy-inflicted damage?
- For top-down 2D specifically: is a screen-space damage tint disorienting when the camera is overhead? Would a vignette/border tint feel more appropriate?
