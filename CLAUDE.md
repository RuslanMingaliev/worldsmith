# Worldsmith

Spec-driven game generation experiment. Generate a retro shooter from structured specifications.

## Current Status

**Status:** Working, playable (top-down 2D)

## Quick Commands

```bash
# Run evals (build + test)
python tooling/run_evals.py

# Run the game
cargo run --manifest-path generated/game/Cargo.toml

# Run tests only
cargo test --manifest-path generated/game/Cargo.toml
```

## Project Structure

```
specs/           # Source of truth (human-readable)
ir/              # Intermediate representation (YAML)
generated/game/  # Generated Rust code (disposable)
knowledge/       # Extracted knowledge (public, versioned)
tests/           # Test scenarios
evals/           # Harness evaluation criteria
tooling/         # Scripts and agent prompts
work/            # Private notes, decisions (gitignored)
reference/       # Research material (private)
```

## Key Files to Read

- `specs/00_project_goal.md` — What we're building, success criteria
- `specs/80_generation_rules.md` — Code generation constraints
- `work/decisions.md` — All design decisions (ADR-style)
- `work/generation_process.md` — How generation works
- `ir/module_plan.yaml` — Module structure

## Current Priority

Focus on specs, knowledge extraction, and gameplay depth — not generation automation.
Generation is manual (human + Claude session). See `work/decisions.md` Decision 16.

## Conventions

- Specs are the source of truth, generated code is disposable
- Interactive generation (human + Claude conversation)
- Run `python tooling/run_evals.py` after changes
- Document decisions in `work/decisions.md`
- Rust: safe code only, no unsafe, minimal dependencies
- Versions are git tags, not hardcoded in docs

## Auto-Documentation Rules

When a decision is made during conversation, **automatically**:

1. **Add to `work/decisions.md`** — Use ADR format (Decision N: Title, Date, Context, Decision, Consequences)
2. **Update agent prompts** — If workflow or process changes, update `tooling/agents/*.md`
3. **Update README files** — If directory structure or conventions change

Don't wait for user to ask — document immediately when decisions are made.

## Multi-Agent System

Agents in `tooling/agents/`:
- **Orchestrator** — Coordinates work, delegates tasks
- **Extractor** — Extracts knowledge from reference → `knowledge/` + `work/findings/`
- **Architect** — Formalizes knowledge into specs
- **Coder** — Generates code from specs
- **Researcher** — Answers questions, explores
- **TestBuilder** — Creates test models
- **EvalWriter** — Writes evaluation criteria

Workflow: `Reference → Extractor → knowledge/ → Architect → specs/ → Coder → generated/`

## Controls

- WASD — movement
- Arrows — turn
- Space — fire
- ESC — quit

## Known Issues

- Player starts facing right (angle=0), W moves right initially
- No visual feedback for shooting (only console output)
- Top-down view, not raycasting
