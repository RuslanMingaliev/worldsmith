#!/usr/bin/env python3
"""
Partial regeneration planner.

Given a set of changed files (either explicit or inferred from git),
determine which modules should be regenerated.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set

try:
    import yaml  # type: ignore
except ImportError as exc:
    raise SystemExit(
        "PyYAML is required. Install with `python -m pip install pyyaml`."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PLAN = REPO_ROOT / "ir" / "module_plan.yaml"
TRIGGER_CONFIG = {
    # Files that, when changed, force a full regeneration.
    "global": [
        "specs/00_project_goal.md",
        "specs/10_system_model.md",
        "specs/80_generation_rules.md",
        "ir/game_ir.yaml",
        "ir/module_plan.yaml",
    ],
    # Initial heuristics mapping files/globs to logical triggers.
    #
    # NOTE: `specs/20_gameplay_model.md` was previously listed under FOUR
    # modules (level_data, weapon_system, enemy_logic, presentation),
    # causing the heuristic to over-fire on every edit to that file.
    # Dependency expansion then sucked in everything downstream. The file
    # is too cross-cutting for module-level triggers — it is the
    # gameplay-model umbrella spec, not a per-module spec. It now lives in
    # `manual_scope` below, which prints the candidate-module list as INFO
    # but does NOT add anything to the affected set unless the human
    # passes `--target` explicitly. The Orchestrator's scope override
    # remains the workflow.
    "file_triggers": {
        "player_state": [
            "specs/21_player_movement.md",
            "knowledge/player_movement.md",
            "tests/player/**",
            # specs/60 § Player Ammo: pickup workflow adds ammo + take_*_pickup.
            "specs/60_pickups.md",
            "knowledge/pickups.md",
        ],
        "weapon_system": [
            "tests/combat/**",
            # specs/60 § Ammo-Gated Firing: ammo gate lives in fire().
            "specs/60_pickups.md",
            "knowledge/pickups.md",
        ],
        "enemy_logic": [
            "tests/enemy/**",
        ],
        "autopilot": [
            "specs/30_test_framework.md",
            "tests/**",
        ],
        "level_data": [
            # specs/60 § Pickup Entity: Pickup type + pickups field live here.
            "specs/60_pickups.md",
            "knowledge/pickups.md",
        ],
        "game_loop": [
            # specs/60 § Per-Frame Pickup Check: Step 2.5 lives in game_loop::update.
            "specs/60_pickups.md",
            "knowledge/pickups.md",
        ],
        "renderer": [
            # specs/50 § HUD: draw routine + bitmap font are renderer-private.
            "specs/50_hud.md",
            "knowledge/hud.md",
            # Pickup sprite layer + HUD ammo pane also live in renderer.
            "specs/60_pickups.md",
            "knowledge/pickups.md",
        ],
    },
    # Files that are too cross-cutting for the per-module heuristic. When one
    # of these changes, partial_regen.py prints the candidate-module list
    # (gathered from human-curated comments below) but does NOT add to the
    # affected set automatically. Forces a human-or-Orchestrator scope
    # decision via `--target`.
    "manual_scope": {
        "specs/20_gameplay_model.md": [
            "level_data", "weapon_system", "enemy_logic", "presentation", "renderer", "game_loop",
            "# Cross-cutting umbrella spec; touches anything player-vs-world.",
            "# An edit may touch all of these or none. Use --target.",
        ],
    },
}


@dataclass(frozen=True)
class ModulePlanEntry:
    name: str
    responsibility: str
    depends_on: List[str]


def load_module_plan(path: Path) -> List[ModulePlanEntry]:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    modules = raw.get("modules", [])
    entries: List[ModulePlanEntry] = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        name = module.get("name")
        responsibility = module.get("responsibility", "")
        depends_on = module.get("depends_on", []) or []
        if isinstance(name, str):
            dep_list = [str(dep) for dep in depends_on if isinstance(dep, str)]
            entries.append(
                ModulePlanEntry(
                    name=name,
                    responsibility=responsibility,
                    depends_on=dep_list,
                )
            )
    return entries


def git_changed_files(base_ref: str) -> List[str]:
    """Return files changed relative to `base_ref`."""
    diff_spec = f"{base_ref}...HEAD"
    result = subprocess.run(
        ["git", "diff", "--name-only", diff_spec],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(
            f"git diff failed for base ref '{base_ref}': {result.stderr.strip()}"
        )

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def match_any(patterns: Sequence[str], path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def determine_modules(
    changed_files: Sequence[str],
    modules: Sequence[ModulePlanEntry],
) -> Set[str]:
    affected: Set[str] = set()
    known_modules = {entry.name for entry in modules}
    manual_scope_files: List[str] = []

    for path in changed_files:
        normalized = path.replace("\\", "/")
        if match_any(TRIGGER_CONFIG["global"], normalized):
            return set(known_modules)

        if normalized in TRIGGER_CONFIG.get("manual_scope", {}):
            manual_scope_files.append(normalized)
            continue

        for module, patterns in TRIGGER_CONFIG["file_triggers"].items():
            if module not in known_modules:
                continue
            if match_any(patterns, normalized):
                affected.add(module)

    # Print INFO for cross-cutting files that need a manual scope decision.
    for path in manual_scope_files:
        candidates = [
            x for x in TRIGGER_CONFIG["manual_scope"][path] if not x.startswith("#")
        ]
        notes = [
            x for x in TRIGGER_CONFIG["manual_scope"][path] if x.startswith("#")
        ]
        print(f"\nINFO: {path} is cross-cutting (manual scope required).")
        print(f"  Candidate modules: {', '.join(candidates) or '(none listed)'}")
        for note in notes:
            print(f"  {note}")
        print("  Use --target to choose; the per-module heuristic does not auto-add any module.")

    # Expand using IR dependencies
    dependency_map = {
        entry.name: [dep for dep in entry_dep_list(entry) if dep in known_modules]
        for entry in modules
    }
    expanded = set(affected)
    queue = list(affected)
    while queue:
        current = queue.pop()
        for module, deps in dependency_map.items():
            if current in deps and module not in expanded:
                expanded.add(module)
                queue.append(module)

    return expanded


def entry_dep_list(entry: ModulePlanEntry) -> List[str]:
    return list(entry.depends_on)


def format_modules(modules: Iterable[str]) -> str:
    return ", ".join(sorted(modules)) if modules else "(none)"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Determine which modules require regeneration."
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Git base ref for diff (default: origin/main). Ignored if --changed is set.",
    )
    parser.add_argument(
        "--changed",
        nargs="*",
        help="Explicit list of changed files (relative paths). Overrides --base.",
    )
    parser.add_argument(
        "--print-command",
        action="store_true",
        help="Print example generate_module.py invocation when modules are detected.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    module_plan = load_module_plan(MODULE_PLAN)

    if args.changed:
        changed_files = [path.strip() for path in args.changed if path.strip()]
    else:
        changed_files = git_changed_files(args.base)

    if not changed_files:
        print("No changed files detected.")
        return

    modules = determine_modules(changed_files, module_plan)

    print("Changed files:")
    for path in changed_files:
        print(f"  - {path}")

    if not modules:
        print("No module-specific regeneration suggested by current heuristics.")
        return

    print("Modules to regenerate:")
    for module in sorted(modules):
        responsibilities = next(
            (entry.responsibility for entry in module_plan if entry.name == module),
            "",
        )
        responsibility = f" ({responsibilities})" if responsibilities else ""
        print(f"  - {module}{responsibility}")

    if args.print_command:
        mod_list = " ".join(sorted(modules))
        print("\nSuggested command:")
        print(f"  python tooling/generate_module.py --target {mod_list}")


if __name__ == "__main__":
    main()
