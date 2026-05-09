# Manual Smoke Checklist

This is a manual pre-release runbook, not a scripted eval. The scripted smoke pipeline is `cargo build` + `cargo test`, run via `tooling/run_evals.py`. Run this checklist before tagging a release.

Automated coverage: see `tooling/run_evals.py`.

## Manual Testing

- [ ] game window opens
- [ ] player can move (WASD)
- [ ] player can turn (arrows)
- [ ] player cannot pass through walls
- [ ] player can attack (space)
- [ ] at least one enemy visible
- [ ] enemy chases player
- [ ] exit condition works (reach cyan X)
- [ ] ESC quits the game

## Covered by Unit Tests

The following are verified by `cargo test`:

- player movement logic
- wall collision detection
- weapon firing and cooldown
- enemy chase behavior
- win/lose conditions
- level structure
