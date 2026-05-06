# Level Generator (Demo Scenarios)

## Intent

Some autopilot scenarios — particularly the one driving the PR-preview GIF — need a purpose-built level whose layout is chosen to demonstrate a specific gameplay behavior in a few seconds. The default level (`level_data::build_default`) is fine for general regression tests but is too cluttered to read at a glance: a short GIF of the bot wandering between an interior wall and a horizontal divider does not visually answer the question "did the enemy navigate around the obstacle?".

This spec defines a minimal `level_generator` module that produces a small, named, fully-deterministic `Level` for each demo scenario, and a tiny extension to the autopilot scenario YAML that lets a scenario opt into one of those levels by name.

The abstraction is deliberately small. There is no procedural generation, no template language, no DSL — each demo level is a hand-authored builder function that returns a `Level`. Adding a new demo level means adding one variant to an enum and one function, then naming the variant in a scenario YAML's `level:` field.

The knowledge basis is `knowledge/level_scenarios.md § Entity Placement Record` and § Key Insights ("a 'scenario' needs almost no new abstraction"). The reference treats a level as a tiny geometry plus a flat list of entity-placement records, processed by exactly the same code path that loads any other level. This spec mirrors that shape: the generator returns the same `Level` struct that `level_data::build_default` returns, and `game_loop` cannot tell which builder produced it.

## Architecture

```
specs/30 (autopilot)              specs/15 (this spec)
        │                                 │
        ▼                                 │
   parse_scenario  ◀─────── adds optional `level: <name>` key
        │                                 │
        │                                 │
   scenario.level.is_some()? ─yes─▶ level_generator::build(kind) ─▶ Level
                                  │
                                  └─no─▶ level_data::build_default() ─▶ Level

                 Level ─▶ game_loop::new(level) ─▶ GameState ─▶ render loop
```

The generator is consumed only by `main.rs` after CLI argument parsing (specs/35 § CLI). It is NOT called from `game_loop::update`, NOT from any per-frame path, and NOT during interactive play. Once `game_loop::new(level)` has built the `GameState`, the runtime treats a generated demo level as just another `Level` — the same struct, the same coordinate system, the same `is_wall` boundary check, the same tick loop.

## Demo Level Catalog

The generator owns a small `DemoLevelKind` enum. Each variant maps to one builder function that returns a fully-populated `Level`. The `Level` type itself is unchanged (`ir/contracts/level_data.yaml § Level`, `specs/25 § Level Layout`) — same struct, same fields, same `Vec<Vec<Tile>>` grid, same `Vec<Pickup>`.

| Variant | YAML name | Purpose | Implemented |
|---------|-----------|---------|-------------|
| `LocalChaseObstacle` | `local_chase_obstacle` | Demonstrates obstacle-aware enemy chase: one wall between player and enemy, valid path around. | yes |

### LocalChaseObstacle

**Purpose.** A short, visually clear demonstration that the basic-trooper enemy can navigate around a static obstacle to reach the player. The level reduces all visual clutter (no pickups, no extra walls, no irrelevant geometry) so the GIF reader's eye is drawn directly to the chase path.

**Layout** (20 × 15 grid — same dimensions as the default level per `specs/25 § Level Layout`, so `GRID_WIDTH` / `GRID_HEIGHT` / `TILE_SIZE` from `level_data` apply unchanged):

- All edges are walls (border): tiles at `x = 0`, `x = 19`, `y = 0`, `y = 14`.
- Interior wall: a single vertical bar at `x = 10`, `y ∈ {4, 5, 6, 7, 8, 9, 10}` (7 tiles tall, vertically centered). This bar blocks the direct horizontal line between player and enemy.
- All other interior tiles are floor.

**Spawns** (tile units; same coordinate system as `level_data::Level::player_spawn` / `enemy_spawns` / `exit`):

| Entity | Position | Rationale |
|--------|----------|-----------|
| Player spawn | `(3.5, 7.5)` | Left side, vertically centered. Faces the obstacle along the horizontal axis. |
| Enemy spawn | `(16.5, 7.5)` | Right side, vertically centered. Mirrors the player so the obstacle sits exactly between them. |
| Exit | `(1.5, 1.5)` | Far top-left corner, well away from the action. The bot's `kill: enemy` objective never directs it toward the exit, so the win-condition check (`player.pos.distance_to(level.exit) < EXIT_RADIUS`) is not triggered during the demo. |
| Pickups | (none) | Empty `Vec<Pickup>`. Pickups would distract from the chase visualization. |

**Path geometry.** The 7-tile-tall obstacle leaves two gaps:

- A 3-tile-tall floor gap at the top: `y ∈ {1, 2, 3}` along the obstacle column (between the obstacle and the top border).
- A 3-tile-tall floor gap at the bottom: `y ∈ {11, 12, 13}` along the obstacle column (between the obstacle and the bottom border).

Either gap is wide enough for both the player (radius `0.4375` tile per `PLAYER_RADIUS_TILES`) and the enemy (radius `0.375` tile per `ENEMY_RADIUS_TILES`) to traverse with margin. The reference's chase routine (knowledge/level_scenarios.md § Obstacle-Aware Chase) prefers a direct diagonal toward the target; with the obstacle blocking that diagonal, the routine falls through to perpendicular alternates and then "continue old direction" — producing the characteristic "skim along the wall" path that this demo is meant to show.

**Visual reading of the GIF.** With both player and enemy moving toward each other, the enemy hits the obstacle first (because the bot stops when it reaches firing range, while the enemy continues to close to contact range). The enemy then takes a perpendicular along the wall, rounds the corner at one of the gaps, and resumes the chase. The bot, separately, navigates around the same obstacle to close the distance for `kill: enemy`. The chase path is visible for several seconds before the engagement begins.

## Scenario YAML Extension

Scenarios opt into a non-default level by adding one optional key:

```yaml
scenario: local_chase_obstacle
description: Enemy chases player around a wall, demonstrating obstacle-aware chase behavior
level: local_chase_obstacle    # NEW — optional; absent = level_data::build_default()

objectives:
  - approach: enemy
  - kill: enemy

assertions:
  - player.alive: true
  - enemy.alive: false
```

**Field semantics:**

- `level:` (string, optional). If present, names a `DemoLevelKind` variant in `snake_case` form (e.g. `LocalChaseObstacle` → `local_chase_obstacle`). If absent or null, the runtime constructs the default level via `level_data::build_default()`. Unknown names are a hard parse error: `parse_scenario` panics with a clear message naming the unknown variant and the list of accepted values, per `specs/30 § Execution Rules` ("`.expect("valid scenario YAML")`").
- All existing fields (`scenario`, `description`, `objectives`, `assertions`) keep their existing semantics from `specs/30`.

**Backwards compatibility.** Every existing scenario YAML in `tests/**/*.yaml` continues to work without modification — the `level:` field defaults to absent, which falls back to `level_data::build_default()`. Specifically:

- `tests/combat/kill_enemy.yaml` — no `level:` field, uses default level.
- `tests/level/complete_level.yaml` — no `level:` field, uses default level.
- `tests/level/reach_exit.yaml` — no `level:` field, uses default level.
- `tests/level/scavenge_run.yaml` — no `level:` field, uses default level.

The parser change is purely additive: the field is `#[serde(default)]` on `Scenario` and the matching enum derives `serde::Deserialize` with `#[serde(rename_all = "snake_case")]`.

## Module Boundaries

The `level_generator` module sits between `level_data` (whose `Level` type it returns) and `main.rs` (its only consumer):

- **Depends on:** `level_data` (for the `Level`, `Tile`, `Vec2`, `Pickup`, `PickupKind` types).
- **Consumed by:** `main.rs` (loads the requested level when `--autopilot` mode parses a scenario with a `level:` field), and `autopilot` (the `DemoLevelKind` enum is a public type referenced by `Scenario.level: Option<DemoLevelKind>`). No other module references the generator.
- **Not consumed by:** anything in the per-frame update path. Generation runs once, at startup, before the render loop begins. `game_loop::update`, `autopilot::bot_step`, `enemy_logic::update`, etc. never reference `level_generator`.

This keeps the generator out of gameplay runtime logic per the issue's "Generator must not be part of gameplay runtime logic" constraint.

### `game_loop::new` constructor signature

To let `main.rs` choose between `level_data::build_default()` and `level_generator::build(kind)` without duplicating GameState construction logic, `game_loop::new()` is generalized to take a `Level` argument:

```rust
// before (specs/30 era):
pub fn new() -> GameState                 // builds default level internally

// after (this spec):
pub fn new(level: Level) -> GameState     // caller chooses the level
```

`main.rs` is the sole caller; it picks the level based on `--autopilot` mode and the parsed scenario:

```rust
let level = match autopilot_scenario.as_ref().and_then(|s| s.level) {
    Some(kind) => level_generator::build(kind),
    None       => level_data::build_default(),
};
let mut game = game_loop::new(level);
```

Interactive play (no `--autopilot`) always passes `level_data::build_default()` — the `level:` scenario field has no effect on interactive play because no scenario is loaded. The combined `--autopilot --record-frames` invocation (the canonical PR-preview path) goes through the same `match` and picks the generated level when the scenario asks for it.

## Determinism

Determinism follows entirely from the rules already established in `specs/35 § Determinism`. The generator itself uses no randomness — each builder function is a pure function from `DemoLevelKind` to `Level`, so repeated calls return byte-equal `Level` structs. With:

1. The fixed BGRA framebuffer recording (`specs/35 § Frame Recording Format`),
2. The fixed `dt = 1/60` simulation step (`specs/35 § Determinism`),
3. The fixed module-private RNG seeds in `--autopilot` mode (`specs/35 § Determinism`), and
4. The pure-function builder defined here,

a `--autopilot tests/level/local_chase_obstacle.yaml --record-frames out.raw` invocation produces a byte-identical `out.raw` across runs. This is the same property `specs/35 § Acceptance Criteria` already requires; this spec adds nothing to the determinism contract beyond "the builder is pure".

## PR Preview Integration

`tests/level/local_chase_obstacle.yaml` is the canonical PR-preview scenario. The split is:

| Use case | Scenario | Level |
|----------|----------|-------|
| PR-preview GIF (visual demo) | `tests/level/local_chase_obstacle.yaml` | `local_chase_obstacle` (this spec) |
| Regression `cargo test` runs | `tests/combat/*.yaml`, `tests/level/{complete_level,reach_exit,scavenge_run}.yaml` | default (`level_data::build_default`) |

The default level (no `level:` field) remains the right choice for regression-style scenarios — they exercise the canonical level layout, the canonical pickup placements, and the canonical exit-reachability path. The demo level is purpose-built for visual clarity and would be a poor regression target (no pickups, single obstacle) but a strong PR-preview target.

The spec asserts that the PR workflow's "Record gameplay GIF" step (`.github/workflows/pr.yml`) and `tooling/record_autopilot.sh`'s default scenario should both name `tests/level/local_chase_obstacle.yaml`. Updating those files is a workflow concern; see `work/pipeline_run_2026-05-03.md § Run-level follow-ups` for the maintainer task list (the agent-intake commit scope does not cover `.github/` or `tooling/` outside `tooling/agents/`, so the workflow swap ships separately).

## Constraints

- **No procedural generation.** Each demo level is a hand-written builder function. No grammar, no PCG seed, no algorithmic placement. Adding a new demo level means adding one enum variant and one function.
- **`Level` representation is unchanged.** The generator returns the same `Level` struct that `level_data::build_default` returns. No new fields, no new tile types, no new entity records. (`ir/contracts/level_data.yaml § Level` is unmodified.)
- **Generator is not part of gameplay runtime.** The only call sites are `main.rs` (once at startup) and the public `DemoLevelKind` type referenced by `autopilot::Scenario.level`. Per-frame paths never reference `level_generator`.
- **Pure builder functions.** Each builder is a `fn(...) -> Level` with no I/O, no randomness, no global state. Repeated calls return byte-equal `Level` structs.
- **Backwards compatible.** Scenarios without a `level:` field continue to use `level_data::build_default`. No existing test fixture is modified.

## Implementation Status

**Implemented:**
- Spec defines the `DemoLevelKind` enum, the `level_generator::build` function, and the `LocalChaseObstacle` variant.
- Spec defines the `level:` scenario YAML field and its fall-back semantics.
- Spec defines the `game_loop::new(level: Level)` signature change and `main.rs`'s call-site decision.
- Test fixture `tests/level/local_chase_obstacle.yaml` exists on disk and uses the `level: local_chase_obstacle` field plus the `approach: enemy` / `kill: enemy` objectives.
- IR module `level_generator` is added to `ir/module_plan.yaml` (universal-sink rule applied: `main.depends_on` lists `level_generator`).
- IR contract for `level_generator` and the autopilot / `game_loop` extensions live in `ir/contracts/level_generator.yaml`, `ir/contracts/autopilot.yaml`, and `ir/contracts/game_loop.yaml`.
- `.github/workflows/pr.yml` and `.github/workflows/release.yml` record the demo GIF using `tests/level/local_chase_obstacle.yaml` as the canonical PR-preview scenario.

**Deferred:**
- Additional demo level variants beyond `LocalChaseObstacle` (e.g. corridor chase, multi-enemy fan-out, pickup-scavenge tutorial). Add a variant to `DemoLevelKind` and a builder function as the need arises.
- Authoring fixtures for additional demo levels.
- Allowing scenarios to override the default level's *contents* (e.g. a scenario that uses the default geometry but adds an extra enemy) — this would require either splitting `Level` into geometry-vs-entities or adding a separate "scenario overlay" concept. Not needed for the current PR-preview goal.

## Related

- `specs/30_test_framework.md` — autopilot scenario YAML format (this spec extends it with the optional `level:` field).
- `specs/35_demo_mode.md` — `--autopilot` CLI mode and frame recording (this spec is consumed during scenario load in that mode).
- `specs/25_game_tuning.md § Level Layout` — the default level's dimensions and layout (kept for backwards compatibility; this spec adds an alternative builder, not a replacement).
- `knowledge/level_scenarios.md` — knowledge basis for "scenario = tiny geometry + entity list, hand-authored, no procedural generation" and the obstacle-aware chase behavior the demo level is designed to expose.
- `ir/module_plan.yaml` — module-graph entry for `level_generator`.
- `ir/contracts/level_generator.yaml` — the public API of the generator; `ir/contracts/autopilot.yaml` — the extended `Scenario` shape; `ir/contracts/game_loop.yaml` — the new `new(level)` signature.
