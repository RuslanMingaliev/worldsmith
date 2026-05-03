# worldsmith

> Generate a playable retro shooter from spec files — and prove the specs are sufficient by regenerating from scratch every release.

![worldsmith gameplay](https://github.com/RuslanMingaliev/worldsmith/releases/download/2026.02/worldsmith-2026.02-gameplay.gif)

*Top-down gameplay from release [`2026.02`](https://github.com/RuslanMingaliev/worldsmith/releases/tag/2026.02). The Rust binary in this clip was generated end-to-end from the specs in this repo.*

## What this is

worldsmith is an experiment in spec-driven game generation. A pipeline takes extracted mechanics knowledge, formalises it into specs, and regenerates a Rust game from those specs. Two releases shipped so far (`2026.01`, `2026.02`); current scope is a top-down 2D shooter with one level, one enemy type, hitscan combat, momentum-based movement, and an autopilot test runner — not a full game, not multi-level, not first-person yet.

The proposition the project tests: *can a structured spec pack alone be enough to reproduce a working game?* — and the discipline that makes the answer trustworthy: sanitization gates, post-generation reconciliation, full regen on every release.

## Why it might be interesting

- **The chain closes end-to-end.** `reference/` → `knowledge/` (1,185 LoC across 7 files) → `specs/` (2,304 LoC across 12 files) → `ir/module_plan.yaml` (11 modules with explicit dependency graph) → `generated/game/src/` (3,970 LoC of Rust). Every release tag is a full regeneration from scratch, not an incremental edit.
- **Honest validation gates.** [`tooling/check_sanitization.py`](tooling/check_sanitization.py) rejects source-game proper nouns and identifiers in public artifacts. [`tooling/validate_specs.py`](tooling/validate_specs.py) *refuses* to let `knowledge/` change when `reference/` is empty — so an agent cannot "remember" mechanics from training data and pass them off as extracted knowledge. Both gates run in CI, not just in docs.
- **Reconciliation, not just generation.** When the Coder agent invents constants the spec didn't pin, the Reconciler captures them back into [`specs/25_game_tuning.md`](specs/25_game_tuning.md). Spec drift is a first-class artifact (ADRs, "deferred" markers) instead of being papered over.
- **Incremental regeneration.** [`tooling/partial_regen.py`](tooling/partial_regen.py) computes the impact of a spec change and only regenerates affected modules, reusing the previous release as baseline — no rebuilding the world for a one-line edit.

## How it works

```
   reference/        private corpus (gitignored, may be empty)
       │
       ▼   Extractor
   knowledge/        sanitized public mechanics notes
       │
       ▼   Architect
   specs/            enforceable design contracts
       │
       ▼   (formalisation)
   ir/               machine-oriented module plan
       │
       ▼   Coder
   generated/game/   disposable Rust
       │
       ▼   Reconciler · PostMortem
   specs/, ADRs      spec drift captured back
```

Each arrow is owned by a named agent — see [`tooling/agents/`](tooling/agents/) for the prompts. Generation is normally driven manually in a Claude Code session, but the same agents are also wired into a GitHub Issues → PR workflow ([`.github/workflows/agent-intake.yml`](.github/workflows/agent-intake.yml) + [`pr.yml`](.github/workflows/pr.yml)) that posts a recorded demo GIF and inline review suggestions on eligible source-of-truth PRs (same-repo PRs that touch `specs/`, `knowledge/`, `ir/`, or `tooling/agents/`; fork PRs are skipped because the OAuth secret isn't available to them). Full CI architecture lives in [CLAUDE.md](CLAUDE.md).

## Try it

The repo does not contain a buildable game — `generated/` is gitignored on principle (it's disposable, regenerated from specs). Two paths to actually run it:

**Just play it.** Download the pre-built binary for your platform from the [latest release](https://github.com/RuslanMingaliev/worldsmith/releases/latest):
- Linux: `worldsmith-game-<tag>-linux-x86_64.tar.gz`
- macOS: `worldsmith-game-<tag>-macos-aarch64.tar.gz`
- Windows: `worldsmith-game-<tag>-windows-x86_64.zip`

**Build from the generated source.** Same release page, grab `worldsmith-game-<tag>-src.zip`:

```bash
unzip worldsmith-game-2026.02-src.zip -d worldsmith-game
cargo run --release --manifest-path worldsmith-game/Cargo.toml
```

Controls: `WASD` move, arrows turn, `Space` fire, `ESC` quit.

The source archive is the snapshot of generated Rust produced from the specs at that tag — read it as the answer to "what does this pipeline actually emit?". To regenerate it from scratch yourself, run the agent pipeline (see [`tooling/agents/`](tooling/agents/) and [CLAUDE.md](CLAUDE.md)).

## Releases

Tags follow the `yyyy.vv` scheme — `yyyy` is the year, `vv` is a zero-padded sequence within that year. Each tagged release is built from a clean regeneration to prove the specs are self-sufficient, and ships:

- pre-built binaries for Linux / macOS / Windows
- the generated Rust source as `*-src.zip`
- a recorded gameplay GIF
- a PostMortem write-up of the run (what the agents did, what hurt, what got reconciled)

Current tags: [`2026.01`](https://github.com/RuslanMingaliev/worldsmith/releases/tag/2026.01), [`2026.02`](https://github.com/RuslanMingaliev/worldsmith/releases/tag/2026.02). Pre-release checks live in [`evals/`](evals/).

## Core principles

- Specs are the source of truth.
- Generated code is disposable.
- Regeneration is incremental by default; releases regenerate from scratch.
- Evaluation is mandatory.
- Reconcile after generation — sync specs with what was actually produced.
- Versions are git tags following `yyyy.vv`, not hardcoded in generated code.

## Repository layout

<details>
<summary>Click to expand</summary>

- `specs/` — source of truth for design and generation constraints
- `ir/` — compact machine-oriented representation derived from specs
- `knowledge/` — extracted knowledge from reference (public)
- `tests/` — test scenarios
- `evals/` — harness evaluation criteria
- `tooling/` — scripts and agent prompts
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
