# Specs

Specifications are the source of truth for what the game does.

## Numbering Convention

Files are numbered for reading order (like SysV init or database migrations):

| Range | Category | Description |
|-------|----------|-------------|
| 00-09 | Meta | Project goals, overview |
| 10-19 | System | Architecture, modules |
| 20-39 | Gameplay | Mechanics, entities |
| 40-59 | Content | Levels, assets (reserved) |
| 60-79 | (reserved) | Future use |
| 80-89 | Generation | Rules for code generation |
| 90-99 | (reserved) | Future use |

Gaps allow inserting new files without renumbering.

## File Size Guidelines

| Lines | Recommendation |
|-------|----------------|
| < 200 | OK, can combine with related content |
| 200-500 | Optimal size |
| 500-1000 | Acceptable |
| > 1000 | Split into multiple files |

**Rule:** One file = one concept that can be read and understood in full.

## File Format

All specs are Markdown (`.md`).

Structure:
```markdown
# [Area] Specification

## Overview
[What this covers]

## [Section]
[Content]

## Constraints
[Limitations, invariants]
```

## What Belongs Here

**YES:**
- Game mechanics and rules
- System architecture
- Module responsibilities
- Generation constraints

**NO:**
- Test scenarios → `tests/`
- Success criteria → `evals/`
- Implementation details → `generated/`
- Research/findings → `work/`

## Related

- `evals/` — How we verify success
- `tests/` — Test scenarios and data
- `ir/` — Machine-readable intermediate representation
- `work/` — Decisions, findings, research
