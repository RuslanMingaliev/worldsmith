# Agent System

Multi-agent architecture for source-of-truth-driven game generation.

## Agents

| Agent | File | Responsibility |
|-------|------|----------------|
| **Orchestrator** | `orchestrator.md` | Coordination, delegation, escalation in manual sessions |
| **Extractor** | `extractor.md` | Extract knowledge from reference |
| **Architect** | `architect.md` | Design specs and per-module IR contracts |
| **Coder** | `coder.md` | Generate Rust from specs and contracts |
| **Reconciler** | `reconciler.md` | Reconcile generated code with specs, IR contracts, and prompt expectations |
| **PostMortem** | `postmortem.md` | Audit the run as a process; propose changes to agent prompts / tooling / ADRs |
| **Release Editor** | `release_editor.md` | Compose release hero/build-health notes from diffs, PRs, and run artifacts |

## Workflow

```
Reference ──► Extractor ──► knowledge/ ──► Architect ──► specs/ + ir/contracts/
             (private)      (public)                          │
                                                              ▼
                                                           Coder ──► generated/
                                                              │
                                                              ▼
                                                        Reconciler ──► specs/ + ir/ + agent prompt edits
                                                              │
                                                              ▼
                                                        PostMortem ──► process findings / ADR drafts
                                                              │
                                                              ▼
                                                     Release Editor ──► release_*.md (release mode only)
```

**Key:** Extractor sanitizes findings before writing to `knowledge/` (source references are kept private).

The same phase prompts are used in two modes:

- **PR mode:** `pr.yml` fetches the latest `generated-snapshot`, runs partial regeneration for impacted modules, builds/tests the generated game, records a demo GIF, and exposes Reconciler/PostMortem edits for maintainer review.
- **Release mode:** `release.yml` deletes `generated/`, regenerates the full game from the source-of-truth pack, packages binaries/source, records the canonical gameplay GIF, and asks Release Editor to produce the release narrative.

Manual Claude Code sessions can still invoke the prompts directly, but they are now the exploration path, not the canonical release path.

## Shared State (Filesystem)

```
specs/              # Specifications (Architect writes)
ir/                 # Intermediate representation (Architect writes)
generated/          # Generated code (Coder writes)
knowledge/          # Public findings, no source refs (Extractor writes)
tests/              # Test scenarios
evals/              # Evaluation criteria
reference/          # Read-only reference material (private)
tooling/agents/     # Agent prompts; Reconciler/PostMortem may propose surgical edits
```

## Quality Control

1. **Automated:** sanitization, spec validation, impact analysis, build/test, demo recording
2. **Cross-agent:** Reconciler captures generation drift; PostMortem captures process drift
3. **Human:** maintainer reviews generated PRs, reconciler diffs, release notes, and architectural decisions

## Usage

Each agent prompt is a system instruction. In CI, `tooling/orchestrator_run.py` loads the phase prompt and constrains the allowed tools per phase. In a manual session, load the prompt and give the agent a specific task.

Example:
```
[Load orchestrator.md as system prompt]

User: Start extraction cycle for player movement.
```

## Decision Records

Design decisions are recorded in ADR format. Run-local drafts may stay in private notes, but accepted decisions that define public workflow or source-of-truth rules should graduate into tracked docs in the same change that depends on them.
