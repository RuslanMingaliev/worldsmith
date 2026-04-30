# Finding: HUD / Status Bar

## Summary

The reference engine renders a persistent status bar as a fixed-height strip occupying the bottom portion of the framebuffer. The bar is composed of a single static background image plus a handful of independent "widgets" (numeric readouts, percentage readouts, multi-state icon slots, on/off icon slots) layered on top. Each widget reads a pointer to a live game value, owns its own bounding rectangle, and redraws itself only when its value changes — except on a full refresh tick (e.g. just after spawn or when the bar is re-shown). Numbers are rendered as right-justified strings of fixed-width bitmap glyph patches. The bar is purely a viewport into game state and never mutates it.

## Observed Mechanics

### Status Bar Layout

- **Behavior**: A horizontal strip pinned to the bottom of the framebuffer, full screen width, fixed height (roughly 1/6 of the screen vertically in the original assets). The strip contains a static background patch ("chrome") with cut-outs that act as wells where dynamic widgets are drawn.
- **Rules**:
  - The strip's Y origin is computed as `screen_height - bar_height` so it stays anchored to the bottom regardless of the framebuffer dimensions.
  - The strip's X origin is 0 and its width is the full framebuffer width.
  - Widget anchor coordinates are absolute framebuffer coordinates, not bar-relative — but they are chosen to fall inside the bar rectangle.
  - When the player is in fullscreen-view mode, the strip is suppressed; in windowed-view mode (or when an automap-style overlay is up), it is drawn.
  - The bar is double-buffered: the chrome is blitted once into a dedicated background buffer, and each subsequent widget redraw first restores the patch of background buffer under the widget's rectangle into the framebuffer, then draws the widget patch on top. This avoids needing to redraw the entire chrome every frame.
- **Constants** (kinds, not absolutes):
  - Bar height in pixels (a small fixed value chosen to fit the chrome art).
  - Bar Y origin = framebuffer height minus bar height.
  - Per-widget anchor (x, y) in framebuffer coordinates.
  - Per-widget max width in glyphs (for numeric widgets).
- **Feel**: A solid, always-present "dashboard" framing the play view. Because the chrome is a real bitmap with embossed wells around each readout, the readouts feel like physical instruments rather than floating text.

### Numeric Widget

- **Behavior**: Displays a signed integer as a sequence of fixed-width digit glyphs, right-justified to the widget's anchor X. Re-blits the rectangular area under the digits from the background buffer first, then draws each glyph from a 10-element array of digit patches (one per decimal digit 0–9).
- **Rules**:
  - The widget stores: anchor (x, y) of the right edge, max digit count `width`, a pointer to the live integer, a pointer to a "visible?" boolean, and a pointer to the digit-glyph patch array.
  - All glyphs in the digit set share the same pixel width (taken from glyph 0); rendering simply walks right-to-left placing one glyph every `glyph_width` pixels.
  - Drawing loop: `while (value > 0 && digits_remaining-- > 0) { x -= glyph_width; draw glyph[value % 10] at x; value /= 10; }`
  - **Zero is special-cased**: an explicit `if (value == 0) draw glyph[0]` ensures a `0` shows up rather than blank.
  - **No leading zeros**: the loop terminates when the value reaches 0, so a value of 7 in a 3-digit slot renders as `  7`, not `007`.
  - **Negative numbers**: clamped to fit (e.g. a 2-digit slot clamps to -9, a 3-digit slot to -99), absolute value rendered as digits, then a separate minus-sign glyph drawn one glyph-width to the left of the leftmost digit.
  - **N/A sentinel**: an out-of-band integer value chosen never to collide with realistic in-game numbers is interpreted as "draw nothing." This lets weapons that don't consume ammo (melee/etc.) show a blank ammo well without a special widget type.
  - **Erase-then-draw**: every redraw first restores the widget's full rectangle (`max_digit_count * glyph_width` by `glyph_height`) from the background buffer, so shrinking from 3 digits to 1 digit doesn't leave stale digits on screen.
  - The widget owns no game state — it only reads through its pointer.
- **Constants**:
  - `width` (max digit slots): 2 for compact summary readouts, 3 for primary readouts (current ammo, current health %, current armor %).
  - Glyph width and height: derived from the loaded bitmap-font patches, not hardcoded; treated as queried metadata.
  - Minus-sign offset: one glyph-width to the left of the rendered digits.
  - Sentinel value: an integer chosen far outside the realistic range of in-game counters.
- **Feel**: Right-justified fixed-width digits give a "calculator readout" stability — the units column never shifts as the value scales from 1 to 10 to 100. The lack of leading zeros keeps low values uncluttered.

### Percent Widget

- **Behavior**: A numeric widget plus a static `%` glyph drawn to the right of the digits. Used for health and armor.
- **Rules**:
  - Wraps a 3-digit numeric widget. The percent-sign glyph is drawn once at the widget's anchor position; it only needs re-drawing when the bar undergoes a full refresh (since nothing ever overwrites it from above).
  - On each tick: if a full refresh is requested, the percent glyph is re-blitted; then the inner numeric widget redraws.
- **Feel**: Reinforces that the value is a 0–100 normalized quantity, not a raw count. Visually distinguishes health/armor from ammo.

### Multi-State Icon Widget

- **Behavior**: A slot that displays one of N icons based on a current integer index (e.g. a key-card slot showing "no key / blue / red / yellow", or a face slot cycling through expression sprites).
- **Rules**:
  - Stores: anchor (x, y), last drawn index, pointer to current index, pointer to "visible?" flag, and an array of icon patches.
  - Index `-1` means "show nothing" — the widget skips drawing.
  - Redraws only when the index changes (or on full refresh): erases the previously drawn icon's rectangle from the background buffer, then draws the new icon's patch.
  - The icon's rectangle is computed from the patch's own width/height/offset metadata, which can differ per-icon — so icons of different sizes can share a slot.
- **Feel**: Used for status that is categorical, not numeric (which weapon is ready, which keys you hold, animated face).

### Binary Icon Widget

- **Behavior**: A slot that shows-or-hides a single icon based on an on/off boolean (e.g. a sub-panel background that is visible only outside competitive mode).
- **Rules**:
  - Stores: anchor, last drawn value, pointer to current bool, pointer to "visible?" flag, and the single icon patch.
  - On change (or full refresh): if true, draws the patch; if false, restores the underlying background buffer rectangle.
- **Feel**: A lightweight conditional layer — useful for "this whole region of the bar shows different content based on game mode" without rebuilding the chrome.

### Color / State Encoding

- **Behavior**: Within the status bar itself, numeric digits are **not** color-shifted by value — health at 5% renders in the same digit color as health at 95%. The reference engine encodes danger and pickup feedback through a different channel: a global palette tint applied to the entire framebuffer.
- **Rules** (palette-tint channel, summarized — the detailed feedback rules belong in the visual-feedback knowledge):
  - A "damage" counter and a "bonus pickup" counter both bias the global palette: damage shifts everything red (8 graded levels of red intensity), pickup flashes everything gold (4 graded levels), an environment-hazard suit shifts everything green.
  - Tint intensity is `(counter + 7) >> 3` (i.e. each tier of intensity covers 8 ticks of the underlying counter), clamped to the available palette range.
  - The status bar's digits, as bitmap patches, inherit the global palette shift naturally — they appear redder during a damage flash and more golden during a pickup flash, even though the bar code itself doesn't change anything.
- **Constants**:
  - Number of red palette tiers (8 in the reference).
  - Number of bonus/pickup palette tiers (4 in the reference).
  - Counter-to-tier shift: 3 bits (one tier per 8 counter units).
- **Feel**: Threshold-coloring of digits would have to be added by the consumer if desired (e.g. "render health digits red below 25%"). The reference doesn't do this in the bar; it does it screen-wide.

### Update Cadence

- **Behavior**: Two redraw modes — *full refresh* (re-blit chrome and every widget) and *diff redraw* (each widget self-checks and only redraws if its tracked value changed).
- **Rules**:
  - Per-frame tick: a logic update reads the latest game state (face index, frag count, current weapon's ammo binding, key-card slot indices) and writes it into the locations the widgets read from. This is separate from drawing.
  - Per-frame draw: choose full-refresh if the bar was just shown or the caller forced it, else diff-redraw. Diff-redraw walks every widget; each widget compares its `oldnum`/`oldval`/`oldinum` against the live value and redraws only on mismatch (or if the global refresh flag is set).
  - The "force refresh" path is taken when: the bar has just been (re)started (e.g. player respawn, level start) and on every frame in which the chrome would otherwise be left stale (e.g. transitioning out of an overlay that drew over the bar).
- **Constants**:
  - The reference engine ticks at 35 Hz; this cadence governs both logic and bar update.
- **Feel**: The minimal-redraw strategy is invisible to the player but matters for performance on the original target hardware. For a modern prototype it can be replaced with "redraw everything every frame" without behavior change.

### Health Value Semantics

- **Behavior**: Health is a signed integer in the range 0..100 nominally, with brief excursions allowed up to 200 (overheal) via specific pickups, and 0 meaning dead.
- **Rules** (as observed via the bar's read-only access):
  - The bar reads `player.health` as a plain `int`. There is no decimal/fractional component at the bar layer.
  - 0 health means dead — the avatar widget switches to a "dead" face index immediately.
  - Values above 100 are not specially marked in the digit display; the 3-digit width accommodates them (and also accommodates the engine's god-mode value).
  - A separate "old health" snapshot is kept by the avatar widget to detect sudden large drops (used to switch to a "ouch" expression when damage in one tick exceeds a pain threshold).
  - Negative health is mathematically representable but is never produced by gameplay code (clamped at 0 on death); the digit widget would render it with a leading minus sign if it ever occurred.
- **Constants**:
  - Nominal max: 100.
  - Overheal max: 200.
  - Death value: 0.
  - Pain-spike threshold (single-tick damage that triggers the special "ouch" face): 20 health units.
- **Feel**: A simple, clamped, integer scale. The 3-digit display silently supports overheal without needing a separate readout.

### Read-only Contract

- **Behavior**: The bar is strictly an observer. It holds **pointers** to game state (`int*` for the value, `boolean*` for the visibility flag) and dereferences them at draw time. It never writes to those pointers.
- **Rules**:
  - Widget initialization records the source pointers; widget update dereferences and renders.
  - Game logic owns mutation of health, ammo, keys, etc. — the bar code only triggers a redraw when it observes a change.
  - The one exception is the avatar widget's own internal animation timers (face index, face countdown), which are bar-owned ephemeral state derived from game state, not the game state itself.
- **Feel**: Architecturally clean — the bar can be swapped out, hidden, resized, or replaced with an alternate visualization without touching gameplay code.

### Font / Glyph Data

- **Behavior**: Two parallel digit fonts are pre-loaded at status-bar init: a "tall" set for primary readouts (current weapon's ammo, health %, armor %) and a "short" set for secondary readouts (per-ammo-type counters, weapon-owned indicators in the arms panel).
- **Rules**:
  - Each font is an array of 10 glyph patches indexed by digit value 0..9; the widget array is just the bare patch pointers.
  - Glyphs are stored as the engine's standard sprite-patch format (column-major, RLE-able transparent bitmap with per-glyph width, height, and origin offsets in the patch header).
  - A separate single "minus" glyph is loaded for negative-number support and is drawn manually by the numeric widget when needed.
  - A separate single "%" glyph is loaded for percent widgets.
  - All glyphs of a given font share the same width (the widget code reads `font[0].width` and assumes uniformity), so digit alignment is purely arithmetic.
  - Glyphs are loaded once at init time and cached in memory until shutdown; they are never reloaded per frame.
- **Constants**:
  - Font count: 2 (tall, short).
  - Glyphs per font: 10.
  - Auxiliary glyphs: 1 minus, 1 percent.
- **Feel**: Bitmap fonts give a baked-in retro look — pixel-perfect, no antialiasing, no kerning surprises. The fixed-width assumption keeps the rendering trivial.

## Key Insights

- **Widgets are the unit of composition.** A status bar is "a chrome image plus N independently-updating widgets." Each widget knows its anchor, its source pointer, and its visibility flag — and nothing else. New readouts (e.g. score, lives, energy) are added by declaring a new widget; no master layout code needs to change.
- **Right-justification + fixed-width glyphs = stable readouts.** The units column never shifts. This is the right default for any HUD numeric.
- **The "out-of-band sentinel" pattern lets one widget type cover both numeric and "blank" cases.** Pick a value that real game data can't produce, write it into the source location when no number applies, and the widget naturally draws nothing. Avoids a separate "is_present" boolean per numeric.
- **Erase-then-draw via a saved background buffer is the cheapest way to get incremental redraw.** Each widget needs to know only its own rectangle and the address of the original chrome bitmap; no global dirty-region tracking.
- **Color encoding of state was done globally (palette tint), not per-widget.** A consumer who wants per-digit color thresholds (e.g. red-below-25%-health) must add that themselves; it's not in the reference's HUD code.
- **Health is a plain int with a soft cap of 100 and a hard cap of 200.** The 3-digit display naturally supports overheal without special UI.
- **The bar is read-only.** Pointer-based binding makes the bar a pure projection of state. This is the right shape for a Rust port: the HUD module borrows immutable refs to game state for the duration of a frame.

## Open Questions

- **Glyph dimensions for our prototype**: the reference's tall digits are roughly 14 pixels wide and 16 tall; the short digits are about 4×6. The right size for a top-down 2D prototype depends on chosen framebuffer resolution and is a spec/25 tuning decision, not a knowledge item.
- **Should the prototype HUD use a chrome image at all, or just floating text?** The reference's chrome is heavy and assumes the bar is the main way to read status. A modern minimal prototype may be better served by a transparent overlay. This is a spec decision.
- **Per-digit color thresholds** (e.g. red health below 25%) are not present in the reference and would need to be a deliberate addition to the spec if desired.
- **Bar widget for a health *bar* (proportional fill rectangle)** is not present in the reference — health is shown numerically only. If the spec requires a bar visualization, that mechanic must be designed fresh and labeled as such (not "from reference").
- **Resolution scaling**: the reference's bar height is multiplied by an integer screen-scale factor for upscaled framebuffers, but glyph patches do not auto-scale — they would need to be re-rendered at the new resolution. The prototype should decide up front whether glyphs scale or whether the framebuffer is fixed.

## Deferred

- **Text overlay system** (timed message lines drawn at the top of the playfield, multi-line console output, in-game chat input echo): the reference engine has a separate module for this, distinct from the status bar. It is out of scope for a minimal HUD whose only requirement is showing health and ammo. If the spec later calls for "pickup confirmation messages" or similar, that mechanic should be extracted in a follow-up pass.
- **Avatar / face widget animation state machine**: a multi-state expression sprite that reflects damage taken, kills landed, current health band, and idle look-around. Skipping for the minimal prototype; would be a separate knowledge entry if the spec calls for it.
- **Cheat code input handling**: the bar's input responder also intercepts keypress sequences for debug commands. Out of scope for a prototype HUD.
- **Palette-tint feedback channel**: covered in the visual-feedback knowledge file. Mentioned here only because it explains why the reference doesn't color-shift digits within the bar itself.
- **Categorical / icon widgets** (key-card slots, weapon-owned panel, score-summary readouts in competitive mode): the *widget shapes* (multi-state icon, binary icon) are documented above; the specific data they display is out of scope for a minimal HUD focused on health and ammo.
