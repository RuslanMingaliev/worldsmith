{{HERO_PITCH}}

![gameplay](https://github.com/RuslanMingaliev/worldsmith/releases/download/{{VERSION}}/worldsmith-{{VERSION}}-gameplay.gif)

## What's new since {{PREV_VERSION}}

{{WHATSNEW_PROSE}}

## Try it

Download a binary for your platform from **Assets** below, unpack, run.
Or build from source:

```bash
unzip worldsmith-game-{{VERSION}}-src.zip
cd worldsmith-game-{{VERSION}}
cargo run --release
```

`W A S D` move · arrows turn · space fire · ESC quit. Reach the cyan **X**.

## Inside the build

- **{{MODULE_COUNT}} modules**, ~{{LOC}} lines of Rust. {{TEST_SUMMARY}}
- Built with `{{RUSTC_VERSION}}`, edition 2024, dependency: `minifb` (window + framebuffer).
- The source archive (`worldsmith-game-{{VERSION}}-src.zip`) is the artifact; the specs at this tag are the source of truth. Regenerating from `specs/` + `ir/` should produce equivalent code (architecture identical; LLM-generated whitespace and comments may vary).

## Read it

This is a spec-driven game. The Rust code is regenerable; the **specs** are what's actually maintained.

- [`specs/`](https://github.com/RuslanMingaliev/worldsmith/tree/{{VERSION}}/specs) — gameplay model, tuning, generation rules.
- [`knowledge/`](https://github.com/RuslanMingaliev/worldsmith/tree/{{VERSION}}/knowledge) — sanitized findings extracted from reference material.
- [`tooling/agents/`](https://github.com/RuslanMingaliev/worldsmith/tree/{{VERSION}}/tooling/agents) — the prompts that generated this code.
- `worldsmith-{{VERSION}}-postmortem.md` (release asset) — full agent-pipeline post-mortem: what worked, what hurt, what to fix next time.

## Assets

{{ASSET_TABLE}}

## Known limitations

See `specs/`'s § Deferred sections at this tag for the full deferred-features list.

<details>
<summary>Generation report (token usage, post-mortem highlights)</summary>

Generated end-to-end from `specs/` on {{GENERATED_AT}} via the multi-agent pipeline (Architect contracts pass → Coder → Reconciler → PostMortem → Release Editor).

### Token usage

{{TOKENS_TABLE}}

### Post-mortem summary

{{POSTMORTEM_SUMMARY}}

</details>
