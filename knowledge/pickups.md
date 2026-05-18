# Finding: Pickups

## Summary

The reference engine routes all pickup interactions through a single touch-handler called from the world's thing-vs-thing collision step. Pickups are world entities tagged with a "special" flag; when an entity carrying a "can-pick-up" flag overlaps one, a giant per-sprite-kind switch dispatches to small per-category routines (give-health, give-ammo, give-weapon, give-armor, give-keycard, give-power) and the pickup entity is removed. Acceptance is conditional: if the player would not benefit (already at cap), most pickups refuse the pickup, leave it in the world, and produce no message.

## Observed Mechanics

### Pickup Touch Detection

- **Behavior**: Pickup detection piggy-backs on the same broadphase that handles solid-body collision. Each tick of player movement, the engine iterates over things in the destination block, and for each one checks an axis-aligned distance against the sum of the two radii. If the player overlaps a pickup-flagged thing, the touch handler is invoked.
- **Rules**:
  - Broadphase: Chebyshev/AABB distance check `abs(dx) < r_player + r_thing AND abs(dy) < r_thing + r_player`. This is a square collision footprint, not a circle.
  - A vertical reach gate also runs in the touch handler itself: the height delta between player and pickup must satisfy `-step_down <= (pickup_z - player_z) <= player_height`. Pickups above head height or far below the floor a step are out of reach (relevant in multi-floor levels; for a flat 2D prototype, the gate is always satisfied).
  - The player entity must carry a "will pick up items" flag. The pickup entity must carry a "is a special-touch item" flag. Both flags are required.
  - A dead player (health <= 0) cannot pick anything up — a sliding corpse is filtered out at the top of the handler.
- **Constants**:
  - Player radius: 16 world units (matches the value already documented in combat balance).
  - Vertical step-down tolerance: 8 world units below player feet.
  - Tick cadence: handler runs at the same rate as player movement (the engine's tick rate, ~35/sec).
- **Feel**: Square collision footprints make pickups slightly "snappier" to grab than circles would — you can corner-clip a pickup. The check happens during movement resolution, so a fast player crossing a pickup in one tick still triggers it (the blockmap iterator sees them in the destination cell).

### Single-use Consumption

- **Behavior**: Once a pickup is successfully applied, the pickup entity is removed from the world. There is no "respawn" in single-player; the entity is destroyed and freed.
- **Rules**:
  - The handler dispatches by item kind. Each branch returns *early without removing* if the player is already at cap and the item is "refused". Otherwise the branch falls through to a single shared tail that:
    1. Increments the run-statistics item counter (if the item is flagged as counting toward the level total).
    2. Removes the entity.
    3. Adds to the player's pickup-flash counter (a short visual tint — see visual feedback knowledge).
    4. Plays the pickup sound.
  - Refusal path: if the give-X helper returns "no benefit" (e.g. health already at max, ammo bin already full), the early return skips removal, so the entity remains in the world and can be picked up later when the player has room.
- **Constants**:
  - Pickup-flash counter add per pickup: a small fixed increment that decays over a few frames. (See visual_feedback.md for the flash mechanic itself.)
- **Feel**: The "leave it if you can't use it" rule is a quietly important design choice. The player can ignore a large health pickup at full HP and come back to it later — the world remembers what's been used and what hasn't, without explicit save state.

### Health Pickup Tiers

The reference engine has four health-affecting pickups across two semantic groups: *normal-cap* heals (refused at full HP) and *over-cap* heals (always accepted, raise HP above the normal cap up to a hard ceiling).

- **Behavior**: Health pickups restore an integer amount, clamped to either the normal cap (small/large heals) or an absolute ceiling (over-cap pickups).
- **Rules**:
  - Normal-cap heals call a give-body helper that refuses the pickup if `health >= normal_max`, otherwise adds the amount and clamps to `normal_max`.
  - Over-cap heals (small bonus, large overheal) bypass the helper and write the player health directly, clamping to the absolute ceiling. Because they bypass the helper, they are *always* accepted (never refused at any HP value).
  - The third over-cap pickup is a "full restore" that sets HP directly to the absolute ceiling regardless of current value, and additionally grants top-tier armor.
  - All branches mirror the new health value into the player's underlying body-entity health field after writing it.
- **Constants** (role → value):
  - small health pickup → +10 HP, clamps at normal_max, refused at full → 10
  - large health pickup → +25 HP, clamps at normal_max, refused at full → 25
  - tiny bonus pickup → +1 HP, clamps at absolute_max, never refused → 1
  - large overheal pickup → +100 HP, clamps at absolute_max, never refused → 100
  - mega pickup → set HP to absolute_max + grant top-tier armor, never refused → 200
  - normal_max (HP cap for normal heals): 100
  - absolute_max (HP ceiling, including over-cap pickups): 200
- **Feel**: The split into "refused at cap" vs "always accepted" is the design lever. Bonus pickups become a +1 trickle the player can graze through any time, while the +25 large pickup creates a meaningful "save it for when I'm hurt" decision because it's wasted at full HP.

### Ammo Pickup Tiers

Four ammo categories (call them A, B, C, D). For each category there is a "small" pickup that grants one clip-load and a "large" pickup that grants five clip-loads. A separate inventory-expander pickup doubles every per-category cap.

- **Behavior**: Ammo pickups grant a fixed number of clip-loads to a specific category, then the helper multiplies clip-loads to actual round counts and clamps to the per-category cap.
- **Rules**:
  - Each category has two constants: `clip_size` (rounds per clip-load) and `cap` (max rounds).
  - **Pickup-to-category binding is one-to-one and fixed by pickup kind.** Each pickup sprite/entity kind hard-codes which ammo category it grants — a small bullet pickup grants only the bullets category, a small shell pickup grants only the shells category, etc. The pickup helper takes the category as a parameter; no pickup ever spills into a sibling pool. This is the rule that makes per-category accounting tractable: the level designer can place a shell pickup in a corridor and know it will not be silently consumed if the player happens to be holding the pistol.
  - Small pickup: 1 clip-load granted.
  - Large pickup ("box"): 5 clip-loads granted.
  - Dropped variant (small pickup that fell from a defeated enemy, marked with a "dropped" flag): grants 0.5 clip-loads (i.e. half the small pickup's amount). This is the only pickup where the source of the entity matters.
  - Inventory-expander pickup: doubles the cap on every category (one-shot — the player has a "owns expander" flag so picking up a second expander does not double again), and additionally grants 1 clip-load to every category.
  - If the player is already at the cap for that category, the helper returns "no benefit" and the pickup is refused (left in the world). The cap check reads only that category's count — a player at the bullets cap can still pick up a shell pickup if shells are below the shells cap, and vice versa.
  - When the player picks up ammo *and was previously at zero* for that category, the helper also auto-switches the player to the best owned weapon that uses that ammo (so the player isn't left punching when bullets arrive). This is a quality-of-life hook that runs only on the zero→nonzero transition. Crucially, the trigger is the category's prior state being zero — so the first shell pickup the player ever finds auto-equips the shotgun (if owned), but a second shell pickup taken on top of a partially-full shells pool does not re-trigger the swap.
- **Constants** (role → value):
  - Category A (primary clip ammo) → clip_size 10, cap 200, expander cap 400
  - Category B (secondary shell ammo) → clip_size 4, cap 50, expander cap 100
  - Category C (tertiary energy ammo) → clip_size 20, cap 300, expander cap 600
  - Category D (heavy explosive ammo) → clip_size 1, cap 50, expander cap 100
  - Small pickup grant: 1 clip-load (all categories)
  - Large pickup grant: 5 clip-loads (all categories)
  - Dropped-from-enemy small pickup grant: 0.5 clip-load (rounded down for cat. D — see open questions)
- **Feel**: The "small = 1 clip, large = 5 clips" pattern keeps the math memorable for the level designer. The dropped-half rule subtly discourages enemy-farming for ammo: each kill returns less than what spawned the enemy used, so the level still has to *place* ammo. The auto-weapon-switch on zero→nonzero is invisible most of the time but rescues the player from a footgun: if you go dry mid-fight and find a clip, you don't have to manually re-equip the weapon you were already trying to use.

### Armor Pickup Tiers

The reference engine has three armor-affecting pickups across two semantic groups: *tiered* pickups that grant a fixed armor pool at a tier-specific absorb rate, and a *tiny over-cap bonus* that adds one point at a time up to an absolute ceiling.

- **Behavior**: An armor pickup grants an *absorb pool* (an integer count of "absorption points") plus an *absorb rate* (the fraction of incoming damage that is taken out of the pool instead of the player's HP). Two named tiers exist, plus a bonus pickup that trickles single points and never changes the tier.
- **Rules**:
  - The two tiered pickups both call a shared give-armor helper. The helper computes the target pool size from the tier (`target_points = tier * 100`), refuses the pickup if the player's current armor points are already `>= target_points`, otherwise overwrites *both* the armor type and the armor points with the new tier and its target pool.
  - The overwrite semantics matter: picking up the small-tier (green) armor when the player has 50 green sets it to 100 green. Picking up the large-tier (blue) armor when the player has 100 green overwrites to 200 blue — the new tier and its full pool both apply. Picking up the small-tier (green) armor when the player has 200 blue is refused, even though the green pool would itself be a full +100 — the refusal compares raw points, not value, so a partially-depleted blue at >100 points blocks a fresh green.
  - The tiny over-cap bonus pickup bypasses the helper. It increments armor points by exactly +1, clamps at an absolute ceiling (200), is *never refused*, and — only if the player has no armor type set — defaults the armor type to the small tier (so the absorb rate becomes 1/3 if you had none). Note: it does NOT upgrade an existing small tier to the large tier; if the player already has small-tier armor, the bonus keeps the small absorb rate even after the points exceed the small pool's nominal 100 cap.
  - Both tiered pickups, when accepted, also set the underlying "items collected" counter (per the deferred mechanic in the Cap Behavior section above). The bonus pickup does the same.
  - No drop variant exists for any armor pickup — enemies do not drop armor on death. Armor pickups are placed by the level designer only.
- **Constants** (role → value):
  - small armor pickup (tier 1, green) → target pool 100, absorb rate 1/3 (i.e. ~33% of damage diverts to armor) → refused if current armor points >= 100
  - large armor pickup (tier 2, blue) → target pool 200, absorb rate 1/2 (i.e. 50% of damage diverts to armor) → refused if current armor points >= 200
  - tiny armor bonus pickup → +1 armor point, clamps at 200, never refused, defaults tier to small if currently untyped
  - armor type values: 0 = none, 1 = small (green), 2 = large (blue)
  - Absolute armor ceiling (any source): 200 points
  - Player's starting armor: 0 points, type 0 (none)
- **Feel**: The two-tier system gives armor a sense of *progression* without ammo-style scarcity: small armor doubles effective health on the next 33 HP of incoming damage, large armor extends that to ~100 HP. The bonus pickup is a slow trickle the level designer can scatter without worrying about waste — it always advances the player's survival margin by a tiny amount. The "refused if at or above target pool" rule is what prevents the player from "downgrading" by walking over a fresh small pickup at high points — the refusal protects the existing pool. The asymmetric overwrite (large always replaces small if there's room, small never replaces large) makes the player's pickup choices read as monotonic upgrades.

### Cap Behavior

- **Behavior**: At cap, behavior splits cleanly by pickup family:
  - Normal-cap health, all ammo, *tiered* armor (small + large), weapons-already-owned-without-ammo: **refused, pickup remains in world**, no message.
  - Over-cap health pickups (tiny bonus, large overheal, full-restore mega) and the tiny armor bonus pickup: **always accepted** up to the absolute ceiling (200 for both health and armor). The tiny armor bonus is parallel to the tiny health bonus: never refused, clamped at 200, trickles single points.
  - Keycard already held: pickup is silently consumed but no message is shown (in single-player; multiplayer keeps cards in the world). This is a special case because cards are one-bit state.
- **Rules**: Each give-X helper returns a boolean. The dispatch checks the boolean and either falls through to the shared "remove + sound + flash" tail or returns early without removing.
- **Constants**: None new beyond those already listed in tier sections.
- **Feel**: The asymmetry between "refused if at cap" (most things) and "always accepted" (over-cap heals) is what makes over-cap pickups feel rewarding even at full health — they stack onto a pool the player otherwise can't fill. Refusing at cap also prevents accidental waste, which is a huge quality-of-life win on tight ammo budgets.

### Player-Side State

A pickup writes to a small set of fields on the player struct. This is the complete list relevant to health/ammo:

- **Health pickup writes**:
  - `player.health` — primary integer.
  - `player.body_entity.health` — mirror field on the underlying actor entity. This must be kept in sync because some other systems read from the body-entity copy.
- **Ammo pickup writes**:
  - `player.ammo[category]` — current rounds in that category. The field is array-indexed by the ammo-category enum; each category is an independent integer, so writes to one slot never read or modify another slot. A small bullet pickup writes `player.ammo[bullets]` and touches nothing else; a small shell pickup writes `player.ammo[shells]` and touches nothing else.
  - `player.maxammo[category]` — cap for that category, array-indexed identically. Only the inventory-expander pickup writes this (and it writes every slot via a loop).
  - `player.owns_expander` — one-bit flag, only the expander pickup writes this.
  - `player.pending_weapon` — only on the zero→nonzero ammo transition for the category that was just topped up, set to the best owned weapon for that category. The actual weapon swap happens later when the current weapon's lower-animation finishes.
- **Armor pickup writes**:
  - `player.armor_points` — current absorption-point pool (0..200).
  - `player.armor_type` — tier identifier (0 = none, 1 = small, 2 = large). The two tiered pickups overwrite both fields; the tiny bonus pickup writes only `armor_points` and only sets `armor_type` to 1 if it was 0.
- **Common writes (any successful pickup)**:
  - `player.pickup_flash_counter` — short visual tint counter, incremented by a small fixed amount.
  - `player.message` — pointer to a static "you got X" string for the HUD message line. (Note: this is a pointer assignment, so the message strings live elsewhere; only the pointer is per-player state.)
  - `player.itemcount` — only if the pickup is flagged as counting toward the level item total. Health and ammo pickups are *not* flagged this way; only over-cap heals, armor pickups, the mega pickup, and powerups count. So routine ammo/health pickups do not advance the "items collected" stat.
- **Player-state observation**: Pickup logic never reads or writes the player's position, velocity, facing angle, or weapon-firing state directly (other than the pending-weapon hint). The player keeps moving / firing through the pickup tick.

### Ammo Gating of Firing

Three checkpoints in the firing pipeline gate on ammo, in this order:

1. **Pre-fire intent check** (`check_ammo` helper, called at the top of every fire-weapon transition):
   - Looks up the active weapon's ammo category.
   - Computes the per-shot cost: 1 round for most weapons, 2 rounds for the double-barrel variant, a larger fixed bundle for the high-tier energy weapon.
   - If the weapon uses no ammo (melee), or the player has at least the per-shot cost in the right category, returns "ok, fire".
   - Otherwise, returns "no, can't fire" *and* sets `pending_weapon` to the best owned alternative (priority order: top-tier energy > double-barrel > rapid-fire > shotgun > pistol > saw-melee > explosive-launcher > top-tier-energy-with-large-reserve, falling back to the bare-fist if nothing else qualifies). This is what makes the player visually swap weapons when they run dry — the lower-animation begins right away.
2. **Shot-time decrement**: When the firing animation reaches the shot-state action, the action routine decrements ammo *before* spawning the shot. So a successful intent check at step 1 can technically still fail conceptually if something invalidated state in between, but in practice ammo is committed at the moment the visual fire happens, not when the trigger is pressed.
3. **Belt-and-suspenders re-check** in the rapid-fire weapon: its per-shot action also checks `ammo[category] > 0` and silently returns without firing if zero. This is a redundant guard — the higher-level intent check should already prevent reaching here on empty — but the rapid-fire weapon fires twice per cycle and the second shot can theoretically hit zero mid-cycle.

- **Behavior** (summary): The trigger is gated. If you have ammo, the gun fires and 1 (or 2, or N) round is consumed *as the shot leaves*. If you don't, the gun does not fire, no sound plays, and you are auto-switched to a fallback weapon.
- **Rules**: Decrement-before-spawn ordering. No "free shot at zero" — the ammo check runs first.
- **Feel**: The auto-switch is the key design move. Running dry doesn't leave the player helpless; the gun visibly lowers and the next-best gun comes up. Minor friction-removal that hugely improves the moment-to-moment feel.

### Drop on Kill

Some enemy kinds drop a small pickup on death. The drop is deterministic per enemy kind (no random roll) and produces a single entity with the "dropped" flag set, which (per the ammo-tier rules above) grants half the round count of a normally-placed equivalent pickup.

- **Behavior**: At the moment an enemy enters its death state, the kill-routine checks the enemy's kind and, for a small subset, spawns one pickup at the enemy's feet.
- **Rules**:
  - The drop is hard-coded by enemy kind, not by a probability table. Some enemy kinds drop nothing.
  - The dropped entity carries the "dropped" flag. The pickup helper's dropped path grants half the normal small-pickup amount.
  - There is no drop for the over-cap heals, armor pickups, large ammo boxes, or expander — only small ammo pickups and (one-of-each) the dead enemy's weapon if they were carrying a weapon variant the player can pick up.
- **Constants** (kind → drops):
  - basic hitscan trooper → small primary-ammo pickup (dropped, ~half clip-load)
  - shotgun trooper → secondary-ammo weapon (which itself comes with some shells via the give-weapon helper)
  - rapid-fire trooper → primary-ammo weapon variant (similar)
  - all other enemies → no drop
- **Feel**: Drops are a slow trickle, not a windfall. The half-amount rule means the player can't sustain themselves indefinitely on enemy kills — they have to engage the level's placed pickups. For a 2D prototype that defers enemy drops entirely, this is purely informational, but it's the reason the *placed* small-pickup amount is 10: half of that (5) is what a basic trooper "refunds" you per kill, and a basic trooper costs you ~2 shots = 2 rounds, leaving a +3 net per kill. That margin is where the level's overall ammo economy lives.

### Difficulty / Skill Multipliers

The engine *does* multiply ammo pickup amounts by skill, but only on the two extreme skill bands.

- **Behavior**: On the easiest skill ("trainer") and hardest skill ("nightmare"), the give-ammo helper doubles the granted amount. On the three middle skills, no multiplier is applied.
- **Rules**:
  - The multiplier is applied inside the give-ammo helper, *after* converting clip-loads to rounds and *before* clamping to cap. So even on doubled-ammo skills you cannot exceed the per-category cap.
  - The multiplier applies to *all* ammo sources (small pickups, large pickups, expander, drops, give-weapon's bundled ammo).
  - Health pickups have *no* skill multiplier.
  - Damage taken on the easiest skill is halved (separate from the pickup multiplier — see combat balance).
- **Constants**:
  - Easiest skill ammo multiplier: 2x
  - Hardest skill ammo multiplier: 2x
  - Middle three skills: 1x
- **Feel**: The doubled-ammo-on-easiest-skill is mercy for new players. The doubled-ammo-on-hardest-skill is a *concession* — the hardest skill respawns enemies and accelerates them, so without the ammo bump the run would be unwinnable on placed ammo alone. Note these two bands have the *same* multiplier despite opposite intent.

## Key Insights

1. **The "left in the world if at cap" rule is the most important design lever.** It turns pickups into persistent reserves the level designer can place liberally without worrying about waste. The player implicitly learns to leave large heals as breadcrumbs and come back hurt.

2. **Two health caps, two pickup families.** The split between "normal-cap heals refused at 100" and "over-cap heals accepted up to 200" gives over-cap pickups intrinsic value at any HP. This is much more elegant than a single cap.

3. **Auto-weapon-switch on zero→nonzero ammo, and on zero ammo while firing.** Both transitions are handled. The result is that the player almost never has to consciously manage which weapon they're holding when ammo runs out or arrives — the engine smoothly demotes/promotes them. This is a large quality-of-life win that's invisible when working and sorely missed when absent.

4. **Drops are deterministic, not random.** No drop tables, no chance rolls. The level designer can predict exactly how much ammo a fight returns.

5. **The "dropped" half-pickup rule** is a clever economy lever: it ensures placed pickups dominate the ammo budget without making enemy kills feel un-rewarding.

6. **The expander pickup doubles caps but is one-shot.** This is the only inventory-shape change in the entire pickup system. It also gives one clip of every category as a sweetener.

7. **Pickup detection lives in the same loop as solid-body collision.** No separate "pickup tick" or "trigger volume" abstraction — pickups are just entities flagged for special touch behavior. This keeps the system simple but means the broadphase has to handle three flag combinations (solid, shootable, special).

8. **Square collision footprints, not circles.** Picking up an item is slightly more forgiving on the diagonal than a circle would be. For a top-down 2D prototype this matches the "feels right" implementation: AABB overlap.

## Open Questions

- For the "dropped" small pickup of category D (heavy explosive ammo), the math `clip_size/2 = 1/2 = 0` would mean enemies of that type drop literally zero rounds. The reference engine has no enemy that drops category-D ammo, so this case never fires in practice — but the formula would silently produce a no-op pickup if someone added one. Worth noting if the prototype ever has an explosive-dropping enemy.
- The exact tick-precision of the auto-weapon-switch: the swap happens during the next weapon-lower frame, not instantly. For the prototype with one weapon, this is moot, but for any prototype with multiple weapons it matters whether the player can fire-cancel the swap.
- The pickup-flash counter additive constant is shared across all pickups. Multiple pickups in quick succession compound the flash. The exact decay rate per tick is in the visual-feedback knowledge, but the question of whether to expose this as a separate "pickup intensity" lever (small heal flash dimmer than mega flash) was *not* taken in the reference engine — every pickup contributes the same flash amount.
- Whether the broadphase guarantees pickup detection at very high player speeds: for the prototype, player speed is bounded such that one tick of movement is well under the radius sum, so this is a non-issue, but a fast-motion mode might tunnel through pickups.

## Deferred

- **Weapon pickups** — same dispatch path, give-weapon helper. Has its own rules around "first-time weapon" vs "duplicate" vs "dropped" (dropped weapons grant 1 clip, found weapons grant 2, and in the multiplayer-deathmatch sub-rule, 5). Out of scope for this pass.
- **Keycard pickups** — six total (three colors, two visual variants per color). One-bit flags. Always picked up but the entity remains in the world in network/multiplayer mode.
- **Powerup pickups** (invulnerability, partial invisibility, environmental-protection suit, full-map reveal, low-light vision, melee-strength) — all route through a give-power helper that writes a tic countdown timer (or a one-bit flag for the map reveal). Each has its own duration constant. Out of scope for this pass; would warrant a separate `knowledge/powerups.md` if the prototype adds any.
- **Sound and HUD message routing** — pickups play a pickup sound and set a HUD message string. The sound varies by pickup family (generic-item sound vs power-up sound vs weapon-up sound). The message strings are localized in a separate header. Both are intentionally not extracted here as constants.
- **Item-count statistics** — pickups optionally increment a level-completion stat for "items collected". Health and ammo pickups are *not* counted; over-cap heals, armor, mega, and powerups *are* counted. Mentioned briefly in player-side state above; full intermission/scoring mechanics deferred.
