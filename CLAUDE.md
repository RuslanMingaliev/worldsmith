# Worldsmith

Spec-driven game generation experiment. Generate a retro shooter from structured specifications.

## Current Status

**Status:** Working, playable (top-down 2D)

## Quick Commands

```bash
# Run evals (build + test)
.venv/bin/python3 tooling/run_evals.py

# Validate specs/IR
.venv/bin/python3 tooling/validate_specs.py --verbose

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
- `ir/module_plan.yaml` — Module structure

## Current Priority

Focus on specs, knowledge extraction, and gameplay depth — not generation automation.
Generation is manual (human + Claude session).

## Post-Generation Reconcile

After any generation (full or partial), reconcile code with specs:

1. **Constants invented by LLM?** → Add to `specs/25_game_tuning.md`
2. **Spec feature not implemented?** → Mark as "deferred" in the spec
3. **Code behavior differs from spec?** → Update spec or fix code
4. **New design decision?** → Document in ADR format

This prevents specs and code from drifting apart across regenerations.

## Conventions

- Specs are the source of truth, generated code is disposable
- Interactive generation (human + Claude conversation)
- Run `python tooling/run_evals.py` after changes
- Document decisions in ADR format
- Rust: safe code only, no unsafe, minimal dependencies
- Versions are git tags, not hardcoded in docs

## Reference and Knowledge Integrity

This project's whole proposition is "specs distilled from a real reference, regenerated into code". That only works if the chain stays honest. Two rules:

1. **`reference/` is gitignored and may be empty.** When it contains only `.gitignore` and `README.md`, no extraction is possible. The Extractor agent must STOP in that state — it must NOT infer mechanics from training data, genre conventions, or common knowledge of similar games. See `tooling/agents/extractor.md` § Step 0.

2. **Only the Extractor writes to `knowledge/`, and only when `reference/` is loaded.** Architect, Orchestrator, Reconciler, and PostMortem must never add or modify knowledge files. If a spec value has no knowledge backing, mark its Source as `Generation default — no knowledge backing` in `specs/25_game_tuning.md` and add a parking-lot item to the run journal — never invent a knowledge citation. See `tooling/agents/architect.md` § Citation discipline.

`tooling/validate_specs.py` enforces this mechanically: a session that modifies `knowledge/` while `reference/` is empty fails validation with a loud banner. Trust the gate; do not work around it. If the gate fires unexpectedly, the right responses are (a) revert the knowledge edit, (b) load the relevant reference and re-run Extractor properly, or (c) demote the value to a `Generation default` in spec/25.

## Auto-Documentation Rules

When a decision is made during conversation, **automatically**:

1. **Record decision** — Use ADR format (Decision N: Title, Date, Context, Decision, Consequences)
2. **Update agent prompts** — If workflow or process changes, update `tooling/agents/*.md`
3. **Update README files** — If directory structure or conventions change

Don't wait for user to ask — document immediately when decisions are made.

## Multi-Agent System

Agents in `tooling/agents/`:
- **Orchestrator** — Coordinates work, delegates tasks
- **Extractor** — Extracts knowledge from reference → `knowledge/`
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

- Top-down view, not raycasting
