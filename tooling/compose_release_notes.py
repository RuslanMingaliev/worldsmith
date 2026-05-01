#!/usr/bin/env python3
"""
Compose release notes for the GitHub draft release.

Reads `.github/release-notes.template.md`, fills placeholders from the
generation manifest (token usage, post-mortem summary, asset list, build
stats), then runs `check_sanitization.py` on the rendered output to ensure
no source-game identifiers or secret-derived strings leak into a public
release.

Inputs:
- --version          release version, e.g. `2026.02`
- --template         path to the markdown template
- --usage-jsonl      JSONL file written by orchestrator_run.py (one record per phase
                       with at minimum: phase, input_tokens, output_tokens, cache_read,
                       cache_creation, model)
- --postmortem       path to artifacts/postmortem.md (sanitized post-mortem report)
- --manifest         path to artifacts/manifest.json — written by the release workflow,
                       contains module_count, loc, test_summary, rustc_version, generated_at
- --assets-dir       directory containing the assets to enumerate in the asset table
- --out              output path for the rendered release notes

Exit codes:
    0 — success.
    1 — sanitization failure (offending tokens detected).
    2 — usage error / missing input file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
SANITIZER = REPO_ROOT / "tooling" / "check_sanitization.py"


@dataclass
class PhaseUsage:
    phase: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read: int
    cache_creation: int

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @classmethod
    def from_record(cls, raw: Dict) -> "PhaseUsage":
        return cls(
            phase=str(raw.get("phase", "(unknown)")),
            model=str(raw.get("model", "(unknown)")),
            input_tokens=int(raw.get("input_tokens", 0) or 0),
            output_tokens=int(raw.get("output_tokens", 0) or 0),
            cache_read=int(raw.get("cache_read", 0) or 0),
            cache_creation=int(raw.get("cache_creation", 0) or 0),
        )


def load_usage(path: Optional[Path]) -> List[PhaseUsage]:
    if path is None:
        return []
    if not path.exists():
        raise SystemExit(
            f"compose_release_notes: --usage-jsonl path does not exist: {path}"
        )
    rows: List[PhaseUsage] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"compose_release_notes: malformed JSON on line {lineno} of {path}: {exc}"
            ) from exc
        rows.append(PhaseUsage.from_record(raw))
    return rows


def render_tokens_table(rows: List[PhaseUsage]) -> str:
    if not rows:
        return "_Token usage was not captured for this run._"

    header = (
        "| Phase | Model | Input | Output | Cache read | Cache creation | Total |\n"
        "|---|---|---:|---:|---:|---:|---:|"
    )
    body_lines: List[str] = []
    totals = PhaseUsage(
        phase="**Total**",
        model="—",
        input_tokens=0,
        output_tokens=0,
        cache_read=0,
        cache_creation=0,
    )
    for row in rows:
        body_lines.append(
            f"| {row.phase} | `{row.model}` | {row.input_tokens:,} | "
            f"{row.output_tokens:,} | {row.cache_read:,} | "
            f"{row.cache_creation:,} | {row.total:,} |"
        )
        totals.input_tokens += row.input_tokens
        totals.output_tokens += row.output_tokens
        totals.cache_read += row.cache_read
        totals.cache_creation += row.cache_creation

    body_lines.append(
        f"| {totals.phase} | {totals.model} | {totals.input_tokens:,} | "
        f"{totals.output_tokens:,} | {totals.cache_read:,} | "
        f"{totals.cache_creation:,} | {totals.total:,} |"
    )
    return "\n".join([header, *body_lines])


def render_asset_table(assets_dir: Path, version: str) -> str:
    if not assets_dir.exists():
        return "_(no assets enumerated)_"
    files = sorted(p for p in assets_dir.iterdir() if p.is_file())
    if not files:
        return "_(no assets present)_"
    rows = ["| File | Size |", "|---|---:|"]
    for path in files:
        size_kb = max(1, path.stat().st_size // 1024)
        rows.append(f"| `{path.name}` | {size_kb:,} KB |")
    return "\n".join(rows)


def load_postmortem(path: Optional[Path]) -> str:
    if path is None:
        return "_Post-mortem report was not produced for this run._"
    if not path.exists():
        # Caller explicitly asked for this file. Refuse to silently substitute
        # a placeholder — the post-mortem is required CI output per
        # tooling/agents/postmortem.md § CI output target.
        raise SystemExit(
            f"compose_release_notes: --postmortem path does not exist: {path}"
        )
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise SystemExit(
            f"compose_release_notes: --postmortem file is empty: {path}"
        )
    return text


def load_manifest(path: Optional[Path]) -> Dict[str, str]:
    defaults = {
        "module_count": "?",
        "loc": "?",
        "test_summary": "_Test summary unavailable._",
        "rustc_version": "rustc (version unrecorded)",
        "generated_at": "(date unrecorded)",
    }
    if path is None or not path.exists():
        return defaults
    raw = json.loads(path.read_text(encoding="utf-8"))
    for key in defaults:
        if key in raw and raw[key] is not None:
            defaults[key] = str(raw[key])
    return defaults


def render(template: str, version: str, replacements: Dict[str, str]) -> str:
    rendered = template
    rendered = rendered.replace("{{VERSION}}", version)
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def run_sanitizer(target: Path) -> int:
    result = subprocess.run(
        [sys.executable, str(SANITIZER), str(target)],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release version, e.g. 2026.02.")
    parser.add_argument(
        "--template",
        type=Path,
        default=REPO_ROOT / ".github" / "release-notes.template.md",
        help="Markdown template (default: .github/release-notes.template.md).",
    )
    parser.add_argument("--usage-jsonl", type=Path, default=None)
    parser.add_argument("--postmortem", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--assets-dir",
        type=Path,
        required=True,
        help="Directory containing the assets to be uploaded with the release.",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--skip-sanitizer",
        action="store_true",
        help="Skip the post-render sanitization gate (NOT recommended outside tests).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.template.exists():
        print(f"error: template not found: {args.template}", file=sys.stderr)
        return 2

    template = args.template.read_text(encoding="utf-8")
    usage = load_usage(args.usage_jsonl)
    manifest = load_manifest(args.manifest)

    replacements = {
        "GENERATED_AT": manifest["generated_at"],
        "MODULE_COUNT": manifest["module_count"],
        "LOC": manifest["loc"],
        "TEST_SUMMARY": manifest["test_summary"],
        "RUSTC_VERSION": manifest["rustc_version"],
        "ASSET_TABLE": render_asset_table(args.assets_dir, args.version),
        "TOKENS_TABLE": render_tokens_table(usage),
        "POSTMORTEM_SUMMARY": load_postmortem(args.postmortem),
    }

    rendered = render(template, args.version, replacements)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")

    if args.skip_sanitizer:
        print(f"Wrote {args.out} (sanitizer skipped).")
        return 0

    rc = run_sanitizer(args.out)
    if rc != 0:
        print(
            f"sanitization gate failed for {args.out}; refusing to publish.",
            file=sys.stderr,
        )
        return 1
    print(f"Wrote {args.out} (sanitizer passed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
