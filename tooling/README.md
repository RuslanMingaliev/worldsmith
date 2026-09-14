# Generation tooling

Run the Python regression tests without invoking an LLM or building the game:

```bash
python3 -m unittest discover -s tooling/tests -v
```

The PR workflow runs these checks in its unconditional `validate` job, including
for tooling-only and fork PRs. Game scenarios remain under `tests/`; Python
tooling tests live under `tooling/tests/`.

Preview regeneration scope locally with repository-relative paths:

```bash
python3 tooling/partial_regen.py --changed ir/contracts/player_state.yaml --json
```

An explicit empty `--changed` list selects nothing without consulting Git.
Without `--changed`, the planner compares `--base` (default `origin/main`) to HEAD.

## Decision 1: Never silently skip an unmapped generation input

Date: 2026-09-14

Context: Most contract shards and several specs selected no modules. A PR could
pass by testing its baseline implementation. Scenario-only PRs did not open the
generation job at all, despite scenarios being planner inputs. The old manual
scope warning referred to a `--target` flag the planner did not implement.

Decision: Reuse `source_of_truth_paths.py` in the planner and include `tests/`
in the prefixes shared by PR and snapshot workflows. Contract shards select their
named module and its transitive consumers. Existing per-module mappings remain
partial. Any source-of-truth path without a mapping selects all modules and emits
a warning on stderr, including shared contracts and cross-cutting specs. Check
each changed path independently, even when another path already selected modules.

Consequences: Unmapped inputs cause broader, more expensive PR generation until
an explicit mapping is added. These PR runs still use the snapshot baseline;
they do not replace the release requirement to regenerate from an empty tree.
Changes outside generation inputs, including Python tooling tests, leave game
generation disabled.

## Running a phase locally

Install the selected CLI and authenticate it locally. The wrapper accepts saved
CLI authentication; GitHub credentials are not required for a local Coder phase.
For Codex, use `codex login`, then check `codex login status`. See the official
[authentication documentation](https://learn.chatgpt.com/docs/auth).

Run from a disposable checkout with a generated baseline for partial changes:

```bash
python3 tooling/orchestrator_run.py \
  --provider codex --phase coder --mode release --workflow pr \
  --target-modules player_state \
  --scope 'Regenerate player_state from its current specs and contract.' \
  --timeout-seconds 1800
```

This invokes a real model and edits files. `--target-modules` requires an existing
`generated/game/src/` baseline; it restores unselected source files on success,
failure, and timeout. It does not constrain changes elsewhere in the checkout.
Omitting it allows full phase scope. A release still requires clean generation.
Each Coder invocation must write a fresh, nonempty `artifacts/coder_report.md`.

`--provider` overrides `WORLDSMITH_AGENT_PROVIDER` (default `claude`). `--model`
overrides `WORLDSMITH_CODEX_MODEL` or `WORLDSMITH_CLAUDE_MODEL`. Without an override,
Claude retains its existing per-phase models and Codex uses its CLI configuration.
The wrapper records `(CLI default)` when Codex does not report the model ID.

Both providers have a wall-clock timeout (`--timeout-seconds`, default 18000).
`--max-turns` remains Claude-only. Failed or incomplete CLI results fail the phase;
a newly written `artifacts/blocker.md` also fails it. Prompts, transcripts, stderr,
and normalized usage are saved in the ignored `artifacts/` directory. Copy them
elsewhere before repeating the same phase if you need to preserve its transcript.

## Selecting the provider in GitHub Actions

| Setting | Effect |
| --- | --- |
| Repository variable `WORLDSMITH_AGENT_PROVIDER` | `claude` (default) or `codex`, used by PR, release, and issue Architect phases |
| Release dispatch input `provider` | Override for that run: `default`, `claude`, or `codex` |
| Repository variable `WORLDSMITH_CODEX_MODEL` | Optional explicit Codex model |
| Repository secret `OPENAI_API_KEY` | Required for Codex; exposed as `CODEX_API_KEY` only on the selected agent steps |
| Repository secret `CLAUDE_CODE_OAUTH_TOKEN` | Required for Claude, including Extractor when the selected provider is Codex |

For a first CI trial, configure `OPENAI_API_KEY`, then select `codex` in the
release dispatch form with `publish=false`. That runs the existing release
pipeline: it can create a drift PR and uploads artifacts even without publishing
a release. Changing the repository variable switches subsequent PR and intake
runs as well. No secrets, repository variables, or remote runs are configured by
the code change itself.

`install_agent_cli.sh` installs only the selected CLI, plus Claude for intake's
Extractor. Codex is pinned to `0.153.4`; the setup script accepts an explicit
`WORLDSMITH_CODEX_CLI_VERSION` environment override for version testing.

## Decision 2: Share phase execution and keep provider protocols separate

Date: 2026-09-14

Context: The headless runner used Claude-specific flags and JSON results.
Local Codex experiments should run through the same phase prompts, reporting,
scope restoration, and CI pipeline without changing the game's design.

Decision: `agent_providers.py` owns CLI commands and result parsing;
`orchestrator_run.py` owns prompts, subprocess lifetime, artifacts, and phase
checks. Claude is the default. Codex runs `exec --json --ephemeral` with a
`workspace-write` sandbox and noninteractive approvals. It never invokes Claude
as a fallback. The existing Extractor remains explicitly Claude-only because
its no-shell tool policy has no verified Codex equivalent. Requesting Codex for
Extractor fails before invoking a model.

In GitHub Actions, Codex receives network access for Cargo/GitHub and write access
to `CARGO_HOME` (default `~/.cargo`), in addition to its workspace. Local runs retain
the user's network configuration and receive no extra writable directories.
Provider credentials are excluded from Codex shell subprocess environments;
`GH_TOKEN` remains available for authorized GitHub queries. This is a direct CLI
integration, not the API-proxy credential isolation of the official Codex action.
See the official [noninteractive execution](https://learn.chatgpt.com/docs/non-interactive-mode)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

Consequences: Codex's completed-turn count is not comparable to Claude's internal
turn count. Codex input usage includes cached input, so the adapter subtracts it
into `cache_read` to avoid double counting; cache creation is not reported and
is recorded as zero. The existing `WORLDSMITH_MAX_TOKENS_PER_RUN` check counts
noncached input plus output after each successful CLI result. It excludes cached
usage and failed/incomplete responses, can overshoot during a phase, and is not
a monetary spending limit. Release tables show the provider; old usage rows
without a provider remain attributable to Claude.

Validation: provider protocol and subprocess tests use fake CLIs. Real Codex
0.153.4 runs verified both a small fixture and a partial `player_state` generation
against snapshot `af88b10` (source PR #80). The game pilot first exposed conflicting
armor prose, then an unspecified collision-velocity rule. Clarifications preserve
the existing contract algorithm and snapshot behavior. After a focused Coder
repair, the game passed 91 tests (baseline 73), including all 11 prior module tests
and 18 added boundary tests. Independent differential checks compared 42,013
damage, pickup/tint, and movement states against the baseline; all passed. Only
the target source changed. Use separate Cargo target directories for the game and
the differential harness so binaries from identical package names cannot mask
which tests actually ran. This verifies one local Coder phase and its repair loop;
full game generation and an actual GitHub Actions run remain untested with Codex.
