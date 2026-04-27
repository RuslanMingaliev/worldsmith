# Agent System

Multi-agent architecture for spec-driven game generation.

## Agents

| Agent | File | Responsibility |
|-------|------|----------------|
| **Orchestrator** | `orchestrator.md` | Coordination, delegation, escalation |
| **Extractor** | `extractor.md` | Extract knowledge from reference |
| **Architect** | `architect.md` | Design specs and IR |
| **Coder** | `coder.md` | Generate code |
| **Researcher** | `researcher.md` | Answer questions, explore |
| **TestBuilder** | `test_builder.md` | Create test models |
| **EvalWriter** | `eval_writer.md` | Write evaluation criteria |
| **Reconciler** | `reconciler.md` | Reconcile code with specs after generation |
| **PostMortem** | `postmortem.md` | Audit the run as a process; propose changes to agent prompts / tooling / ADRs |

## Workflow

```
Reference ──► Extractor ──► knowledge/ ──► Architect ──► Coder ──► Evals ──► Reconciler ──► PostMortem
             (private)      (public)           │            │                    │              │
                                               ▼            ▼                   ▼              ▼
                                            specs/      generated/        specs updated   process recs
                                              ir/                         (closes loop)   (closes meta-loop)
```

**Key:** Extractor sanitizes findings before writing to `knowledge/` (source references are kept private).

## Shared State (Filesystem)

```
specs/              # Specifications (Architect writes)
ir/                 # Intermediate representation (Architect writes)
generated/          # Generated code (Coder writes)
knowledge/          # Public findings, no source refs (Extractor writes)
tests/              # Test scenarios
evals/              # EvalWriter output
reference/          # Read-only reference material (private)
```

## Quality Control

1. **Automated:** Build, test, evals
2. **Cross-agent:** Architect reviews Extractor, etc.
3. **Human:** Architectural decisions, escalations

## Usage

Each agent prompt is a system instruction. Load the prompt and give the agent a specific task.

Example:
```
[Load orchestrator.md as system prompt]

User: Start extraction cycle for player movement.
```

## Decision Log

Design decisions are recorded in ADR format in the project's private notes.
