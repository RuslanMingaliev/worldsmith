#!/usr/bin/env python3
"""
Basic validator for specs, IR, and knowledge files.

Checks:
- Required spec/knowledge files exist.
- `ir/game_ir.yaml` and `ir/module_plan.yaml` parse as YAML.
- Minimal schema validation for the IR files.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "PyYAML is required. Install with `python -m pip install pyyaml`."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SPEC_FILES = [
    REPO_ROOT / "specs" / "00_project_goal.md",
    REPO_ROOT / "specs" / "10_system_model.md",
    REPO_ROOT / "specs" / "20_gameplay_model.md",
    REPO_ROOT / "specs" / "21_player_movement.md",
    REPO_ROOT / "specs" / "80_generation_rules.md",
]

REQUIRED_KNOWLEDGE_FILES = [
    REPO_ROOT / "knowledge" / "README.md",
]


@dataclass
class ValidationIssue:
    path: Path
    message: str

    def __str__(self) -> str:
        rel_path = self.path.relative_to(REPO_ROOT)
        return f"{rel_path}: {self.message}"


def load_yaml(path: Path) -> Dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError:
        raise ValidationError(f"File does not exist: {path}")
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML: {exc}")

    if data is None:
        raise ValidationError("YAML file is empty.")

    if not isinstance(data, dict):
        raise ValidationError("Expected top-level mapping.")

    return data


class ValidationError(RuntimeError):
    """Raised for fatal issues when loading files."""


def validate_required_files(paths: Sequence[Path]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for path in paths:
        if not path.exists():
            issues.append(ValidationIssue(path, "Missing required file."))
    return issues


def validate_game_ir(path: Path) -> List[ValidationIssue]:
    try:
        data = load_yaml(path)
    except ValidationError as exc:
        return [ValidationIssue(path, str(exc))]

    issues: List[ValidationIssue] = []
    for key in ["game_family", "version", "goal", "player", "combat", "enemy", "level"]:
        if key not in data:
            issues.append(ValidationIssue(path, f"Missing required key `{key}`."))

    player = data.get("player", {})
    if not isinstance(player, dict) or "movement" not in player:
        issues.append(ValidationIssue(path, "player.movement must be defined."))

    level = data.get("level", {})
    if not isinstance(level, dict) or "count" not in level or "type" not in level:
        issues.append(
            ValidationIssue(path, "level.count and level.type must be defined.")
        )

    return issues


def validate_module_plan(path: Path) -> List[ValidationIssue]:
    try:
        data = load_yaml(path)
    except ValidationError as exc:
        return [ValidationIssue(path, str(exc))]

    issues: List[ValidationIssue] = []
    modules = data.get("modules")
    if not isinstance(modules, list) or not modules:
        return [ValidationIssue(path, "`modules` must be a non-empty list.")]

    seen_names = set()
    for idx, module in enumerate(modules):
        if not isinstance(module, dict):
            issues.append(
                ValidationIssue(path, f"modules[{idx}] must be a mapping/dict.")
            )
            continue

        name = module.get("name")
        responsibility = module.get("responsibility")

        if not name or not isinstance(name, str):
            issues.append(
                ValidationIssue(path, f"modules[{idx}] missing string `name`.")
            )
        elif name in seen_names:
            issues.append(
                ValidationIssue(path, f"Duplicate module name `{name}` detected.")
            )
        else:
            seen_names.add(name)

        if not responsibility or not isinstance(responsibility, str):
            issues.append(
                ValidationIssue(
                    path, f"modules[{idx}] missing string `responsibility`."
                )
            )

    return issues


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate specs, knowledge, and IR files."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print success messages for each check.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    issues: List[ValidationIssue] = []

    issues.extend(validate_required_files(REQUIRED_SPEC_FILES))
    issues.extend(validate_required_files(REQUIRED_KNOWLEDGE_FILES))
    issues.extend(validate_game_ir(REPO_ROOT / "ir" / "game_ir.yaml"))
    issues.extend(validate_module_plan(REPO_ROOT / "ir" / "module_plan.yaml"))

    if issues:
        print("Validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print("All spec/IR/knowledge checks passed.")


if __name__ == "__main__":
    main()
