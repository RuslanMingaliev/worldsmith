# HUD Specification

## Overview

This specification defines the in-game heads-up display: a persistent on-screen UI that reports the player's combat-relevant state (currently: health). HUD is purely a *renderer* concern — it reads existing player state, never mutates it, and never affects gameplay outcomes.

Scope is the current 2D top-down prototype. The HUD is drawn directly into the framebuffer; no separate UI layer or font asset file is introduced.

All numeric sizes, colors, and positions referenced by name (e.g. `HUD_MARGIN_PX`, `HUD_HEALTH_BAR_WIDTH_PX`) are defined in [`25_game_tuning.md`](25_game_tuning.md#hud). The behavior spec only refers to constants by name.

Source: [`knowledge/hud.md`](../knowledge/hud.md). Spec values that are NOT directly grounded in knowledge are marked `Generation default — no knowledge backing` in spec/25, with the rationale recorded in this spec.

## Design Goals

- **Always readable.** The HUD must be drawn *above* all gameplay layers (including the player damage tint overlay) so health is legible at any tint level.
- **Discrete digits, not text.** A bitmap font for digits `0–9` is shipped inside the renderer. No font file, no string formatting, no fallback paths. (Knowledge: § Font / Glyph Data — fixed-width bitmap glyphs.)
- **Read-only.** HUD reads `player.health` and `PLAYER_MAX_HEALTH` only. No HUD-owned state. (Knowledge: § Read-only Contract.)

## Behaviors

### Health Pane

**Trigger:** Every frame, after all gameplay layers (including damage tint) are drawn.

**Effect:** A health pane is drawn in the top-left corner of the framebuffer. The pane consists of:
1. A horizontal **health bar** of fixed width `HUD_HEALTH_BAR_WIDTH_PX` and height `HUD_HEALTH_BAR_HEIGHT_PX`.
2. A **numeric health value** drawn to the right of the bar, using the bitmap digit font.

(The HUD also draws an **ammo pane** directly below the health pane; see § Ammo Pane.)

**Rules:**
- Pane origin is `(HUD_MARGIN, HUD_MARGIN)` from the top-left of the framebuffer (code constant: `HUD_MARGIN = 4`). *(Generation default: the reference engine uses a bottom-anchored full-width strip; we use top-left because our top-down 2D viewport fills the entire window with no chrome budget. See spec/25 § HUD.)*
- The bar's interior is filled with `HUD_HEALTH_BAR_BG_COLOR` (background), then a foreground fill covers a fraction proportional to `player.health / PLAYER_MAX_HEALTH`, clamped to `[0.0, 1.0]`. A 1 px outline (`HUD_FRAME_COLOR`) is **deferred** — not drawn in current code; see § Deferred. *(Generation default: the reference engine uses digits-only, no proportional bar. The bar is added because our prototype lacks the global palette-shift damage feedback that the reference's digits inherit; a visible bar substitutes for the missing channel.)*
- The foreground fill color is selected by health band (see § Health Bands below). *(Generation default: the reference engine does NOT color-shift digits by value — see knowledge/hud.md § Color / State Encoding. We add bands for the same reason as the bar above.)*
- The numeric value is drawn immediately to the right of the bar with a gap of `HUD_PANE_GAP_PX`. Each glyph is `HUD_DIGIT_WIDTH_PX × HUD_DIGIT_HEIGHT_PX`, scaled by `HUD_DIGIT_PIXEL_SIZE`. Digits are drawn **no leading zeros, with `0` special-cased to render as a single glyph rather than blank**. Right-justified anchoring (knowledge § Numeric Widget) is **deferred** — code renders left-to-right from a fixed x offset. *(Knowledge: § Numeric Widget — exact rules for no-leading-zeros and zero-special-case.)*
- The numeric value is `player.health.max(0)` (never negative — clamp to zero for display).
- Digit color matches the foreground fill color of the bar in the same frame, so the whole pane shifts hue together. *(Generation default; see § Color / State Encoding caveat above.)*

### Health Bands

**Trigger:** Computing the foreground fill color each frame.

**Effect:** The fill color is selected by the player's current health fraction:

| Fraction (`health / PLAYER_MAX_HEALTH`) | Color constant |
|------------------------------------------|----------------|
| `>= HUD_HEALTH_BAND_HIGH_THRESHOLD` | `HUD_HEALTH_COLOR_HIGH` |
| `>= HUD_HEALTH_BAND_LOW_THRESHOLD` and below high | `HUD_HEALTH_COLOR_MID` |
| below low (including zero) | `HUD_HEALTH_COLOR_LOW` |

**Rules:**
- Thresholds are evaluated against the *fraction*, not the absolute value, so the bands stay correct if `PLAYER_MAX_HEALTH` is later changed.
- Band selection happens once per frame; the same color is used for the bar fill and the digits.

*(Generation default: the entire band system is not knowledge-backed. The reference uses global palette tint to communicate damage state; we cannot easily mimic palette tint in our framebuffer model, so per-band coloring is our substitute. Re-evaluate once spec/40 § damage tint behavior is observable in play.)*

### Ammo Pane

**Trigger:** Every frame, in the same `draw_hud` call that draws the health pane. Shipped together with the pickup system (see [`60_pickups.md`](60_pickups.md)).

**Effect:** A second pane is drawn directly below the health pane:
1. A small filled **ammo icon** of size `HUD_AMMO_ICON_PX × HUD_AMMO_ICON_PX` in `HUD_AMMO_COLOR` (mirrors the on-map ammo pickup color).
2. The player's `ammo` value drawn to the right of the icon using the same bitmap digit font, color `HUD_AMMO_COLOR`. Vertically centered against the icon.

**Rules:**
- Pane origin: `(HUD_MARGIN, HUD_MARGIN + HUD_HEALTH_BAR_HEIGHT_PX + HUD_PANE_GAP_PX)` (note: code constant is `HUD_MARGIN`, not `HUD_MARGIN_PX`).
- Icon-to-digits gap is `HUD_PANE_GAP_PX` (same constant as the inter-pane vertical gap; no separate `HUD_DIGIT_GAP_PX` constant exists in code — the health pane bar→digits gap also uses `HUD_PANE_GAP_PX`).
- No background bar; the pane is `[icon] [digits]`.
- Ammo digits use the same right-justified, no-leading-zeros, zero-special-cased rules as health digits (knowledge § Numeric Widget — same pattern, applied to a single color instead of a band).
- Ammo digits are single-color (`HUD_AMMO_COLOR`). No band thresholds. Low-ammo warning color is **deferred**.
- Always drawn — including when `ammo == 0` (renders the digit `0`).

### Armor Pane

**Trigger:** Every frame, in the same `draw_hud` call that draws the health and ammo panes. Shipped together with the armor system (see [`60_pickups.md § Armor (Green) Pickup Consumption`](60_pickups.md), [`25_game_tuning.md § Armor`](25_game_tuning.md#armor)).

**Effect:** A third pane is drawn directly below the ammo pane:
1. A small filled **armor icon** of size `HUD_ARMOR_ICON_PX × HUD_ARMOR_ICON_PX` in the per-tier color picked from `player.armor_type` (`HUD_ARMOR_COLOR_NONE` / `HUD_ARMOR_COLOR_GREEN` / `HUD_ARMOR_COLOR_BLUE` — specs/25 § HUD Armor Pane).
2. The player's `armor` value drawn to the right of the icon using the same bitmap digit font, in the same per-tier color as the icon. Vertically centered against the icon.

**Rules:**
- Pane origin: `(HUD_MARGIN, HUD_MARGIN + HUD_HEALTH_BAR_HEIGHT_PX + HUD_PANE_GAP_PX + HUD_AMMO_ICON_PX + HUD_PANE_GAP_PX)`. The pane stacks below the ammo pane with the same inter-pane gap (`HUD_PANE_GAP_PX`) used between the health and ammo panes.
- Icon-to-digits gap is `HUD_PANE_GAP_PX` (matches the ammo pane).
- No background bar; the pane is `[icon] [digits]`.
- Armor digits use the same left-aligned, no-leading-zeros, zero-special-cased rules as health and ammo digits (knowledge § Numeric Widget). Right-justification is deferred per the same § Deferred entry as health/ammo.
- Armor digits are tri-state color (gray / green / blue), one per `armor_type`. No band thresholds within a tier — a blue armor at 1 point and at 200 points render in the same blue. Knowledge `hud.md § Color / State Encoding` notes the reference does NOT color-shift digits by value; the prototype's tri-state encoding discriminates by *tier* (categorical), not value (continuous), which matches the spirit of the reference's "color = state, not magnitude" rule. *(Generation default — knowledge does not pin a per-tier HUD color scheme; we reuse the on-map green/blue pickup colors for visual continuity. See specs/25 § HUD Armor Pane for the rationale.)*
- Always drawn — including when `armor == 0` (renders the digit `0` in `HUD_ARMOR_COLOR_NONE`, mirroring the ammo pane's "always drawn at zero" rule).

### Render Order Update

**Trigger:** The renderer's existing `draw()` routine.

**Effect:** The HUD pane is inserted into the existing render order between the player damage tint overlay and the game-over border:

```
... existing layers ...
8. Player damage tint overlay (existing)
9. HUD pane                       (new)
10. Game-over border (existing)
```

**Rules:**
- HUD draws *above* the damage tint so the bar and digits remain readable at maximum tint alpha.
- HUD draws *below* the game-over border so the colored border still frames the entire screen on win/lose.
- HUD is drawn whether the game is in play or in a game-over state. Health-zero displays as `0` with the `LOW` band color.

## State

The HUD owns **no state**. Every per-frame value is recomputed from `player.health`, `PLAYER_MAX_HEALTH`, and the tuning constants. *(Knowledge: § Read-only Contract — the reference's widget structs hold pointers and never write back.)*

The bitmap font is a compile-time constant table (`HUD_DIGIT_GLYPHS`) of ten entries, each a `HUD_DIGIT_HEIGHT_PX`-element array of bitmask rows of width `HUD_DIGIT_WIDTH_PX`. Glyph data lives in the renderer module; it is not a tuning constant. *(Generation default: the reference loads glyphs from an asset lump system at startup and reads dimensions from each patch header. We use a hardcoded compile-time bitmap because the prototype has no asset pipeline. Glyph dimensions are picked freshly — they cannot be inherited from the reference because the reference reads them from runtime metadata.)*

### Update Cadence

**Trigger:** Every call to `renderer::draw()`.

**Effect:** The HUD redraws fully — every frame, every pixel of the pane.

**Rules:**
- *(Knowledge-deferred optimization)*: the reference engine uses a diff-redraw model — each widget self-checks `old != current` and only re-blits its rectangle, with a "first frame" full-refresh trigger. Our prototype redraws everything every frame because (a) the framebuffer is a flat `Vec<u32>` with no double-buffer, (b) our renderer already redraws floor / walls / enemies / effects every frame, so the marginal cost of HUD pane re-redraw is negligible, (c) implementing widget-level diff would require state on the renderer side, breaking the read-only contract for no observable benefit at this scale.

## Interactions

### With Renderer
- HUD is a private set of helpers inside `renderer`. The public surface is the existing `draw()` function with one additional internal call site.
- HUD reads no other module's state besides `Player` and the tuning constants already imported by the renderer.

### With Player State
- Read-only. HUD reads `player.health`, `player.ammo`, `player.armor`, and `player.armor_type`. It must not mutate the player. *(Knowledge: § Read-only Contract.)*

### With Visual Effects
- None. HUD is drawn *on top of* the damage tint overlay produced by `visual_effects`, but does not interact with the effects list. *(In the reference, the equivalent damage feedback is a global palette tint that the digits inherit passively; we instead overlay digits *above* the tint so they remain readable.)*

### With Game Loop
- None. HUD has no per-frame tick or update; the renderer's existing `draw()` call is the sole entry point.

## Constraints

### Invariants
- `player.health` is read but never written by the HUD.
- The HUD pane never overlaps gameplay-critical pixels at the top-left corner of the framebuffer (the pane footprint is `HUD_MARGIN_PX + bar_width + gap + 3*digit_width + HUD_MARGIN_PX` wide and `HUD_MARGIN_PX + max(bar_height, digit_height) + HUD_MARGIN_PX` tall).
- The HUD is drawn every frame `draw()` is called, including the first frame.

### Determinism
- HUD output is a pure function of `player.health` and the tuning constants. No randomness.

## Deferred

The following are intentionally out of scope for this prototype HUD (or not yet implemented despite being specified):

- **Health bar 1 px outline** (`HUD_FRAME_COLOR` `#C0C0C0`) — specified in spec/25 § HUD Colors; not drawn by current `draw_hud`. Code draws background fill + foreground fill only. Low-priority visual polish.
- **Right-justified digit field** — knowledge § Numeric Widget; current code left-aligns digits from a fixed `digits_x`. Causes field-width shift when health crosses a digit-count boundary (e.g. 100→99). Low-priority given small field size.
- **Multi-state icon widgets** (key cards, weapon-ready slots, animated face portrait) — knowledge documents these but the prototype has no inventory or weapon roster to drive them.
- **HUD low-ammo warning color** — ammo digits are single-color (`HUD_AMMO_COLOR`). Color shift on `ammo < threshold` is deferred.
- **Score / kill counter** — no scoring system in v2026.01.
- **Minimap** — top-down view already shows the entire level.
- **Crosshair / aim reticle** — direction line on the player serves this purpose in 2D top-down.
- **HUD animations** — number tweens, bar drain animation, pulse on damage, low-health flash. Static rendering only.
- **HUD configurability** — position, scale, opacity. Fixed top-left corner.
- **Localization / non-ASCII text** — digits-only.
- **Pickup popup notifications** ("+25 health", "+1 clip"). Visual-feedback spec/40 already defers pickup tint.
- **Diff-redraw optimization** (per § Update Cadence) — deferred until profiling shows full-frame HUD redraw is a hot path.
- **Bottom-anchored chrome strip** (knowledge default layout) — deferred; top-down view does not have a "bottom" UI band convention.
- **Global palette-shift damage feedback** (knowledge default color channel) — covered separately by spec/40 damage tint overlay; the bar's per-band coloring is the prototype substitute.

## Test Scenarios

### Health Pane Geometry
1. With `player.health = PLAYER_MAX_HEALTH`, the foreground fill spans the full interior of the bar.
2. With `player.health = PLAYER_MAX_HEALTH / 2`, the foreground fill spans approximately half the interior of the bar (rounded by integer pixel math).
3. With `player.health = 0`, the foreground fill is zero pixels wide; the background fill remains visible.
4. With `player.health < 0` (transient before clamp), the displayed digit is `0`, not a negative sign or empty.

### Health Bands
1. Health at `PLAYER_MAX_HEALTH` selects `HUD_HEALTH_COLOR_HIGH`.
2. Health just below the high threshold selects `HUD_HEALTH_COLOR_MID`.
3. Health just below the low threshold selects `HUD_HEALTH_COLOR_LOW`.
4. Health at zero selects `HUD_HEALTH_COLOR_LOW`.

### Numeric Widget (knowledge-grounded behaviors)
1. Health value 7 in a 3-digit field renders as `7`, NOT `007` (no leading zeros — knowledge § Numeric Widget).
2. Health value 0 renders as the digit `0`, NOT blank (zero special-case — knowledge § Numeric Widget).
3. Each digit `0..=9` renders into a `HUD_DIGIT_WIDTH_PX × HUD_DIGIT_HEIGHT_PX` glyph block, scaled by `HUD_DIGIT_PIXEL_SIZE`.
4. Multi-digit numbers (e.g. `100`) advance horizontally by `HUD_DIGIT_WIDTH_PX*HUD_DIGIT_PIXEL_SIZE + HUD_DIGIT_KERN_PX` per glyph (= 3×2 + 1 = 7 px per character).

### Render Order
1. The HUD pane pixels are not overwritten by any subsequent gameplay layer.
2. The game-over border draws *over* the HUD on the four edge bands; the HUD interior remains visible.
3. With damage tint at maximum alpha, the HUD foreground color remains distinct from the surrounding tinted area.

## Implementation Status

**Implemented:**
- Health bar (frame, background, foreground fill) in top-left corner.
- Numeric health display next to the bar using a bitmap digit font (no leading zeros, `0` special-cased per knowledge § Numeric Widget). Right-justification is **not yet implemented** — digits are left-aligned from a fixed x offset (`digits_x = HUD_MARGIN + HUD_BAR_WIDTH + HUD_PANE_GAP_PX`); tracked as deferred below.
- Color-coded health bands (HIGH / MID / LOW thresholds).
- HUD layered above damage tint, below game-over border.
- Ammo pane below health pane (yellow icon + yellow digits, single color).
- Armor pane below ammo pane (tri-state color per `armor_type`: gray / green / blue; icon + digits).

**Deferred** (also listed in the Deferred section above):
- Multi-state icon widgets.
- Score / kill counter.
- Minimap.
- Crosshair / aim reticle.
- HUD animations.
- HUD configurability.
- Localization / non-ASCII text.
- Pickup popup notifications.
- Diff-redraw optimization.
- Bottom-anchored chrome strip.
- Global palette-shift damage feedback.
