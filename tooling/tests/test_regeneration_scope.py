"""Regression checks for the CI gate and partial regeneration planner."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

TOOLING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING))

from partial_regen import MODULE_PLAN, ModulePlanEntry, determine_modules, load_module_plan
from source_of_truth_paths import is_source_of_truth


class RegenerationScopeTests(unittest.TestCase):
    def setUp(self):
        self.modules = [
            ModulePlanEntry("player_state", "player", []),
            ModulePlanEntry("weapon_system", "combat", ["player_state"]),
            ModulePlanEntry("autopilot", "scenarios", ["weapon_system"]),
            ModulePlanEntry("raycaster", "view", []),
            ModulePlanEntry("main", "entry", ["autopilot", "raycaster"]),
        ]
        self.all_modules = {module.name for module in self.modules}

    def scope(self, paths):
        with contextlib.redirect_stderr(io.StringIO()):
            return determine_modules(paths, self.modules)

    def test_contract_selects_owner_and_transitive_consumers(self):
        self.assertEqual(
            self.scope(["ir/contracts/player_state.yaml"]),
            {"player_state", "weapon_system", "autopilot", "main"},
        )

    def test_shared_and_unmapped_sources_regenerate_all_modules(self):
        for path in (
            "ir/contracts/_shared.yaml",
            "ir/contracts/deleted_module.yaml",
            "specs/20_gameplay_model.md",
            "specs/35_demo_mode.md",
            "specs/40_visual_feedback.md",
            "specs/99_new_feature.md",
            "knowledge/new_mechanic.md",
            "tooling/agents/coder.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.scope([path]), self.all_modules)

    def test_unmapped_source_is_not_hidden_by_another_mapped_change(self):
        self.assertEqual(
            self.scope(["specs/45_raycaster_renderer.md", "specs/99_new_feature.md"]),
            self.all_modules,
        )

    def test_existing_renderer_scope_stays_partial(self):
        self.assertEqual(
            self.scope(["specs/45_raycaster_renderer.md"]), {"raycaster", "main"}
        )

    def test_scenario_only_change_opens_ci_gate_and_selects_runner(self):
        path = "tests/combat/armor_absorbs_damage.yaml"
        self.assertTrue(is_source_of_truth(path))
        self.assertEqual(self.scope([path]), {"weapon_system", "autopilot", "main"})

    def test_tooling_and_root_docs_do_not_trigger_game_generation(self):
        paths = ["tooling/tests/test_regeneration_scope.py", "README.md", "tooling/README.md"]
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(is_source_of_truth(path))
        self.assertEqual(self.scope(paths), set())

    def test_every_current_contract_reaches_its_owner_and_entry_point(self):
        modules = load_module_plan(MODULE_PLAN)
        for module in modules:
            if module.name == "main":
                continue
            path = f"ir/contracts/{module.name}.yaml"
            with self.subTest(path=path):
                self.assertTrue(is_source_of_truth(path))
                affected = determine_modules([path], modules)
                self.assertIn(module.name, affected)
                self.assertIn("main", affected)

    def test_dependency_cycles_terminate(self):
        modules = [
            ModulePlanEntry("player_state", "player", ["weapon_system"]),
            ModulePlanEntry("weapon_system", "combat", ["player_state"]),
        ]
        self.assertEqual(
            determine_modules(["ir/contracts/player_state.yaml"], modules),
            {"player_state", "weapon_system"},
        )

    def test_cli_fallback_emits_json_and_explains_reason_on_stderr(self):
        result = subprocess.run(
            [sys.executable, str(TOOLING / "partial_regen.py"),
             "--changed", "specs/99_new_feature.md", "--json"],
            capture_output=True, text=True, check=True,
        )
        expected = {module.name for module in load_module_plan(MODULE_PLAN)}
        self.assertEqual(set(json.loads(result.stdout)), expected)
        self.assertIn("specs/99_new_feature.md", result.stderr)

    def test_cli_explicit_empty_changes_does_not_read_git(self):
        result = subprocess.run(
            [sys.executable, str(TOOLING / "partial_regen.py"),
             "--base", "nonexistent-regression-test-ref", "--changed", "--json"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout), [])


if __name__ == "__main__":
    unittest.main()
