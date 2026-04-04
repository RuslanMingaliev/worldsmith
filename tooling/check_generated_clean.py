#!/usr/bin/env python3
"""
Ensure generated/ has no modifications relative to the current commit.

Intended for CI to prevent manual edits to generated code inside pull requests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain", "generated"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    if result.returncode != 0:
        print("Failed to inspect git status for generated/.", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    if lines:
        print(
            "generated/ contains changes. Regenerated code should not be edited in PRs:",
            file=sys.stderr,
        )
        for line in lines:
            print(f"  {line}", file=sys.stderr)
        sys.exit(1)

    print("generated/ directory is clean relative to the current commit.")


if __name__ == "__main__":
    main()
