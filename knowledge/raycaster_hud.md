# Finding: First-Person HUD Layout (Bottom Chrome Strip + Crosshair)

## Summary

In a first-person column-renderer of the reference's lineage, the on-screen HUD has two distinct surfaces. The **bottom chrome strip** is a horizontal dashboard pinned to the bottom of the framebuffer, occupying roughly the bottom 16% of vertical space, composed of a single static background bitmap and a fixed set of widgets layered at hard-coded absolute pixel positions. The **on-aim crosshair** in the reference engine is **absent from the first-person view itself**: the engine relies on implicit center-screen aim for hitscan weapons and renders no crosshair sprite over the gameplay viewport. The only crosshair the reference draws is a single mid-gray pixel at the geometric center of the auxiliary overhead-map view. This finding pins down the bottom-strip layout (widget positions, dimensions, draw order, fonts, color treatment) and documents the crosshair gap explicitly so downstream specs can decide whether to introduce a small static cross as a deliberate departure from the reference.

## Observed Mechanics

### Viewport-to-HUD Vertical Partition

- **Behavior**: The framebuffer is split into two horizontal regions stacked vertically. The top region — the "view window" — hosts the column-rendered world (walls, floor, ceiling, entity sprites, view-space weapon overlay). The bottom region — the "chrome strip" — hosts the dashboard. There is no overlap: the column renderer never writes into the strip region, and the strip widgets never extend above the strip's top edge.
- **Rules**:
  - The strip's height is a fixed bitmap-height constant. The strip's vertical origin is `(framebuffer_height - strip_height)`; with the reference's 200-row framebuffer this puts the strip at row 168 onward, leaving rows 0..167 for the world view.
  - The column renderer's `view_height` is computed once at startup from the chosen view-size step. The largest non-fullscreen view step gives `view_height = 168` rows; the smallest steps give progressively smaller (boxed) world views with chrome visible around them. Only the largest non-fullscreen step is relevant to a minimal port — the strip sits flush against the bottom of the world view.
  - A separate "fullscreen" view-size step exists where the strip is suppressed entirely and the world fills all 200 rows. This is opt-in; the default has the strip visible.
- **Constants** (in the reference's 320×200 internal coordinate space):
  - Framebuffer: 320 wide × 200 tall.
  - Strip height: 32 rows (16% of vertical space).
  - Strip width: 320 (full framebuffer width).
  - Strip top edge: row 168.
  - World viewport (default with strip visible): rows 0..167 (height 168).
- **Feel**: A solid, always-present "dashboard frame." The strip's hard top edge gives the world view a stable visible floor — sprites that walk near the camera don't fall off the bottom of the screen, they fall behind the dashboard.

### Bottom Chrome Strip — Static Background Bitmap

- **Behavior**: A single full-width bitmap is blitted once at the top-left of the strip region as the dashboard's background. The bitmap has embossed wells (recessed rectangular cutouts) at hard-coded positions where dynamic widgets will draw. Widgets later layer their digits / icons / sprites into those wells.
- **Rules**:
  - The background bitmap is the full strip rectangle (320 × 32 pixels). It is loaded once at level start and cached.
  - The background is blitted into a dedicated off-screen background buffer first, then copied to the framebuffer when a full HUD refresh is needed. Widget incremental redraws read FROM the background buffer (to restore the bitmap underneath a stale digit) and write TO the framebuffer (to lay the new digit on top).
  - In competitive multiplayer mode a small face-background tile is overlaid on top of the chrome to color-code the local player; this is a multiplayer-only feature and out of scope for a single-player port.
  - When the auxiliary overhead-map view is active, the chrome strip is still drawn (the overhead map occupies the world-view region, not the strip).
- **Constants**:
  - Background bitmap dimensions: 320 × 32 pixels at the reference's 320×200 resolution.
  - Background blit origin within the strip: (0, 0) — the bitmap is the strip.
- **Feel**: The chrome is a heavy, opaque, baked piece of metal-looking art. It establishes that the player is "inside a machine" — the HUD is part of the world's diegesis, not a translucent overlay floating in screen space.

### Widget Layout Within the Strip

- **Behavior**: Six classes of widget overlay the chrome at fixed absolute framebuffer coordinates: a current-weapon ammo readout, a health percentage readout, a weapons-owned subpanel, an avatar face slot, an armor percentage readout, and three key-card slots. A second tier of secondary readouts (per-ammo-type running counts plus their per-type caps) sits on the right side of the strip.
- **Rules** (all positions are absolute framebuffer (x, y) of the widget's anchor; rows 168..199 inclusive are inside the strip; y-coordinates given relative to the framebuffer top):
  - **Current ammo (primary)**: tall-digit numeric, max 3 digits, right-justified anchor at (44, 171). Drawn in tall-digit font.
  - **Health %**: tall-digit numeric (max 3 digits) at (90, 171), followed by a tall percent-sign glyph immediately to the right.
  - **Weapons-owned subpanel background**: small embossed sub-bitmap at (104, 168). Visible in single-player; suppressed in competitive mode in favor of a frag count.
  - **Weapons-owned indicators**: 6 slots arranged in a 2-row × 3-column grid starting at (111, 172). Column spacing 12 pixels, row spacing 10 pixels. Each slot shows a small digit in one of two colors (gray = unowned, yellow = owned). Slots correspond to the 2nd through 7th weapons; the always-owned default melee/sidearm pair is implicit and not shown.
  - **Avatar face slot**: a multi-state icon at (143, 168). The slot displays an animated portrait that cycles through five pain levels × five expressions plus two special states (invulnerable, dead). See the existing HUD knowledge for the state machine; for layout it is one fixed-size sprite slot.
  - **Armor %**: tall-digit numeric at (221, 171), followed by a tall percent-sign glyph.
  - **Key-card slots**: three multi-state icon slots at (239, 171), (239, 181), (239, 191) — vertically stacked along the right side of the strip's middle band. Each slot shows a key-card icon when the corresponding key is held, or restores the chrome background when not.
  - **Secondary ammo counts** (4 ammo types × 2 fields each): a 2-column × 4-row block on the far right. Current-count column at x=288, max-count column at x=314. Row y-coordinates: 173, 179, 185, 191 (one row per ammo type, ~6 pixels of vertical pitch). All eight use the short-digit font.
  - **Deathmatch frags readout** (suppressed in single-player): tall-digit numeric, max 2 digits, at (138, 171). Overlays the position the weapons-owned subpanel occupies in single-player mode.
- **Constants** (every coordinate is in the reference 320×200 space):
  - All anchor positions are absolute framebuffer (x, y); they fall inside the (0..319, 168..199) strip rectangle.
  - Tall-digit font glyph size: ~14 wide × 16 tall.
  - Short-digit font glyph size: ~4 wide × 6 tall.
  - Weapons-owned slot stride: 12 horizontal, 10 vertical.
  - Key-card slot vertical stride: 10 pixels.
  - Secondary-ammo block columns: x=288 (current) and x=314 (cap), block width ~30 pixels.
- **Feel**: The layout reads left-to-right as a sentence: "you have N rounds in your current weapon," "your health is P%," "these are the weapons you have," "this is your current state of mind (the face)," "your armor is Q%," "these are your keys," "this is how much of each ammo type you're carrying overall." The hard-coded absolute coordinates mean every widget always sits in the same spot — there is no responsive layout, but the trade-off is a HUD the player learns to read without conscious scanning.

### Bottom-Strip Font Treatment

- **Behavior**: Two parallel digit fonts are pre-loaded: a *tall* font (one glyph per digit 0–9) used for primary readouts (current-weapon ammo, health %, armor %, optional frags) and a *short* font used for the secondary per-ammo-type block on the right. Both are fixed-width bitmap glyph sets, right-justified inside their widget's reserved rectangle.
- **Rules**:
  - Each font is a 10-element array of glyph patches indexed by digit value 0..9; all glyphs in a given font share width and height (the widget code reads glyph 0's dimensions and assumes uniformity).
  - A single percent-sign glyph (same height as the tall digits) is loaded separately and drawn next to health % and armor %.
  - A single minus-sign glyph is loaded for negative-number support (used only on the optional frags readout; the percent and ammo readouts are never negative).
  - Glyphs are baked bitmaps — they inherit the framebuffer's active palette when blitted. They do NOT change color based on the value (e.g. health at 5% is not colored red by the digit pipeline; see palette-tint feedback under "Color Treatment").
  - The right-justification rule: the widget's anchor x is the right edge of the rightmost digit; digits are placed walking right-to-left.
- **Constants**:
  - Number of digit fonts: 2 (tall + short).
  - Glyphs per font: 10.
  - Auxiliary tall glyphs: 1 percent, 1 minus.
- **Feel**: Heavy, blocky digits in the tall font dominate the player's attention budget — a tall "20" for low health is unmistakable across the room. The short font lets a lot of numerical detail (eight per-type counts) coexist on the right side without crowding.

### Color Treatment (Bottom Strip)

- **Behavior**: The bottom strip's colors come entirely from the palette-indexed bitmaps of the chrome and the digit fonts. Within the strip itself there is no per-widget threshold coloring — health at 5% renders in the same baseline color as health at 95%. State coloring is instead delivered via a global palette-tint channel that affects the whole framebuffer (including the strip).
- **Rules**:
  - The framebuffer is 8-bit palette-indexed; all bitmap art is encoded against this palette. The active palette is one of N pre-loaded variants (a base palette plus damage/pickup/environment-suit tint variants).
  - Damage tint: when the player has been hurt recently, the active palette swaps to one of 8 progressively-redder variants. The tint affects every pixel in the framebuffer, including the chrome strip and its digits.
  - Pickup tint: when the player has just collected an item, the active palette swaps to one of 4 progressively-more-golden variants for a brief flash.
  - Environment-hazard tint: a single greenish-palette variant active while a hazard-suit power-up is held.
  - Tint intensity is computed as `(counter + 7) >> 3`, i.e. each tier of intensity covers 8 ticks of the underlying damage/pickup counter, clamped to the variant count.
  - Tint changes are tracked by a small integer state on the strip code; the palette is only swapped when the desired tint tier changes (not every frame).
- **Constants**:
  - Damage palette variants: 8 graded reds (palette indices 1..8 in the palette-pack indexing scheme).
  - Pickup palette variants: 4 graded golds (palette indices 9..12).
  - Environment-suit palette variant: 1 green (palette index 13).
  - Counter-to-tier shift: 3 bits (one tier per 8 counter units).
- **Feel**: The strip's "feel" of conveying health state is mostly carried by the avatar face animation (which has color built into its expression sprite frames) plus the full-screen palette tint during damage. The digits themselves stay readable and neutral-colored, which is the right default for a small port that doesn't ship the avatar's full expression set.

### Bottom-Strip Palette Reference

- **Behavior**: When porting to a true-color framebuffer, the bottom-strip color decisions are: dashboard chrome = warm dark gray-brown (the embossed metal look); tall digits = saturated red (the "warning panel" look that makes them readable against the gray chrome); short digits and weapon-owned digits = bright yellow (highest-readability palette entry); inactive weapon-owned digits = neutral gray. These are derived from the reference palette's gray-ramp and warm-ramp blocks.
- **Rules**:
  - The palette is partitioned into named ramp blocks of 16 entries each. The 6th ramp block (entries 96..111) is the gray ramp; the 7th (112..127) is the green ramp; the last few blocks contain the red, yellow, and warm-brown ramps used by chrome and digits.
  - For a port that uses 32-bit BGRA framebuffers (no palette), pick concrete RGB values that match the palette ramp's appearance at the appropriate brightness step. The reference's tall digits are a saturated mid-bright red — roughly the upper-third of the red ramp.
  - The crosshair color (see next section) is sourced from the gray ramp's base entry.
- **Constants** (RGB suggestions for a port, derived from the reference palette's nominal appearance):
  - Tall-digit red: a saturated red roughly in the (200, 0, 0) – (220, 0, 0) range.
  - Short-digit yellow (active weapons-owned): a saturated yellow roughly (220, 220, 0).
  - Weapons-owned gray (inactive slot): a mid-gray, roughly (100, 100, 100).
  - Chrome warm-gray: a desaturated warm gray, roughly (90, 80, 80).
  - Crosshair gray: a mid-bright neutral gray, roughly (160, 160, 160).
- **Feel**: The palette is deliberately desaturated overall, with the digits as one of very few saturated elements on screen — they read as alarm-panel indicators against the rest of the dashboard.

### On-View Crosshair — Absent in the Reference's First-Person View

- **Behavior**: **The reference engine renders no crosshair sprite over the first-person world view.** Hitscan weapons project a trace from the player's position along the player's facing angle and report a hit if the trace intersects an entity inside the weapon's range; the "aim point" is the screen-center implicitly because that is what the column projection puts at the camera ray's center. There is no pixel-level reticle, no plus-shape, no dot drawn over the world view.
- **Rules**:
  - During world rendering: no crosshair-drawing call is made between sprite-pass completion and HUD draw. The screen-center column is rendered exactly like any other column.
  - During HUD draw: the chrome strip and its widgets are drawn (see above sections); no widget overlays the world-view region.
  - Hitscan accuracy is conveyed exclusively by spread (the trace is jittered by a per-weapon angular distribution before being projected), not by a visible aim indicator.
- **Feel**: The lack of a crosshair forces the player to develop a "where the center of the screen is" intuition, which works because (a) hitscan weapons have generous spread and (b) the held-weapon view sprite anchors the eye to the bottom-center of the screen, making "straight ahead" feel implicit. A small static crosshair would not break this — it would only make the implicit center explicit.

### On-View Crosshair — The Auxiliary-Map Single-Pixel Crosshair

- **Behavior**: The only crosshair the reference ever draws is a *single pixel* at the geometric center of the auxiliary overhead-map view. It is drawn when the overhead-map view is active, not during the first-person view. Its color is a mid-bright gray.
- **Rules**:
  - The crosshair is rendered as a single pixel write: `framebuffer[ (overhead_view_width * (overhead_view_height + 1)) / 2 ] = gray_palette_index`. For a 320×200 frame this lands at framebuffer row 100, column 160 (approximately).
  - The crosshair color is the base entry of the gray ramp block — palette index 96 in the reference's standard palette. In RGB terms this is approximately (160, 160, 160) to (192, 192, 192) — a neutral mid-bright gray.
  - There is no plus / X / dot shape — the rendered shape is literally one pixel.
  - The crosshair sits "on top of" the overhead-map drawing (drawn after walls, things, and player markers) so it is never occluded.
- **Constants**:
  - Crosshair size: 1 × 1 pixel.
  - Crosshair color: mid-bright gray (palette index 96; ~(160, 160, 160) – (192, 192, 192) in RGB).
  - Crosshair position: geometric center of the auxiliary-view framebuffer rectangle.
- **Feel**: A single-pixel mark is barely visible at the reference resolution and reads as "this is where you are" rather than "this is where you'll shoot." It is a positional indicator for the overhead map, not an aiming reticle for combat.

### Recommended Crosshair Shape for a Port (Inferred, Not Reference-Native)

- **Behavior**: A port that wants a visible centered cross on the first-person view (a deliberate departure from the reference) should pick a small static shape that does not interfere with target identification. A simple +-shape (horizontal bar plus vertical bar, each ~7 pixels long and 1 pixel thick, with a 1-pixel gap in the center so the very center of the screen is not occluded) is a conservative choice; an X-shape works similarly. The shape stays static — it does not animate with weapon firing, expand with spread, or contract on aim. It is anchored to the geometric center of the world-view region (not the whole framebuffer — the bottom strip is below the world view and the crosshair should ignore it).
- **Rules** (proposed, since the reference does not constrain this):
  - Center position: the geometric center of the world-view region, i.e. `(framebuffer_width / 2, (framebuffer_height - strip_height) / 2)`. For a 320×200 framebuffer with a 32-row strip this lands at (160, 84).
  - Shape: + or X. The + reads as "iron sights"; the X reads as "scoped." For a low-tech retro feel, the + is the conservative pick.
  - Arm length: small relative to the framebuffer — a 7-pixel arm on a 320-wide framebuffer is ~2% of width, which is visible but not intrusive. Scales to the natural pixel grid; do not antialias.
  - Thickness: 1 pixel. A 2-pixel-thick crosshair looks heavy at retro resolutions.
  - Center pixel: leave empty (transparent / unmodified) so the crosshair does not occlude small distant targets.
  - Color: the same mid-bright gray as the reference's overhead-map crosshair, for visual coherence with the rest of the HUD. This palette block reads as "instrument, not part of the world."
  - Behavior: completely static. Does not animate, scale, or change color on hit. (More elaborate crosshair behaviors — color-change on enemy-hover, expand-on-fire — exist in later engines, are NOT in the reference, and should be marked as a deliberate spec-layer decision if added.)
- **Constants** (proposed):
  - Crosshair shape: +.
  - Arm length: 7 pixels per arm (3 pixels each side of the center, plus a center gap).
  - Arm thickness: 1 pixel.
  - Center gap: 1 pixel (so the exact center pixel is untouched).
  - Color: mid-bright gray, approximately (160, 160, 160) in RGB.
  - Anchor: the geometric center of the world-view region (not the whole framebuffer).
- **Feel**: A static + crosshair is the smallest possible departure from the reference. It tells the player "aim here" without changing how the underlying hitscan system behaves. Because it never animates, it never lies to the player about accuracy.

## Key Insights

- **The first-person HUD is a single 32-row dashboard strip pinned to the bottom of the framebuffer.** Its dimensions (320 × 32 at the reference resolution) are constants chosen to match the chrome bitmap art — they are not parameterized.
- **Widget positions are absolute framebuffer coordinates, not strip-relative.** A port can shift the strip vertically only by re-baselining every widget anchor. The simplest port keeps the reference layout 1:1 and scales the whole framebuffer.
- **Within the strip, color is never used to encode value thresholds.** No "health digits turn red below 25%" — that effect is delivered through the global palette tint (which the digits inherit). A port that wants per-digit thresholds is adding a feature, not porting one.
- **The reference's first-person view has no crosshair.** This is the truthful extraction. Any centered cross drawn over the world view is a deliberate spec-layer choice — defensible because hitscan-screen-center is the implicit aim point — but it is NOT "porting the reference's crosshair." Document it as such.
- **The single crosshair pixel the reference does draw is in the overhead-map view, not the world view.** It is one pixel, mid-bright gray, at the geometric center of the map framebuffer. It is a position marker, not a reticle.
- **A conservative crosshair shape for a port is a 7×7 + with a 1-pixel center gap, drawn at the geometric center of the world-view region in mid-bright gray.** This is the smallest visible cross that does not occlude the center pixel. It is a port-side decision, not a reference-derived behavior.
- **The world-view-region center is NOT the framebuffer center** when the strip is visible. With a 320×200 framebuffer and a 32-row strip, the world view occupies rows 0..167 and its center is at (160, 84), not (160, 100). A port that draws a crosshair at the framebuffer center will see the crosshair sit too low — visually under the player's actual line of sight.
- **The two HUD surfaces compose without interaction.** The bottom strip and the (port-added) crosshair never overlap; the strip never extends into the world view region; the crosshair never extends into the strip region. A port can implement them as two independent draw passes layered after the world renderer finishes.

## Open Questions

- **Should the port draw the bottom chrome strip at all, or use a transparent overlay?** The reference's chrome is heavy and diegetic. A modern minimal port might be better served by a transparent or semi-transparent overlay with the same widget positions. This is a spec-layer choice; the reference does not constrain it.
- **What concrete RGB values for chrome and digits in a 32-bit framebuffer?** The reference is palette-indexed; ports must pick representative RGB. The "Bottom-Strip Palette Reference" section above gives suggestions but final choices belong in the tuning spec.
- **Should the port include the avatar face slot?** The face is one of the reference's signature HUD elements but requires a full sprite expression set (5 pain levels × ~7 expressions ≈ 35 frames). A minimal port may skip it and leave the slot blank, fill it with a placeholder color block, or use the slot for a different readout. This is a spec decision.
- **Should the port include the secondary per-ammo-type counts on the right side?** With only one ammo type in scope, four counters collapse to one. The right-side block becomes mostly empty. A port should either suppress the block or repurpose the slots.
- **Should the crosshair scale with framebuffer resolution?** At 320×200 a 1-pixel-thick crosshair is visible; at 640×400 it becomes hair-thin. A port that runs at higher internal resolutions should scale the crosshair arm length and thickness in integer multiples of the framebuffer scale factor.
- **Per-weapon crosshair variants?** The reference has no crosshair, so it has no per-weapon variants. A port could conceivably add them (e.g. a dot for a precision weapon, a wide cross for a spread weapon), but doing so would diverge sharply from the reference. Leave as deferred unless the spec explicitly calls for it.

## Deferred

- **Avatar face state machine** — the multi-state expression sprite cycling through pain levels and special expressions. Layout-wise it occupies one fixed slot at (143, 168); the state machine itself is documented in the existing HUD knowledge and is out of scope for a minimal port focused on health/ammo readouts.
- **Cheat-code input handling** — the strip's input responder intercepts keypress sequences for debug toggles. Out of scope for a HUD layout extraction.
- **Auxiliary overhead-map view (and its single-pixel crosshair)** — the only crosshair the reference draws lives here, but the overhead map itself is a separate gameplay feature (an overlay the player toggles on) and is out of scope for the raycaster port's first slice that adds an FPS HUD.
- **Animated / dynamic crosshair behaviors** — color-change on enemy-hover, expand-on-fire, dot-when-aiming-at-pickup. None are in the reference; all are later-engine conventions. If the spec calls for them, extract them in a follow-up pass and label them as spec-layer decisions rather than reference ports.
- **Multi-line message overlay** above the world view — the reference has a separate timed-message subsystem that draws text strings in the top-left of the world view region. This is a separate HUD surface from the bottom strip and is out of scope for slice 4; see the existing HUD knowledge's "Deferred" section.
- **Competitive-mode frag display** — the reference replaces the weapons-owned subpanel with a frag count in deathmatch mode. Single-player port does not need this widget; the position is documented above only so a future multi-player port has the layout pinned.
- **Per-key-card-type visual** — the three key-card slots can each display one of two icons (card-shape or skull-shape) depending on the key picked up. Layout-wise it's still three slots at fixed positions; the icon variants are an asset detail out of scope here.
