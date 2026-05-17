# evals/textures

This directory holds the texture-domain drift detectors and the constitution
that defines what they are detecting drift from. The word "evals" here is
borrowed in the playbook sense -- mechanical checks that measure whether a
candidate texture stays within the identity envelope established by the
`reference/textures/good/` corpus and by `evals/textures/identity.md`. It is
not the same system as `tooling/run_evals.py`, which builds the generated
Rust game and runs `cargo test` on it to verify that the generation pipeline
still produces working code. The two share the word "evals" by accident, run
on disjoint inputs (textures vs. code), and have separate entry points. The
name collision is documented here rather than resolved by renaming either
system in this PR; see `adr/0001-textures-evals-as-source-of-truth.md` for
the rationale.

## How to add a new eval

A texture eval is a small script that scores one or more images against a
constraint described in `identity.md`. To add one: drop the implementation
under `tooling/texture_evals/` as a standalone script with a stable CLI
(`<script.py> <path-or-dir> [--out report.json]` is the existing shape used
by `readability.py`); make it emit a JSON array with one record per image,
each record carrying `texture`, `passed`, `scores`, and `violations` fields;
keep `passed` as `null` with `violations` empty for successfully scored
images until thresholds are calibrated against the curated corpus, and emit
`passed: false` with the failure described in `violations` when an input
cannot be scored at all (corrupt or unreadable image) so a directory of
broken files is distinguishable from an empty one; and document the eval's
inputs, outputs, and current threshold state in `identity.md` under either
Required (when the constraint has a numeric threshold) or Calibration
parking lot (when it does not yet). Markdown that
lives in this directory is sanitization-gated by `tooling/validate_specs.py`
on the same terms as `knowledge/*.md`, so the same forbidden-token rules
apply to anything written here.

## Pointer

The decision to treat `reference/textures/{good,bad}/` plus the evals here
as source of truth for the texture domain -- rather than `specs/` -- is
recorded in `adr/0001-textures-evals-as-source-of-truth.md`. Read that ADR
before adding a new eval, changing the constitution, or proposing that a
texture concern move into `specs/`.
