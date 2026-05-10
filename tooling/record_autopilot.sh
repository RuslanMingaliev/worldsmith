#!/usr/bin/env bash
# Record an autopilot session as a GIF for release artifacts.
#
# Usage:
#   tooling/record_autopilot.sh <scenario.yaml> [output.gif]
#
# Defaults:
#   scenario  = tests/level/scavenge_run.yaml
#   output    = release/demo.gif
#
# Behavior:
#   1. cargo build --release for the generated game.
#   2. Run the binary with --autopilot <scenario> --record-frames <tmp.raw>.
#      (specs/35 § CLI; both flags must be supported by the regenerated binary.)
#   3. ffmpeg two-pass (palettegen + paletteuse) to convert raw BGRA -> GIF.
#
# Requirements:
#   - ffmpeg in PATH
#   - A regenerated game binary that implements specs/35.
#     Older binaries (no --autopilot/--record-frames flags) will fail.
#
# This script is a thin wrapper. Frame dimensions, pixel format, and the
# fixed simulation framerate come from the spec, not from runtime probing
# of the binary -- if specs/25 § Visual changes the window size, update
# the constants below.

set -euo pipefail

# ---------------------------------------------------------------------------
# Spec-pinned constants (specs/25 § Visual; specs/35 § Frame Recording Format)
# ---------------------------------------------------------------------------
readonly WINDOW_WIDTH=640
readonly WINDOW_HEIGHT=480
readonly TARGET_FPS=60
readonly PIXEL_FORMAT="bgr0"   # minifb framebuffer is 0x00RRGGBB native-endian u32;
                               # on little-endian byte order is B,G,R,0. The "0"
                               # (high byte) is alpha=0 in BGRA terms, which would
                               # render the gif fully transparent. Use bgr0 so
                               # ffmpeg ignores the high byte and produces opaque pixels.

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
readonly SCENARIO="${1:-tests/level/scavenge_run.yaml}"
readonly OUTPUT="${2:-release/demo.gif}"
# Sibling mp4: same basename, .mp4 extension. Encoded from the same raw
# stream as the gif, so both artifacts are frame-aligned.
readonly OUTPUT_MP4="${OUTPUT%.gif}.mp4"

# Locate repo root from the script's own location so the script works
# regardless of caller's cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

if [[ ! -f "${SCENARIO}" ]]; then
    echo "error: scenario not found: ${SCENARIO}" >&2
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "error: ffmpeg not found in PATH" >&2
    exit 1
fi

mkdir -p "$(dirname "${OUTPUT}")"

# ---------------------------------------------------------------------------
# Build (release)
# ---------------------------------------------------------------------------
echo "==> cargo build --release"
cargo build --release --manifest-path generated/game/Cargo.toml

BINARY="$(find generated/game/target/release -maxdepth 1 -type f -executable ! -name '*.d' | head -n 1)"
if [[ -z "${BINARY}" || ! -x "${BINARY}" ]]; then
    echo "error: release binary not found under generated/game/target/release/" >&2
    exit 1
fi
echo "    using binary: ${BINARY}"

# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------
RAW_FRAMES="$(mktemp -t worldsmith-frames.XXXXXX.raw)"
trap 'rm -f "${RAW_FRAMES}"' EXIT

echo "==> recording autopilot: ${SCENARIO}"
# Optional render-mode override. Used while the renderer migration is in
# flight (slices 1..4) so the demo GIF visibly shows the raycaster path even
# though the binary's own default is still topdown. After slice 5 flips the
# default, this env var becomes redundant and can be dropped from pr.yml.
RENDER_MODE_ARGS=()
if [[ -n "${WORLDSMITH_RENDER_MODE:-}" ]]; then
    RENDER_MODE_ARGS=(--render-mode="${WORLDSMITH_RENDER_MODE}")
    echo "==> render mode override: ${WORLDSMITH_RENDER_MODE}"
fi
# Hard wall-clock cap on the binary. The bot's own BOT_MAX_FRAMES guard caps
# in-sim frames, but if minifb's set_target_fps gating misbehaves under xvfb
# or the bot enters an unintended infinite loop inside a single bot_step (BFS,
# LoS ray-cast), the in-sim guard never fires. 90 s is ~9x the typical
# scavenge_run wall-clock (~10 s observed) — well above any healthy run, well
# below the GitHub job timeout. Exits 124 on hang so CI surfaces the problem
# in seconds instead of hours.
if ! timeout --signal=KILL 90s "${BINARY}" --autopilot "${SCENARIO}" --record-frames "${RAW_FRAMES}" "${RENDER_MODE_ARGS[@]}"; then
    rc=$?
    if [[ "${rc}" == "124" || "${rc}" == "137" ]]; then
        echo "error: autopilot binary exceeded 90 s wall-clock cap and was killed" >&2
        echo "       (likely an autopilot regression — bot did not complete the scenario)" >&2
    else
        echo "error: autopilot binary exited with status ${rc}" >&2
    fi
    exit "${rc}"
fi

if [[ ! -s "${RAW_FRAMES}" ]]; then
    echo "error: no frames recorded (file empty)" >&2
    exit 1
fi

readonly FRAME_BYTES=$((WINDOW_WIDTH * WINDOW_HEIGHT * 4))
RAW_SIZE=$(stat -c %s "${RAW_FRAMES}" 2>/dev/null || stat -f %z "${RAW_FRAMES}")
if (( RAW_SIZE % FRAME_BYTES != 0 )); then
    echo "error: raw stream size ${RAW_SIZE} is not a multiple of frame size ${FRAME_BYTES}" >&2
    exit 1
fi
FRAME_COUNT=$((RAW_SIZE / FRAME_BYTES))
echo "    recorded ${FRAME_COUNT} frames (${RAW_SIZE} bytes)"

# ---------------------------------------------------------------------------
# Convert raw -> GIF (palettegen + paletteuse two-pass)
# ---------------------------------------------------------------------------
echo "==> ffmpeg: raw -> gif"
PALETTE="$(mktemp -t worldsmith-palette.XXXXXX.png)"
trap 'rm -f "${RAW_FRAMES}" "${PALETTE}"' EXIT

# Pass 1: generate optimal 256-color palette from the full stream.
ffmpeg -hide_banner -loglevel error -y \
    -f rawvideo \
    -pixel_format "${PIXEL_FORMAT}" \
    -video_size "${WINDOW_WIDTH}x${WINDOW_HEIGHT}" \
    -framerate "${TARGET_FPS}" \
    -i "${RAW_FRAMES}" \
    -vf "palettegen=stats_mode=full" \
    "${PALETTE}"

# Pass 2: encode the GIF using that palette.
ffmpeg -hide_banner -loglevel error -y \
    -f rawvideo \
    -pixel_format "${PIXEL_FORMAT}" \
    -video_size "${WINDOW_WIDTH}x${WINDOW_HEIGHT}" \
    -framerate "${TARGET_FPS}" \
    -i "${RAW_FRAMES}" \
    -i "${PALETTE}" \
    -lavfi "paletteuse=dither=bayer:bayer_scale=4" \
    "${OUTPUT}"

GIF_SIZE=$(stat -c %s "${OUTPUT}" 2>/dev/null || stat -f %z "${OUTPUT}")
echo "==> wrote ${OUTPUT} (${GIF_SIZE} bytes)"

# ---------------------------------------------------------------------------
# Convert raw -> MP4 (h264 yuv420p for broad compatibility)
# ---------------------------------------------------------------------------
echo "==> ffmpeg: raw -> mp4"
ffmpeg -hide_banner -loglevel error -y \
    -f rawvideo \
    -pixel_format "${PIXEL_FORMAT}" \
    -video_size "${WINDOW_WIDTH}x${WINDOW_HEIGHT}" \
    -framerate "${TARGET_FPS}" \
    -i "${RAW_FRAMES}" \
    -c:v libx264 \
    -pix_fmt yuv420p \
    -preset medium \
    -crf 20 \
    -movflags +faststart \
    "${OUTPUT_MP4}"

MP4_SIZE=$(stat -c %s "${OUTPUT_MP4}" 2>/dev/null || stat -f %z "${OUTPUT_MP4}")
echo "==> wrote ${OUTPUT_MP4} (${MP4_SIZE} bytes)"
