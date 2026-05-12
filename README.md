# worldsmith

> Generate a playable retro shooter from versioned source-of-truth artifacts — and prove they are sufficient by regenerating from scratch every release.

![worldsmith gameplay](https://github.com/RuslanMingaliev/worldsmith/releases/download/2026.04/worldsmith-2026.04-gameplay.gif)

*First-person gameplay from release [`2026.04`](https://github.com/RuslanMingaliev/worldsmith/releases/tag/2026.04). The Rust binary in this clip was generated end-to-end from the specs in this repo, including the column-based raycaster renderer (`specs/45`) and the autopilot bot's kiting / pathfinding behavior (`specs/30`).*

## What this is

worldsmith is an experiment in operating a generated game from public, reviewable source-of-truth artifacts. The game mechanics chain is `reference/` → `knowledge/` → `specs/` + per-module `ir/contracts/` → disposable Rust; the release chain proves that this pack is sufficient by rebuilding `generated/` from empty on every tagged version.

Four releases have shipped (`2026.01` through `2026.04`). Current scope is a first-person column-based raycaster with multiple enemies per level, hitscan combat, momentum-based movement, pickups, and an autopilot bot that does line-of-sight-gated firing, kiting at melee range, BFS pathfinding around walls, and pickup-seeking detours. The top-down view remains in the codebase as `--render-mode=topdown` because it is still the fastest debug view for bot pathing, sprite positions, level geometry, and autopilot decisions.

The proposition the project tests: *can a structured source-of-truth pack be enough to reproduce a working, non-trivial game?* The answer is only trustworthy if the process is strict: sanitization gates, post-generation reconciliation, full regen from empty `generated/` on every release, and a multi-agent pipeline whose phases (Extractor / Architect / Coder / Reconciler / PostMortem / Release Editor) are each runnable from CI or by hand.

The scope of "spec-driven" is deliberate, not dogmatic. For mechanics and generated Rust, specs and IR are the source of truth. For domains that are not naturally deterministic prose-and-number artifacts (for example future visual identity work), the right source of truth may be a curated corpus plus evals instead. The project rule is not "everything must be a spec"; it is "each domain must have an explicit, versioned source of truth and checks that catch drift."

## Why it might be interesting

- **The chain closes end-to-end.** `reference/` → `knowledge/` (~1,879 LoC across 12 files) → `specs/` (~3,639 LoC across 14 files) + `ir/contracts/` (per-module formal contracts) → `generated/game/src/` (~3,607 LoC of Rust across 14 modules at `2026.04`). Every release tag is a full regeneration from empty `generated/`, not an incremental edit — a `release.yml` invocation runs the agent phases from scratch and produces a binary, source archive, demo GIF, release notes, and PostMortem as paired evidence.
- **The pipeline is part of the artifact.** `tooling/agents/`, `.github/workflows/pr.yml`, `.github/workflows/release.yml`, `generated-snapshot`, and the release-note composer are not supporting scripts around the experiment; they are the experiment's operational surface. PR-mode answers "what changed from this source-of-truth diff?", while release-mode answers "can the whole pack reproduce the game from zero?"
- **Honest validation gates.** [`tooling/check_sanitization.py`](tooling/check_sanitization.py) rejects source-game proper nouns and identifiers in public artifacts (including release notes — the 2026.04 publish hit this when the release-editor agent quoted an identifier-prefix verbatim, and the gate blocked it). [`tooling/validate_specs.py`](tooling/validate_specs.py) *refuses* to let `knowledge/` change when `reference/` is empty — an agent cannot "remember" mechanics from training data and pass them off as extracted knowledge.
- **Reconciliation, not just generation.** When the Coder agent invents constants the spec didn't pin or simplifies a contract shape, the Reconciler captures it back into [`specs/25_game_tuning.md`](specs/25_game_tuning.md) and the relevant [`ir/contracts/<module>.yaml`](ir/contracts/). PostMortem then audits the run as a process and proposes surgical edits to the agent prompts themselves — so the next regen does not repeat the same class of mistake.
- **Two-mode regeneration.** Releases regen the full tree from empty `generated/` (proves the source-of-truth pack is self-sufficient). PRs use partial regen — [`tooling/partial_regen.py`](tooling/partial_regen.py) computes the affected module set from a spec/IR diff, baselines from a long-lived `generated-snapshot` branch that's force-pushed after every regen-bearing merge, and only re-emits the affected modules. Both paths converge on the same agent prompts; the mode is the variable.
- **Agent-task driven gameplay slices.** Substantial features (the raycaster migration, the smart-bot rewrite, the new default level) shipped as multi-PR series filed via [`/create-agent-task`](.claude/skills/create-agent-task) → [`.github/workflows/agent-intake.yml`](.github/workflows/agent-intake.yml) → Extractor + Architect drafts a PR → maintainer reviews, merges, repeats. The release-notes generator groups such series into a single thematic bullet for the user.

## How it works

```
   reference/        private corpus (gitignored, may be empty)
       │
       ▼   Extractor
   knowledge/        sanitized public mechanics notes
       │
       ▼   Architect
   specs/, ir/       enforceable design + per-module formal contracts
       │
       ▼   Coder
   generated/game/   disposable Rust
       │
       ▼   Reconciler
   specs/', ir/'     captured drift folded back into source-of-truth
       │
       ▼   PostMortem
   tooling/agents/'  surgical prompt edits informed by this run's pain
       │
       ▼   Release Editor                    (release.yml only)
   release_*.md      hero + buildhealth caveat → composed release notes
```

Each arrow is owned by a named agent — see [`tooling/agents/`](tooling/agents/) for the prompts. CI runs the agents through [`.github/workflows/release.yml`](.github/workflows/release.yml) (full regen, publishes a draft release on GitHub) and [`.github/workflows/agent-intake.yml`](.github/workflows/agent-intake.yml) + [`pr.yml`](.github/workflows/pr.yml) (file an issue → agents draft a PR → partial regen + cargo build/test + recorded demo GIF on every push). Manual generation in a Claude Code session is still supported and useful for ad-hoc spec exploration, but the typical loop is now `gh issue create` → review → merge, not chat-and-paste. Full CI architecture lives in [CLAUDE.md](CLAUDE.md).

## Try it

The repo does not contain a buildable game — `generated/` is gitignored on principle (it's disposable, regenerated from specs). Two paths to actually run it:

**Just play it.** Download the pre-built binary for your platform from the [latest release](https://github.com/RuslanMingaliev/worldsmith/releases/latest):
- Linux: `worldsmith-game-<tag>-linux-x86_64.tar.gz`
- macOS: `worldsmith-game-<tag>-macos-aarch64.tar.gz`
- Windows: `worldsmith-game-<tag>-windows-x86_64.zip`

**Build from the generated source.** Same release page, grab `worldsmith-game-<tag>-src.zip`:

```bash
unzip worldsmith-game-2026.04-src.zip -d worldsmith-game
cargo run --release --manifest-path worldsmith-game/Cargo.toml
```

Controls: `WASD` move, arrows turn, `Space` fire, `ESC` quit. Default renderer is the first-person raycaster; pass `--render-mode=topdown` for the debug 2D view.

The source archive is the snapshot of generated Rust produced from the specs at that tag — read it as the answer to "what does this pipeline actually emit?". To regenerate it from scratch yourself, dispatch [`release.yml`](.github/workflows/release.yml) with a new version input, or run the phases via [`tooling/orchestrator_run.py`](tooling/orchestrator_run.py) locally (see [`tooling/agents/`](tooling/agents/) and [CLAUDE.md](CLAUDE.md)).

## Releases

Tags follow the `yyyy.vv` scheme — `yyyy` is the year, `vv` is a zero-padded sequence within that year. Each tagged release is built from a clean regeneration to prove the source-of-truth pack is self-sufficient, and ships:

- pre-built binaries for Linux / macOS / Windows
- the generated Rust source as `*-src.zip`
- a recorded gameplay GIF
- a PostMortem write-up of the run (what the agents did, what hurt, what got reconciled)

Current tags: [`2026.01`](https://github.com/RuslanMingaliev/worldsmith/releases/tag/2026.01), [`2026.02`](https://github.com/RuslanMingaliev/worldsmith/releases/tag/2026.02), [`2026.03`](https://github.com/RuslanMingaliev/worldsmith/releases/tag/2026.03), [`2026.04`](https://github.com/RuslanMingaliev/worldsmith/releases/tag/2026.04). Pre-release checks live in [`evals/`](evals/).

## Core principles

- Every domain needs an explicit source of truth. For generated game code, that is `knowledge/`, `specs/`, and `ir/contracts/`.
- Specs are not a dumping ground for every future asset or aesthetic judgment; use the source-of-truth form the domain can actually sustain.
- Generated code is disposable; release artifacts are evidence of what a source-of-truth pack produced at a tag.
- Two modes by intent: PR regen is partial and baselined from the most recent snapshot; release regen is full from empty `generated/` and proves the source-of-truth pack is sufficient. Don't blur the modes.
- Reconcile after generation — sync specs and per-module IR contracts with what was actually produced. Drift is captured back, not papered over.
- PostMortem audits the run as a process and writes its findings into the agent prompts themselves — recurring failure modes become checklist items, not folklore.
- Versions are git tags following `yyyy.vv`, not hardcoded in generated code.
- Public release notes are content-driven (read the diff first, attribute to PRs second) and lean — the GitHub compare view handles the audit trail, the hero handles the story.

## Repository layout

<details>
<summary>Click to expand</summary>

- `specs/` — human-readable design and generation constraints
- `ir/` — compact machine-oriented representation and per-module contracts derived from specs
- `knowledge/` — extracted knowledge from reference (public)
- `tests/` — test scenarios
- `evals/` — harness evaluation criteria
- `tooling/` — scripts, validators, release composition, and agent prompts
- `.github/workflows/` — PR-mode partial regen, release-mode full regen, post-merge snapshots, and PR demo artifact cleanup
- `generated/` — disposable generated implementation (gitignored)
- `work/` — private notes, decisions (gitignored)
- `reference/` — research material (gitignored, may be empty)

`ir/module_plan.yaml` defines every generated module, its responsibility, and a `depends_on` list for understanding regeneration scope.

</details>

## License and scope

Everything in this repo (code, specs, IR, knowledge files, tooling, generated samples that ship with tags) is released under the MIT License — see [LICENSE](LICENSE).

Two directories are gitignored and not part of the public release:

- `reference/` — private research corpus used for mechanic extraction.
- `work/` — private intermediate findings and drafts that graduate into `knowledge/` and `specs/` when ready.

Anything outside those two paths is MIT and safe to share. Sanitised findings or specs merged into the repository fall under the same license automatically.
