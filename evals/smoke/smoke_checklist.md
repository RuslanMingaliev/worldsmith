# Smoke Checklist

## Automated (via `python tooling/run_evals.py`)

- [x] project builds (`cargo build`)
- [x] all tests pass (`cargo test`)

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
