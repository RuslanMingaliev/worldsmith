# Finding: Player Movement

## Summary

Player movement in a classic retro shooter uses a momentum-based physics model where input adds thrust to velocity, which then decays through friction. Movement feels weighty and responsive because thrust is applied instantly but stopping requires the friction system to drain momentum over several frames. The key distinction is that players cannot control movement while airborne.

## Observed Mechanics

### Thrust (Acceleration)

- **Behavior**: When the player presses forward/backward or strafe keys, thrust is applied in the corresponding direction based on the player's facing angle. Thrust is instantaneous — it directly adds to the existing momentum.
- **Rules**:
  - Thrust only applies when the player is on the ground
  - Forward movement applies thrust along the facing angle
  - Strafe movement applies thrust perpendicular to facing angle (90 degrees offset)
  - Thrust magnitude is proportional to input value
- **Feel**: Movement starts immediately but builds momentum. The instant thrust application makes the game feel responsive.

### Friction (Deceleration)

- **Behavior**: Each frame, horizontal momentum is multiplied by a friction coefficient, causing exponential decay toward zero. When momentum drops below a threshold and no input is held, the player stops completely.
- **Rules**:
  - Friction only applies when on the ground
  - Friction is NOT applied to missiles or airborne objects
  - If momentum is below stop threshold AND no movement input, momentum is set to zero
  - Otherwise, momentum is multiplied by friction coefficient
- **Constants**:
  - Friction coefficient: approximately 0.906 (about 91% preservation per tick)
  - Stop threshold: small value below which player stops completely
- **Feel**: The ~91% friction coefficient creates a noticeable "slide" when releasing keys — the player doesn't stop instantly but decelerates smoothly over roughly 10-15 frames. This gives movement a satisfying weight without feeling sluggish.

### Maximum Speed

- **Behavior**: Velocity is clamped to a maximum value each frame, preventing infinite acceleration.
- **Rules**:
  - Both X and Y momentum are independently clamped to maximum
  - Clamping happens before movement is processed
- **Constants**:
  - Maximum velocity: approximately 30 units per tick per axis
- **Feel**: Players can reach top speed quickly but cannot exceed it, even with continuous input. The cap prevents exploits while maintaining fast-paced gameplay.

### Turning

- **Behavior**: Turning is handled separately from movement and modifies the player's facing angle directly. Turn commands accumulate into the angle without acceleration or inertia.
- **Rules**:
  - Turn input is added directly to the player's angle
  - Turn is applied every frame regardless of ground state
  - No friction or momentum on turning — it's instant
- **Feel**: Turning is crisp and immediate with no momentum. This creates precise aiming control that contrasts with the momentum-based movement.

### Ground Check

- **Behavior**: The player can only apply thrust when standing on a surface.
- **Rules**:
  - Ground is determined by comparing player Z position to floor height
  - When airborne, movement input is ignored (no air control)
  - Friction does not apply in the air
- **Feel**: Jumping commits the player to their current trajectory. This creates risk/reward in combat situations and differentiates ground play from aerial situations.

### View Bobbing

- **Behavior**: The camera oscillates vertically while moving, simulating head movement during walking/running.
- **Rules**:
  - Bob amount is proportional to movement speed (velocity magnitude squared)
  - Bob oscillates using a sine wave tied to game time
  - Bob is capped at maximum amplitude
  - Bob frequency: approximately 1.75 Hz (matches a running cadence)
- **Feel**: View bob provides kinesthetic feedback that reinforces movement. Faster movement = more pronounced bob.

### Step-Up

- **Behavior**: Players can automatically climb over small height differences without jumping.
- **Rules**:
  - Maximum step height: approximately 24 units
  - Steps higher than this block movement
  - When stepping up, the view smoothly transitions to the new height
- **Feel**: Smooth step-up allows fluid navigation of stairs and small obstacles without interrupting flow. The view interpolation prevents jarring camera jumps.

### Collision and Sliding

- **Behavior**: When the player collides with a wall at an angle, they slide along it rather than stopping dead.
- **Rules**:
  - On collision, the game calculates the wall angle
  - Movement is projected onto the wall direction
  - Remaining momentum carries the player along the wall
  - Multiple slide attempts are made per movement tick
- **Feel**: Wall sliding makes navigation forgiving and maintains game flow. Players can run along walls at glancing angles without getting stuck.

### Vertical Movement (Z-axis)

- **Behavior**: Gravity pulls the player down when airborne; landing on surfaces stops vertical momentum.
- **Rules**:
  - Gravity is applied each tick when airborne
  - First tick of falling may apply stronger impulse
  - Hard landings (high downward velocity) trigger a view "squat" effect
- **Feel**: Gravity feels moderate — not floaty but not too heavy. The landing squat provides satisfying feedback for big drops.

## Key Insights

1. **Momentum creates weight without sluggishness**: The combination of instant thrust and gradual friction decay makes movement feel responsive on input but weighty in execution. This is a crucial feel element.

2. **No air control is a design choice**: Unlike many modern FPS games, once airborne the player is committed to their trajectory. This adds strategic depth to jump timing.

3. **Turning is decoupled from movement physics**: While movement has momentum, turning does not. This asymmetry gives precise aim control while maintaining movement inertia.

4. **Friction coefficient of ~91% per tick is the sweet spot**: At typical tick rates, the player loses about 95% of speed in one second of no input — enough to feel the slide but not so much that it's frustrating.

5. **Wall sliding prevents frustration**: The multi-attempt slide system means players almost never get stuck on geometry at glancing angles.

6. **View bob frequency matches running cadence**: The ~1.75 Hz bob creates a subconscious connection to physical running.

## Movement Constants Summary

| Constant | Approximate Value | Meaning |
|----------|-------------------|---------|
| Friction | 0.906 (~91%) | Per-tick velocity preservation |
| Stop threshold | ~0.06 | Fraction of max speed for full stop |
| Max speed | 30 units/tick | Maximum velocity per axis |
| Gravity | 1 unit/tick² | Downward acceleration |
| View height | 41 units | Player eye height |
| Max bob | 16 units | Maximum view bob amplitude |
| Max step | 24 units | Maximum auto-climb height |

## Open Questions

- How does the "reactiontime" system work for teleport protection? (Movement is blocked briefly after teleporting)
- What is the relationship between map units and real-world scale? (Affects perception of speed)
- How do special weapon states affect movement feel?
- What is the exact behavior when friction differs by floor type? (Some floors may have different friction)
