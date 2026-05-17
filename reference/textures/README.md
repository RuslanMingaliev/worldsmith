# reference/textures

This directory holds the curated corpus that anchors the texture-domain
source of truth. It is split into two slots:

- `good/` -- operator-curated examples of textures that fall inside the
  identity envelope described by `evals/textures/identity.md`. These are
  the positive examples a future generator targets and the corpus that
  numeric thresholds are calibrated against.
- `bad/` -- examples of textures that drift outside the envelope. In a
  constraint-based identity, negative examples often carry more signal
  than positive examples: they pin down exactly which failure modes the
  drift detectors must catch.

Image files (`*.png`, `*.jpg`, `*.jpeg`, `*.webp`, `*.gif`, `*.bmp`,
`*.tga`) are gitignored via `reference/textures/.gitignore`. Only the
READMEs in this subtree are committed -- they serve as directory markers
and explain each slot's purpose so the layout survives a clean checkout
even when the corpus itself is empty.

This corpus is deliberately not "the reference" in the
knowledge-extraction sense. The wider integrity gate in
`tooling/validate_specs.py` treats `reference/` as empty when its contents
are limited to a baseline of READMEs and gitignores, which blocks
`knowledge/` edits made without a real reference loaded. The
`reference/textures/` subtree is excluded from that determination so that
adding curated texture material here never unlocks knowledge-extraction
edits elsewhere. The two source-of-truth tracks are operationally
independent; see `adr/0001-textures-evals-as-source-of-truth.md`.
