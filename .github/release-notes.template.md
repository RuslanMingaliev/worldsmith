Tagged generated sample of the retro shooter. The whole `generated/game/` tree was regenerated end-to-end from the specs on {{GENERATED_AT}} via the multi-agent pipeline (Architect contracts pass → Coder waves → Reconciler → PostMortem).

![gameplay](https://github.com/RuslanMingaliev/worldsmith/releases/download/{{VERSION}}/worldsmith-{{VERSION}}-gameplay.gif)

## What's in this build

- {{MODULE_COUNT}} modules, ~{{LOC}} lines of Rust
- {{TEST_SUMMARY}}
- Built with `{{RUSTC_VERSION}}`, edition 2024, dependency: `minifb` (window + framebuffer)

## Controls

`W A S D` move · arrows turn · space fire · ESC quit.

## Assets

{{ASSET_TABLE}}

## Reproducibility

This is a "generated sample". The source archive is the artifact; specs at this tag are the source of truth. Regenerating from `specs/` + `ir/` should produce equivalent code (architecture identical; LLM-generated whitespace/comments may vary).

## Generation report

Pipeline run via the `release.yml` GitHub Actions workflow.

### Token usage

{{TOKENS_TABLE}}

### Post-mortem summary

{{POSTMORTEM_SUMMARY}}

## Known limitations

See `specs/` directory at this tag for the deferred-features list.
