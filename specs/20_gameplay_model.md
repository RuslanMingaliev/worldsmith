# Gameplay Model

## Intent

The generated prototype should feel like a minimal retro shooter vertical slice, not like a generic tech demo.

The player should perceive:
- immediate responsiveness
- pressure while moving
- a clear hostile space
- simple combat
- a clear objective

## Core Gameplay Loop

explore -> encounter threat -> attack or evade -> survive -> reach exit

## Required Gameplay Features

### Player Movement
The player must be able to:
- move forward and backward
- turn left and right
- strafe left and right

Movement uses a momentum-based physics model. See [21_player_movement.md](21_player_movement.md) for detailed mechanics.

### World Collision
The player must not be able to walk through walls.

### Combat
The player must have:
- one basic ranged attack or one simple shooting mechanic

### Enemy
At least one enemy archetype must exist.

The enemy must:
- update every frame or tick
- react to the player in some simple way
- threaten the player through movement, contact, or attack

### Level
The level must:
- contain walls and walkable space
- contain a player spawn
- contain at least one enemy
- contain at least one clear objective or exit

## Deferred Features

- multiple weapons
- advanced enemy coordination
- cutscenes
- inventory UI
- dialogue
- stealth systems
- multiplayer
- procedural generation
