# Demo Mode (Headed Autopilot + Frame Recording)

## Intent

Each tagged release ships with a short animated GIF demonstrating gameplay. The GIF must be:

- **Reproducible** — the same scenario produces the same frames on any machine, regardless of display server, frame-rate jitter, or compositor capture quirks.
- **Spec-driven** — the scenario file is one of the existing `tests/**/*.yaml` files; no new manual play recording.
- **Built from generated code** — the recording binary is the same generated binary that ships with the release.

This spec defines the **demo mode** in which the existing autopilot bot drives the live render loop with the framebuffer dumped frame-by-frame to disk for later GIF assembly.

## Architecture

```
specs/30 (autopilot)            specs/35 (this spec)
        │                              │
        ▼                              ▼
   #[test] runner          main --autopilot <yaml> [--record-frames <out>]
   (cargo test)             │
                            ▼
                  load Scenario  ──▶ bot_step each frame ──▶ game_loop::update
                                                           │
                                          minifb window ◀──┴──▶ frame_recorder (optional)
                                                                       │
                                                                       ▼
                                                             tooling/record_autopilot.sh
                                                                  ffmpeg → gif
```

The autopilot module (specs/30) already owns scenario parsing and bot decision logic. Demo mode reuses both — it does **not** introduce a second bot implementation.

## CLI

The generated binary accepts these mutually compatible flags (parsed by `main.rs` from `std::env::args`):

| Flag | Argument | Behavior |
|------|----------|----------|
| `--autopilot <path>` | path to a scenario YAML | Replace human keyboard input with `autopilot::bot_step`. Render loop, window, and timing are otherwise identical to interactive play. Exits when all objectives complete, the bot times out, or the player loses. |
| `--record-frames <path>` | path to the raw frame output file | After each `renderer::draw` call, append the framebuffer (raw `BGRA` bytes, `WINDOW_WIDTH * WINDOW_HEIGHT` u32s in little-endian native order) to the file. May be combined with `--autopilot` (the intended use) or used alone for interactive recording. |

No flags → existing interactive play (unchanged from prior releases).

Argument parsing is `std::env::args` only — **no** `clap` or other CLI crate dependency.

## Scenario Loading (Release Builds)

When `--autopilot <path>` is passed, `main.rs` reads the file via `std::fs::read_to_string` and calls `autopilot::parse_scenario(&yaml)`. This means `parse_scenario` and the `Scenario` / `Objective` types **must compile in release builds**, not only under `#[cfg(test)]`.

The test runner (`#[test] fn run_all_scenarios`) and the offline `run_scenario` driver remain `#[cfg(test)]`-gated — only the per-frame primitives (`parse_scenario`, `bot_step`, `BotState`, `BotProgress`) are promoted to release.

See `ir/contracts/autopilot.yaml` for the exact split.

## Frame Recording Format

The recorded file is **raw concatenated framebuffers**, no header, no per-frame metadata:

- Each frame: `WINDOW_WIDTH * WINDOW_HEIGHT` `u32` values, written in native-endian order. (Project targets little-endian platforms today; see specs/80.)
- Source pixel format: minifb writes `0x00RRGGBB` packed `u32`s. On little-endian, the byte sequence per pixel is `B, G, R, 0x00`.
- ffmpeg pixel-format flag: **`bgr0`**, not `bgra` — the `0x00` high byte is *not* alpha=opaque, it is alpha=fully-transparent. Reading the stream as `bgra` produces a transparent GIF (renders as solid background). `bgr0` tells ffmpeg to ignore the high byte and treat each pixel as fully opaque.
- One frame per `renderer::draw` call (i.e. one per game tick).
- File grows unbounded — caller is responsible for stopping the game (the autopilot bot exits the game when objectives complete, capping file size).

Why raw and not PNG/per-frame: zero encoding cost, zero new dependencies, and `ffmpeg -f rawvideo` reads it directly. PNG-per-frame would require the `png` or `image` crate, which conflicts with specs/80 § Dependencies.

## Determinism

Demo mode must produce the same byte-for-byte recording across runs of the same generated binary on the same scenario. Constraints:

- The bot RNG seed (if the bot uses any randomness in stuck-detection or strafe choice) must be a fixed constant — **not** time-based. Coder owns the choice of constant; document it in `work/decisions.md`.
- The game-side RNGs (weapon damage, enemy pain check) must use a fixed seed in demo mode. Spec/25 § Damage Randomization does not pin the seed today; demo mode adds the constraint *"when `--autopilot` is set, all module-private RNGs initialize from a fixed seed"*. Coder choice of seed value; document in `work/decisions.md`.
- `dt` per frame must be exactly `1.0 / 60.0` (same constant as `BOT_FRAME_TIME` in autopilot, specs/30 § Execution Rules) — **not** `Instant::now()` deltas. The window may render at whatever rate the host supplies; the simulation step is fixed.

Interactive play (no flags) is unaffected — RNG seeding falls back to its existing behavior, `dt` falls back to wall-clock as today.

## Bot Per-Frame API (Released)

The autopilot module exposes a per-frame stepping API in addition to the test-only batch `run_scenario`:

```rust
pub struct BotState { /* opaque, internal */ }
impl BotState {
    pub fn new() -> Self;
}

pub enum BotProgress {
    Running,
    AllObjectivesComplete,
    Failed(String),    // bot timed out, or player died, etc.
}

pub fn bot_step(
    game: &GameState,
    scenario: &Scenario,
    bot: &mut BotState,
) -> (InputState, BotProgress);
```

`run_scenario` (test-only) is implemented in terms of `bot_step` to avoid two divergent bots.

## Test Scenario Suitability for Demo

Any scenario in `tests/**/*.yaml` is a valid demo input. The release process selects one scenario that produces the most visually informative recording. Two canonical choices exist, picked at release-time:

- **PR-preview GIF** (per-PR, on every push): `tests/level/local_chase_obstacle.yaml`. Uses the `local_chase_obstacle` demo level (specs/15) — a single vertical wall between player and enemy that forces the chase routine through priority-2 (perpendicular alternates) and priority-3 (continue old direction) of `knowledge/level_scenarios.md § Obstacle-Aware Chase`. The recorded GIF visibly answers "did the enemy navigate around the obstacle?" in a few seconds.
- **Tagged-release GIF** (`release.yml`): `tests/level/scavenge_run.yaml`. Uses the default level — exercises movement + pickup pickup + combat + exit-reach in one run. Better suited for "tour of mechanics" than for any single behavior demo.

Selection is a release-time choice, not a property of this spec; the spec asserts only that any `tests/**/*.yaml` scenario is a valid demo input. The PR-preview / release-gif split lives in `.github/workflows/{pr,release}.yml`.

Demo recordings are intentionally short (< 10 seconds at 60 FPS = < 600 frames). The bot's `BOT_MAX_FRAMES` (3600) caps long runs; the recording script should also pass a soft duration budget.

## Tooling Contract

`tooling/record_autopilot.sh` is the canonical recording entry point:

1. Build the game in release mode (`cargo build --release --manifest-path generated/game/Cargo.toml`).
2. Run the binary with `--autopilot <scenario>` `--record-frames <tmp.raw>`.
3. After the binary exits, invoke `ffmpeg` twice on the same raw stream:
   - **GIF** via two-pass `palettegen` / `paletteuse` (palette-based; smaller for short loops, displays inline in markdown).
   - **MP4** via `libx264` + `yuv420p` + `+faststart` (h264; much smaller per second, preferred for PR embeds and social).
4. Place artifacts at `release/demo.gif` and `release/demo.mp4` (or paths derived from a caller-provided basename).

Both artifacts are frame-aligned — they decode from the same raw stream — so they are guaranteed to show the same gameplay; only the codec differs.

The script is a thin wrapper — no game logic lives in it. `WINDOW_WIDTH`, `WINDOW_HEIGHT`, and `TARGET_FPS` are passed in as ffmpeg flags.

## Out of Scope

- Audio: no audio in the binary, none in the GIF.
- Cropping or HUD overlays added in post: the GIF is the framebuffer as-rendered.
- Multiple-scenario montages: one scenario per GIF.
- Comparison gifs (before/after a regen): release artifact is a single demo.

## Acceptance Criteria

- `cargo build --release` produces a binary that accepts `--autopilot <path>` and `--record-frames <path>` flags.
- Running the binary with `--autopilot tests/combat/kill_enemy.yaml --record-frames /tmp/frames.raw` produces a non-empty file whose size is exactly `WINDOW_WIDTH * WINDOW_HEIGHT * 4 * frame_count` bytes.
- Two runs of the same command produce **byte-identical** files (determinism).
- `tooling/record_autopilot.sh tests/combat/kill_enemy.yaml release/demo.gif` produces a playable GIF **and** an h264 MP4 sibling (`release/demo.mp4`) from the same raw stream.
- The interactive `cargo run` path (no flags) is unchanged — existing manual-play behavior preserved.

## Implementation Status

**Implemented:**
- `--autopilot <path>` and `--record-frames <path>` CLI flags parsed via `std::env::args`.
- Headed autopilot mode: bot drives live minifb render loop at fixed `dt = 1/60`.
- Raw BGRA frame recording (`frame_recorder` module): `open`, `write_frame`, `close`; `bgr0` pixel format for ffmpeg.
- Determinism: all module-private RNGs seeded from fixed constants in `--autopilot` mode.
- `tooling/record_autopilot.sh`: GIF (two-pass palettegen/paletteuse) + MP4 (libx264 yuv420p faststart) from the same raw stream.
- Per-frame API (`parse_scenario`, `BotState`, `BotProgress`, `bot_step`) always compiled (not `#[cfg(test)]`).

**Deferred:**
- Audio in recordings (no audio system in binary).
- Post-production HUD overlays or cropping.
- Multiple-scenario montage recordings.
- Before/after comparison GIFs.
