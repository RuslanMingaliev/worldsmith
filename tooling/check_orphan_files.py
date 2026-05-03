#!/usr/bin/env python3
"""
Orphan-file check.

Every `*.rs` in `generated/game/src/` (other than `main.rs`) must have a
matching `mod <stem>;` declaration in `main.rs`. An orphan file is silently
omitted from the crate by rustc: zero warnings, zero compiled tests, but
the file ships in the release artifact and any human reading it would
assume it's wired up.

Background: in PR #10's regen pass the Coder correctly created
`generated/game/src/level_generator.rs` and wrote a blocker note when
`main.rs` turned out to be outside its --target-modules scope; the file
was therefore never declared. `cargo build` was clean, `cargo test`
reported 45 passing — and 7 tests inside `level_generator.rs` silently
skipped. Reconciler caught it manually by `ls`-ing the dir and grepping
`main.rs`. This script makes that check mechanical.

Exit 0 if no orphans (or `generated/` doesn't exist yet), exit 1 with the
list otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "generated" / "game" / "src"
MAIN_RS = SRC_DIR / "main.rs"

MOD_DECL = re.compile(r"^\s*(?:pub\s+)?mod\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*;", re.MULTILINE)


def find_orphans() -> list[str]:
    if not SRC_DIR.is_dir() or not MAIN_RS.is_file():
        return []
    declared = set(MOD_DECL.findall(MAIN_RS.read_text(encoding="utf-8")))
    on_disk = {p.stem for p in SRC_DIR.glob("*.rs") if p.name != "main.rs"}
    return sorted(on_disk - declared)


def main() -> int:
    orphans = find_orphans()
    if not orphans:
        return 0
    print(
        f"Orphan files in {SRC_DIR.relative_to(REPO_ROOT)} "
        f"(present on disk but not declared in main.rs):",
        file=sys.stderr,
    )
    for stem in orphans:
        print(f"  - {stem}.rs (missing `mod {stem};` in main.rs)", file=sys.stderr)
    print(
        "\nThe compiler will silently skip these files. Any unit tests "
        "inside them will not run. Add `mod <name>;` to main.rs or delete "
        "the orphan.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
