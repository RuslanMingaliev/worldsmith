#!/usr/bin/env python3
"""
Compose release notes for the GitHub draft release.

Reads `.github/release-notes.template.md`, fills placeholders from the
generation manifest (token usage, cache totals, build stats, optional
build-health caveat), then runs `check_sanitization.py` on the rendered
output to ensure no source-game identifiers or secret-derived strings
leak into a public release.

Inputs:
- --version             release version, e.g. `2026.04`
- --template            path to the markdown template
- --prev-version        previous release tag (substituted into the compare-view link)
- --usage-jsonl         JSONL file written by orchestrator_run.py (one record per phase
                          with at minimum: phase, input_tokens, output_tokens, cache_read,
                          cache_creation, model)
- --manifest            path to artifacts/manifest.json — module_count, loc, test_summary,
                          rustc_version, generated_at
- --release-hero        path to artifacts/release_hero.md (LLM-authored hero pitch)
- --release-buildhealth path to artifacts/release_buildhealth.md (LLM-authored caveat
                          paragraph; empty if no regression to flag)
- --out                 output path for the rendered release notes

The post-mortem is no longer embedded in the release notes — it ships as a
separate release asset (`worldsmith-<version>-postmortem.md`) and the
template's Read-it section links to it. The asset enumeration is also
gone from the template — GitHub renders the asset list at the bottom of
every release page natively.

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


def _format_token_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def render_cache_totals(rows: List[PhaseUsage]) -> Dict[str, str]:
    if not rows:
        return {"CACHE_READ_TOTAL": "0", "CACHE_CREATION_TOTAL": "0"}
    total_read = sum(r.cache_read for r in rows)
    total_creation = sum(r.cache_creation for r in rows)
    return {
        "CACHE_READ_TOTAL": _format_token_count(total_read),
        "CACHE_CREATION_TOTAL": _format_token_count(total_creation),
    }


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


def load_optional_markdown(path: Optional[Path], fallback: str) -> str:
    """Read an LLM-authored markdown fragment, falling back to `fallback` if
    the file is absent or empty. Returning a non-empty string keeps the
    template's section visible even when the upstream LLM phase failed —
    the maintainer just sees the fallback and edits the draft release.
    """
    if path is None or not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    return text or fallback


def run_sanitizer(target: Path) -> int:
    # `release-notes` mode keeps every literal + the year-range regex but
    # drops the generic SCREAMING_SNAKE fallback — see check_sanitization.py
    # for the rationale (knowledge/ and release notes have different threat
    # models; the fallback over-fires on worldsmith's own constants cited
    # from specs/).
    result = subprocess.run(
        [sys.executable, str(SANITIZER), "--mode", "release-notes", str(target)],
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
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--prev-version",
        default=None,
        help="Previous release tag, e.g. 2026.02. Substituted into {{PREV_VERSION}}. "
             "If absent, the placeholder is left as a literal string.",
    )
    parser.add_argument(
        "--release-hero",
        type=Path,
        default=None,
        help="Path to artifacts/release_hero.md (LLM-authored hero pitch). If absent, "
             "{{HERO_PITCH}} falls back to a short generic line.",
    )
    parser.add_argument(
        "--release-buildhealth",
        type=Path,
        default=None,
        help="Path to artifacts/release_buildhealth.md (LLM-authored 1-paragraph caveat "
             "naming any Reconciler-flagged coverage regression or other release-blocker "
             "the operator should know about before publishing). If absent or empty, "
             "{{BUILD_HEALTH_NOTE}} renders as empty (no caveat is the success case).",
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

    hero_pitch = load_optional_markdown(
        args.release_hero,
        fallback=(
            "_(Release Editor agent did not produce a hero pitch — write one "
            "in this draft before publishing.)_"
        ),
    )
    # Build-health note is empty by default — "clean run" is the success case
    # and adds no caveat paragraph. The fallback is the empty string, NOT a
    # placeholder marker, so the template's surrounding whitespace renders
    # cleanly without a maintainer-edit prompt.
    build_health_note = load_optional_markdown(args.release_buildhealth, fallback="")
    prev_version = args.prev_version or "_(previous tag)_"

    replacements = {
        "GENERATED_AT": manifest["generated_at"],
        "MODULE_COUNT": manifest["module_count"],
        "LOC": manifest["loc"],
        "TEST_SUMMARY": manifest["test_summary"],
        "RUSTC_VERSION": manifest["rustc_version"],
        "TOKENS_TABLE": render_tokens_table(usage),
        "HERO_PITCH": hero_pitch,
        "BUILD_HEALTH_NOTE": build_health_note,
        "PREV_VERSION": prev_version,
        **render_cache_totals(usage),
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
