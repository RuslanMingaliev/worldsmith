# ADRs (Architecture Decision Records)

This directory holds committed, accepted ADRs for Worldsmith. Each ADR is a
small, immutable record of a decision that shaped the project: the context in
which it was made, the decision itself, and the consequences it carries
forward. Local-only drafts and scratchpads (kept outside the tracked tree per
CLAUDE.md) are not records -- only files committed here are.

## Naming

`NNNN-kebab-title.md`, with `NNNN` as a zero-padded four-digit sequence number
allocated in commit order. Numbers are never reused; superseding an earlier
ADR is done by adding a new ADR that references the older one in its Context
section, not by editing the earlier file in place.

## Format

Each ADR file uses this structure:

- `# Title` (H1; matches the title used in `NNNN-kebab-title.md`)
- `Date: YYYY-MM-DD`
- `## Context` -- the situation and forces that made a decision necessary
- `## Decision` -- what was decided, stated declaratively
- `## Consequences` -- what follows from the decision, both positive and
  negative, including any new obligations on agents, gates, or workflows

ASCII text only, matching the rest of the tracked tree.

## Follow-up: agent prompts

The agent prompts in `tooling/agents/*.md` are NOT updated as part of an ADR
being accepted. Migrating those prompts to reflect new ADRs (for example,
teaching the Architect or Reconciler about `adr/` and any new domain
conventions) is a deliberate, separate PR. This keeps each ADR change small
and auditable, and avoids bundling prompt edits with structural decisions.
