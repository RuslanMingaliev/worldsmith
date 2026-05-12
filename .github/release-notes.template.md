{{HERO_PITCH}}

![Worldsmith {{VERSION}} gameplay](https://github.com/RuslanMingaliev/worldsmith/releases/download/{{VERSION}}/worldsmith-{{VERSION}}-gameplay.gif)

## How it was generated

End-to-end on {{GENERATED_AT}} through the multi-agent pipeline: Architect drafts the per-module contracts, Coder writes the Rust, Reconciler reconciles code against specs, PostMortem audits the run, Release Editor authors these notes.

{{TOKENS_TABLE}}

Plus {{CACHE_READ_TOTAL}} cache reads / {{CACHE_CREATION_TOTAL}} cache creation — the inlined frozen-context prefix (specs + IR + shared contract) is shared across phases, so the second Architect / Coder / Reconciler call onward serves the prefix from cache instead of re-billing it.

**Output: {{MODULE_COUNT}} modules, ~{{LOC}} lines of Rust.** Built with `{{RUSTC_VERSION}}`, edition 2024, single runtime dependency: `minifb` (window + framebuffer). {{TEST_SUMMARY}}.

{{BUILD_HEALTH_NOTE}}

## Try it

Download a binary for your platform from the assets list below this release page, unpack, run.
Or build from source:

```bash
unzip worldsmith-game-{{VERSION}}-src.zip
cd worldsmith-game-{{VERSION}}
cargo run --release
```

`W A S D` move · arrows turn · space fire · ESC quit. Reach the cyan **X**.

## Read it

This is a spec-driven game. The Rust code is regenerable; the **specs** are what's actually maintained. Regenerating from `specs/` + `ir/` at this tag should produce equivalent code (architecture identical; LLM-generated whitespace and comments may vary).

- [`specs/`](https://github.com/RuslanMingaliev/worldsmith/tree/{{VERSION}}/specs) — gameplay model, tuning, generation rules.
- [`knowledge/`](https://github.com/RuslanMingaliev/worldsmith/tree/{{VERSION}}/knowledge) — sanitized findings extracted from reference material.
- [`tooling/agents/`](https://github.com/RuslanMingaliev/worldsmith/tree/{{VERSION}}/tooling/agents) — the prompts that generated this code.
- [`worldsmith-{{VERSION}}-postmortem.md`](https://github.com/RuslanMingaliev/worldsmith/releases/download/{{VERSION}}/worldsmith-{{VERSION}}-postmortem.md) — full agent-pipeline post-mortem: what worked, what hurt, what to fix next time.
- [Full PR-by-PR diff vs `{{PREV_VERSION}}`](https://github.com/RuslanMingaliev/worldsmith/compare/{{PREV_VERSION}}...{{VERSION}}).
