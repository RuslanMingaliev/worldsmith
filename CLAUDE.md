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

## PR workflow

`.github/workflows/pr.yml` runs on every pull request. Two jobs:

- **`validate`** — always runs. Validates specs/IR/knowledge integrity, checks `generated/` for manual edits, and computes whether the PR touches `specs/**`, `knowledge/**`, `ir/**`, or `tooling/agents/**` (the source-of-truth paths).
- **`regenerate-and-build`** — runs only when (a) source-of-truth paths changed AND (b) the PR head is from this repo (fork PRs are skipped because the OAUTH secret is unavailable to forked workflows). Steps:
  1. Download last release's `worldsmith-game-X-src.zip` as a baseline and unpack into `generated/game/`.
  2. `tooling/partial_regen.py --json` — determine which modules need regeneration.
  3. Coder / Reconciler / PostMortem phases via `tooling/orchestrator_run.py --target-modules ...`. The harness snapshots `generated/game/src/` and reverts any file touched outside the listed modules — so Coder can't silently scope-creep.
  4. `cargo build/test --release` (under `xvfb-run` because autopilot tests need a display).
  5. Record `release/demo.gif` via `tooling/record_autopilot.sh`.
  6. Reconciler's edits to `specs/`, `knowledge/`, `ir/`, `tooling/agents/` and PostMortem's surgical edits to `tooling/agents/*.md` are captured as a unified diff and posted as **inline review suggestions** via `reviewdog/action-suggester` (only on lines this PR already touches; the rest of the diff is in the `agent_changes.diff` artifact).
  7. PostMortem's narrative analysis (run summary, "what hurt", ADR drafts) is saved to `artifacts/postmortem.md` and linked from the PR comment.
  8. The demo GIF is uploaded to a single shared `pr-assets` branch (auto-created on first run from `main`'s HEAD) as `pr-<N>-run-<run_id>-demo.gif`, then embedded inline in the PR status comment via its `raw.githubusercontent.com` URL. PR number + run id make filenames unique, so concurrent PR runs don't race. The branch is **never automatically pruned** — see Known Issues for cleanup.

### Branch protection (one-time setup)

Settings → Branches → main → "Require status checks to pass before merging":

- Required: `validate`
- Required: `regenerate-and-build`

`regenerate-and-build` is conditionally `if:`-skipped on fork PRs and on PRs that don't touch source-of-truth paths. GitHub treats a skipped job as a passing required check, so skipping doesn't block merge. A skipped check on a fork PR means the maintainer must rerun the workflow from this repo's branch (or close-and-reopen as a maintainer) to actually validate regeneration before merging.

### Cost control

- `concurrency: cancel-in-progress: true` per PR — re-pushes cancel the prior run, but tokens already spent are not refunded.
- `WORLDSMITH_MAX_TOKENS_PER_RUN` repo variable caps per-run spend (enforced in `orchestrator_run.py`).
- A PR that touches `specs/00_project_goal.md` (or another global-trigger file in `partial_regen.py`) regenerates ALL modules — effectively a full release run. This is intentional: such PRs are rare, and the alternative (forcing them through `release.yml`) blocks otherwise valid edits.

## Issue-driven agent flow

`.github/workflows/agent-intake.yml` lets a maintainer launch the Extractor + Architect pipeline from a GitHub Issue. End-to-end:

1. Anyone files an issue using `.github/ISSUE_TEMPLATE/agent-task.yml` — fields are Goal, Scope, Affected modules (optional), Constraints, Acceptance criteria. The form auto-applies the inert label `agent:task`. **Filing alone does NOT spend tokens.**
2. A maintainer (admin / write / maintain) reviews the issue and applies `agent:run`. The workflow verifies the sender's permission via `gh api .../collaborators/.../permission` before doing anything else.
3. The job clones the public reference repo from `vars.WORLDSMITH_REFERENCE_REPO` into `reference/`, runs Extractor, runs `check_sanitization.py` + `validate_specs.py`, runs Architect, validates again, wipes `reference/`, commits to `agent/issue-<N>`, force-pushes, and opens a draft PR `Closes #<N>`.
4. The PR triggers the existing `pr.yml` flow — Coder / Reconciler / PostMortem on the affected modules, plus `cargo build/test` and the demo GIF.
5. On success the workflow swaps the issue's labels to `agent:in-pr`. On failure (including the `EXTRACTOR_BLOCKED` sentinel from an empty reference clone), it comments the reason and applies `agent:failed`. Re-applying `agent:run` re-runs and force-pushes onto the same branch.

Local helper: the project-level skill `/create-agent-task` (`.claude/skills/create-agent-task/`) walks you through writing a well-formed issue body for `gh issue create --body-file -`.

### One-time configuration

- Repo variable `WORLDSMITH_REFERENCE_REPO` — clone URL (public HTTPS) of the reference corpus.
- Labels: `agent:task`, `agent:run`, `agent:in-pr`, `agent:failed`.
- Recommended: Settings → Issues → restrict label management to collaborators (defense-in-depth on top of the workflow's permission gate).

### Cost control

- Permission gate, label gate, and reference clone all run before the first `claude` invocation — unauthorized triggers spend no tokens.
- `WORLDSMITH_MAX_TOKENS_PER_RUN` is honoured by both phases via `orchestrator_run.py`.
- `concurrency: cancel-in-progress: true` keyed on issue number — re-labeling the same issue cancels the prior run.

## Known Issues

- Top-down view, not raycasting
- The shared `pr-assets` branch grows by one file per PR run and is never pruned automatically. Periodic cleanup is needed — either a cron workflow that drops files older than N days, or a `pull_request: types: [closed]` workflow that deletes `pr-<N>-*.gif` for the closed PR. Not implemented yet.
