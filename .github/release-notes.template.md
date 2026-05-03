{{HERO_PITCH}}

![Worldsmith {{VERSION}} gameplay](https://github.com/RuslanMingaliev/worldsmith/releases/download/{{VERSION}}/worldsmith-{{VERSION}}-gameplay.gif)

## What's new since {{PREV_VERSION}}

{{WHATSNEW_PROSE}}

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

## Stats

**{{MODULE_COUNT}} modules** · ~{{LOC}} lines of Rust · {{TEST_SUMMARY}} · `{{RUSTC_VERSION}}`, edition 2024 · single dependency: `minifb` (window + framebuffer).

<details>
<summary>Generation report (token usage, post-mortem highlights)</summary>

Generated end-to-end from `specs/` on {{GENERATED_AT}} via the multi-agent pipeline (Architect contracts pass → Coder → Reconciler → PostMortem → Release Editor).

### Token usage

{{TOKENS_TABLE}}

### Post-mortem summary

{{POSTMORTEM_SUMMARY}}

</details>
