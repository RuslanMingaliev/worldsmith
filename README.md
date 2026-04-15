# worldsmith

Experimental spec-driven development project for building a retro shooter generation pipeline.

## Vision

The project explores whether a game similar in feel to classic retro FPS titles can be reproduced from a structured specification pack instead of being hand-written from scratch.

The long-term target is not "one more generated prototype", but a body of design knowledge sufficient to reproduce the game:

reference -> extracted knowledge -> specs -> intermediate representation -> generated game -> evaluation

## Current Goal

Build a minimal playable vertical slice from specs.

The generated game must include:
- first-person movement
- wall collision
- one weapon
- one enemy type
- one static level
- one exit condition

## Non-goals

This project does not currently aim to:
- recreate any original game exactly
- generate multiple levels
- support mod/plugin system
- support fancy graphics
- rebuild the whole project from scratch on every small change

These may become goals in later phases.

## Repository Layout

- `specs/` — source of truth for design and generation constraints
- `ir/` — compact machine-oriented representation derived from specs
- `knowledge/` — extracted knowledge from reference (public)
- `tests/` — test scenarios
- `evals/` — harness evaluation criteria
- `tooling/` — scripts and agent prompts
- `generated/` — disposable generated implementation
- `work/` — private notes, decisions (gitignored)
- `reference/` — research material (private)
- `ir/module_plan.yaml` defines every generated module, its responsibility, and a `depends_on` list for understanding regeneration scope.

## License and Scope

This repository (code, specs, IR, knowledge files, tooling, and generated samples that ship with tags) is released under the MIT License. See [LICENSE](LICENSE) for the exact terms.

**Not included in the open-source release:**
- `reference/` — private research corpus used for mechanic extraction. Excluded from git.
- `work/` — private intermediate findings, drafts, and notes that will graduate into `knowledge/` and `specs/` when ready.

Public contributors should treat everything outside these private directories as MIT-licensed and safe to share. Any sanitized findings or specs merged into the repository automatically fall under the same license.

## Release Artifacts and CI

- `generated/` contains the most recent generated game that passed evals, committed at each tagged release.
- CI validates specs, IR, and knowledge on every PR (see `.github/workflows/pr.yml`).
- Code generation is a manual process: the maintainer triggers generation in a Claude Code session, verifies results, and commits. See `tooling/agents/` for agent prompts.
- Full regeneration from scratch is performed for tagged releases to prove spec self-sufficiency.

## Development Workflow

- `generated/` always contains the most recent fully generated game that passed evals. Refresh only when cutting a new tag or after a maintainer-triggered regeneration.
- Pull requests should change specs, IR, knowledge, tests, or tooling. Direct edits to `generated/` are discouraged.
- For releases, the maintainer runs the full pipeline (specs → IR → generation → evals → reconcile) to rebuild from scratch.

## Core Principles

- Specs are the source of truth.
- Generated code is disposable.
- Regeneration should be incremental by default.
- Evaluation is mandatory.
- Reconcile after generation: sync specs with what was actually produced.
- Versions are git tags, not hardcoded in docs.
