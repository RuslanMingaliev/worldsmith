#!/usr/bin/env python3
"""Lint an agent-task issue body for known over-scope / deadlock patterns.

Reads the issue body from stdin. Emits a JSON verdict to stdout.

Exit codes:
  0  pass
  1  hard reject  (workflow should block)
  2  soft warn    (workflow should comment but proceed)

Rules and rationale: work/ideas/2026-05-09_constraint_linter.md.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import List, Tuple

MAX_MODULES = 2

KNOWLEDGE_MANDATE_PATTERNS = [
    r"knowledge[- ]backed",
    r"MUST cite knowledge",
    r"MUST trace to knowledge",
    r"must be knowledge[- ]backed",
    r"knowledge/[\w./-]+\.md",
]

VERB_JOINERS = (" and ", " plus ", " also ", ", and ", ", plus ")
VERB_COUNT_THRESHOLD = 3

EMPTY_MODULE_MARKERS = {"", "—", "-", "none.", "none", "n/a", "tbd"}

MODULE_STOPWORDS = {
    "optional", "and", "or", "the", "a", "an",
    "modules", "module", "none", "n", "a",
}


def parse_section(body: str, heading: str) -> str:
    """Extract content under a `### heading` marker (case-insensitive)."""
    pattern = rf"###\s+{re.escape(heading)}\s*\n(.*?)(?=\n###\s|\Z)"
    m = re.search(pattern, body, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def count_modules(body: str) -> int:
    section = parse_section(body, "Affected modules")
    if not section or section.strip().lower() in EMPTY_MODULE_MARKERS:
        return 0
    tokens = re.findall(r"[a-z_][a-z0-9_]*", section.lower())
    return len([t for t in tokens if t not in MODULE_STOPWORDS])


def has_knowledge_mandate(body: str) -> bool:
    return any(re.search(p, body, re.IGNORECASE) for p in KNOWLEDGE_MANDATE_PATTERNS)


def reference_repo_empty() -> bool:
    """True if the reference repo (per REF_REPO env var) has no refs.

    Treat any failure (no env var, network error, no refs) as empty so the
    knowledge-mandate gate fires whenever the reference is unreachable. The
    caller can override this by populating reference/ before triggering.
    """
    repo = os.environ.get("REF_REPO", "").strip()
    if not repo:
        return True
    try:
        r = subprocess.run(
            ["git", "ls-remote", "--refs", repo],
            capture_output=True, timeout=10, text=True,
        )
    except (subprocess.SubprocessError, OSError):
        return True
    return r.returncode != 0 or not r.stdout.strip()


def goal_track_count(body: str) -> int:
    """Count distinct tracks in the Goal first paragraph via joiner heuristic."""
    section = parse_section(body, "Goal")
    if not section:
        return 0
    first_para = section.split("\n\n")[0].lower()
    joiner_hits = sum(first_para.count(j) for j in VERB_JOINERS)
    return joiner_hits + 1


def lint(body: str) -> Tuple[int, List[str], List[str]]:
    """Return (exit_code, hard_reasons, soft_reasons)."""
    hard: List[str] = []
    soft: List[str] = []

    n_modules = count_modules(body)
    if n_modules > MAX_MODULES:
        hard.append(
            f"`Affected modules` lists {n_modules} modules. Bundles of "
            f">{MAX_MODULES} modules historically take 13+ regens to land "
            f"(PR #28 post-mortem). Split into {n_modules} focused issues; "
            f"the agent-intake will run each in <2 regens."
        )

    if has_knowledge_mandate(body) and reference_repo_empty():
        hard.append(
            "Issue mandates knowledge backing (matched a knowledge-mandate "
            "phrase) but the reference repo is empty or unreachable. Either "
            "populate `reference/`, drop the knowledge requirement, or mark "
            "affected values upfront as `Generation default — no knowledge "
            "backing` in the issue body. Issue #26 hit this exact deadlock."
        )

    n_tracks = goal_track_count(body)
    if n_tracks >= VERB_COUNT_THRESHOLD:
        soft.append(
            f"Goal first paragraph appears to combine {n_tracks} distinct "
            f"tracks (joined by 'and'/'plus'/'also'). Consider splitting "
            f"before running. (Soft warning, not a block.)"
        )

    if n_modules == 0:
        soft.append(
            "`Affected modules` is empty. Pipeline will run a full release "
            "regen for this issue (~5x more tokens than partial regen). If "
            "you intended a narrow scope, add the field."
        )

    if hard:
        return 1, hard, soft
    if soft:
        return 2, hard, soft
    return 0, hard, soft


def main() -> int:
    body = sys.stdin.read()
    code, hard, soft = lint(body)
    verdict = {0: "pass", 1: "hard_reject", 2: "soft_warn"}[code]
    out = {
        "verdict": verdict,
        "hard": hard,
        "soft": soft,
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
