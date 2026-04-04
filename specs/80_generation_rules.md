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

### Dependencies

- Minimize external dependencies
- Prefer standard library when possible
- For graphics/windowing:
  - `minifb` for window, input, and framebuffer rendering
- Avoid adding dependencies for one-time operations

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
