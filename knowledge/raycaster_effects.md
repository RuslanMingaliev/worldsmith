# Finding: First-Person Effects in a Column-Based Renderer

## Summary

In a first-person column renderer, weapon-firing visual feedback splits into four distinct surfaces: (1) a **muzzle flash** drawn as a separate full-bright sprite layered over the held-weapon view sprite, (2) a global **extra-light bias** that brightens every world-shading lookup for the duration of the flash, simulating muzzle illumination, (3) **impact puffs** at the trace endpoint, drawn as world-space billboards using the same sprite pipeline as enemies and pickups, and (4) a brief **brightness pulse on walls and sprites** as a side effect of (2). Critically, the reference engine does **NOT** render any visible projectile-trail line ("tracer") between the shooter and the impact point for hitscan weapons; the visible feedback is entirely flash + light bias + impact billboard. A separate held-weapon view sprite ("player sprite") is layered on top of the world after walls/floors/ceilings/sprites have been drawn, with its own coordinate system anchored to the screen rather than the world.

## Observed Mechanics

### Held-Weapon View Sprite ("Player Sprite")

- **Behavior**: The held weapon is drawn as a screen-anchored sprite, separate from any world-space sprite system. It uses its own scale factor (independent of distance — the gun is always the same size on screen) and its own (sx, sy) coordinates measured in a fictitious 320×200 reference space. Two such sprite slots exist per player: one for the weapon body, one for the muzzle flash overlay.
- **Rules**:
  - Each per-player sprite slot has its own state machine that ticks independently of the world. The "weapon body" slot drives the firing/idle/lower/raise animation. The "flash" slot is empty most of the time and is set to a flash sprite for a few ticks when a shot fires.
  - Both slots are projected with the same per-player sprite scale (a fixed scale, not a per-frame distance-based one). The weapon body and flash thus share screen position; the flash is drawn after the body so it appears layered on top.
  - The flash sprite is drawn at full brightness (it bypasses the distance-attenuated colormap) so it appears equally bright regardless of the surrounding sector light.
  - Both slots clip to the rendered view area (the framebuffer above the status bar). They do not interact with the per-column wall-depth array — they always draw on top.
  - The weapon body sprite is offset slightly each frame by a "bob" function based on player movement speed, producing the characteristic walking sway. The flash slot does NOT bob — its position is fixed at a per-state coordinate so consecutive shots are stable visual anchors.
- **Constants**:
  - Resting height of the weapon body: a fixed offset from the top of the reference 200-row vertical space.
  - Lowered height (during weapon-switch): another fixed offset further down.
  - Raise/lower speed: 6 reference-units per tick (so a full lower or raise takes ~16 ticks at 35 ticks/sec ≈ 0.46 s).
  - Bob amplitude is proportional to player speed; the bob function is a simple sine table lookup keyed on world time.
- **Feel**: Layering the flash on its own sprite slot is the simplest possible way to get a "muzzle flash overlay" without disrupting the weapon's main animation. The weapon can continue its recoil/recovery while the flash flicker plays on top, which is what makes the firing animation feel layered rather than monolithic.

### Muzzle Flash Sprite (View-Space Overlay)

- **Behavior**: When a hitscan weapon fires, its fire action sets the per-player flash slot to a weapon-specific flash sprite for a fixed number of ticks. The flash sprite is drawn full-bright over the weapon body, then auto-transitions to a "light done" state that resets all the auxiliary flash effects (extra-light, etc.).
- **Rules**:
  - The flash sprite is a single short-lived state for simple weapons (small handgun: one frame, ~7 ticks ≈ 0.20 s) or a two-frame sequence for higher-yield weapons (the second frame is dimmer / a slightly later phase of the flash).
  - The flash state's "next state" auto-points to either a second flash frame or directly to the "light done" reset state, so the auxiliary effects auto-clean-up without any explicit timer in the firing code.
  - Multi-shot weapons (rapid-fire chain weapon) randomize between two near-identical flash variants per shot so consecutive frames don't stutter.
  - The first flash frame typically calls a "set extra light to 1" action; the second flash frame (if any) calls a "set extra light to 2" action; the terminal "done" state calls "set extra light to 0".
  - Burst-fire weapons (rapid hitscan repeater) use the lower extra-light setting (1) on every flash. Big single-shot weapons (slug-thrower, energy launcher) use the higher setting (2).
- **Constants** (at 35 ticks/sec):
  - Small handgun flash: 1 frame, 7 ticks (~0.20 s), extra-light 1.
  - Single-barrel hitscan-spread: 2 frames at 4 + 3 ticks (~0.20 s), extra-light steps 1 → 2.
  - Double-barrel hitscan-spread: 2 frames at 5 + 4 ticks (~0.26 s), extra-light steps 1 → 2.
  - Rapid-fire chain weapon: 1 frame at 5 ticks (~0.14 s), extra-light 1, randomized variant.
  - High-energy launcher: 4 frames at 3+4+4+4 ticks (~0.43 s, longer for the launch plume), extra-light steps 1 → 2.
  - Energy beam: 1 frame at 4 ticks (~0.11 s), extra-light 1, randomized variant.
- **Feel**: The flash is short — typically under a quarter second — but unmistakable. Because it draws at full brightness, it pops against any dim sector lighting. Because it's on its own sprite slot, it can be triggered repeatedly without disrupting the weapon body's animation timing.

### Extra-Light Bias (Global Brightness Pulse)

- **Behavior**: A single integer counter, set by the flash state's action function and reset by a follow-up state, biases every world-shading lookup upward by 1 or 2 steps for the duration of the flash. The result is that during a shot, the entire visible scene — walls, floors, ceilings, and entity sprites — appears one or two brightness ramp-steps lighter, simulating muzzle illumination of the room.
- **Rules**:
  - The world's light-table is structured as a 16-step ramp: each sector has a 0–255 brightness value that is right-shifted by 4 bits to yield a 0–15 ramp index. The renderer adds the extra-light counter to this index before clamping into the table.
  - The bias is applied identically in three places: wall-segment shading, flat (floor/ceiling) shading, and entity-sprite shading. A single counter drives all three.
  - The bias is **additive on the ramp index, not multiplicative on color**. One bias step = one shade brighter on the precomputed ramp. The effect is uniform across the screen rather than concentrated at the gun's screen position.
  - Because the reference uses a precomputed colormap ramp, the visual effect of the bias is roughly "everything gets one or two ramp steps lighter" — equivalent to ~6–12% brighter in linear-light terms (16-step ramp ≈ 6.25%/step), but applied as a palette swap rather than a multiplicative tint.
  - Sprites with the full-bright flag (the muzzle flash sprite itself, the first frame of the impact puff) are exempt — they always use the brightest ramp entry regardless of the bias, so the bias only affects "normally lit" surfaces.
  - On player respawn / level start, the counter is force-reset to 0 (gun flashes are cancelled across map transitions).
- **Constants**:
  - Counter range: 0, 1, or 2.
  - Bias semantics: index += counter, then clamp to [0, 15] before lookup.
  - Light-ramp resolution: 16 steps (so each unit of bias is ~6.25% in linear-light terms).
- **Feel**: The bias is the difference between a flash that looks like a sprite-slap on top of the screen and a flash that looks like *light coming out of the gun*. Without it, the gun would feel decoupled from the world. With it, the world briefly acknowledges that the muzzle is a real light source. The effect is short enough (matching the flash sprite's lifetime) that it never obscures the underlying sector lighting design.

### Hitscan Trace Endpoint: NO Tracer Line

- **Behavior**: When the player fires a hitscan weapon, the engine does **not** draw any visible line, beam, or projectile path between the muzzle and the impact point. The weapon's effect is reduced to: (a) the view-space muzzle flash, (b) the global extra-light pulse, (c) a small billboard at the impact endpoint (puff or blood). The line itself is invisible.
- **Rules**:
  - The fire action calls a line-attack helper that immediately walks the world structure to find the first solid surface or shootable target along the firing ray.
  - At the resulting endpoint, a single billboard entity is spawned. There is no "trail" entity, no per-segment particle, no line-drawing call.
  - For continuous-fire weapons (rapid-fire chain, energy beam), each shot spawns its own independent flash + endpoint billboard. There is no temporal smoothing; each shot is discrete.
  - Only "missile-class" weapons (a slow projectile that visibly travels) involve any kind of in-flight visual — and those are not tracers but full mobile entities with their own sprites and physics. The hitscan family has no equivalent.
- **Why this matters for a raycaster reimplementation**:
  - A raycaster CAN cheaply add a tracer line by projecting two world-space points (muzzle position, hit endpoint), perspective-projecting them into screen space, and drawing a 1-or-2-pixel-wide line with a per-column z-buffer test. This is a generation-default visual: it does not appear in the reference, so it should be flagged as a Generation default in the spec rather than cited as reference-backed.
  - If a tracer is added, its visibility window should match the muzzle flash's (a few ticks) so it visually pairs with the firing event.
- **Feel** (reference behavior): Without a tracer, the player reads the shot as "instant teleporting damage from gun to puff", which is exactly what hitscan is. The puff at the wall is the only spatial cue that a shot landed somewhere out there. Adding a tracer would make a hitscan weapon visually closer to a slow projectile, which is a deliberate genre-style choice rather than a faithful recreation.

### Wall-Hit Impact Puff (World-Space Billboard)

- **Behavior**: At the trace endpoint against a wall, a small billboard entity is spawned. It animates over a fixed lifetime, drifts upward slowly, and has a full-bright first frame so it visually pops against the wall behind it. It uses the same sprite-projection pipeline as enemies and pickups, so it z-buffers against walls correctly.
- **Rules**:
  - Spawned a few units short of the actual hit point (so the sprite doesn't z-fight or clip into the wall).
  - Random vertical jitter at spawn: about ±32 fractional units up or down, so consecutive hits don't stack visually.
  - Initial upward velocity of 1 unit per tick (slow rise).
  - Lifetime: 4 frames at 4 ticks each = 16 ticks total (~0.46 s at 35 ticks/sec).
  - First frame uses the full-bright flag: drawn at the brightest colormap regardless of distance/sector light. Subsequent frames use normal distance-attenuated shading, so the puff visually "settles into" the surrounding lighting as it fades.
  - Initial duration jitter: subtract 0–3 random ticks from the first frame's duration so puffs spawned the same tick don't sync.
  - Flagged "no blockmap" and "no gravity": the puff doesn't collide with anything and doesn't fall.
  - Melee impacts (e.g., punch) skip the bright first frame and start at the second frame instead — a punch on stone should not "spark."
  - For raycaster rendering: the puff is projected through the same back-to-front sprite pass as enemies/corpses/pickups, with per-column z-buffer test against the wall-depth array written by the wall pass. Sprites occluded by closer walls are clipped out.
- **Constants**:
  - Sprite radius / height: small (~20 / ~16 fractional units in the reference's coordinate system, i.e., much smaller than an enemy).
  - Drift velocity: 1 unit per tick upward.
  - Lifetime: 16 ticks (~0.46 s).
  - First frame: full-bright; subsequent frames: distance-attenuated.
  - Vertical jitter at spawn: ±~32 fractional units.
- **Feel**: The puff is a critical "did I hit" signal. The full-bright first frame makes the moment of impact visible even in dim sectors. The slow upward drift implies smoke/dust dispersion. The four-frame fade-out is just long enough to read as "a thing happened there" without lingering enough to clutter the screen during sustained fire.

### Effect Pass Ordering (Per-Frame Layering)

- **Behavior**: Each frame, the renderer composes the scene in a fixed order so the effects layer correctly without explicit z-sorting between layers.
- **Rules** (in draw order, back to front):
  1. **Walls + floor + ceiling**: column-by-column wall projection plus floor/ceiling spans. Writes the per-column wall-depth array. Wall and flat shading lookups apply the **extra-light bias** at this step (so during a flash, walls are brighter).
  2. **World-space sprites**: enemies, corpses, blood splats, pickups, **impact puffs** — all back-to-front, all clipped per-column against the wall-depth array. Sprite shading lookups also apply the **extra-light bias**, except sprites with the full-bright flag set, which always use the brightest ramp entry regardless of bias.
  3. **Held-weapon view sprite (body)**: drawn after the world, anchored to screen coordinates rather than world coordinates. Always on top of the world; never z-tested.
  4. **Muzzle flash view sprite (overlay)**: drawn after the weapon body so it visually overlays the gun. Full-bright (uses brightest ramp entry).
  5. **HUD / status bar / damage tint / pickup tint**: any post-world overlay, applied last.
- **Constraints**:
  - The flash sprite and the puff first frame both use full-bright shading; this is the only place they "ignore" the extra-light bias.
  - The bias is read-once-per-frame at the start of the frame's wall pass (the renderer caches the player's extra-light counter into a frame-scoped shading offset). Mid-frame ticks of the flash state are not visible until the next frame.
- **Feel**: The fixed order is what makes the flash look like it's *attached to the gun* rather than floating in the world. The world brightens, the impact billboard appears in-world, but the flash itself is fixed to the screen. The combination reads as "muzzle flash on the gun is illuminating the room I'm looking at."

### Brief Brightness Pulse on Walls (Extra-Light, Restated for Implementers)

- **Behavior**: This is the wall-and-sprite-side observable effect of the extra-light bias above. During the flash, every wall, floor, ceiling, and non-full-bright sprite renders one or two ramp steps brighter than its baseline sector lighting; when the flash ends, they snap back.
- **Rules**:
  - The pulse is **synchronized with the flash sprite's lifetime**: it begins on the same tick the flash sprite is set, and ends on the same tick the "light done" state runs.
  - The pulse is **per-shot, not per-firing-button-held**. Every individual shot of a rapid-fire weapon retriggers a fresh flash + bias.
  - Stacking is not additive: the bias is *set* (assigned, not incremented) by each flash state's action. Two near-simultaneous flashes do not produce a brighter pulse than one — they produce the same pulse (with the second shot's "set 1" overwriting the first shot's still-active "set 2", potentially briefly).
  - Implementers in a per-channel-color framebuffer (rather than a colormap-ramp framebuffer) can approximate the bias as a per-channel additive boost on every world-shading multiplier, with magnitude calibrated so 1 ramp-step ≈ 6% brighter and 2 ramp-steps ≈ 12% brighter (since the ramp has 16 steps).
  - The pulse should not be implemented as a full-screen overlay rectangle — it must be a shading-time multiplier, otherwise full-bright sprites (the flash itself, puff first frames) would be incorrectly tinted along with the rest of the scene.
- **Constants**:
  - Bias values: 1 (small/rapid weapons), 2 (heavy/slow weapons).
  - Ramp resolution: 16 steps (so 1 step ≈ 6.25% brighter, 2 steps ≈ 12.5% brighter in linear-light terms).
  - Duration: matches the corresponding flash sprite (typically 7–15 ticks, i.e., 0.20–0.43 s).
- **Feel**: The pulse is what sells the muzzle as a real light source. Without it, the flash is a sprite slapped on the screen; with it, the player perceives the gun as briefly illuminating the room.

## Key Insights

1. **The flash and the puff are independent effects.** The flash is a screen-space view sprite with its own state machine. The puff is a world-space billboard at the trace endpoint. They share the firing tick but are otherwise unrelated. A correct reimplementation must spawn both, not one or the other.

2. **The extra-light bias is the linkage between them.** Without the bias, the flash and the puff feel like two unrelated visuals. The bias makes the *whole world* briefly acknowledge that a shot was fired, tying the flash, the puff, and the surrounding walls into a single moment.

3. **No tracer line in the reference.** Hitscan weapons in the reference do not draw a visible bullet trail. If a raycaster reimplementation adds one, that is a generation-default visual, not a reference-backed one. The minimum reference-faithful set is flash + bias + puff.

4. **Full-bright is a flag, not a tint.** The muzzle flash sprite and the puff's first frame both use the brightest colormap entry directly. They are not tinted versions of darker sprites. In a per-channel-color framebuffer, the equivalent is "skip the distance-attenuation multiply and write at full color." Implementers must handle this as an early-out in the shading pipeline.

5. **The view sprite layer is post-world.** The held weapon and its flash are drawn AFTER the world is composed, in screen space, with no per-column z-buffer interaction. They always appear on top of every wall, sprite, and floor pixel. Never project them into the world.

6. **Effect pass ordering is fixed.** Walls/flats first (writing depth), then world sprites back-to-front (depth-tested), then view sprites (no depth). HUD on top. Mixing these orders produces visible bugs (puffs floating in front of walls, gun being occluded by enemies, etc.).

7. **The bias is per-channel-of-shading-input, not per-pixel.** For a colormap-based renderer it's a ramp index offset. For a per-channel-color renderer it should be applied at the same logical step (during shading-multiplier computation), not as a full-screen post-process.

## Open Questions

- The slice spec calls for **bullet tracer lines**, which the reference does not have. The Architect should decide whether to (a) drop tracers from the spec to match reference faithfulness, (b) keep tracers as a Generation default with `Source: Generation default — no knowledge backing` in the tuning spec, or (c) keep tracers but document them as a deliberate genre-style departure with no claim to reference backing. This knowledge file documents what the reference does; the spec decision is the Architect's.
- Whether the extra-light bias on a per-channel-color framebuffer should be implemented as an additive offset, a multiplicative gain, or a palette LUT swap is a Coder choice. The visual effect at the magnitudes specified (1 or 2 ramp steps ≈ 6%/12%) is roughly the same across all three implementations.
- The reference's puff sprite has 4 frames with distinct artwork. A reimplementation with fewer art assets may collapse to 2 frames (full-bright burst + dim fade) or 1 frame (a fading particle). The lifetime and rise behavior should be preserved regardless of frame count.
- Whether the view-sprite "bob" (movement-driven sway of the held weapon) is in scope for this slice or deferred to a later HUD slice — the bob is per-frame state on the weapon view-sprite, independent of firing effects, but the same view-sprite system carries both.
