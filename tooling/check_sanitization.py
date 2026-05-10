#!/usr/bin/env python3
"""
Sanitization gate for any markdown file that may be published.

The Extractor agent writes knowledge files that get versioned and published.
A previous sanitization commit (`87863b7`) explicitly removed source-game
identifiers from public knowledge. Without an automated gate, future
extractions can re-introduce them — observed concretely when a Sonnet
Extractor pass leaked source-code identifiers (`ST_Drawer`, `STlib_*`)
and the source-game's release year as a "sentinel value".

This script is the single source of truth for forbidden patterns. It is
called from three places:

1. `tooling/agents/extractor.md` § Sanitization gate — the Extractor agent
   runs `python3 tooling/check_sanitization.py knowledge/<area>.md` after
   writing each knowledge file and treats non-zero exit as a hard rejection.

2. `tooling/validate_specs.py` — runs this script over every file in
   `knowledge/` as part of every full validation run, so a leak that
   somehow survived the Extractor's gate fails the next validate_specs
   invocation.

3. `release.yml` workflow — runs this script over the composed release
   notes before publishing, so source-game identifiers cannot reach a
   public GitHub release through the post-mortem section.

Usage:

    python3 tooling/check_sanitization.py knowledge/hud.md
    python3 tooling/check_sanitization.py knowledge/*.md artifacts/release-notes.md
    python3 tooling/check_sanitization.py --all   # scans everything in knowledge/

Exit codes:
    0 — all files clean (no forbidden tokens matched).
    1 — at least one file has a leak; offending lines printed to stderr.
    2 — usage error / file not found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"


# ---------------------------------------------------------------------------
# Forbidden patterns — single source of truth
# ---------------------------------------------------------------------------
#
# Patterns are case-insensitive. Add to this list (with a one-line rationale
# in a comment) rather than maintaining parallel grep blocks elsewhere.
# Each entry is (pattern, kind) where `kind` categorizes the leak class
# for the report. `pattern` is a regex; literal substrings are also fine
# because they get escaped via `re.escape` upstream — see PROPER_NOUN_LITERALS.

# Literal substrings (escaped before use). These are case-insensitive
# whole-or-partial matches within a line.
PROPER_NOUN_LITERALS: List[Tuple[str, str]] = [
    # Source-game identifying terms — engine name, developer, item names, enemies.
    ("doom", "source-game name"),
    ("id software", "source-game developer"),
    ("stimpack", "source-game proper noun (small medkit)"),
    ("medikit", "source-game proper noun (large medkit)"),
    ("medkit", "source-game proper noun (large medkit, alt spelling)"),
    ("soulsphere", "source-game proper noun (overheal sphere)"),
    ("megasphere", "source-game proper noun (mega-pickup)"),
    ("supercharge", "source-game proper noun (overheal alias)"),
    ("berserk", "source-game proper noun (melee strength powerup)"),
    ("backpack", "source-game proper noun (inventory expander)"),
    ("ironfeet", "source-game proper noun (radiation suit alias)"),
    # Source-code identifiers — function/struct/macro/var prefixes.
    ("st_drawer", "source-code identifier (status bar draw fn)"),
    ("st_ticker", "source-code identifier (status bar tick fn)"),
    ("st_responder", "source-code identifier (status bar input fn)"),
    ("stlib_", "source-code identifier (status bar widget lib prefix)"),
    ("tallnum", "source-code identifier (digit font array)"),
    ("shortnum", "source-code identifier (small digit font array)"),
    ("p_touch", "source-code identifier (pickup touch fn)"),
    ("p_give", "source-code identifier (give-X helper prefix)"),
    ("p_check", "source-code identifier (pre-fire check fn)"),
    ("mobjtype", "source-code identifier (thing-type enum)"),
    ("ammotype", "source-code identifier (ammo-type enum)"),
    ("weapontype", "source-code identifier (weapon-type enum)"),
    # Source-code identifier prefixes — match at a word boundary only. These
    # are the named, pre-known reference prefixes; keeping them explicit means
    # `release-notes` mode (which drops the generic SCREAMING_SNAKE fallback)
    # still rejects e.g. `MT_PLAYER`, `MF_SPECIAL`, `SPR_STIM`, `MN_GAMEMSG`.
    # Substring matching (the previous behaviour) fired on legitimate prose
    # like `column_height` (containing `mn_`) — real source-code mentions
    # always sit at a word boundary, so the boundary form preserves recall
    # while dropping the false positives. See `build_compiled_patterns`.
    ("mt_", "source-code identifier prefix (thing-type macro)"),
    ("mf_", "source-code identifier prefix (mobj-flag macro)"),
    ("spr_", "source-code identifier prefix (sprite enum)"),
    ("mn_", "source-code identifier prefix (menu enum)"),
    # Cheat code strings — strong proper-noun risk.
    ("idkfa", "source-game cheat code"),
    ("iddqd", "source-game cheat code"),
    ("idclip", "source-game cheat code"),
    ("idspispopd", "source-game cheat code"),
    ("idmypos", "source-game cheat code"),
    ("idbeholdv", "source-game cheat code"),
    ("idclev", "source-game cheat code"),
    # Asset/lump/sprite naming conventions.
    ("stbar", "source-game lump/sprite name"),
    ("sttnum", "source-game lump/sprite name"),
    ("stysnum", "source-game lump/sprite name"),
    ("sttminus", "source-game lump/sprite name"),
    ("sttprcnt", "source-game lump/sprite name"),
]

# Regex patterns (compiled below). Use raw strings.
REGEX_PATTERNS: List[Tuple[str, str]] = [
    # Year-range — 1990s and 2000s release/copyright years are strong identifiers.
    # A previous extraction leaked a source-game year as a "sentinel value".
    (r"\b(199[0-9]|200[0-9])\b", "release-year sentinel (1990s-2000s integer literal)"),
    # Generic ALL-CAPS macro pattern (e.g. `MT_PLAYER`, `MF_SPECIAL`, `SPR_STIM`).
    # Two or more uppercase letters then underscore then alphanumeric. Common in C
    # source code; almost never appears in legitimate prose. Keep this last so
    # specific literals are matched first for a more useful kind label.
    (r"\b[A-Z]{2,}_[A-Za-z0-9_]+\b", "generic source-code macro/identifier"),
]


# The generic SCREAMING_SNAKE fallback regex is the last entry in REGEX_PATTERNS.
# It is broad on purpose — for `knowledge/`, anything that looks like a C
# macro is suspect. For `artifacts/release-notes.md` it over-fires on
# worldsmith's *own* legitimate constants (e.g. `PLAYER_RADIUS_TILES` cited
# from `specs/25`). The release-notes mode drops this one regex but keeps
# every literal + the year-range regex — which means real source-game leaks
# (`MT_PLAYER`, `stimpack`, `1993`) are still rejected, only via their
# specific prefixes rather than the generic shape match.
GENERIC_SCREAMING_SNAKE_KIND = "generic source-code macro/identifier"


def build_compiled_patterns(
    *, drop_generic_fallback: bool = False
) -> List[Tuple[re.Pattern, str]]:
    compiled: List[Tuple[re.Pattern, str]] = []
    for literal, kind in PROPER_NOUN_LITERALS:
        # Identifier *prefixes* (kind tagged "source-code identifier prefix")
        # match only at a word boundary — substring match was over-eager and
        # fired on legitimate prose like `column_height` (the substring `mn_`
        # sits inside the word). Real source-code mentions of `MN_FOO` /
        # `mn_bar` / etc. always begin at a word boundary, so this preserves
        # recall while dropping false positives. Other literals (full names
        # like `mobjtype`, cheat codes, lump names) keep substring match.
        if kind.startswith("source-code identifier prefix"):
            pattern = re.compile(r"\b" + re.escape(literal), re.IGNORECASE)
        else:
            pattern = re.compile(re.escape(literal), re.IGNORECASE)
        compiled.append((pattern, kind))
    for raw, kind in REGEX_PATTERNS:
        if drop_generic_fallback and kind == GENERIC_SCREAMING_SNAKE_KIND:
            continue
        pattern = re.compile(raw)
        compiled.append((pattern, kind))
    return compiled


# Module-level COMPILED keeps the strict default for callers that import
# `scan_file` without going through the CLI (currently none, but cheap to
# preserve). The CLI rebuilds the list per --mode.
COMPILED: List[Tuple[re.Pattern, str]] = build_compiled_patterns()


# ---------------------------------------------------------------------------
# False-positive allowlist (per-file, per-line)
# ---------------------------------------------------------------------------
#
# Some lines in knowledge/ legitimately mention a generic English word that
# happens to substring-match a forbidden literal (e.g. "imm**edi**ately"
# triggers "medi"). Allow specific (file, line_no_or_substring) exemptions
# here. Keep the list short — if it grows, the literal is too aggressive.
ALLOWED_SUBSTRINGS: List[str] = [
    # Currently empty. Add as needed with a comment per entry explaining why.
]


def is_allowed_false_positive(line: str) -> bool:
    return any(s in line for s in ALLOWED_SUBSTRINGS)


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def scan_file(
    path: Path,
    compiled: Optional[List[Tuple[re.Pattern, str]]] = None,
) -> List[Tuple[int, str, str, str]]:
    """Return list of (line_no, line, matched_text, kind) for forbidden hits."""
    if compiled is None:
        compiled = COMPILED
    hits: List[Tuple[int, str, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    for line_no, line in enumerate(text.splitlines(), start=1):
        if is_allowed_false_positive(line):
            continue
        # Skip the YAML front-matter so reference_paths can legitimately
        # mention "reference/doom/..." without flagging.
        # Heuristic: lines between the first two `---` of the file are skipped.
        # We re-scan with a small state below; for now treat lines starting
        # with `reference_paths:` or under that block as exempt by checking
        # the "reference/" prefix.
        if line.lstrip().startswith("- reference/") or line.startswith("reference_paths:"):
            continue
        for pattern, kind in compiled:
            for match in pattern.finditer(line):
                hits.append((line_no, line.rstrip(), match.group(0), kind))
                # one hit per pattern per line is enough
                break
    return hits


def scan_paths(
    paths: List[Path],
    compiled: Optional[List[Tuple[re.Pattern, str]]] = None,
) -> int:
    total_leaks = 0
    for path in paths:
        hits = scan_file(path, compiled=compiled)
        if not hits:
            continue
        total_leaks += len(hits)
        try:
            rel = path.relative_to(REPO_ROOT) if path.is_absolute() else path
        except ValueError:
            rel = path
        print(f"\n{rel}: {len(hits)} forbidden token(s) found:", file=sys.stderr)
        for line_no, line, matched, kind in hits:
            print(f"  line {line_no}: matched {matched!r} ({kind})", file=sys.stderr)
            print(f"    > {line}", file=sys.stderr)
    return total_leaks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check knowledge/*.md for forbidden source-identifying tokens."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Knowledge files to check (relative or absolute paths).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan every *.md file in knowledge/.",
    )
    parser.add_argument(
        "--mode",
        choices=["strict", "release-notes"],
        default="strict",
        help=(
            "strict (default): apply every pattern incl. the generic "
            "SCREAMING_SNAKE fallback — appropriate for knowledge/ where any "
            "C-shaped identifier is suspect. "
            "release-notes: drop the generic fallback but keep all literals "
            "and the year-range regex — appropriate for artifacts/release-notes.md "
            "where worldsmith may legitimately cite its own constants while "
            "real source-game leaks are still rejected via their named prefixes."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.all:
        paths = sorted(KNOWLEDGE_DIR.glob("*.md"))
    else:
        paths = args.paths

    if not paths:
        print("error: no files to scan (pass paths or --all)", file=sys.stderr)
        sys.exit(2)

    compiled = build_compiled_patterns(
        drop_generic_fallback=(args.mode == "release-notes"),
    )

    total_leaks = scan_paths(paths, compiled=compiled)

    if total_leaks > 0:
        print(
            f"\nSanitization FAILED: {total_leaks} forbidden token(s) across "
            f"{sum(1 for p in paths if scan_file(p, compiled=compiled))} file(s).",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
