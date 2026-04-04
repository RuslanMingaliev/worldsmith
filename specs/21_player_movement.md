# Player Movement Specification

## Overview

This specification defines the player movement system for the retro shooter. Movement uses a momentum-based physics model where input applies thrust to velocity, which decays through friction. This creates movement that feels responsive on input but weighty in execution.

## Design Goals

- **Immediate responsiveness**: Input affects movement instantly
- **Momentum-based weight**: Players slide to a stop rather than halting instantly
- **Precise aiming**: Turning has no momentum, allowing crisp aim control
- **Commitment in air**: No air control creates tactical depth for jumps
- **Smooth navigation**: Wall sliding and auto step-up prevent movement frustration

## State

### Position
- **Type:** 2D or 3D coordinates (x, y, z)
- **Initial:** Set by level spawn point
- **Constraints:** Must remain within level bounds and not inside solid geometry

### Velocity (Momentum)
- **Type:** 2D vector (x, y components)
- **Initial:** Zero
- **Constraints:** Each component independently clamped to maximum speed
- **Update:** Modified by thrust (input) and friction each tick

### Facing Angle
- **Type:** Angle (0-360 degrees or equivalent)
- **Initial:** Set by level spawn point
- **Constraints:** Wraps at full circle
- **Update:** Modified directly by turn input (no momentum)

### Ground State
- **Type:** Boolean (on ground / airborne)
- **Derived from:** Position z compared to floor height
- **Affects:** Whether thrust and friction apply

### View Height
- **Type:** Vertical offset for camera
- **Initial:** Standing eye height (normalized: ~41 units)
- **Transitions:** Smoothly interpolates during step-up and landing

## Behaviors

### Thrust (Acceleration)

**Trigger:** Player holds forward, backward, or strafe input while on ground

**Effect:** Velocity is increased in the direction of movement

**Rules:**
- Forward/backward thrust is applied along the player's facing angle
- Strafe thrust is applied perpendicular to facing angle (90 degrees offset)
- Thrust is instantaneous (added directly to velocity, no gradual acceleration)
- Thrust only applies when the player is on the ground
- Thrust magnitude is proportional to input strength

**Constants:**
| Name | Value | Description |
|------|-------|-------------|
| THRUST_FACTOR | 2048 | Input-to-velocity conversion multiplier |

### Friction (Deceleration)

**Trigger:** Each tick while player is on the ground

**Effect:** Velocity decays toward zero

**Rules:**
- Each tick, velocity is multiplied by the friction coefficient
- This creates exponential decay (velocity approaches zero asymptotically)
- When velocity magnitude drops below stop threshold AND no movement input is held, velocity is set to exactly zero
- Friction does NOT apply while airborne

**Constants:**
| Name | Value | Description |
|------|-------|-------------|
| FRICTION | 0.906 | Per-tick velocity preservation (~91%) |
| STOP_THRESHOLD | 0.0625 | Velocity below which player stops completely (as fraction of max) |

**Feel:** At typical tick rates, the player loses ~95% of speed in one second without input. This creates a noticeable but not frustrating "slide."

### Speed Limiting

**Trigger:** Each tick, after thrust is applied

**Effect:** Velocity is clamped to maximum

**Rules:**
- X and Y velocity components are independently clamped to +/- maximum
- Clamping happens before position is updated
- This prevents infinite acceleration and speed exploits

**Constants:**
| Name | Value | Description |
|------|-------|-------------|
| MAX_SPEED | 30.0 | Maximum velocity per axis (units per tick) |

### Turning

**Trigger:** Player holds left or right turn input

**Effect:** Facing angle changes immediately

**Rules:**
- Turn input is added directly to facing angle (no momentum or acceleration)
- Turning works regardless of ground state (can turn while airborne)
- Turn rate is proportional to input magnitude
- Angle wraps at full circle (no discontinuity)

**Feel:** Turning is crisp and immediate, contrasting with the momentum-based movement. This allows precise aiming.

### Ground Check

**Trigger:** Each tick

**Effect:** Determines whether thrust and friction apply

**Rules:**
- Player is "on ground" when: position.z <= floor height at current (x, y)
- When airborne, movement input is ignored (no air control)
- When airborne, friction does not apply (velocity preserved)

**Feel:** Jumping commits the player to their current trajectory, adding risk/reward to aerial movement.

### Wall Collision and Sliding

**Trigger:** Movement would place player inside solid geometry

**Effect:** Player slides along wall instead of stopping

**Rules:**
- When collision is detected, calculate the wall's angle
- Project the player's velocity onto the wall direction
- Move the player along the wall using the projected velocity
- Attempt sliding up to 3 times per tick to handle corners
- If all attempts fail, player stops

**Feel:** Wall sliding makes navigation forgiving. Players can run along walls at glancing angles without getting stuck.

### Step-Up (Auto-Climb)

**Trigger:** Player moves toward a height change within step range

**Effect:** Player automatically climbs small ledges

**Rules:**
- Maximum step height: 24 units
- Height differences greater than max step block movement
- When stepping up, view height smoothly interpolates to new position
- View interpolation speed: approximately 8 ticks to reach target

**Constants:**
| Name | Value | Description |
|------|-------|-------------|
| MAX_STEP_HEIGHT | 24.0 | Maximum height that can be auto-climbed |

**Feel:** Smooth step-up allows fluid navigation of stairs and small obstacles without interrupting flow.

### Gravity and Falling

**Trigger:** Player position.z > floor height

**Effect:** Player accelerates downward

**Rules:**
- Gravity is applied each tick when airborne
- Gravity adds to negative z velocity (downward)
- First tick of falling applies double gravity (initial impulse)
- On landing (z reaches floor), z velocity is zeroed
- Hard landings (high downward velocity) trigger view "squat" effect

**Constants:**
| Name | Value | Description |
|------|-------|-------------|
| GRAVITY | 1.0 | Downward acceleration per tick |
| HARD_LANDING_THRESHOLD | 8.0 | Downward velocity that triggers squat |
| VIEW_HEIGHT | 41.0 | Normal eye height above feet |
| MIN_VIEW_HEIGHT | 20.5 | Minimum view height during squat |

**Feel:** Gravity feels moderate, not floaty but not heavy. Landing squat provides feedback for big drops.

### View Bobbing

**Trigger:** Player is moving on the ground

**Effect:** Camera oscillates vertically to simulate walking/running

**Rules:**
- Bob amplitude is proportional to movement speed (velocity magnitude squared)
- Bob oscillates using a sine wave tied to game time
- Bob is capped at maximum amplitude
- Bob frequency: one complete cycle every ~20 ticks (~0.57 seconds at 35 ticks/sec)
- Bob only applies while on ground and moving

**Constants:**
| Name | Value | Description |
|------|-------|-------------|
| MAX_BOB | 16.0 | Maximum view bob amplitude (in units) |
| BOB_PERIOD | 20 | Ticks per complete bob cycle |

**Feel:** View bob provides kinesthetic feedback reinforcing movement. Faster movement = more pronounced bob. The ~1.75 Hz frequency matches a running cadence.

## Interactions

### With Combat System
- Player can fire weapons while moving
- Movement does not affect weapon accuracy (no spread penalty)
- Taking damage does not interrupt movement directly

### With Level Geometry
- Walls block movement but allow sliding
- Floors define ground plane for step-up
- Ceilings limit upward movement (if jumping is implemented)

### With Game Loop
- Movement is processed once per tick
- Order: input -> thrust -> friction -> collision -> position update
- View bob and height are calculated after position update

## Constraints

### Invariants
- Player position must never be inside solid geometry
- Velocity components must never exceed MAX_SPEED
- View height must be between MIN_VIEW_HEIGHT and VIEW_HEIGHT + MAX_BOB

### Current Simplifications
- No jumping (z-axis movement reserved for future)
- No variable friction by floor type
- No special movement states (teleport recovery, etc.)
- View bob is optional enhancement

### Implementation Notes
- Constants use normalized units, not fixed-point
- Implementations may use fixed-point, float, or integer math as appropriate
- Tick rate affects feel; constants assume ~35 ticks/second but should scale

## Test Scenarios

### Basic Movement
1. Pressing forward adds velocity in facing direction
2. Releasing all input causes gradual deceleration to stop
3. Velocity cannot exceed maximum in any axis
4. Turning changes facing angle without affecting velocity direction

### Friction Behavior
1. With no input, velocity decays to zero over approximately 1 second
2. Below stop threshold with no input, velocity becomes exactly zero
3. Continuous input maintains near-constant speed (thrust balances friction)

### Collision
1. Walking into a wall stops forward movement
2. Walking into a wall at an angle causes sliding
3. Cannot pass through walls regardless of speed

### Ground State
1. Thrust only applies when on ground
2. Friction only applies when on ground
3. Movement input is ignored when airborne (future: when jumping is added)
