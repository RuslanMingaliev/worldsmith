# Finding: Level Scenarios (Scripted Entity Placement + Deterministic Replay)

## Summary

The reference game treats a level as two concerns that are kept strictly separate: a static geometry description (lines and sectors) and a list of entity-placement records ("things"). Every entity that exists at the start of a level — player spawn, monsters, pickups, decorations — is one fixed-shape record in that list, processed by a single dispatch loop at level-init. Combined with a fixed-table pseudo-random sequence that is reset to a known state at level-init, this gives the engine a surprisingly small surface for "purpose-built scenario": author a tiny geometry, append a few entity-placement records, reset the random index, and the resulting playback is byte-stable.

Two behaviors make such scenarios visually informative for a chase-around-obstacle demo: (a) enemies move on an 8-direction discrete grid with a short commitment counter, so direction changes are visible per-tick rather than averaged into a smooth curve; (b) the chase routine treats blockage and "commitment expired" as the same trigger — both call the same direction-reselection routine, which prefers a direct diagonal toward the target before falling through to perpendicular and finally a full 8-direction sweep.

## Observed Mechanics

### Entity Placement Record

- **Behavior**: A level's entity content is a flat array of fixed-size records. Each record is exactly five small integers — world x, world y, facing angle (in degrees), a numeric type tag, and a bitmask of placement options (skill-level mask, multiplayer-only flag, etc.). At level-init, the engine walks the array and dispatches each record by its type tag to a corresponding spawn routine.
- **Rules**:
  - Type tags are dense small integers, not strings. The dispatch is a linear scan over a table of "entity info" rows, one per known type, looking for a matching tag.
  - Position is in world units (the same units the simulation uses for movement and collision); facing is quantized to 45° increments before being stored on the live entity.
  - A handful of type tags are reserved for the player's spawn point — they don't create a free-standing entity, they instead bind a position and angle to the (already-existing) player-state and put the player in a "live" state.
  - Options bits filter records out before dispatch (e.g. "this thing only exists on hard skill", "this thing only exists in multiplayer"). A scenario that wants every record to spawn unconditionally simply sets all relevant bits.
- **Constants**:
  - Record size: 5 short integers (10 bytes when packed, but the format is what matters, not the byte layout).
  - Facing quantization: 45° increments (8 distinct facings).
  - Reserved spawn-point type tags: a small contiguous range at the bottom of the type space (the first few tags map to player slots, not to free entities).
- **Feel**: Because every entity is "just another row", the reference game has no concept of a "scenario" as a distinct object — it gets scenario-style determinism for free by writing tiny levels with hand-picked rows. There is no procedural generator, no template language, no DSL. The generator is the level author.

### Obstacle-Aware Chase (Direction Reselection)

- **Behavior**: An enemy in the chase state moves in one of 8 discrete directions (cardinal + diagonal). On each behavior tick, the enemy decrements a commitment counter; when the counter reaches zero — or when an attempted move is blocked by geometry or another entity — the enemy reselects its direction. After committing to a new direction, the counter is re-randomized to a small value (0–15 ticks), so direction changes stay visible but the entity does not jitter every frame.
- **Rules** (direction-reselection algorithm, in priority order):
  1. **Direct diagonal toward target.** Compute the world-axis preference along x and y from the displacement vector to the target (ignoring an axis if the displacement on it is below a small dead-band). If both axes have a preference, try the diagonal that combines them.
  2. **Perpendicular alternates.** If the diagonal failed (or one axis was dead), try the two pure-axis directions individually. The order in which they are tried is biased: roughly 80% of the time the algorithm tries the larger-displacement axis first; the remaining 20% it swaps. The "swap" branch also fires unconditionally when the y-displacement magnitude exceeds the x-displacement magnitude — making the rare-direction choice slightly more interesting near vertical chases.
  3. **Continue old direction.** If neither perpendicular worked, retry the direction the entity was already moving in. This is what produces the characteristic "skim along a wall" behavior — the enemy runs parallel to an obstacle until it ends.
  4. **Full 8-direction sweep.** Iterate every direction (excluding the U-turn back toward where the enemy just came from). The iteration order is itself randomized — half the time it sweeps clockwise from east, half the time counter-clockwise from south-east — so two enemies stuck against the same obstacle don't always pick the same escape.
  5. **U-turn.** Last-resort: turn around 180°. If even that fails, the enemy enters a "no direction" state and stops moving until something changes.
  - Each candidate direction is validated by an actual movement attempt (collision-checked against geometry and other entities). The reselection routine commits as soon as one attempt succeeds; later candidates are not considered.
  - The U-turn direction is excluded from priorities 2 and 4 explicitly. The reference does this so that enemies never oscillate between two directions on consecutive ticks — without this exclusion, an enemy that gets briefly blocked would frequently snap back the way it came.
- **Constants**:
  - Direction count: 8 (cardinals + diagonals), plus a sentinel "no direction" state.
  - Displacement dead-band: 10 world units. Within ±10 of perfect alignment on an axis, that axis is treated as "no preference" rather than rounded to one direction or the other.
  - Commitment counter range after a successful direction commit: 0–15 ticks (inclusive).
  - Perpendicular-swap probability: ~22% (the random byte > 200 out of 256). Boosted to 100% when |dy| > |dx|.
  - Sweep-direction coin: 50/50.
- **Feel**: The combination of "commit for 0–15 ticks then reconsider" with "blockage forces immediate reconsideration" is what makes enemies look intent rather than twitchy. They visibly slide along walls, round corners, and only lose the player when an obstacle pushes them through the full priority chain. For a chase-around-obstacle demo, an obstacle that occupies the diagonal between enemy and player forces priority 1 to fail; the enemy then takes a perpendicular and skims the obstacle (priority 3) — exactly the behavior such a demo is meant to show.

### Determinism Preconditions

- **Behavior**: The engine produces byte-identical playback for a given input scenario when three preconditions hold: the random sequence is reset to a known state at level-init, the simulation steps at a fixed time-per-tick (decoupled from rendering), and player input is replayed from a recorded stream rather than read from the live device.
- **Rules**:
  - **Random sequence**. The engine carries a single 256-byte fixed table and two byte-wide indices into it (one for gameplay, one for cosmetic uses). Each call returns the table value at the next index and increments the index modulo 256. There is no seed-from-time, no hash-from-platform-state — the sequence is the table. At every level-init the engine zeros both indices, so any scenario starts from the same first random byte regardless of what happened before.
  - **Fixed simulation step**. The simulation runs at a fixed tick rate (35 ticks per second in the reference; the rate itself is not the point — the determinism property is). Per-tick logic uses `1/tick_rate` as its delta, never wall-clock deltas. The renderer is allowed to sample the simulation at the host's actual frame rate, but the simulation itself never sees host timing.
  - **Recorded input replay**. Demo playback substitutes a recorded byte stream for the live input device. The replay code path is otherwise the same as live play — same tick loop, same simulation, same random table — so the only source of non-determinism that remains is the input stream, and that is what was recorded.
- **Constants**:
  - Random table: 256 bytes, fixed values, hardcoded.
  - Index width: one byte each (so the period is 256 calls before the table repeats — short by modern standards, but adequate for the gameplay uses it serves).
  - Tick rate: 35 Hz in the reference. (The current project's spec uses 60 Hz; the determinism property is independent of the specific rate.)
- **Feel**: The "reset at level-init" rule is what makes scenarios composable. An author can write a tiny level, know that a fresh load will deterministically produce the same monster behavior, and trust that the demo recorded today will be byte-identical to the demo recorded a year from now from the same level + the same recorded inputs.

## Key Insights

- **A "scenario" needs almost no new abstraction.** The reference shows that "purpose-built scripted level" is just (a) a tiny geometry description and (b) a short list of entity-placement records, processed by exactly the same code path that processes any other level. A project introducing a level-generator abstraction does not need a generator class hierarchy or a procedural pipeline — it needs a way to produce one geometry and one entity list, then hand both to whatever already loads levels.
- **Entity placement is a flat record, not an object graph.** Five numbers per entity — position, facing, type tag, options — is enough to fully specify any spawnable entity. A scenario abstraction that sticks to this shape stays trivially serializable, trivially diff-able, and avoids accidentally encoding behavior in placement data.
- **Demo-quality "navigates around an obstacle" is already produced by the existing chase loop**, provided two things are true: (a) the obstacle is solid to the enemy's collision check, and (b) the obstacle is positioned roughly between the enemy and the target. Priority 1 of the reselection algorithm fails (diagonal blocked); priority 2 picks the perpendicular that opens up; the commitment counter then keeps the enemy on that perpendicular long enough to be visually obvious before the next reselection rounds the corner. Authors do not need to encode pathfinding waypoints — they only need to author the obstacle.
- **Determinism is a precondition, not a feature.** Three rules — reset random state at level-init, fixed simulation step, recorded input — are all that is needed. None of the three involves the scenario itself. A scenario abstraction that adds its own RNG seeding is solving a problem that was already solved upstream; it should instead document its dependence on the existing reset.
- **Reserve the type-tag space for spawn points distinctly from free entities.** The reference uses the bottom of the type space for player-slot spawn points and emits them through a different code path than free entities (they bind to a player object rather than spawning one). A scenario abstraction that wants to specify both player and enemies in one list can mirror this split — keep one small reserved range for spawn points, use the rest for actual entity types — rather than introducing two separate lists.
- **Commitment-counter granularity sets the visual "decision rate" of a chase demo.** A counter range of 0–15 ticks at 35 Hz means an enemy reconsiders direction roughly every 0.2 seconds on average. Halving or doubling the range produces visibly twitchier or visibly more committed enemies. For a short demo recording (under 10 seconds), the existing range produces 30–50 visible decisions — plenty of opportunity for a chase-around-obstacle to show priority-1 failures and priority-3 wall-skimming.

## Open Questions

- The reference's options-bitmask filtering (skill-level, multiplayer-only) is straightforward to ignore when authoring scenarios, but if a scenario abstraction wants to support "this entity only spawns when scenario flag X is set", a similar bitmask is the natural place to put it. Worth deciding once whether scenario abstractions get an analogous filter or whether they spawn unconditionally.
- The reference's perpendicular-swap probability (~22%) and the dead-band (10 world units) are tuned to one specific simulation rate and one specific entity-radius scale. A spec adopting them verbatim should record where the values come from and whether the project's units justify keeping them, scaling them, or replacing them.
- The reference's chase routine does not look ahead — it commits one direction, walks, then on the next reselection re-evaluates. For a scenario where a single obstacle is small relative to the entity's commitment-counter walk distance, this works well. For obstacles wider than `commitment_counter_max × per-tick step`, the enemy might walk past the obstacle and have to backtrack. Worth measuring whether any planned scenario exceeds that ratio before designing the obstacle layout.
- The reference uses a separate gameplay-vs-cosmetic random index split. The current project may or may not need that split — only relevant if cosmetic randomness (visual variation, particle jitter) gets added later and we want gameplay determinism preserved when those visuals change.
