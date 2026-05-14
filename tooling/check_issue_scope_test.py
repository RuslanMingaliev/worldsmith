"""Stdlib-only unit tests for check_issue_scope.

Run: `python3 -m unittest tooling/check_issue_scope_test.py`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

LINTER = Path(__file__).resolve().parent / "check_issue_scope.py"


def run_linter(body: str, ref_repo: str = "") -> tuple[int, dict]:
    env = {**os.environ, "REF_REPO": ref_repo}
    r = subprocess.run(
        [sys.executable, str(LINTER)],
        input=body, capture_output=True, text=True, env=env,
    )
    payload = json.loads(r.stdout) if r.stdout.strip() else {}
    return r.returncode, payload


# Issue body fixtures.
# Each one exercises a specific rule documented in the linter source.

PR26_LIKE_BODY = """\
### Goal
Replace the current minimalist default level with a richer real level whose
geometry mirrors the reference's first map. Teach the smart autopilot bot to
additionally route via the nearest active health pickup.

### Scope
Extractor phase. Load reference/. Capture the reference's first-map geometry
into knowledge/first_map.md. Each entry must cite the source reference file.

### Affected modules

level_data, autopilot, main

### Constraints
The richer default level's geometry MUST be knowledge-backed. Each pinned
coordinate must trace to a citation in knowledge/*.md.

### Acceptance criteria
- knowledge/ gains reference-cited entries
- specs/25 rewritten with knowledge-backed Source citations
"""

GOOD_SINGLE_TRACK_BODY = """\
### Goal
Fix the kite-mode LoS gate in autopilot.

### Scope
Update `autopilot::compute_nav_target` kite condition to add a
`has_line_of_sight` check.

### Affected modules

autopilot

### Constraints
None.

### Acceptance criteria
- `tests/level/local_chase_obstacle.yaml` runs without indefinite back-pedal.
- `cargo test` passes.
"""

TWO_MODULES_NO_KNOWLEDGE_BODY = """\
### Goal
Add a stagger animation hook.

### Scope
Renderer reads a new `Enemy.stagger_remaining` field set by enemy_logic.

### Affected modules

enemy_logic, renderer

### Constraints
None.

### Acceptance criteria
- Tests pass.
"""

EMPTY_MODULES_BODY = """\
### Goal
Refactor the renderer.

### Scope
Touch some renderer code.

### Affected modules

—

### Constraints
None.

### Acceptance criteria
- Tests pass.
"""

MULTI_TRACK_GOAL_BODY = """\
### Goal
Refactor the renderer and add new pickup AI and update the demo source and
document the variant policy.

### Scope
Touch some code.

### Affected modules

renderer

### Constraints
None.

### Acceptance criteria
- Tests pass.
"""


class LinterTests(unittest.TestCase):
    def test_pr26_like_body_hard_rejects(self) -> None:
        code, output = run_linter(PR26_LIKE_BODY, ref_repo="")
        self.assertEqual(code, 1, output)
        self.assertEqual(output["verdict"], "hard_reject")
        joined = "\n".join(output["hard"])
        self.assertIn("3 modules", joined)
        self.assertIn("knowledge", joined.lower())

    def test_good_single_track_body_passes(self) -> None:
        code, output = run_linter(GOOD_SINGLE_TRACK_BODY, ref_repo="")
        self.assertEqual(code, 0, output)
        self.assertEqual(output["verdict"], "pass")
        self.assertEqual(output["hard"], [])
        self.assertEqual(output["soft"], [])

    def test_two_modules_no_knowledge_passes(self) -> None:
        code, output = run_linter(TWO_MODULES_NO_KNOWLEDGE_BODY, ref_repo="")
        self.assertEqual(code, 0, output)
        self.assertEqual(output["verdict"], "pass")

    def test_empty_modules_soft_warns(self) -> None:
        code, output = run_linter(EMPTY_MODULES_BODY, ref_repo="")
        self.assertEqual(code, 2, output)
        self.assertEqual(output["verdict"], "soft_warn")
        self.assertEqual(output["hard"], [])
        self.assertTrue(any("Affected modules" in r for r in output["soft"]))

    def test_multi_track_goal_soft_warns(self) -> None:
        code, output = run_linter(MULTI_TRACK_GOAL_BODY, ref_repo="")
        self.assertEqual(code, 2, output)
        self.assertEqual(output["verdict"], "soft_warn")
        self.assertTrue(any("distinct tracks" in r for r in output["soft"]))


if __name__ == "__main__":
    unittest.main()
