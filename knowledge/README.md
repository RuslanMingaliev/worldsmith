# Knowledge

Extracted knowledge about game mechanics, behaviors, and design patterns.

## Purpose

This directory contains findings from reference analysis — the accumulated knowledge about how classic retro shooter mechanics work. This is the **public knowledge base** that informs spec creation.

## What Belongs Here

- Mechanics descriptions (how things behave)
- Design patterns and rules
- Constants and their meanings
- "Feel" descriptions (what makes mechanics satisfying)
- Open questions for future research

## What Does NOT Belong Here

- Source references to private reference material
- Direct code quotes or file paths from reference
- Implementation details tied to specific codebases

## Relationship to Other Directories

```
reference/ → Private source material (gitignored)
knowledge/ → Public findings WITHOUT source refs (versioned)
specs/     → Formalized specifications (versioned)
```

## Workflow

1. **Extractor** reads `reference/`, produces findings (with source refs kept private)
2. Findings are reviewed and sanitized
3. Clean findings are saved to `knowledge/` (without source refs)
4. **Architect** reads `knowledge/`, writes to `specs/`

## File Format

```markdown
# Finding: [Area Name]

## Summary
[2-3 sentence overview]

## Observed Mechanics
### [Mechanic Name]
- **Behavior**: [what it does]
- **Rules**: [governing logic]
- **Feel**: [what makes it distinctive]

## Key Insights
[Design wisdom extracted]

## Open Questions
[Areas for future research]
```
