# Worldsmith

Experimental spec-driven development project for building a retro shooter generation pipeline.

## Vision

The project explores whether a game similar in feel to classic retro FPS titles can be reproduced from a structured specification pack instead of being hand-written from scratch.

The long-term target is not "one more generated prototype", but a body of design knowledge sufficient to reproduce the game:

reference -> extracted knowledge -> specs -> intermediate representation -> generated game -> evaluation

## Current Goal

Build a minimal playable vertical slice from specs.

The generated game must include:
- player movement (currently top-down 2D; raycasted first-person is a future goal)
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

- `generated/` is gitignored. The generated game is shipped as a release asset (archive) attached to the corresponding tag, not committed to the repository.
- Releases are tagged using the `yyyy.vv` scheme (e.g. `2026.01` for the first release of 2026, `2026.02` for the second).
- CI validates specs, IR, and knowledge on every PR (see `.github/workflows/pr.yml`).
- Code generation is a manual process: the maintainer triggers generation in a Claude Code session, verifies results, and packages the artifact. See `tooling/agents/` for agent prompts.
- Full regeneration from scratch is performed for tagged releases to prove spec self-sufficiency.

## Development Workflow

- `generated/` lives only locally during development; it is rebuilt from specs by the maintainer and never tracked in git.
- Pull requests should change specs, IR, knowledge, tests, or tooling. Direct edits to `generated/` are discouraged (they are erased on regeneration).
- For releases, the maintainer runs the full pipeline (specs → IR → generation → evals → reconcile) to rebuild from scratch, then packages `generated/game/` as a release asset attached to the tag.

## Core Principles

- Specs are the source of truth.
- Generated code is disposable.
- Regeneration should be incremental by default.
- Evaluation is mandatory.
- Reconcile after generation: sync specs with what was actually produced.
- Versions are git tags following the `yyyy.vv` scheme, not hardcoded in docs.
