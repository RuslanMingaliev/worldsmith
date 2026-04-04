#!/usr/bin/env python3
"""
Smoke evaluation script for worldsmith-game.

Runs automated checks:
1. cargo build - code compiles
2. cargo test - all tests pass
3. cargo clippy - no warnings (optional)

Usage:
    python tooling/run_evals.py [--clippy]
"""

import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
GAME_DIR = PROJECT_ROOT / "generated" / "game"


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{'='*60}")
    print(f"[EVAL] {description}")
    print(f"{'='*60}")
    print(f"$ {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=GAME_DIR)

    if result.returncode == 0:
        print(f"\n[PASS] {description}")
        return True
    else:
        print(f"\n[FAIL] {description}")
        return False


def main() -> int:
    """Run all smoke evaluations."""
    print("Worldsmith Smoke Evaluation")
    print(f"Game directory: {GAME_DIR}")

    if not GAME_DIR.exists():
        print(f"[ERROR] Game directory not found: {GAME_DIR}")
        return 1

    results = []

    # 1. Build check
    results.append(("Build", run_command(
        ["cargo", "build"],
        "Building project (cargo build)"
    )))

    # 2. Test check
    results.append(("Tests", run_command(
        ["cargo", "test"],
        "Running tests (cargo test)"
    )))

    # 3. Clippy check (optional)
    if "--clippy" in sys.argv:
        results.append(("Clippy", run_command(
            ["cargo", "clippy", "--", "-D", "warnings"],
            "Running clippy (cargo clippy)"
        )))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {name}: {status}")
        if not passed:
            all_passed = False

    print(f"{'='*60}")
    if all_passed:
        print("Result: ALL CHECKS PASSED")
        return 0
    else:
        print("Result: SOME CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
