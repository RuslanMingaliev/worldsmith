# Test Framework (Autopilot)

## Intent

The game must be testable without human input. An automated bot interprets declarative YAML scenarios, executes objectives against the game simulation, and checks assertions on the resulting state.

This enables:
- Regression testing after regeneration
- Proof that game mechanics work as specified
- Headless CI validation

## Architecture

The autopilot module runs inside the game binary. Its primary role is a test harness: scenario-driven `cargo test` runs that drive `GameState` headlessly and check assertions. A secondary role — defined in `specs/35_demo_mode.md` — reuses the same scenario parser and bot-decision logic to drive the live render loop for release demo recording.

The split is:

| API | Available in | Purpose |
|-----|--------------|---------|
| `parse_scenario`, `Scenario`, `Objective`, `BotState`, `BotProgress`, `bot_step` | Always (release + test) | Per-frame primitives; consumed by `main.rs` in `--autopilot` mode and by the test runner. |
| `run_scenario`, `ScenarioResult`, `#[test] run_all_scenarios` | `#[cfg(test)]` only | Batch test-runner that iterates `tests/**/*.yaml` and asserts. |

Both code paths reuse the same `GameState` and `InputState` as the real game loop and replace human input with bot decisions.

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
level: local_chase_obstacle    # OPTIONAL — see specs/15. Absent = use default level.

objectives:
  - kill: enemy
  - reach: exit

assertions:
  - player.alive: true
  - enemy.alive: false
```

The `level:` field is optional. When present, it names a `DemoLevelKind` variant in `snake_case` form (currently only `local_chase_obstacle`); `main.rs` calls `level_generator::build(kind)` instead of `level_data::build_default()` to construct the scenario's level. When absent or null, the runtime uses the default level. See [`15_level_generator.md`](15_level_generator.md) for the catalog of demo levels and the layout details. Existing fixtures (`tests/combat/kill_enemy.yaml`, `tests/level/{complete_level,reach_exit,scavenge_run}.yaml`) omit the field and continue to use the default level.

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
| `enemy` | First alive enemy position; falls back to first enemy's last position, then to `exit`, if no enemies are alive. |
| `exit` | Level exit position |
| `spawn` | Player spawn position |
| `pickup_health` | First active health pickup position (specs/60). Falls back to player's current position when no active health pickup remains, so a `reach: pickup_health` objective trivially completes once all health pickups are consumed. **Partial drift**: current code in `resolve_pos_target` uses `find(kind == Health)` without filtering `active`, so a consumed (inactive) pickup's position is still returned instead of falling back to the player's position. |
| `pickup_ammo` | First active ammo pickup position (specs/60). Same fallback rule as `pickup_health`. Same partial drift as above. |

The fallback semantics for pickup targets are deliberate: a scavenge-style scenario like `reach: pickup_health → reach: pickup_ammo → reach: exit` should not stall when a pickup is missing or already consumed — it should treat that objective as already satisfied and move on. The `active` filter and fallback are not yet enforced in code (flagged as drift; fix in next Coder pass).

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
- `serde`, `serde_yaml` — runtime dependencies (used by `main.rs` in `--autopilot` mode per specs/35); also used by the `#[cfg(test)]` test runner. Promoted from `[dev-dependencies]` to `[dependencies]` when demo mode shipped (specs/80 § Dependencies carries the rationale).

## Implementation Status

**Implemented:**
- Scenario YAML format (`scenario`, `description`, `objectives`, `assertions` fields).
- Optional `level:` field on Scenario (specs/15) — selects a generated demo level instead of `level_data::build_default()` when set; backwards compatible with all existing fixtures.
- Objective types: `kill:`, `reach:`, `approach:`, `wait:`.
- Target names: `enemy`, `exit`, `spawn`, `pickup_health`, `pickup_ammo` (with fallback semantics).
- Assertion fields: `player.alive`, `player.health`, `enemy.alive`, `game.won`, `game.frames` — these five are implemented in `autopilot::eval_assertion`.
- **Not yet implemented** (return "unknown assertion field" error at runtime): `player.position.x`, `player.position.y`, `enemy.health`, `game.running`.
- Assertion operators: `=`, `>`, `<`, `>=`, `<=`.
- Bot behavior: turn-toward objective, move-forward when roughly facing, fire when aligned and in range, stuck detection with strafe recovery.
- Execution rules: fresh `GameState` per scenario, 60 FPS fixed-`dt` simulation, 3600-frame max.
- Per-frame API (`parse_scenario`, `BotState`, `BotProgress`, `bot_step`) always compiled for `--autopilot` mode (specs/35).
- Batch driver (`run_scenario`, `run_all_scenarios`) gated behind `#[cfg(test)]`.

**Deferred:**
- Objectives that require game features not yet implemented (e.g., `kill: boss`, multi-enemy targeting).
- Parallel scenario execution (currently sequential).
- Scenario-level RNG seed override (determinism currently tied to global seed from specs/35).

## Related

- `specs/15_level_generator.md` — `DemoLevelKind` catalog and the optional `level:` scenario field.
- `specs/35_demo_mode.md` — headed-autopilot CLI mode and frame recording for release demos.
