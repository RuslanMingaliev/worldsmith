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
| `reach: <position-target>` | Navigate to target position. Completes when `distance(player.pos, target_pos) < BOT_REACH_DISTANCE` (1.0). Position targets: `exit`, `spawn`. |
| `reach: pickup_<kind>` | Travel to and **consume** the first active `<kind>` pickup. Completes when `resolve_target_pos` returns `None` — i.e. no active pickup of that kind remains, because the bot collected it (or the level had none). The proximity check is intentionally NOT used for pickup targets: the bot's BFS path runs over a tile grid and "within `BOT_REACH_DISTANCE`" can be satisfied by the bot's continuous position without it actually walking onto the pickup tile, which is what `game_loop` uses to flip `pickup.active = false`. Without this rule the objective completes on proximity, the bot moves on, and the BFS path away from the pickup orbits without ever consuming it. |
| `approach: <target>` | Get within weapon range of target (distance < 8.0) |
| `wait: <frames>` | Do nothing for N frames |

### Targets

| Name | Resolves to |
|------|-------------|
| `enemy` | Nearest alive enemy position (minimum `player.pos.distance_to(enemy.pos)` over `enemies.iter().filter(|e| e.alive)`; ties broken by index in `level.enemy_spawns`). Returns `None` when no enemies are alive — downstream callers handle this: `Kill` completes via `enemies.iter().all(|e| !e.alive)` regardless, `Reach`/`Approach` auto-complete on `None` per `check_objective_complete`, and `compute_input` returns the default `InputState`. The "nearest" rule keeps single-enemy fixtures (`tests/combat/{kill_enemy,kite_enemy}.yaml`) bit-for-bit equivalent to the old "first alive" rule, while letting multi-enemy fixtures (`tests/level/{scavenge_run,local_chase_obstacle}.yaml`) target the immediate threat instead of an arbitrary index-zero enemy that may be flanked by a closer one. |
| `exit` | Level exit position |
| `spawn` | Player spawn position |
| `pickup_health` | First active health pickup (filtered by `kind == Health` AND `active == true`, per `specs/60 § Pickup Entity § Transitions`). Returns `None` when no active health pickup remains; combined with the `reach: pickup_<kind>` completion rule above, this means the objective completes (rather than stalls) once the bot has collected the pickup or the level had none to begin with. |
| `pickup_ammo` | First active bullet pickup (filtered by `kind == AmmoBullets` AND `active == true`). Same filter and completion semantics as `pickup_health`. The target name is `pickup_ammo` rather than `pickup_bullets` for backwards-compat with the pre-ammo-split scenarios (`tests/level/scavenge_run.yaml`); the dispatch maps to the bullet variant because that is what the pre-slice "ammo" name covered. |
| `pickup_shells` | First active shell pickup (filtered by `kind == AmmoShells` AND `active == true`). Same filter and completion semantics. Added in the 2026-05-18 ammo-split slice. |

The "first active" filter is critical to the `reach: pickup_<kind>` semantics: it must distinguish between "pickup still on the floor" (objective unmet, keep routing toward it) and "pickup already collected" (objective satisfied, advance to next). Pickups can only deactivate, never reactivate within a run (`specs/60 § Pickup Entity § Transitions`), so the active filter encodes exactly the binary the objective check needs.

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
| `player.bullets` | number | Player bullets pool (0-`PLAYER_BULLETS_MAX`); added 2026-05-18 ammo-split slice (specs/25 § Pickups § Player Ammo Pools). |
| `player.shells` | number | Player shells pool (0-`PLAYER_SHELLS_MAX`); added 2026-05-18 ammo-split slice. |
| `player.ammo` | number | Convenience alias for "the equipped weapon's ammo pool" — currently always `player.bullets` because pistol is the only weapon (its category is `AmmoCategory::Bullets`). When the deferred shotgun ships, this alias flips to read `player.shells` for any frame where the player has the shotgun equipped. Tests that need a per-category guarantee should use `player.bullets` / `player.shells` directly. |
| `player.armor` | number | Player armor pool (0-200); added 2026-05-14 armor slice (specs/25 § Armor). |
| `player.position.x` | number | Player X coordinate |
| `player.position.y` | number | Player Y coordinate |
| `enemy.alive` | bool | Enemy is alive |
| `enemy.health` | number | Enemy health |
| `game.won` | bool | Player reached exit |
| `game.running` | bool | Game is still running |
| `game.frames` | number | Frames elapsed |

## Bot Behavior

The bot is a deterministic per-frame controller that derives `InputState` from the current `GameState` plus the active scenario objective. It implements four explicit policies — **LoS-gated firing**, **range-gated firing**, **kiting**, and **BFS pathfinding** — so scenarios can stress combat behavior alongside navigation. Stuck detection remains as a backstop for cases the BFS planner cannot resolve (e.g. a dynamic occupant on a tile the planner treats as walkable).

The bot is narrow-purpose. It drives scenario validation and the PR-preview demo, not general gameplay; it is autopilot tooling, not reference-derived gameplay AI. Constants below are project-internal tuning defaults — none are knowledge-backed (see [`25_game_tuning.md § Autopilot`](25_game_tuning.md#autopilot-bot-tuning)).

### Per-frame Decision

Each frame the bot resolves the active objective's target position, computes `dist = player.pos.distance_to(target_pos)`, and emits an `InputState`:

1. **Turn toward target.** Emit `turn` with sign matching the angular delta and magnitude 1.0, except when `|delta_angle| < BOT_TURN_THRESHOLD` (emit `turn = 0` to suppress oscillation around the target heading).
2. **Pick a movement mode:**
   - **Kite mode** — when the active objective targets an enemy (`kill: enemy` or `approach: enemy`) AND there exists at least one alive enemy `e` with `player.pos.distance_to(e.pos) < BOT_KITE_RANGE` AND `has_line_of_sight(player.pos, e.pos, &level)` returns true: emit `forward = -1.0` (back-pedal). The bot keeps facing the objective target so LoS for firing on it is preserved while the player position retreats from the closest threat. The trigger evaluates over ALL alive enemies (not just the objective target) so that a closer flanking enemy correctly forces a back-pedal even when the objective target is far away. The LoS gate prevents wall-separated kiting: when an enemy is within `BOT_KITE_RANGE` but a wall lies between the two, the bot stays in path-follow mode and routes around the wall via BFS instead of indefinitely backing away from a non-threatening proximity. Captured during 2026-05-08 reconcile after the Coder added the LoS check to fix indefinite westward back-pedal in `local_chase_obstacle`.
   - **Path-follow mode** — otherwise: follow the next waypoint from the BFS path (see § Pathfinding). The path's destination is normally the objective target tile, but may be temporarily redirected via a pickup tile by the pickup-seeking modifiers (see § Pickup-Seeking). The bot turns toward the waypoint's center and emits `forward = +1.0` once roughly facing it.
3. **Decide whether to fire** (combat objectives only, i.e. `kill`). The bot fires when there exists any alive enemy `e` such that **all three** gates hold for that enemy:
   - `player.pos.distance_to(e.pos) < BOT_FIRE_MAX_RANGE`,
   - AND `has_line_of_sight(player.pos, e.pos, &level)` returns true,
   - AND `|angle_to(e.pos) - player.facing| < BOT_FACING_THRESHOLD`.

   The fire gate is keyed on "any alive enemy in range/LoS/facing", not on the objective target alone, so the bot can defend itself against a flanking enemy while routing toward the objective. Single-enemy fixtures behave identically because "the only alive enemy" and "the objective target" coincide. The previous gate (`roughly_facing && dist < BOT_APPROACH_DISTANCE + ENEMY_RADIUS_TILES`) is retired. Range and LoS replace it. `BOT_APPROACH_DISTANCE` is no longer a fire gate; it remains the success threshold for the `approach:` objective only.

### Line-of-sight Test

`has_line_of_sight(from, to, &level)` is a tile-grid ray-cast. It samples points along the line segment from `from` to `to` at step `BOT_FIRE_LOS_RAY_STEP` (in tile units) and returns `false` as soon as a sampled point lands inside a `Tile::Wall`; otherwise `true`. Step size is a CPU/accuracy tradeoff — sized so a one-tile-wide gap reliably reads as transparent at all reasonable angles. A closed-form 2D DDA is allowed (`coder_degrees_of_freedom` covers the implementation choice) provided the wall-hit semantics match.

### Pathfinding

`find_path(from, to, &level) -> Vec<(usize, usize)>` runs a breadth-first search over the tile grid:

- Graph nodes are walkable tiles (`Tile::Floor`).
- Edges are **4-connected** (N/S/E/W). Diagonals are not edges. This keeps path geometry compatible with the existing axis-aligned wall-slide behavior used by `player_state` and `enemy_logic`.
- BFS starts at the tile containing `from` (floor of `from.x`, `from.y`) and ends at the tile containing `to`, returning the tile sequence including both endpoints.
- The first tile after `from` is the next waypoint. The bot turns toward the waypoint center and moves forward; once within one tile's worth of progress to that waypoint, the bot consumes it and advances to the next.
- **Replan cadence.** Recomputation runs every `BOT_PATH_REPLAN_FRAMES` frames OR whenever the objective's target position has moved by more than one tile since the last plan. BFS over the 20×15 grid is cheap but still allocates; per-frame replanning is wasteful.
- **Fallback.** If BFS finds no path (target unreachable, or `to` is inside a wall on this frame), the bot falls back to bee-lining toward the straight-line target. This preserves behavior for objectives whose target resolves to a position not on the walkable graph (e.g. a transient frame where the enemy's tile-rounded position lands inside a wall).

The pathfinding internals (turn-toward, waypoint-consume distance, kite vs path-follow precedence when both apply) are listed under `coder_degrees_of_freedom` in `ir/contracts/_shared.yaml`.

### Pickup-Seeking (Path Modifier)

Pickup-seeking is a **path modifier** layered on top of the existing
objective system. The active objective (`kill:` / `approach:` / `reach:` /
`wait:`) does NOT change when pickup-seeking activates — the bot still
evaluates objective completion against the original objective target.
What changes is the BFS path's destination tile: the bot routes via a
pickup tile, then resumes routing toward the objective target.

Two distinct modifiers exist; both feed into the same underlying BFS
mechanism.

#### HP-threshold health routing

**Trigger.** On any path replan (per `BOT_PATH_REPLAN_FRAMES`, or when the
objective target moves > 1 tile), if the bot is in path-follow mode AND
`player.health < BOT_HEALTH_PICKUP_THRESHOLD * PLAYER_MAX_HEALTH` AND there
exists at least one `Pickup` in `level.pickups` with
`kind == PickupKind::Health` and `active == true`, the modifier activates.

**Effect.** The "intermediate target" tile is set to the nearest active
health pickup's tile (Euclidean `player.pos.distance_to(pickup.pos)`; ties
broken by the pickup's index in `level.pickups` via `Iterator::min_by`'s
"first equal minimum" rule). The BFS path is computed from `player.pos`
to this intermediate tile. The bot follows that path. Once the bot's
tile-position equals the pickup's tile (by which point `game_loop`'s
per-frame pickup check has consumed the pickup, flipping its `active`
flag to `false`), the next replan re-evaluates: the trigger fails (no
`active == true` pickup at that index any more), the modifier deactivates,
and the BFS path retargets the original objective. (BFS-graph Manhattan
distance is the precise form for the prototype's 4-connected grid; the
Euclidean approximation is cheaper and agrees with Manhattan on the test
fixtures' open-corridor geometry. Tracked as a deferred refinement.)

**Edge cases.**
- **Pickup unreachable.** If BFS to the intermediate target returns an
  empty path (the pickup is enclosed in walls), the modifier no-ops for
  this replan and the bot routes directly to the objective target.
  Re-evaluated on the next replan.
- **Pickup consumed before bot arrives.** Cannot happen in the prototype:
  only the bot can consume pickups (the basic-trooper enemy ignores them
  per `specs/60`). For a future multi-pickup-consumer world, the
  same edge case as "unreachable" applies — the next replan re-evaluates.
- **Health restored above threshold mid-route.** The modifier deactivates
  on the next replan (HP check fails) and the bot retargets the original
  objective. The bot does NOT immediately abandon its current waypoint;
  it finishes the in-flight waypoint then replans.
- **`reach: pickup_health` objective active.** No special interaction —
  the trigger condition still fires if HP is low and the objective's
  pickup target equals the modifier's intermediate target, the BFS path
  is computed once toward that single tile, and the original objective
  completes when the bot reaches it. If the objective targets a *different*
  pickup, both targets are in `level.pickups`; the modifier picks the
  nearest active health pickup, which may or may not be the objective's
  target. The objective's target wins for objective completion; the
  modifier's target wins for movement.

**Concurrent-objective interaction.** The modifier is a path modifier, NOT
an objective. It does not pause `kill:` / `approach:` / `reach:` / `wait:`
progression. While routing toward the health pickup, the bot still:
- evaluates firing decisions against the original objective target
  (kill/approach combat objectives — the bot may fire at an enemy along
  the route to the pickup if LoS, range, and facing all hold);
- counts frames toward `wait:` countdowns;
- checks `reach:` distance against the original objective target.

#### Ammo opportunism

**Trigger.** On any path replan, if the bot is in path-follow mode AND the
HP-threshold modifier did NOT activate this replan AND
`player.bullets == 0` AND there exists at least one `Pickup` in
`level.pickups` with `kind == PickupKind::AmmoBullets` and `active == true`, the
modifier evaluates the detour cost. The trigger reads the bullets pool (not the shells pool) because the pistol — the only weapon this slice — consumes bullets; a future shotgun-shipping slice will either widen the gate to "the equipped weapon's pool is zero" or grow a parallel `player.shells == 0 + AmmoShells filter` arm. The 2026-05-18 ammo-split slice renamed `player.ammo == 0` to `player.bullets == 0` and narrowed the pickup filter to `AmmoBullets` (was `Ammo`).

**Effect.** Trigger tightened from the earlier `< PLAYER_AMMO_MAX` rule:
at the pre-slice prototype's starting ammo of 12 / max 30, the looser trigger fires
unconditionally on round one and the demo always detours; `== 0` keeps
the modifier discriminating. The post-slice starting bullets / max bullets are 50 / 200 (knowledge-direct values — specs/25 § Pickups § Player Ammo Pools); the `== 0` gate continues to be the right discriminator at those values too — the bot does not run out of bullets in existing scenarios, so the gate stays cold and existing `--autopilot` recordings are byte-identical. Reintroduce the broader trigger when the
ammo economy is rebalanced.

The current implementation uses a Euclidean approximation of the detour
cost rather than a BFS path-length comparison: the modifier selects the
*nearest* active ammo pickup (`Iterator::min_by` over Euclidean
`player.pos.distance_to(pickup.pos)`; ties broken by iteration order in
`level.pickups`) and accepts it iff
`player.pos.distance_to(pickup.pos) <= player.pos.distance_to(objective_target) + BOT_PICKUP_DETOUR_BUDGET`.
When the check passes, the BFS path destination is set to that pickup's
position; the bot consumes the first segment, collects the pickup on
arrival (per `game_loop`'s per-frame check), the pickup goes inactive,
and on the next replan the trigger fails (this pickup no longer counts)
so the bot retargets the original objective directly. The Euclidean
budget check is a simpler approximation of the BFS-path detour: it admits
some pickups whose actual two-segment path exceeds the budget and may
reject others whose BFS detour is small but whose Euclidean distance is
large. For the prototype's 20×15 grid with sparse interior walls the two
metrics agree on the test fixtures; a BFS-based detour calculation
(`via_pickup_len - direct_len`) is the precise form and is tracked as a
deferred refinement.

**Edge cases.**
- **Two-segment path implementation.** The contract is that the bot's
  next waypoint is the next tile along the `player → pickup → target`
  joined path. The Coder may either (a) compute both BFS segments
  separately and concatenate, or (b) treat the pickup tile as a forced
  intermediate via two replans (first replan: `player → pickup`; on
  arrival, second replan: `pickup → target`). Both meet the spec; option
  (b) is simpler and reuses the existing single-target BFS.
- **No active ammo pickup, or the nearest active pickup fails the
  Euclidean budget check.** The modifier no-ops and the bot routes
  directly to the objective target. (The current implementation only
  evaluates the single nearest candidate against the budget; if that
  one is too far, no further candidates are considered this replan —
  a consequence of `Iterator::min_by` collapsing the candidate set to
  one before the budget check.)
- **Multiple candidates.** `Iterator::min_by` over Euclidean
  `distance_to(player.pos)` picks the nearest; ties resolved by the
  pickup's index in `level.pickups` (min_by's "first equal minimum"
  rule). Deterministic because the pickup vector is constructed in a
  fixed order in `level_data::build_default`.
- **Pickup blocks the direct path.** If the ammo pickup's tile already
  lies on the direct BFS path, the modifier still fires and the bot
  collects the pickup as part of its normal traversal — same behavior as
  without the modifier, which is fine.

**Concurrent-objective interaction.** Same as HP-threshold: the modifier
is a path modifier, not an objective. Firing, `wait:` countdowns, and
objective completion checks all run against the original objective target.

#### Modifier priority

When multiple modifiers could apply, the priority is:

1. **Kite mode wins over both modifiers.** Kite mode (specs/30 § Per-frame
   Decision step 2) activates when the active objective targets an enemy
   AND `dist < BOT_KITE_RANGE`. While kiting, the bot back-pedals (`forward
   = -1.0`) and does not follow a BFS path at all — pickup-seeking is moot.
2. **HP-threshold wins over ammo opportunism.** When path-follow mode is
   active and both modifiers' triggers fire, only the HP-threshold modifier
   activates; ammo opportunism is skipped this replan. Health is more
   critical than ammo: a dead bot can't grab any pickup, but an
   under-armed bot can still kite or close to contact range.
3. **At most one modifier per replan.** A single replan never produces a
   three-segment `player → health → ammo → target` path. The next replan
   re-evaluates and a different modifier may apply.

#### Replan triggering

Pickup-seeking modifiers piggyback on the existing replan cadence: every
`BOT_PATH_REPLAN_FRAMES` frames OR on objective-target movement > 1 tile.
A pickup that becomes active (impossible in this prototype but defined for
future-proofing — pickups can only deactivate, never reactivate, within a
run, per `specs/60 § Pickup Entity § Transitions`) does NOT trigger a
replan; the next scheduled replan sees the new state.

The on-arrival pickup consumption (player tile equals pickup tile, pickup
flips to inactive) does NOT itself trigger a replan — the bot continues
on the in-flight path. The next scheduled replan deactivates the now-stale
modifier and retargets the original objective.

### Stuck Detection (Fallback)

Stuck detection remains as a backstop for cases BFS cannot resolve:

- Another agent (typically an enemy) standing on the bot's next waypoint.
- A path that the bot cannot physically traverse due to player-radius collision near a corner.

If the bot's position hasn't moved for `BOT_STUCK_FRAMES`, it begins strafing. After `BOT_REVERSE_STRAFE_FRAMES`, it reverses strafe direction. Behavior is unchanged from earlier revisions; what changed is its role — primary navigation is BFS, strafing only kicks in when BFS-driven motion is itself blocked.

## Execution Rules

- Each scenario runs with fresh `GameState`
- Simulation runs at 60 FPS (FRAME_TIME = 1/60)
- Maximum duration: `BOT_MAX_FRAMES` frames (see [`25_game_tuning.md § Autopilot`](25_game_tuning.md#autopilot-bot-tuning) — currently 18000 / 300 game-seconds; raised from the original 3600 to fit two-enemy fixtures across the central divider)
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
- Assertion fields: `player.alive`, `player.health`, `player.ammo`, `player.bullets`, `player.shells`, `player.armor`, `enemy.alive`, `game.won` — these eight are implemented in `autopilot::get_field_value` per `ir/contracts/autopilot.yaml § run_scenario § Field-value resolver`. `player.armor` was added in the 2026-05-14 armor slice for the `tests/combat/armor_absorbs_damage.yaml` scenario. `player.bullets` and `player.shells` were added in the 2026-05-18 ammo-split slice for the `tests/combat/shell_pickup.yaml` scenario; `player.ammo` remains as a convenience alias for the equipped weapon's pool (currently always the bullets pool — see § Available Fields).
- **Not yet implemented** (return "unknown field: <name>" failure at runtime): `player.position.x`, `player.position.y`, `enemy.health`, `game.running`, `game.frames`.
- Assertion operators: `=`, `>`, `<`, `>=`, `<=`.
- Bot behavior: turn-toward objective, BFS pathfinding with periodic replan and bee-line fallback, kite at `BOT_KITE_RANGE`, range-gated firing at `BOT_FIRE_MAX_RANGE`, LoS-gated firing via tile-grid ray-cast, stuck detection with strafe recovery as fallback.
- `reach: pickup_<kind>` completes on actual pickup consumption (`pickup.active == false`), not on proximity, per § Objectives.
- Execution rules: fresh `GameState` per scenario, 60 FPS fixed-`dt` simulation, `BOT_MAX_FRAMES`-frame max (see specs/25 § Autopilot).
- Per-frame API (`parse_scenario`, `BotState`, `BotProgress`, `bot_step`) always compiled for `--autopilot` mode (specs/35).
- Batch driver (`run_scenario`, `run_all_scenarios`) gated behind `#[cfg(test)]`.

**Deferred:**
- Objectives that require game features not yet implemented (e.g., `kill: boss`, multi-enemy targeting).
- Parallel scenario execution (currently sequential).
- Scenario-level RNG seed override (determinism currently tied to global seed from specs/35).

## Related

- `specs/15_level_generator.md` — `DemoLevelKind` catalog and the optional `level:` scenario field.
- `specs/35_demo_mode.md` — headed-autopilot CLI mode and frame recording for release demos.
