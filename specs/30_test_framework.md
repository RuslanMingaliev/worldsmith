# Test Framework (Autopilot)

## Intent

The game must be testable without human input. An automated bot interprets declarative YAML scenarios, executes objectives against the game simulation, and checks assertions on the resulting state.

This enables:
- Regression testing after regeneration
- Proof that game mechanics work as specified
- Headless CI validation

## Architecture

The autopilot module runs inside the game binary as a test harness. It reuses the same `GameState` and `InputState` as the real game loop, but replaces human input with bot decisions.

```
YAML scenario → Parser → Objectives + Assertions
                              ↓
                         Bot (decides InputState each frame)
                              ↓
                         GameState.update() loop
                              ↓
                         Assertions checked → Pass/Fail
```

## Scenario Format

Scenarios are YAML files in `tests/` organized by area:

```yaml
scenario: scenario_name
description: Human-readable description

objectives:
  - kill: enemy
  - reach: exit

assertions:
  - player.alive: true
  - enemy.alive: false
```

## Objectives

Objectives are executed sequentially. Each must complete before the next begins.

| Objective | Behavior |
|-----------|----------|
| `kill: <target>` | Navigate to target, attack until dead |
| `reach: <target>` | Navigate to target position (distance < 1.0) |
| `approach: <target>` | Get within weapon range of target (distance < 8.0) |
| `wait: <frames>` | Do nothing for N frames |

### Targets

| Name | Resolves to |
|------|-------------|
| `enemy` | Current enemy position |
| `exit` | Level exit position |
| `spawn` | Player spawn position |

## Assertions

Checked after the simulation ends (all objectives complete or timeout).

### Syntax

- `field: value` — exact match (bool or number)
- `field: "> N"` — greater than
- `field: "< N"` — less than
- `field: ">= N"` — greater or equal
- `field: "<= N"` — less or equal

### Available Fields

| Field | Type | Description |
|-------|------|-------------|
| `player.alive` | bool | Player is alive |
| `player.health` | number | Player health (0-100) |
| `player.position.x` | number | Player X coordinate |
| `player.position.y` | number | Player Y coordinate |
| `enemy.alive` | bool | Enemy is alive |
| `enemy.health` | number | Enemy health |
| `game.won` | bool | Player reached exit |
| `game.running` | bool | Game is still running |
| `game.frames` | number | Frames elapsed |

## Bot Behavior

The bot is a simple agent that:
1. Turns toward the current objective target
2. Moves forward when roughly facing the target
3. Fires when in weapon range and aligned with enemy
4. Detects stuck situations and strafes to unstick

The bot does not need to be smart — it needs to be reliable enough to complete simple scenarios. Complex AI is not a goal.

### Stuck Detection

If the bot's position hasn't changed for 30 frames, it begins strafing. After 60 frames stuck, it reverses strafe direction. This handles simple obstacle situations.

## Execution Rules

- Each scenario runs with fresh `GameState`
- Simulation runs at 60 FPS (FRAME_TIME = 1/60)
- Maximum duration: 3600 frames (60 seconds)
- If max frames exceeded, assertions are checked against current state
- Scenarios are independent — no shared state between tests

## Dependencies

- `game_loop` (GameState)
- `input_controller` (InputState)
- `level_data` (Vec2, positions)
- `player_state` (Player)
- `enemy_logic` (Enemy)
- `weapon_system` (Weapon, indirectly via GameState)
- `serde`, `serde_yaml` (dev-dependencies, for YAML parsing)
