#!/usr/bin/env python3
"""
Headless wrapper that drives the multi-agent pipeline from CI.

For each invocation, this script runs ONE phase (extractor / architect / coder /
reconciler / postmortem) using Claude or Codex in non-interactive mode,
captures the per-call token usage, and appends a JSON record to
`artifacts/usage.jsonl`. Phase outputs that the agent writes to disk (e.g.
edits to `generated/`, `artifacts/postmortem.md`) are side effects of the
agent's tool use — this wrapper does not parse them.

`release.yml` calls this script once per phase in sequence; between phases
the workflow runs validation steps (validate_specs.py, etc.) so a failing
intermediate state surfaces immediately.

Inputs:
- --phase            extractor | architect | coder | reconciler | postmortem
- --provider         claude (default) | codex; Extractor remains Claude-only
- --mode             release (kept as a parameter for future use)
- --workflow         optional pr | release — names the calling GitHub workflow
                     so agents can disambiguate PR-mode from release-mode runs
                     (both pass `--mode release`; the framing string previously
                     said `Mode: release` for both, which confused
                     Reconciler/PostMortem mode-detection heuristics)
- --scope            optional free-text scope (forwarded into the prompt)
- --usage-jsonl      output path for the usage record (default: artifacts/usage.jsonl)
- --transcript       optional path to also save the raw stream-json transcript
- --max-turns        Claude-only turn cap (default: 240)
- --timeout-seconds  wall-clock cap for either provider (default: 18000)
- --model            provider-specific model override

Exit codes:
    0 — phase completed (usage record appended).
    1 — phase failed (CLI returned non-zero).
    2 — usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from agent_providers import (
    PHASES, PROVIDERS, PhaseUsage, build_command, parse_result,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "tooling" / "agents"
DEFAULT_USAGE = REPO_ROOT / "artifacts" / "usage.jsonl"
GENERATED_SRC_DIR = REPO_ROOT / "generated" / "game" / "src"

# Read-only inputs that are stable across all phases of a regen pass. Inlined
# verbatim at the top of every agent prompt so the Anthropic prompt-cache
# matches their prefix across consecutive `claude -p` calls — agents can still
# Read these via tool call, but the inlined copy is what the cache keys off.
#
# STRICT ALLOWLIST: only files that the regen pass DOES NOT mutate may appear
# here. specs/25_game_tuning.md (Reconciler writes to it) and the per-module
# ir/contracts/<module>.yaml shards (Architect writes to them) are deliberately
# excluded. The assertion below guards against accidental additions.
FROZEN_CONTEXT_FILES: List[str] = [
    "specs/00_project_goal.md",
    "specs/10_system_model.md",
    "specs/80_generation_rules.md",
    "ir/game_ir.yaml",
    "ir/module_plan.yaml",
    "ir/contracts/_shared.yaml",
]

_FROZEN_FORBIDDEN_PREFIXES = (
    "specs/25_game_tuning.md",  # Reconciler writes
    "ir/contracts/",            # per-module shards (only _shared.yaml allowed)
)
for _path in FROZEN_CONTEXT_FILES:
    for _bad in _FROZEN_FORBIDDEN_PREFIXES:
        if _path.startswith(_bad) and _path != "ir/contracts/_shared.yaml":
            raise AssertionError(
                f"FROZEN_CONTEXT_FILES contains mutable file `{_path}`. "
                f"Only stable, regen-pass-immutable files belong here — agents "
                f"that write to a file must NOT see it inlined as frozen "
                f"context (the cache key would invalidate every time)."
            )

def build_frozen_context() -> str:
    """Inline every file in FROZEN_CONTEXT_FILES verbatim. Missing files are
    skipped with a sentinel line so the prompt is still well-formed (e.g. on
    a checkout that predates the file)."""
    sections: List[str] = []
    for rel_path in FROZEN_CONTEXT_FILES:
        path = REPO_ROOT / rel_path
        sections.append(f"### {rel_path}\n")
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                sections.append(f"_(read error: {exc})_\n")
                continue
            sections.append(f"```\n{content}\n```\n")
        else:
            sections.append("_(file not present in this checkout)_\n")
    body = "\n".join(sections)
    header = (
        "## Frozen context\n\n"
        "The files below are read-only inputs for this regen pass. They are "
        "inlined here so the prompt cache hits across consecutive agent "
        "invocations. You may still re-read them via the Read tool; the "
        "inlined copy is for cache stability, not for restricting your access."
    )
    return f"{header}\n\n{body}"


def build_prompt(
    phase: str, mode: str, scope: Optional[str], workflow: Optional[str], provider: str = "claude"
) -> str:
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

    # Workflow disambiguates PR-mode from release-mode runs. Both currently
    # pass `--mode release` (the only valid value), so a previous "Mode:
    # release" framing string was the same for both — Reconciler/PostMortem
    # mode-detection heuristics misread pr.yml runs as release.yml runs.
    # See PostMortem #80 (2026-05-14) for the misdiagnosis pattern.
    workflow_line = (
        f"Workflow: `{workflow}.yml`. " if workflow else
        "Workflow: unknown (manual / local invocation). "
    )

    framing = (
        "You are running NON-INTERACTIVELY through the phase runner. "
        "Treat all instructions in the role prompt as authoritative. "
        f"Mode: `{mode}`. {workflow_line}"
        "Repository root is the current working directory. "
        "Use the tools available to you to make file changes. "
        "Respect the runtime tool and sandbox restrictions. "
        "Do not ask questions — if information is missing, escalate by writing a "
        "clear blocker note to `artifacts/blocker.md` and exit. When you are done, "
        "exit normally."
    )

    # Order matters for prompt-cache prefix matching: most-stable content first.
    # frozen_context is identical across every phase + scope combination, so it
    # forms the largest cacheable prefix.
    runtime = (
        "Claude runtime: the --allowedTools list is authoritative."
        if provider == "claude" else
        "Codex runtime: workspace-write sandbox, no interactive approvals. "
        "Use the available native tools instead of Claude-specific tool names. "
        "Do not invoke Claude or delegate to another model. "
        "The wrapper enforces a wall-clock timeout, not Claude's --max-turns."
    )
    return "\n\n".join([build_frozen_context(), framing, runtime, scope_block, "---", role_prompt])


def append_usage(usage: PhaseUsage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "provider": usage.provider,
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
    workflow: Optional[str],
    provider: str = "claude",
    timeout_seconds: int = 18000,
) -> PhaseUsage:
    try:
        cmd = build_command(provider, phase, model, max_turns, REPO_ROOT)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if shutil.which(provider) is None:
        raise SystemExit(f"`{provider}` CLI not found in PATH. Install it first.")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if provider == "codex" and os.environ.get("WORLDSMITH_CODEX_AUTH") == "chatgpt":
            from codex_session import read_auth, require_owner
            require_owner()
            read_auth(Path(os.environ["CODEX_HOME"]) / "auth.json")
        else:
            credential = "CODEX_API_KEY" if provider == "codex" else "CLAUDE_CODE_OAUTH_TOKEN"
            if not os.environ.get(credential):
                raise SystemExit(f"{credential} is required for {provider} in GitHub Actions.")

    prompt = build_prompt(phase, mode, scope, workflow, provider)
    # Save the rendered prompt as an artifact so the operator can inspect what
    # actually went to the model.
    prompt_artifact = REPO_ROOT / "artifacts" / f"prompt_{phase}.txt"
    prompt_artifact.parent.mkdir(parents=True, exist_ok=True)
    prompt_artifact.write_text(prompt, encoding="utf-8")

    print(f"+ {' '.join(cmd)} <<<(prompt fed via stdin)", file=sys.stderr)
    started = time.monotonic()
    timed_out = False
    with subprocess.Popen(
        cmd, cwd=REPO_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=(os.name == "posix"),
    ) as proc:
        try:
            stdout, stderr = proc.communicate(prompt, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            stdout, stderr = proc.communicate()
    suffix = "jsonl" if provider == "codex" else "json"
    if (provider == "codex" and os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("WORLDSMITH_CODEX_AUTH") == "chatgpt"):
        from codex_session import read_auth, redact
        session_dir = Path(os.environ["CODEX_HOME"])
        sessions = [read_auth(session_dir / name) for name in ("initial-auth.json", "auth.json")]
        stdout, stderr = redact(stdout, *sessions), redact(stderr, *sessions)
    transcript = transcript or REPO_ROOT / "artifacts" / f"{phase}.{provider}.{suffix}"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text(stdout, encoding="utf-8")
    transcript.with_suffix(transcript.suffix + ".stderr.log").write_text(stderr, encoding="utf-8")
    if timed_out:
        raise SystemExit(f"{provider} phase '{phase}' exceeded {timeout_seconds}s; see {transcript}.")
    if proc.returncode != 0:
        raise SystemExit(f"{provider} CLI exited {proc.returncode} for phase '{phase}'; see {transcript}.")
    try:
        usage = parse_result(provider, stdout, phase, mode, model)
    except (ValueError, TypeError, AttributeError) as exc:
        raise SystemExit(f"{provider} phase '{phase}' failed: {exc}; see {transcript}.") from exc
    if provider == "codex":
        usage.duration_ms = round((time.monotonic() - started) * 1000)
    return usage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument(
        "--provider", choices=PROVIDERS,
        default=os.environ.get("WORLDSMITH_AGENT_PROVIDER", "claude"),
        help="Phase provider (default: WORLDSMITH_AGENT_PROVIDER or claude).",
    )
    parser.add_argument("--mode", required=True, choices=["release"])
    parser.add_argument(
        "--workflow",
        default=None,
        choices=["pr", "release"],
        help="Name the calling GitHub workflow (pr.yml or release.yml). "
             "Surfaces in the agent framing string as `Workflow: <name>.yml` "
             "so Reconciler/PostMortem can disambiguate which workflow "
             "scheduled the run. Both workflows pass `--mode release` (the "
             "only valid mode value), so without this flag the framing was "
             "ambiguous and PostMortem repeatedly misread PR runs as release "
             "runs (see PR #79 / PostMortem #80).",
    )
    parser.add_argument("--scope", default=None)
    parser.add_argument("--usage-jsonl", type=Path, default=DEFAULT_USAGE)
    parser.add_argument("--transcript", type=Path, default=None)
    parser.add_argument("--max-turns", type=int, default=240)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--timeout-seconds", type=int, default=18000,
        help="Wall-clock phase limit for either provider (default: 18000).",
    )
    parser.add_argument(
        "--target-modules",
        nargs="+",
        default=None,
        help="Restrict edits to these module files (e.g. player_state weapon_system). "
             "Snapshots generated/game/src/ before the phase and reverts any file "
             "that does not correspond to a listed module after the phase. Used by "
             "the PR workflow for partial regeneration.",
    )
    args = parser.parse_args()
    if args.provider not in PROVIDERS:
        parser.error("WORLDSMITH_AGENT_PROVIDER must be claude or codex")
    if args.timeout_seconds <= 0 or args.max_turns <= 0:
        parser.error("--timeout-seconds and --max-turns must be positive")
    if args.model is None:
        args.model = os.environ.get(f"WORLDSMITH_{args.provider.upper()}_MODEL") or None
    return args


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
            if src.read_bytes() != dest.read_bytes():
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
    coder_report = REPO_ROOT / "artifacts" / "coder_report.md"
    report_before = coder_report.stat().st_mtime_ns if coder_report.exists() else None
    blocker = REPO_ROOT / "artifacts" / "blocker.md"
    blocker_before = blocker.stat().st_mtime_ns if blocker.exists() else None

    baseline: Optional[Path] = None
    if args.target_modules:
        baseline = _snapshot_src(GENERATED_SRC_DIR)
        if baseline is None:
            raise SystemExit("--target-modules requires an existing generated source baseline.")

    try:
        usage = run_real(
            phase=args.phase,
            mode=args.mode,
            scope=args.scope,
            transcript=args.transcript,
            max_turns=args.max_turns,
            model=args.model,
            workflow=args.workflow,
            provider=args.provider,
            timeout_seconds=args.timeout_seconds,
        )
    finally:
        if baseline is not None:
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
        f"provider={usage.provider} phase={usage.phase} mode={usage.mode} model={usage.model} "
        f"in={usage.input_tokens} out={usage.output_tokens} "
        f"cache_r={usage.cache_read} cache_c={usage.cache_creation} "
        f"turns={usage.turns}"
    )

    if blocker.exists() and blocker.stat().st_mtime_ns != blocker_before:
        if blocker.read_text(encoding="utf-8").strip():
            print(f"Phase reported a blocker; see {blocker}.", file=sys.stderr)
            return 1

    if args.phase == "coder":
        if (not coder_report.exists()
                or coder_report.stat().st_mtime_ns == report_before
                or not coder_report.read_text(encoding="utf-8").strip()):
            print(
                f"Coder phase exited without a fresh, non-empty {coder_report.relative_to(REPO_ROOT)}. "
                "Required by tooling/agents/coder.md § CI mode output; Reconciler's "
                "Step 0 framing-grep and Step 3 cross-walk depend on it. The PR #80 "
                "armor regen exited cleanly after 67 turns / 26.8k output tokens with "
                "no report, blinding both downstream phases. Aborting.",
                file=sys.stderr,
            )
            return 1

        forbidden = re.compile(
            r"Unchanged|already correct|carried from|carry-forward|"
            r"pre-existing|no changes needed|baseline was correct|no changes required"
        )
        report_lines = coder_report.read_text(encoding="utf-8").splitlines()
        hits = [
            f"  {coder_report.relative_to(REPO_ROOT)}:{lineno}: {line.rstrip()}"
            for lineno, line in enumerate(report_lines, start=1)
            if forbidden.search(line)
        ]
        if hits:
            print(
                f"Coder phase wrote forbidden release-style framing into "
                f"{coder_report.relative_to(REPO_ROOT)}. "
                "Mirrors the self-grep mandated by tooling/agents/coder.md § Quality "
                "Checklist (the 'Before submitting artifacts/coder_report.md, self-grep "
                "for forbidden release-style framing phrases' item). The same framing "
                "has now shipped in seven consecutive release-style regens "
                "(2026-05-11, -12, -14, -15 x2, -16 x2); prompt-side escalation is "
                "exhausted, so the gate now runs here. Hits:",
                file=sys.stderr,
            )
            for hit in hits:
                print(hit, file=sys.stderr)
            print(
                "Rewrite each line to describe what THIS run emitted, not the baseline "
                "delta. See tooling/agents/coder.md § Release regeneration mode.",
                file=sys.stderr,
            )
            return 1

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
