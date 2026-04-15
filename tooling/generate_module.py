#!/usr/bin/env python3
"""
Prompt preparation helper for worldsmith module generation.

Usage:
    python tooling/generate_module.py --target player_state input_controller
    python tooling/generate_module.py --target all > prompts.md

The script loads `ir/module_plan.yaml` plus curated context files and emits a
Markdown prompt containing the relevant specs, knowledge, and responsibilities.
Humans (or future automation) can feed the prompt to an LLM and then copy the
resulting code back to `generated/game/src/<module>.rs`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML is required. Install with `python -m pip install pyyaml`."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_CONTEXT_FILES = [
    REPO_ROOT / "specs" / "00_project_goal.md",
    REPO_ROOT / "specs" / "10_system_model.md",
    REPO_ROOT / "specs" / "80_generation_rules.md",
    REPO_ROOT / "ir" / "game_ir.yaml",
]

# File heuristics for each module. Extend as specs/knowledge grow.
MODULE_CONTEXT_FILES: Dict[str, List[Path]] = {
    "level_data": [
        REPO_ROOT / "specs" / "20_gameplay_model.md",
        REPO_ROOT / "tests" / "level" / "README.md",
    ],
    "player_state": [
        REPO_ROOT / "specs" / "21_player_movement.md",
        REPO_ROOT / "knowledge" / "player_movement.md",
        REPO_ROOT / "tests" / "player" / "README.md",
    ],
    "input_controller": [
        REPO_ROOT / "specs" / "21_player_movement.md",
        REPO_ROOT / "tests" / "player" / "README.md",
    ],
    "weapon_system": [
        REPO_ROOT / "specs" / "20_gameplay_model.md",
        REPO_ROOT / "tests" / "combat" / "README.md",
    ],
    "enemy_logic": [
        REPO_ROOT / "specs" / "20_gameplay_model.md",
        REPO_ROOT / "tests" / "enemy" / "README.md",
    ],
    "presentation": [
        REPO_ROOT / "specs" / "20_gameplay_model.md",
    ],
    "renderer": [
        REPO_ROOT / "specs" / "20_gameplay_model.md",
    ],
    "game_loop": [
        REPO_ROOT / "specs" / "20_gameplay_model.md",
        REPO_ROOT / "specs" / "21_player_movement.md",
        REPO_ROOT / "tests" / "level" / "README.md",
    ],
    "autopilot": [
        REPO_ROOT / "specs" / "30_test_framework.md",
        REPO_ROOT / "tests" / "README.md",
        REPO_ROOT / "tests" / "level" / "complete_level.yaml",
        REPO_ROOT / "tests" / "combat" / "kill_enemy.yaml",
    ],
}


@dataclass
class ModuleEntry:
    name: str
    responsibility: str
    depends_on: List[str]


def load_module_plan() -> List[ModuleEntry]:
    path = REPO_ROOT / "ir" / "module_plan.yaml"
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    modules = raw.get("modules", [])
    entries: List[ModuleEntry] = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        name = module.get("name")
        responsibility = module.get("responsibility", "")
        depends_on = module.get("depends_on", []) or []
        if isinstance(name, str):
            dep_list = [str(dep) for dep in depends_on if isinstance(dep, str)]
            entries.append(
                ModuleEntry(name=name, responsibility=responsibility, depends_on=dep_list)
            )
    return entries


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return f"[Missing file: {path.relative_to(REPO_ROOT)}]"


def render_file_section(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT)
    content = read_file(path)
    return f"### {rel}\n```\n{content}\n```\n"


def render_module_prompt(entry: ModuleEntry) -> str:
    lines = [
        f"# Module: {entry.name}",
        "",
        f"**Responsibility:** {entry.responsibility or 'n/a'}",
        f"**Depends on:** {', '.join(entry.depends_on) if entry.depends_on else 'none'}",
        "",
        "## Global Context",
    ]
    for path in GLOBAL_CONTEXT_FILES:
        lines.append(render_file_section(path))

    lines.append("## Module-Specific Context")
    for path in MODULE_CONTEXT_FILES.get(entry.name, []):
        lines.append(render_file_section(path))

    lines.append(
        "## Instructions\n"
        "Generate the Rust module following the specs above and the rules in "
        "`specs/80_generation_rules.md`. Ensure the code integrates with existing "
        "modules, maintains explicit state, and includes unit tests covering the "
        "key behaviors described in the specs/tests."
    )

    return "\n".join(lines) + "\n"


def determine_targets(
    requested: Sequence[str], modules: Sequence[ModuleEntry]
) -> List[ModuleEntry]:
    if not requested or requested == ["all"]:
        return list(modules)

    module_map = {entry.name: entry for entry in modules}
    result: List[ModuleEntry] = []
    for name in requested:
        if name not in module_map:
            raise SystemExit(f"Unknown module '{name}'.")
        result.append(module_map[name])
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare prompts for module regeneration."
    )
    parser.add_argument(
        "--target",
        nargs="*",
        default=["all"],
        help="List of module names (default: all modules).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List known modules and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    modules = load_module_plan()

    if args.list:
        print("Available modules:")
        for entry in modules:
            deps = f" (depends on: {', '.join(entry.depends_on)})" if entry.depends_on else ""
            print(f"  - {entry.name}{deps}")
        return

    targets = determine_targets(args.target, modules)
    for idx, entry in enumerate(targets):
        if idx > 0:
            print("\n---\n")
        print(render_module_prompt(entry))


if __name__ == "__main__":
    main()
