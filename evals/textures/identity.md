# Texture Identity Constitution

This file is sanitization-gated. The same forbidden-token rules that apply to
`knowledge/*.md` apply here: no proper nouns of any source or reference game,
no release-year sentinels, no source-code identifiers from a reference. The
gate is enforced mechanically by `tooling/validate_specs.py`, which runs
`tooling/check_sanitization.py` over every top-level markdown file in
`evals/textures/` as part of every full validation (the glob is
non-recursive). A leak fails the validate run with the same loud banner used
for `knowledge/` leaks.

This is a constitution, not a spec: it describes identity through constraints
rather than enumerating pixels. The constraints below are deliberately
expressed as rules the corpus and any generated candidate must satisfy, not
as recipes for how to produce a texture. Numeric thresholds are placeholders
and live in the Calibration parking lot until the corpus is large enough to
fit them from data.

## Forbidden

- Photographic realism. Any candidate that reads as a photograph or a
  photorealistic render fails.
- Smooth gradients across the surface that obscure tileable seams or wash out
  edges. A texture that looks airbrushed is not in the corpus.
- High-frequency noise without underlying structure. Random per-pixel grain
  with no readable shapes underneath fails.
- Drop-shadows, soft glows, or bevels that imply a light source outside the
  texture plane. The texture is a surface, not a rendered object.
- Anti-aliased text, smooth vector glyphs, or hinted typography baked into
  the texture. Lettering, if present at all, must be readable as discrete
  pixels.
- Modern UI flourishes: rounded rectangles with thick smooth borders, glassy
  highlights, "neumorphic" embossing.

## Required

- Palette of N colours or fewer per texture (N placeholder, calibrate from
  corpus). Colour count is measured after a fixed quantization step; see the
  readability drift detector in `tooling/texture_evals/`.
- Readability at 64x64. A texture downscaled to 64x64 and viewed at
  intended size must remain recognizable as the same surface. The
  edge-retention and contrast-preservation scores in the readability eval
  are the mechanical proxy for this.
- Tileable without visible seams along both axes. Adjacent placements of
  the same texture must not show a hard line at the boundary.
- Hand-placed pixel structure: the texture should read as composed of
  discrete coloured cells rather than continuous tone.
- Coherent local contrast. A reader must be able to point at the dominant
  shapes within the texture; flat fields of nearly-identical luminance fail.

## Desired feel

- Built, not grown. Surfaces should read as constructed -- panels, plates,
  bricks, tiles -- rather than as organic textures like skin, foliage, or
  cloud.
- Worn but not decorative. Edges, scratches, and discoloration are welcome
  when they suggest use; ornamental flourishes added purely for prettiness
  are not.
- Cool, slightly desaturated palette as the default register. Saturated
  primaries are reserved for accent textures and pickups, not bulk surfaces.
- Each texture carries enough character to be identifiable in isolation but
  reads as part of a single family when tiled next to siblings.

## Calibration parking lot

These thresholds and choices are deferred until the curated corpus is large
enough to fit them from data. Until calibration, the readability eval emits
scores with `passed: null` and an empty `violations` list for every image
that was successfully read and scored. Images that cannot be read at all
(corrupt, truncated, or oversized inputs) are reported as their own record
with `passed: false`, empty `scores`, and a single `violations` entry
naming the underlying error -- the eval still emits one record per input,
regardless of calibration state.

- N (palette colour cap per texture). Candidate range 8 to 32; final value
  is the highest power-of-two cap that the curated `good/` corpus all
  satisfies.
- Edge-retention threshold for the 64x64 downscale roundtrip. Candidate
  range 0.6 to 0.85; final value is one standard deviation below the
  `good/` corpus mean.
- Contrast-preservation threshold for the same roundtrip. Same fitting
  approach as edge-retention; the two thresholds are independent because
  some surfaces lose edges but preserve contrast and vice versa.
- Tileability score. No mechanical detector yet; needs a wrap-around
  difference measurement implementation. Listed here so the gap is visible.
- Palette-coherence across the texture family. Listed here as a future
  cross-texture eval, not a per-image one; needs the corpus to exist
  before the metric can be designed.
- Per-slot overrides. Some texture slots (sky, water, pickup) may need a
  different N or different thresholds; this is parked until the per-slot
  taxonomy stabilizes.
