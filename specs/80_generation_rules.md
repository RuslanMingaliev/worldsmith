# Generation Rules

## General Rules

- Generate only what is requested.
- Do not rewrite unrelated modules.
- Prefer explicit code over clever abstractions.
- Prefer stable interfaces over repeated redesign.
- Prefer repair over regeneration.

## Architecture Rules

The generated project should separate:
- game loop
- input handling
- player state
- enemy behavior
- level data
- rendering or presentation logic
- frame recording (specs/35) — small, isolated module; only consumed by `main.rs` when `--record-frames` is passed

## Regeneration Rules

Two distinct modes exist: iterative (during development) and release (for versions).

### Iterative Development Mode

During active development, prefer efficiency:

**Repair** (most preferred):
- Fix specific issues in existing code
- Preserve working functionality

**Partial Generation** (preferred):
- Regenerate only affected modules
- Keep stable modules intact

**Full Regeneration** (when needed):
- Architecture changed substantially
- Too many patches accumulated
- Starting fresh is faster than fixing

### Release Generation Mode

For each tagged release:

**Full Regeneration** (required):
- Delete all generated code
- Regenerate everything from specs + IR
- Produce a "generated sample" artifact

This proves that specs are self-sufficient. The generated sample can be published as a playable release.

## Token Efficiency Rules

- Do not include the entire reference source in normal generation.
- Use extracted specs and IR as the main context.
- Include only relevant interfaces and related modules.
- Keep prompts focused on one target module or one vertical slice.

## Context Scope Modes

When regenerating a module, use one of these context modes:

- **Minimal**: Specs + IR + module interface signatures only
  - Lower token usage
  - Faster generation
  - Use when module is well-isolated

- **Full**: Specs + IR + full source code of related modules
  - Higher token usage
  - Better cross-module consistency
  - Use when module has complex dependencies

Default behavior: Start with minimal, escalate to full if integration issues arise.

Rule: Do not modify code outside the current target module during generation.

## Validation Rules

Before generation, perform basic validation:

- Validate YAML syntax and structure of IR files
- Check that required fields exist
- Verify module names are valid identifiers
- Catch simple errors early (typos, malformed YAML)

Advanced validation (dependency cycles, completeness checks) is deferred.

## Current Bias

The generator should be biased toward:
- vertical slice delivery
- boring architecture
- explicit state
- static level data
- simple enemy logic
- direct control flow

## Rust Code Constraints

The generated Rust code must follow these constraints:

### Safety

- `unsafe` code is forbidden
- All operations must use safe Rust primitives

### Error Handling

Use a pragmatic approach:
- In `main()`, initialization, and resource loading: use `Result<T, E>` with `?` operator
- In game logic and update loops: use `.expect("clear message")` instead of `.unwrap()`
- Never use bare `.unwrap()` without justification
- Panic messages must be descriptive

Example:
```rust
// Initialization - use Result
fn load_level() -> Result<Level, std::io::Error> {
    let data = std::fs::read("level.dat")?;
    Ok(parse_level(&data)?)
}

// Game logic - use expect with clear messages
fn update_enemy(enemy: &mut Enemy) {
    let target = find_target()
        .expect("player must exist during game loop");
    enemy.chase(target);
}
```

### Architecture

- Use simple procedural or object-oriented style
- Organize code with structs and functions
- Do NOT use Entity-Component-System (ECS) architecture
- Keep data structures straightforward and explicit

### Cargo Manifest

The generated `Cargo.toml` MUST pin these values verbatim so the release pipeline (`release.yml` matrix `bin:` entry) can locate the built binary at a stable path. Coder-side discretion in package naming has historically broken `release.yml`'s `Package binary archive` step (2026.04 release run #25670337576: Coder produced `[package].name = "worldsmith-game"`; release.yml matrix expected `bin: game`, the previous 2026.03 release shipped with).

- `[package].name = "worldsmith-game"`
- `[[bin]].name = "worldsmith-game"`
- `[[bin]].path = "src/main.rs"`

cargo will then build the binary as `target/release/worldsmith-game` on Unix and `target/release/worldsmith-game.exe` on Windows, matching `.github/workflows/release.yml`'s matrix.

### Dependencies

- Minimize external dependencies
- Prefer standard library when possible
- For graphics/windowing:
  - `minifb` for window, input, and framebuffer rendering
- For scenario-driven autopilot and demo recording (specs/30, specs/35):
  - `serde`, `serde_yaml` as runtime dependencies (NOT just `[dev-dependencies]`).
    Released because `main.rs` in `--autopilot` mode parses scenario YAML at runtime.
  - **`serde_yaml` 0.9.x quirk** (the deprecated-but-pinned line): externally-tagged enums emitted in the `- variant: value` single-key-map form (the shape used by every `tests/*.yaml` Objective entry) cannot be deserialized via `#[derive(serde::Deserialize)] #[serde(rename_all = "snake_case")]`. v0.9 expects YAML `!tag` notation for externally-tagged enums and fails on the prose-style map. The `Objective` enum in `autopilot.rs` therefore ships a hand-rolled `impl<'de> Deserialize<'de> for Objective` via a MapAccess Visitor; see `ir/contracts/autopilot.yaml § public_types § Objective` for the contract spelling. If serde_yaml is ever bumped to ≥1.0, revisit and consider restoring the derive.
- Avoid adding dependencies for one-time operations
- Frame recording (specs/35) MUST use raw `std::fs::File` writes — do NOT add `png`, `image`, or any encoder crate. The recording is raw BGRA, decoded by ffmpeg downstream.
- CLI argument parsing (specs/35) MUST use `std::env::args` — do NOT add `clap`, `argh`, or similar.

### Code Style

Balance idiomatic Rust with readability:

**Encouraged:**
- Use iterators and pattern matching where they improve clarity
- Leverage Rust type system for compile-time safety
- Use standard naming conventions (snake_case, etc.)

**Discouraged:**
- Clever abstractions and over-engineering
- Excessive use of generic types or trait bounds
- Complex macro usage
- Functional-style chains that obscure logic

**Game logic should:**
- Be explicit and algorithm-like
- Read like a step-by-step description
- Use comments only for non-obvious logic
- Prioritize clarity over brevity

Example of preferred style:
```rust
fn update_enemy(enemy: &mut Enemy, player_pos: Vec2) {
    let dx = player_pos.x - enemy.pos.x;
    let dy = player_pos.y - enemy.pos.y;
    let distance = (dx * dx + dy * dy).sqrt();

    if distance < CHASE_RANGE {
        let direction = Vec2::new(dx, dy).normalize();
        enemy.pos += direction * enemy.speed;
    }
}
```

### API Surface

**No dead `pub` exports.** Every `pub fn`, `pub struct` field, or `pub const` a module emits must have at least one in-crate caller. If the only consumers are `#[cfg(test)]` (autopilot test runner, integration tests, test-only inspection), gate the export itself with `#[cfg(test)]` rather than leaving it public-and-dead in release builds. If a spec value has no consumer yet, leave it as a private constant or add the consumer in the same generation pass — do not ship "API for future use".

**Exception — autopilot per-frame primitives.** `parse_scenario`, `bot_step`, `BotState`, `BotProgress`, `Scenario`, and `Objective` from the autopilot module ARE released (not `#[cfg(test)]`-gated) because `main.rs` consumes them in `--autopilot` mode (specs/35). The autopilot module's batch driver (`run_scenario`, `ScenarioResult`, `#[test] run_all_scenarios`) remains `#[cfg(test)]`-gated. See `ir/contracts/autopilot.yaml` for the exact split.

**Exception — wave-cascade dead-code during partial regen:** when a Coder generates module A whose public symbols will be consumed by module B in a later wave of the same run, the symbols may be temporarily dead at the end of wave A. They must become live by the end of the run; otherwise the rule above applies.

**No cross-cutting `&mut <ServiceType>` in trait or non-orchestration methods.** A trait method or a non-orchestration module's public method must NOT take `&mut` on a global service type (`VisualEffects`, future `AudioMixer`, future `EventBus`). If the action requires emitting into such a service, return data describing the emission and let the orchestration layer (`game_loop`) emit. Exceptions: `update`-style methods that already take the full per-frame borrow-graph (e.g. `Enemy::update(&mut self, &mut Player, &Level, &mut VisualEffects, dt)`) — those are *defined* as the orchestration hook and may take service references directly.
