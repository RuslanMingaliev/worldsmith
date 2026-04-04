# Tests

Declarative test scenarios for automated game validation.

## Philosophy

Tests are specs. Instead of hardcoded bot logic, we describe:
- **Objectives**: What the bot should achieve (kill, reach, approach)
- **Assertions**: What should be true after execution

The test runner interprets objectives into low-level inputs.

## Structure

```
tests/
├── README.md           # This file
├── level/              # Level completion scenarios
├── combat/             # Combat scenarios
└── player/             # Player mechanics scenarios
```

Organize by **area being tested**, not by complexity.

## Scenario Format

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

## Primitive Objectives

| Objective | Description |
|-----------|-------------|
| `kill: <target>` | Navigate to target and attack until dead |
| `reach: <target>` | Navigate to target position |
| `approach: <target>` | Get within weapon range of target |
| `wait: <frames>` | Do nothing for N frames |

## Assertion Syntax

- `field: value` — exact match
- `field: "> N"` — greater than
- `field: "< N"` — less than
- `field: ">= N"` — greater or equal
- `field: "<= N"` — less or equal

## Available Fields

### player
- `player.alive` — boolean
- `player.health` — integer 0-100
- `player.position.x` — float
- `player.position.y` — float

### enemy
- `enemy.alive` — boolean
- `enemy.health` — integer

### game
- `game.won` — boolean
- `game.frames` — integer (frames elapsed)

## Execution

Scenarios are loaded from `tests/**/*.yaml` and executed headlessly.
Each scenario runs independently with fresh game state.

## Related

- `specs/` — Game specifications (source of truth)
- `evals/` — Success criteria per version
