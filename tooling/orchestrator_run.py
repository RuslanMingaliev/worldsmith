#!/usr/bin/env python3
"""
Headless wrapper that drives the multi-agent pipeline from CI.

For each invocation, this script runs ONE phase (extractor / architect / coder /
reconciler / postmortem) by calling the `claude` CLI in non-interactive mode,
captures the per-call token usage, and appends a JSON record to
`artifacts/usage.jsonl`. Phase outputs that the agent writes to disk (e.g.
edits to `generated/`, `artifacts/postmortem.md`) are side effects of the
agent's tool use — this wrapper does not parse them.

`release.yml` calls this script once per phase in sequence; between phases
the workflow runs validation steps (validate_specs.py, etc.) so a failing
intermediate state surfaces immediately.

Inputs:
- --phase            extractor | architect | coder | reconciler | postmortem
- --mode             release (kept as a parameter for future use)
- --scope            optional free-text scope (forwarded into the prompt)
- --usage-jsonl      output path for the usage record (default: artifacts/usage.jsonl)
- --transcript       optional path to also save the raw stream-json transcript
- --max-turns        cap on agent turns (default: 80)
- --model            override the Claude model id (default: inherits from CLI/env)

Exit codes:
    0 — phase completed (usage record appended).
    1 — phase failed (CLI returned non-zero).
    2 — usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "tooling" / "agents"
DEFAULT_USAGE = REPO_ROOT / "artifacts" / "usage.jsonl"
GENERATED_SRC_DIR = REPO_ROOT / "generated" / "game" / "src"

PHASES = ["extractor", "architect", "coder", "reconciler", "postmortem"]

# Tools each phase is permitted to invoke. Conservative defaults — broaden
# only when the phase legitimately needs more.
PHASE_TOOLS: Dict[str, List[str]] = {
    "extractor": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    "architect": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    "coder": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    "reconciler": ["Read", "Edit", "Bash", "Grep", "Glob"],
    "postmortem": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
}


@dataclass
class PhaseUsage:
    phase: str
    mode: str
    model: str = "(unknown)"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    turns: int = 0
    duration_ms: int = 0
    notes: List[str] = field(default_factory=list)


def build_prompt(phase: str, mode: str, scope: Optional[str]) -> str:
    role_prompt_path = AGENTS_DIR / f"{phase}.md"
    if not role_prompt_path.exists():
        raise SystemExit(
            f"Agent prompt not found for phase '{phase}': {role_prompt_path}"
        )
    role_prompt = role_prompt_path.read_text(encoding="utf-8")

    scope_block = (
        f"## Scope override\n\n{scope}\n"
        if scope
        else "## Scope\n\nProceed with the default scope described in the role prompt above.\n"
    )

    framing = (
        "You are running NON-INTERACTIVELY inside a CI workflow. "
        "Treat all instructions in the role prompt as authoritative. "
        f"Mode: `{mode}`. Repository root is the current working directory. "
        "Use Read/Write/Edit/Bash tools to make file changes; do not ask questions — "
        "if information is missing, escalate by writing a clear blocker note to "
        "`artifacts/blocker.md` and exit. When you are done, exit normally."
    )

    return "\n\n".join([framing, scope_block, "---", role_prompt])


# Pin per-phase. CLI default is Sonnet 4.6 (200K) which blew up on issue #6.
# Coder stays on Sonnet — per-module context fits 200K and Orchestrator has
# its own Opus fallback after repeated cargo-check failures.
PHASE_DEFAULT_MODEL = {
    "extractor": "claude-opus-4-7[1m]",
    "architect": "claude-opus-4-7[1m]",
    "coder": "sonnet",
    "reconciler": "claude-opus-4-7[1m]",
    "postmortem": "claude-opus-4-7[1m]",
}


def claude_command(phase: str, model: Optional[str], max_turns: int) -> List[str]:
    """Build the `claude` CLI invocation. The prompt is fed via stdin
    (the CLI does not expose a `--prompt-file` flag) and a single JSON
    summary is emitted via `--output-format json` once the agent finishes."""
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--max-turns",
        str(max_turns),
        "--allowedTools",
        ",".join(PHASE_TOOLS.get(phase, ["Read", "Write", "Edit", "Bash"])),
    ]
    effective_model = model or PHASE_DEFAULT_MODEL.get(phase)
    if effective_model:
        cmd.extend(["--model", effective_model])
    return cmd


def parse_usage_from_json(stdout: str, phase: str, mode: str) -> PhaseUsage:
    """Parse the single JSON object emitted by `claude -p --output-format json`.

    Shape (per Agent SDK docs): top-level fields include `result`, `session_id`,
    `num_turns`, `duration_ms`, `usage` (with input/output/cache token counts),
    and optionally `model`."""
    usage = PhaseUsage(phase=phase, mode=mode)
    text = stdout.strip()
    if not text:
        return usage
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        print(
            f"warning: could not decode claude JSON output ({exc}); usage will be zero.",
            file=sys.stderr,
        )
        return usage

    usage.duration_ms = int(payload.get("duration_ms", 0) or 0)
    usage.turns = int(payload.get("num_turns", 0) or 0)
    # Newer Claude CLI emits `modelUsage` (a dict keyed by model id) instead
    # of a top-level `model` field. A single phase routinely uses multiple
    # models (e.g. Opus for primary inference + Haiku for sub-task decisions),
    # so pick the primary by output token volume — that's the model the
    # operator cares about for cost / capability attribution. Older CLIs
    # with a top-level `model` field still work via the fallback.
    model_usage = payload.get("modelUsage") or {}
    if model_usage:
        # Rank by total token volume (input + output + cache_read + cache_creation)
        # rather than output_tokens alone — Haiku helpers often emit more
        # output_tokens on trivial sub-tasks than the primary Opus pass that
        # actually carries the work. Total volume tracks model effort honestly.
        def _model_volume(stats: dict) -> int:
            stats = stats or {}
            return sum(
                int(stats.get(k, 0) or 0)
                for k in (
                    "inputTokens",
                    "outputTokens",
                    "cacheReadInputTokens",
                    "cacheCreationInputTokens",
                )
            )

        primary = max(model_usage.items(), key=lambda kv: _model_volume(kv[1]))
        usage.model = primary[0]
    elif "model" in payload:
        usage.model = str(payload["model"])

    agg = payload.get("usage") or {}
    usage.input_tokens = int(agg.get("input_tokens", 0) or 0)
    usage.output_tokens = int(agg.get("output_tokens", 0) or 0)
    usage.cache_read = int(agg.get("cache_read_input_tokens", 0) or 0)
    usage.cache_creation = int(agg.get("cache_creation_input_tokens", 0) or 0)
    return usage


def append_usage(usage: PhaseUsage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "phase": usage.phase,
        "mode": usage.mode,
        "model": usage.model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read": usage.cache_read,
        "cache_creation": usage.cache_creation,
        "turns": usage.turns,
        "duration_ms": usage.duration_ms,
    }
    if usage.notes:
        record["notes"] = usage.notes
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def run_real(
    phase: str,
    mode: str,
    scope: Optional[str],
    transcript: Optional[Path],
    max_turns: int,
    model: Optional[str],
) -> PhaseUsage:
    if shutil.which("claude") is None:
        raise SystemExit(
            "`claude` CLI not found in PATH. Install Claude Code first."
        )

    prompt = build_prompt(phase, mode, scope)
    # Save the rendered prompt as an artifact so the operator can inspect what
    # actually went to the model.
    prompt_artifact = REPO_ROOT / "artifacts" / f"prompt_{phase}.txt"
    prompt_artifact.parent.mkdir(parents=True, exist_ok=True)
    prompt_artifact.write_text(prompt, encoding="utf-8")

    cmd = claude_command(phase, model, max_turns)
    print(f"+ {' '.join(cmd)} <<<(prompt fed via stdin)", file=sys.stderr)

    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        input=prompt,
        capture_output=True,
        text=True,
        check=False,
    )

    if transcript:
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text(proc.stdout, encoding="utf-8")

    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(
            f"claude CLI exited {proc.returncode} for phase '{phase}'."
        )

    return parse_usage_from_json(proc.stdout, phase, mode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--mode", required=True, choices=["release"])
    parser.add_argument("--scope", default=None)
    parser.add_argument("--usage-jsonl", type=Path, default=DEFAULT_USAGE)
    parser.add_argument("--transcript", type=Path, default=None)
    parser.add_argument("--max-turns", type=int, default=80)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--target-modules",
        nargs="*",
        default=None,
        help="Restrict edits to these module files (e.g. player_state weapon_system). "
             "Snapshots generated/game/src/ before the phase and reverts any file "
             "that does not correspond to a listed module after the phase. Used by "
             "the PR workflow for partial regeneration.",
    )
    return parser.parse_args()


def _snapshot_src(src_dir: Path) -> Optional[Path]:
    """Copy src_dir to a sibling .baseline directory before a phase runs.

    Returns the baseline path, or None if src_dir doesn't exist."""
    if not src_dir.exists():
        return None
    baseline = src_dir.parent / f".{src_dir.name}.baseline"
    if baseline.exists():
        shutil.rmtree(baseline)
    shutil.copytree(src_dir, baseline)
    return baseline


def _revert_out_of_scope(
    src_dir: Path,
    baseline: Path,
    target_modules: List[str],
) -> List[str]:
    """Revert any file in src_dir that does not correspond to a target module.

    A target module name `X` maps to filename `X.rs`. Anything else is reverted
    from baseline (if present) or deleted (if Coder created a new file).
    Files Coder removed (and that aren't in targets) are restored from baseline.

    Returns a list of reverted entries for logging."""
    target_files = {f"{name}.rs" for name in target_modules}
    current_files = {
        p.relative_to(src_dir) for p in src_dir.rglob("*") if p.is_file()
    }
    baseline_files = {
        p.relative_to(baseline) for p in baseline.rglob("*") if p.is_file()
    }

    reverted: List[str] = []

    for rel in current_files:
        rel_str = str(rel)
        if rel_str in target_files:
            continue
        dest = src_dir / rel
        src = baseline / rel
        if src.exists():
            shutil.copy2(src, dest)
            reverted.append(f"{rel_str} (reverted to baseline)")
        else:
            dest.unlink()
            reverted.append(f"{rel_str} (deleted; was new and out-of-scope)")

    for rel in baseline_files - current_files:
        rel_str = str(rel)
        if rel_str in target_files:
            continue
        dest = src_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline / rel, dest)
        reverted.append(f"{rel_str} (restored; Coder deleted it)")

    return reverted


def main() -> int:
    args = parse_args()

    baseline: Optional[Path] = None
    if args.target_modules:
        baseline = _snapshot_src(GENERATED_SRC_DIR)
        if baseline is None:
            print(
                f"warning: --target-modules set but {GENERATED_SRC_DIR} does not exist; "
                "skipping snapshot. Coder will run unguarded.",
                file=sys.stderr,
            )

    try:
        usage = run_real(
            phase=args.phase,
            mode=args.mode,
            scope=args.scope,
            transcript=args.transcript,
            max_turns=args.max_turns,
            model=args.model,
        )
    finally:
        if baseline is not None and GENERATED_SRC_DIR.exists():
            reverted = _revert_out_of_scope(
                GENERATED_SRC_DIR, baseline, args.target_modules
            )
            if reverted:
                print(
                    "Out-of-scope edits reverted to baseline (--target-modules guard):",
                    file=sys.stderr,
                )
                for entry in reverted:
                    print(f"  - {entry}", file=sys.stderr)
            shutil.rmtree(baseline)

    append_usage(usage, args.usage_jsonl)
    print(
        f"phase={usage.phase} mode={usage.mode} model={usage.model} "
        f"in={usage.input_tokens} out={usage.output_tokens} "
        f"cache_r={usage.cache_read} cache_c={usage.cache_creation} "
        f"turns={usage.turns}"
    )

    cap_env = os.environ.get("WORLDSMITH_MAX_TOKENS_PER_RUN")
    if cap_env:
        try:
            cap = int(cap_env)
        except ValueError:
            cap = None
        if cap and args.usage_jsonl.exists():
            total = 0
            for line in args.usage_jsonl.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                total += int(row.get("input_tokens", 0) or 0)
                total += int(row.get("output_tokens", 0) or 0)
            if total > cap:
                print(
                    f"WORLDSMITH_MAX_TOKENS_PER_RUN={cap} exceeded "
                    f"(used {total:,}); aborting before next phase.",
                    file=sys.stderr,
                )
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
