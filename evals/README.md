# Evals

Evals test the **harness** (generation pipeline), not the game itself.

## Tests vs Evals

| Aspect | tests/ | evals/ |
|--------|--------|--------|
| **What** | Game code | Generation pipeline |
| **Question** | Does the game work? | Can we reliably generate a working game? |
| **Runs on** | Generated code | Specs, IR, agents, process |
| **Analogy** | ML model inference tests | ML model quality benchmarks |

## What Evals Check

### Generation Pipeline
- Specs + IR → compilable code?
- Build succeeds?
- Regeneration produces consistent results?

### Specs Quality
- Complete? (all mechanics covered)
- Consistent? (no contradictions)
- Unambiguous? (clear enough for generation)

### Agent Outputs
- Extractor findings accurate?
- Architect decisions sound?
- Coder follows constraints?

### Coverage
- All specs have corresponding tests?
- All modules have evals?

## Structure

```
evals/
├── README.md               # This file
├── smoke/                  # Manual pre-release runbook (not scripted)
│   └── manual_smoke_checklist.md
├── generation/             # Pipeline evals
│   ├── builds.md
│   └── reproducibility.md
├── specs/                  # Spec quality evals
│   ├── completeness.md
│   └── consistency.md
└── agents/                 # Agent output quality
    └── extractor.md
```

Release criteria are defined by the specs at that git tag, not by separate version folders.

## Eval Format

```markdown
# Eval: [Name]

## Purpose
[What this eval verifies about the harness]

## Automated Checks
- [ ] [check with command]

## Manual Checks
- [ ] [check with instructions]

## Pass Criteria
[When is this eval considered passing]
```

## When to Run

| Trigger | Which evals |
|---------|-------------|
| After spec change | `specs/` |
| After generation | `generation/` |
| Before release (git tag) | All evals must pass + walk the `smoke/` runbook |
| After agent run | `agents/` |

## Background

This separation is inspired by:
- **ML evaluation harnesses** (lm-evaluation-harness, HELM) — assess model quality
- **Acceptance testing** — verify product meets requirements
- **CI/CD quality gates** — criteria for release

Applied to source-of-truth-driven code generation: evals verify the pipeline can reliably produce correct code from the public knowledge/spec/IR pack.

## Related

- `tests/` — Test scenarios for the generated game
- `specs/` — Source of truth for what the game does
- `tooling/agents/` — Agent definitions
