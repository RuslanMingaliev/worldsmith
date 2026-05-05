#!/usr/bin/env python3
"""
Source-of-truth path detection for CI gating.

Both `.github/workflows/pr.yml` (impact analysis) and
`.github/workflows/post-merge-snapshot.yml` (regen detection on main) use
this to decide whether a changeset touches the agent-authored sources
that drive regeneration. Keeping it in one place prevents the two
workflows from drifting on the definition of "this PR/merge contains
regen".

CLI: read newline-separated paths from stdin, exit 0 if any path matches
a source-of-truth prefix, exit 1 otherwise.

    git diff --name-only HEAD^..HEAD | python tooling/source_of_truth_paths.py
"""

from __future__ import annotations

import sys


SOURCE_OF_TRUTH_PREFIXES: tuple[str, ...] = (
    "specs/",
    "knowledge/",
    "ir/",
    "tooling/agents/",
)


def is_source_of_truth(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in SOURCE_OF_TRUTH_PREFIXES)


def main() -> int:
    for line in sys.stdin:
        if is_source_of_truth(line.strip()):
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
