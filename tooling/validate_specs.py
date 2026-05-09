#!/usr/bin/env python3
"""
Basic validator for specs, IR, and knowledge files.

Checks:
- Required spec/knowledge files exist.
- `ir/game_ir.yaml` and `ir/module_plan.yaml` parse as YAML.
- Minimal schema validation for the IR files.
- Reference / knowledge integrity: if `reference/` is empty, knowledge/
  must not have uncommitted additions or modifications. (This catches
  the failure mode where a session writes invented "knowledge" without
  any reference loaded.)
"""

from __future__ import annotations

import argparse
import subprocess
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


def validate_contracts_shards(
    contracts_dir: Path, module_plan_path: Path
) -> List[ValidationIssue]:
    """Verify the ir/contracts/ shard layout is intact.

    Rules:
    - `ir/contracts/_shared.yaml` exists, parses, and has a `shared_types` key.
    - Every module listed in `ir/module_plan.yaml` has a matching
      `ir/contracts/<name>.yaml` that parses and whose top-level `name` field
      matches the file stem.
    - No `ir/module_contracts.yaml` monolith remains (the shard layout
      replaces it).
    """
    issues: List[ValidationIssue] = []
    repo = module_plan_path.parents[1]
    legacy = repo / "ir" / "module_contracts.yaml"
    if legacy.exists():
        issues.append(
            ValidationIssue(
                legacy,
                "Legacy monolith ir/module_contracts.yaml is present. The "
                "contracts moved to ir/contracts/_shared.yaml + per-module "
                "ir/contracts/<name>.yaml. Delete the monolith.",
            )
        )

    shared = contracts_dir / "_shared.yaml"
    if not shared.exists():
        issues.append(ValidationIssue(shared, "Missing ir/contracts/_shared.yaml."))
    else:
        try:
            shared_data = load_yaml(shared)
        except ValidationError as exc:
            issues.append(ValidationIssue(shared, str(exc)))
            shared_data = None
        if shared_data is not None and "shared_types" not in shared_data:
            issues.append(
                ValidationIssue(
                    shared,
                    "ir/contracts/_shared.yaml missing required key `shared_types`.",
                )
            )

    try:
        plan_data = load_yaml(module_plan_path)
    except ValidationError:
        return issues  # already reported by validate_module_plan
    modules = plan_data.get("modules") or []
    expected_names: List[str] = []
    for module in modules:
        if isinstance(module, dict):
            name = module.get("name")
            if isinstance(name, str) and name != "main":
                expected_names.append(name)

    for name in expected_names:
        shard = contracts_dir / f"{name}.yaml"
        if not shard.exists():
            issues.append(
                ValidationIssue(
                    shard,
                    f"Missing contract shard for module `{name}`. Every entry in "
                    f"ir/module_plan.yaml (except `main`) needs ir/contracts/<name>.yaml.",
                )
            )
            continue
        try:
            shard_data = load_yaml(shard)
        except ValidationError as exc:
            issues.append(ValidationIssue(shard, str(exc)))
            continue
        shard_name = shard_data.get("name")
        if shard_name != name:
            issues.append(
                ValidationIssue(
                    shard,
                    f"Shard top-level `name` is `{shard_name}` but file is `{name}.yaml`. "
                    f"They must match.",
                )
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
    main_depends_on: List[str] = []
    main_present = False
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

        if name == "main":
            main_present = True
            deps = module.get("depends_on", []) or []
            if isinstance(deps, list):
                main_depends_on = [d for d in deps if isinstance(d, str)]

    # If `main` is in the plan, it must list every other module in depends_on.
    # Rationale: partial_regen.py's reverse-dep closure relies on main being a
    # universal sink so any triggered module pulls main into the regen scope.
    # Forgetting to add a new module to main.depends_on creates a silent gap
    # — the new module would regenerate without main.rs being re-emitted to
    # declare it, reproducing the orphan-file bug from PR #10. This invariant
    # makes that mistake a hard validation error.
    if main_present:
        expected = seen_names - {"main"}
        listed = set(main_depends_on)
        missing = expected - listed
        extra = listed - expected
        if missing:
            issues.append(
                ValidationIssue(
                    path,
                    f"main.depends_on is missing modules: {sorted(missing)}. "
                    f"main is the universal sink in partial_regen.py's "
                    f"reverse-dep closure; every module must be listed.",
                )
            )
        if extra:
            issues.append(
                ValidationIssue(
                    path,
                    f"main.depends_on lists unknown modules: {sorted(extra)}. "
                    f"Either add the module to ir/module_plan.yaml or remove "
                    f"the entry from main.depends_on.",
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Reference / knowledge integrity check
# ---------------------------------------------------------------------------
#
# `reference/` is a private corpus; it is gitignored except for `.gitignore`
# and `README.md`. When `reference/` contains nothing else (i.e. no source
# files have been loaded), the Extractor agent CANNOT run — there is nothing
# to extract from. In that state, ANY uncommitted change to `knowledge/`
# (modified tracked files OR untracked new files) is almost certainly an
# invented entry that does not come from a real reference. This check
# surfaces that condition loudly so the model does not silently fabricate.
#
# Rule (enforced):
#   if reference/ is empty AND knowledge/ has uncommitted changes -> FAIL.
#
# Rule (warning only):
#   if reference/ is empty -> print a banner reminding the session that
#   the Extractor is disabled this run.

REFERENCE_DIR = REPO_ROOT / "reference"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"

# Files that may be present in reference/ even when "no reference is loaded".
REFERENCE_BASELINE = {".gitignore", "README.md"}


def reference_is_empty() -> bool:
    """True iff reference/ contains only the baseline placeholder files."""
    if not REFERENCE_DIR.is_dir():
        return True
    for entry in REFERENCE_DIR.iterdir():
        if entry.name not in REFERENCE_BASELINE:
            return False
    return True


def knowledge_has_uncommitted_changes() -> List[str]:
    """Return a list of `knowledge/*` paths with modifications or untracked content.

    Uses `git status --porcelain knowledge/` so the check works without a
    full diff. If git is unavailable, returns an empty list (the script
    still runs in non-git environments — the warning above is enough).
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "knowledge/"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
    except FileNotFoundError:
        return []

    if result.returncode != 0:
        return []

    paths: List[str] = []
    for line in result.stdout.splitlines():
        # Porcelain format: `XY path` where XY are status codes.
        if len(line) < 4:
            continue
        path = line[3:].strip()
        # Strip surrounding quotes that git adds for paths with spaces.
        path = path.strip('"')
        if path.startswith("knowledge/"):
            paths.append(path)
    return paths


def validate_reference_knowledge_integrity() -> List[ValidationIssue]:
    """Block invented knowledge when no reference is loaded."""
    if not reference_is_empty():
        return []

    # Reference is empty. Print a loud banner regardless of knowledge state.
    banner = (
        "\n"
        "============================================================\n"
        "  EXTRACTOR DISABLED: reference/ is empty.\n"
        "  No knowledge/ entries can be ADDED or MODIFIED this session.\n"
        "  Existing knowledge files were extracted before the public\n"
        "  release; treat them as immutable until reference/ is\n"
        "  repopulated. If a spec value lacks knowledge backing, mark\n"
        "  Source as `Generation default — no knowledge backing` in\n"
        "  spec/25 instead of inventing a knowledge citation.\n"
        "============================================================\n"
    )
    print(banner, file=sys.stderr)

    dirty = knowledge_has_uncommitted_changes()
    if not dirty:
        return []

    issues = [
        ValidationIssue(
            KNOWLEDGE_DIR,
            "reference/ is empty but knowledge/ has uncommitted changes — "
            "Extractor cannot run, so these entries cannot have a real "
            "reference source. Revert them or load reference/ first.",
        )
    ]
    for path in dirty:
        issues.append(ValidationIssue(REPO_ROOT / path, "uncommitted knowledge change without reference/ backing"))
    return issues


# ---------------------------------------------------------------------------
# Sanitization gate (delegates to tooling/check_sanitization.py)
# ---------------------------------------------------------------------------
#
# Forbidden-token detection lives in `tooling/check_sanitization.py` (the
# single source of truth). Any leak in a `knowledge/*.md` file is a hard
# validation error: the public knowledge artifact must be source-identifier
# clean regardless of whether the offending file is committed or freshly
# modified.

CHECK_SANITIZATION_SCRIPT = REPO_ROOT / "tooling" / "check_sanitization.py"
CHECK_ORPHAN_FILES_SCRIPT = REPO_ROOT / "tooling" / "check_orphan_files.py"


def validate_knowledge_sanitization() -> List[ValidationIssue]:
    """Fail validation if any `knowledge/*.md` file has a forbidden token."""
    if not CHECK_SANITIZATION_SCRIPT.exists():
        return []

    all_files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not all_files:
        return []

    cmd = [sys.executable, str(CHECK_SANITIZATION_SCRIPT)] + [str(p) for p in all_files]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode == 0:
        return []
    return [
        ValidationIssue(
            KNOWLEDGE_DIR,
            "sanitization leak — see tooling/check_sanitization.py output above",
        )
    ]


def validate_orphan_files() -> List[ValidationIssue]:
    """Run the orphan-file gate over generated/game/src/.

    A `*.rs` file in src/ that has no matching `mod <name>;` in main.rs is
    silently omitted from the crate by rustc — zero warnings, zero compiled
    tests. The Reconciler agent learned to flag this manually after PR #10;
    this is the mechanical complement.
    """
    if not CHECK_ORPHAN_FILES_SCRIPT.exists():
        return []
    result = subprocess.run(
        [sys.executable, str(CHECK_ORPHAN_FILES_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode == 0:
        return []
    return [
        ValidationIssue(
            REPO_ROOT / "generated" / "game" / "src",
            "orphan source files present — see tooling/check_orphan_files.py "
            "output above.",
        )
    ]


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
    issues.extend(
        validate_contracts_shards(
            REPO_ROOT / "ir" / "contracts",
            REPO_ROOT / "ir" / "module_plan.yaml",
        )
    )
    issues.extend(validate_reference_knowledge_integrity())
    issues.extend(validate_knowledge_sanitization())
    issues.extend(validate_orphan_files())

    if issues:
        print("Validation failed:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print("All spec/IR/knowledge checks passed.")


if __name__ == "__main__":
    main()
