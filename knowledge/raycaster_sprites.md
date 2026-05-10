# Finding: Sprites and Billboards in a Column Renderer

## Summary

The reference engine draws every world-space entity (enemies, projectiles, pickups, corpses, gibs, decoration items, blood splats and similar visuals) as a screen-aligned billboard — a flat 2D image scaled by perspective. Each billboard is processed in three steps: (1) transform its world position into camera space and reject anything behind the camera plane or off the side; (2) compute a single per-sprite scale factor `xscale = focal / forward_distance` and use it to derive the screen-space x-range and the per-row vertical extent; (3) draw the sprite column-by-column, occluded by closer walls and (in regions of overlap) by closer sprites. Wall occlusion is per-column: each screen column carries a depth value written during the wall pass, and a sprite column is drawn only where its own forward distance is smaller than that column's wall depth. Sprites are sorted back-to-front so that overlapping sprites composite correctly without per-pixel depth comparisons against each other.

## Observed Mechanics

### World → Camera-Space Transform

- **Behavior**: An entity's world-space position is rotated and translated into a camera-relative frame so that the camera-forward axis becomes the depth axis (`z` / forward) and the camera-right axis becomes the screen-horizontal axis (`x_cam`). Only the forward and right components matter for billboard projection — vertical placement is handled separately from sprite anchor data.
- **Rules**:
  - Translate by camera position: `tr = entity.world_pos - camera.pos`.
  - Rotate into camera frame using the camera's forward unit vector `f = (cos(yaw), sin(yaw))` and right unit vector `r = (sin(yaw), -cos(yaw))` (or the same rotation expressed via stored `viewcos` / `viewsin`):
    - `forward_dist = dot(tr, f) = tr.x * cos(yaw) + tr.y * sin(yaw)`
    - `right_offset = dot(tr, r) = tr.x * sin(yaw) - tr.y * cos(yaw)`
  - The reference computes both as paired fixed-point multiplies of the translated coordinates with the cached cosine/sine of the camera yaw; the sign convention on `right_offset` makes positive values map to the right half of the screen.
- **Constants**:
  - **Near-plane reject** (`MINZ`): the reference rejects any sprite whose forward distance is less than 4 world units (`FRACUNIT * 4`). Below this, the projection scale would explode (`focal / 0`). Combined with the entity's own collision radius, this means an entity directly on top of the camera is invisible — a deliberate fail-safe rather than a visible artifact, because such a state already implies a hit / pickup pickup-tile event has fired.
  - **Side-cone reject**: a coarse pre-test of `|right_offset| > 4 * forward_dist` rejects sprites well outside the horizontal field of view before the screen-x range is computed. The factor of 4 corresponds to the reference's 90° FOV: at the FOV edge, `tan(45°) = 1`, so `|right_offset| < forward_dist` is the precise edge; the `× 4` slack is an early-out that keeps obviously-off-screen sprites out of the more expensive screen-x clip path.
- **Feel**: The camera-space transform is the single point where "world position" becomes "what the player sees from here." Bugs in sign convention manifest as sprites snapping to the wrong side of the screen when the player turns; mismatched cosine/sine handedness puts entities on the opposite side of every wall.

### Per-Sprite Scale and Screen-Space X-Range

- **Behavior**: The reference treats each billboard as having one perspective scale across its whole horizontal extent — the sprite is screen-aligned, so it does not foreshorten as you walk past it. The scale is `focal / forward_dist`, identical in form to the wall projection (knowledge: `raycaster_renderer.md` § Column Projection Model). The screen-x edges and the per-column vertical extent are derived from this single scale.
- **Rules**:
  - `xscale = projection / forward_dist`, where `projection` is the same focal-length value used for wall column projection (knowledge: `raycaster_renderer.md` § Column Projection Model — at 90° FOV, `projection = screen_half_width`).
  - Screen-x of the left edge: shift `right_offset` left by the sprite's left-bearing (its world-space left-of-anchor distance), then `x1 = screen_center_x + (left_edge_offset * xscale)`.
  - Screen-x of the right edge: add the sprite's world-space width, then `x2 = screen_center_x + (right_edge_offset * xscale) - 1`.
  - Both edges are clamped to `[0, viewport_width - 1]` after computing — this handles sprites partially off-screen by drawing only their visible columns.
  - The horizontal step into the sprite's source pixels per screen column is `xiscale = 1 / xscale` (a multiply-and-step rather than a per-column divide). Negative `xiscale` denotes a horizontally-flipped sprite (used for the rotational-frame system, below).
  - Vertical placement uses the sprite's anchor offset: the top edge of the sprite in screen rows is `screen_center_y - (anchor_top_world_offset - camera_z) * xscale`. For an entity standing on the floor with the camera at the same eye height, this places the sprite's vertical center near the horizon row.
  - Per-row vertical step into the sprite's source pixels is the same `1 / xscale`. The reference tolerates non-square pixels by using the same scale for both axes — a square-pixel target produces correctly-proportioned billboards without a separate vertical scale.
- **Constants**:
  - The per-sprite scale is clamped to the same range as walls (knowledge: `raycaster_renderer.md` § Perpendicular Distance — `[~1/256, 64×]` of the unit projection). Below the lower bound the sprite is too small to draw and is skipped; above the upper bound it is drawn at near-screen size.
  - **Vertical-FOV cap** (implicit): a too-close sprite produces `xscale` so large that the projected billboard exceeds the viewport. The clamp prevents a runaway divide; visually, the sprite "fills the screen" briefly before it is consumed (touched / shot / picked up).
- **Feel**: Single-scale-per-sprite keeps sprites as flat cardboard cutouts. The choice is the genre's defining "look" for entities — what makes the reference's enemies look painted on the world rather than truly 3D. A consumer who picks per-column scale instead would either need genuine 3D models (out of scope) or a per-column world-space transform that re-derives forward_dist for each column (more expensive than the single divide here, with no perceptual benefit at billboard cardinality).

### Per-Column Wall Depth (Z-Buffer Equivalent)

- **Behavior**: For sprites to be occluded by walls correctly, the renderer needs a per-column "how close is the wall in this column" value. The reference encodes this implicitly via two paired structures: per-segment scale values (`scale1`, `scale2` — the sprite-scale equivalents at the segment's two screen-x endpoints) and per-column clip arrays (`sprtopclip[x]`, `sprbottomclip[x]`) populated during the wall pass. A column-renderer simplification — natural for a tile-grid world (knowledge: `raycaster_renderer.md` § Wall Traversal Strategy) — is a single per-column depth array of size `viewport_width`, written during the wall pass and consulted during the sprite pass.
- **Rules** (the reference's drawseg-based form):
  - Each visible wall segment records `scale1` and `scale2` — the per-sprite-scale values at its left and right screen-x edges. These are computed from the segment's perpendicular distance and the column's view angle, identical in form to wall column scaling (knowledge: `raycaster_renderer.md` § Perpendicular Distance).
  - During the wall pass, two arrays of length `viewport_width` are filled: `ceilingclip[x]` records the lowest screen row above which subsequent draws may write (the top of "open space" per column), and `floorclip[x]` records the highest screen row below which subsequent draws may write. A solid (single-sided) wall sets `ceilingclip[x] = viewport_height` and `floorclip[x] = -1` after writing its column — i.e. "no open space remains in this column."
  - Sprite-vs-wall depth is decided per drawseg, not per column: when a sprite overlaps a drawseg's screen-x range, the renderer compares the drawseg's `scale1`/`scale2` against the sprite's `scale`. If the wall scale is strictly greater than the sprite scale (wall is closer), the wall clips the sprite — the sprite's top/bottom clip arrays inherit the drawseg's `sprtopclip` / `sprbottomclip`. Otherwise the sprite is drawn unclipped over the wall in those columns.
- **Rules** (the column-renderer / grid-DDA simplification, equivalent up to per-pixel rounding):
  - Allocate one `wall_depth[viewport_width]` array, sized to the framebuffer width. Initialize to `+infinity` (or the far-clip value) at frame start.
  - During the wall column pass (knowledge: `raycaster_renderer.md` § Per-Frame Draw Dispatch step 4), after computing each column's perpendicular distance, write `wall_depth[x] = perp_dist`. If a column's DDA walk hit no wall within the far-clip distance, leave the entry at `+infinity` — sprites in that column are drawn unobstructed.
  - During the sprite pass, for each sprite column `x ∈ [x1, x2]`, compare the sprite's forward distance to `wall_depth[x]`. If `sprite_forward_dist < wall_depth[x]`, draw the column; otherwise skip it.
  - This single-array scheme works because every wall column has exactly one depth value (one ray per column), so the per-column `wall_depth` is the natural successor to the reference's per-drawseg `scale1`/`scale2` interpolation.
- **Constants**:
  - **Storage**: one float per column, allocated once at startup (size = viewport width). No per-frame allocation; written in the wall pass, read in the sprite pass, otherwise untouched.
  - **Initialization sentinel**: a far-clip-equivalent value (positive infinity, or any value at least as large as the renderer's maximum render distance) so that a column with no wall hit still produces a legitimate depth comparison.
  - **Comparison**: strict-less-than (`<`), not less-or-equal — at exact equality (sprite touching the wall) the wall wins, matching the reference's drawseg-comparison convention.
- **Feel**: The per-column z-buffer is the cheapest possible occlusion mechanism for a billboard system — one float-compare per sprite column. It produces clean wall-edges-cutting-off-sprite silhouettes; without it, sprites visibly poke through walls or float in front of them. The reference's drawseg-and-clip-array machinery exists because its world geometry is line-and-sector data with non-axis-aligned walls and varying floor/ceiling heights; for a uniform tile grid, the per-column z-buffer is the same idea collapsed to a single array.

### Per-Column Height and Vertical Clip

- **Behavior**: For each visible sprite column, the renderer computes a top and bottom screen row (`yl`, `yh`) using the per-sprite scale and the sprite's anchor offsets, then clips against `mceilingclip[x]` and `mfloorclip[x]` — column-of-arrays populated by the previous draw passes (walls, masked mid-textures, and any earlier sprites). Only rows in the surviving `[yl, yh]` range are written to the framebuffer.
- **Rules**:
  - Top row: `yl = ((sprite_top_screen + frac_unit - 1) >> frac_bits)` with `sprite_top_screen = screen_center_y_frac - (texturemid * xscale)` where `texturemid = sprite_top_world_z - camera_z`.
  - Bottom row: `yh = (sprite_bottom_screen - 1) >> frac_bits` with `sprite_bottom_screen = sprite_top_screen + (sprite_world_height * xscale)`.
  - Per-column clip:
    - if `yh >= mfloorclip[x]`: `yh = mfloorclip[x] - 1`
    - if `yl <= mceilingclip[x]`: `yl = mceilingclip[x] + 1`
  - If `yl > yh` after clipping, no rows are written for this column (the sprite is fully behind a wall in this column).
  - **Per-column stepping into source pixels** is independent of `yl`/`yh`: the column iterator walks the source patch's posts top-to-bottom, mapping each post's vertical extent to screen rows via the same `xscale`. A patch with a vertical hole produces a transparent gap in the sprite — used heavily for thin sprites with fine alpha edges.
- **Constants**:
  - The per-column clip arrays have one entry per column; a single sprite drawing pass reads them but does not modify them. The next sprite (drawn over earlier ones) sees the earlier sprite's painted columns only via the framebuffer, not via the clip arrays — overlapping sprites composite via paint order, not via clip-array inheritance.
- **Feel**: The per-column clip step is what makes sprites look correctly cut by wall corners and by floor edges — a sprite halfway behind a corner shows only the visible columns. Skipping it produces sprites that float in front of geometry; getting the clip equation right on edge cases (sprite straddling a near wall) is the most common bug in column-renderer sprite systems.

### Sort Order: Back-to-Front

- **Behavior**: Sprites that overlap on screen are composited via paint order — the farther sprite is drawn first, and the closer sprite paints over it. The reference sorts the visible-sprite list by per-sprite scale once per frame (smallest scale first = farthest first) and walks the sorted list head-to-tail when drawing. There is no per-pixel depth comparison between two sprites; their relative order is decided once globally, then they paint in that order.
- **Rules**:
  - Build the visible-sprite list during world traversal: a per-sector (BSP) or per-tile (grid) collection pass projects each entity into a vissprite record.
  - Sort the vissprite list by scale ascending — equivalently, by `forward_dist` descending. The reference uses an O(n²) selection sort because n is bounded (`MAXVISSPRITES = 128`); a stable sort is not required because the sort key alone (scale) is a total order on visible sprites.
  - Walk the sorted list head-to-tail, drawing each sprite. The result is correct back-to-front compositing: any closer sprite that overlaps a farther one paints over it.
  - The reference also draws masked mid-textures (translucent two-sided wall sections — knowledge: `raycaster_renderer.md` § Wall Traversal Strategy "Sprites are collected during BSP traversal and drawn back-to-front in a separate masked pass") inline with sprites, in a single combined pass. A column-renderer with no two-sided walls only needs the sprite half.
- **Constants**:
  - **Visible sprite cap** (`MAXVISSPRITES`): 128 — a pre-allocated buffer; sprites beyond the cap fall back to an "overflow" slot and are effectively dropped (drawn at the same position as the previous overflow). For a small project with at most a few enemies + projectiles + corpses + pickups + blood splats per frame, 128 is far above the actual count and the cap acts as a safety net rather than a tuning knob.
  - **Sort cost**: O(n²) selection sort over visible sprites is `n × (n-1) / 2` comparisons per frame; for n ≤ ~32 active entities, this is well under 1 µs of work and not a concern. Switching to an O(n log n) sort gives no perceptible benefit at this scale.
- **Feel**: Back-to-front sort means that two enemies passing through each other display correctly — the one closer to the camera occludes the one farther away. Get the sort wrong and you see distant sprites painting over near ones, which reads as "enemies suddenly teleport in front of each other" when the camera moves.

### Sprite Rotational Frames (Reference) and the Single-Frame Simplification

- **Behavior**: The reference supports two sprite-frame regimes. (a) Single-frame: one painting per sprite, used from any view angle (decorations, projectiles, pickups). (b) Eight-frame: eight paintings around the entity at 45° increments, with the renderer picking the frame that matches the relative angle between the camera's view ray to the entity and the entity's own facing. Mirroring is used to halve storage — the renderer flips the patch horizontally and re-uses the same source data for the symmetric rotation.
- **Rules**:
  - For an entity with rotational frames, the rotation index is `rot = (angle_to_entity − entity_facing + (45°/2) × 9) >> 29` — i.e. round the relative angle to the nearest 45° step, then take the resulting integer in `[0, 7]` as the frame index.
  - For an entity without rotational frames, the rotation lookup is bypassed and the single frame is used regardless of viewing angle.
  - The flip flag is per-rotation: rotations on the right side of the entity may be mirrored renderings of rotations on the left, with the renderer's per-column horizontal stepping reversed to produce the mirrored image.
- **Constants**:
  - **Rotation count**: 8 (45° per step). The reference encodes this in lump naming and in frame-table arithmetic; a column-renderer without per-rotation art has nothing to vary by viewing angle and can skip the rotation lookup entirely.
- **Generation default for a simplified renderer**: single-frame, no rotation. Each entity type carries one sprite (or one flat-color rectangle, in the un-textured form) and looks the same from every viewing angle. Adding rotation later requires (a) authoring the additional art, (b) extending the entity record with a facing angle, and (c) adding the relative-angle-to-rotation-index lookup. None of this is on the critical path for "sprites visible in first-person view."

### Flat-Color vs Textured Choice

- **Behavior**: Reference sprites are textured patches — column-major, run-length-encoded "posts" of opaque pixels with transparent gaps. The renderer steps through each visible column with `xiscale` (the per-column horizontal step into the source pixels), and each post within a column is drawn with the per-row vertical step (also derived from `xscale`). The colormap selected per sprite (full-bright for muzzle-flash frames, distance-attenuated for normal frames, special palette for damage/pickup states) is the same colormap machinery used for walls (knowledge: `raycaster_renderer.md` § Distance Attenuation).
- **Rules**:
  - Textured form: sprite columns sample source pixels via `xiscale` step, the per-row step samples within each post, and per-pixel writes go through `colormap[index]` for distance attenuation. Non-opaque source bytes (transparent runs between posts) leave the framebuffer unchanged.
  - Flat-color simplification: each entity type has a single fill color (e.g. red rectangle for an enemy, yellow for a pickup, white for a projectile). The per-column vertical extent is computed identically to the textured form; the source-pixel step is replaced with "write the entity's fill color." Distance attenuation is optional — if applied, it follows the same lerp-toward-far convention as the wall pass (knowledge: `raycaster_renderer.md` § Distance Attenuation "simplified" alternative). A vertical-line silhouette (left and right edges drawn in a darker shade, fill in nominal) helps separate adjacent sprites visually.
- **Constants**:
  - **Texturing cost**: one source-pixel byte read per drawn pixel, plus a colormap lookup. For a billboard at near-screen size (height = viewport height, width ≈ viewport width / 8), this is on the order of `viewport_height × viewport_width / 8` per sprite — bounded but non-trivial when many large sprites overlap. Flat-color drops the source-byte read; the colormap lookup may also be replaced by a single per-channel multiply.
  - **Asset pipeline cost**: a textured sprite pipeline requires per-entity art (per rotation, per frame) — a substantial asset budget. Flat-color costs nothing beyond a per-entity-type RGB tuple.
- **Feel**: Textured sprites are essential for the genre's identity — without them entities read as "labeled rectangles" rather than as living things. Flat-color is the natural first-pass sprite output when the asset pipeline is not yet built; it proves that projection, occlusion, and sort are correct, and is cheap to upgrade to textured later by replacing the column-fill step alone (the projection / clip / sort code is unchanged).

### Player-Sprite (Weapon) Overlay

- **Behavior**: The reference draws the first-person weapon (the gun in the player's hands, animated through frames during fire / reload) using the same sprite machinery as world entities, but with two differences: (a) the screen-x range and per-column scale are computed from a fixed "player-sprite scale" rather than a perspective scale (the weapon does not get smaller with distance — there is no distance), and (b) the clip arrays are set to "draw everywhere" so the weapon paints over walls, sprites, and the masked-mid-texture pass alike.
- **Rules**:
  - `pspritescale = projection × viewport_width / screen_width` — a fixed scale used for all player-sprite draws, equal to the per-pixel sprite scale at the screen's nominal projection.
  - The weapon sprite's screen-x position is computed from the player-sprite anchor (`psp->sx`, `psp->sy` — frame-relative offsets that animate when the weapon is fired or reloaded), translated to screen pixels via the fixed scale.
  - Clip arrays: `mfloorclip = screenheightarray` (allow drawing all the way down) and `mceilingclip = negonearray` (allow drawing all the way up). The weapon overlay therefore ignores world occlusion entirely — it paints last, over everything else.
- **Constants**:
  - The weapon overlay is the single sprite that does not participate in the per-column z-buffer comparison or the back-to-front sort. It is drawn after the masked-mid-texture / world-sprite pass, in its own dedicated step.
- **Feel**: The weapon overlay is what makes the view "first-person" rather than just "free camera looking at a world." Its absence is jarring; its incorrect handling (clipping into walls, sorting behind enemies) is even more jarring. Out of scope for the world-sprite slice; covered separately when the first-person weapon is added.

## Key Insights

- **The per-column z-buffer is the natural successor to the reference's drawseg-and-clip-array machinery for a tile-grid world.** Both store the same information (per-column wall depth) in different forms — the reference encodes it as per-segment `scale1`/`scale2` plus per-column `ceilingclip`/`floorclip`, the grid-DDA renderer encodes it as a single per-column `wall_depth[x]` array. A correctness proof reduces to "the column's perp_dist matches what the reference's interpolated `scale` value would yield for that column" — the projection math is the same in both worlds.
- **One scale per sprite, not per column.** Sprites are screen-aligned billboards: the same `xscale = focal / forward_dist` applies to every column of the sprite. This is what gives entities the painted-cardboard look. Per-column scale would imply a true 3D model and is a different, more expensive algorithm with no benefit at the cardinality of in-frame entities.
- **Back-to-front sort with paint-order compositing is enough for sprite-vs-sprite occlusion.** Two billboards at the same column do not need a per-pixel depth test against each other — the closer one painted last wins. The per-column z-buffer is only needed for sprite-vs-wall, because walls and sprites are drawn by different code paths and occupy different vertical extents per column.
- **Near-plane and side-cone rejects are first-class.** Without them, dividing by a tiny `forward_dist` produces astronomical scales and fills the screen with a single sprite; with them, the projection math has guaranteed bounded outputs. The reference's `MINZ = 4` and `|right_offset| > 4 × forward_dist` thresholds are tuned for its 90° FOV and its world-unit scale; a target with different units must scale these constants proportionally.
- **Flat-color sprites are a legitimate first slice.** They prove that camera-space transform, screen-x range, per-column height, per-column z-test, and back-to-front sort are all correct, and the upgrade to textured sprites swaps the column-fill step alone. Building the projection/clip/sort skeleton and the texture pipeline at the same time is harder to debug than separating them.
- **Vertical anchoring is the most common subtle bug.** The sprite top edge is `screen_center_y - (sprite_top_world_z - camera_z) × xscale`, not `screen_center_y - sprite_top_world_z × xscale` and not `screen_center_y - sprite_top_world_z`. Forgetting the camera-z subtraction makes sprites slide vertically as the camera moves; using the un-scaled offset makes them too small or too large. For an entity standing on the floor with the camera at the same eye height, the sprite's bottom edge sits at the horizon row and the top edge is `(entity_height × xscale)` rows above the horizon.

## Open Questions

- **Per-column z-buffer vs. drawseg for masked mid-textures**: a future slice that adds two-sided / portal walls (knowledge: `raycaster_renderer.md` § Deferred — Portal / window walls) will need either drawseg metadata (in addition to the per-column z-buffer) or a more elaborate per-column data structure. Out of scope while the world is solid/empty tiles only.
- **Translucent sprite rendering**: the reference uses a "shadow / fuzz" column function for partially-transparent entities — a per-pixel screen-space dither that samples the existing framebuffer pixel and a colormap entry. A flat-color simplification can ignore this; the trade-off is that translucent entities (e.g. a partially-fading death animation) lose their characteristic look.
- **Frame interpolation between sprite frames**: the reference draws discrete animation frames at the engine's tick rate and does not interpolate between them. Sub-tick interpolation is a separate concern and would belong with first-person weapon / animation work, not with the sprite-projection skeleton.
- **Entity vertical motion**: entities with non-zero height-above-floor (e.g. a hovering projectile, a rocket arc) require the camera-z-subtraction term to use the entity's actual world Z, not a hardcoded floor anchor. Out of scope for the floor-only entity set in early slices.

## Deferred

- **Sprite texturing** (column-major posts with transparent gaps, distance-attenuated colormap lookup) — replaced by flat-color rectangles in the first sprite slice; revisit when an asset pipeline exists.
- **Eight-rotation sprite frames** (per-relative-angle artwork with horizontal mirroring) — replaced by a single fixed sprite per entity type; the rotation lookup is dead code without per-rotation art.
- **Translucent / "fuzz" column rendering** — used for partial-invisibility frames in the reference; the flat-color form has no equivalent and skips this entire path.
- **Player-sprite (first-person weapon) overlay** — separate from world-sprite drawing; covered in a later slice with its own anchor and clip rules.
- **Masked mid-textures** (two-sided walls with translucent middle bands) — knowledge: `raycaster_renderer.md` § Deferred — Portal / window walls.
- **Per-sprite full-bright / damage-flash colormap selection** — depends on the colormap-table form of distance attenuation (knowledge: `raycaster_renderer.md` § Distance Attenuation "32 brightness steps"); the continuous-lerp simplification has no slot for "one frame at full brightness" without re-introducing the table.
- **Entity-to-camera-distance LOD** (drawing fewer columns per sprite at very far distances) — a micro-optimization not relevant at the cardinality of entities in a small grid level.
