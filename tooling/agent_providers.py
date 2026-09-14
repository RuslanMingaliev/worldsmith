"""CLI commands and result normalization for generation phase providers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

PROVIDERS = ("claude", "codex")


PHASES = ["extractor", "architect", "coder", "reconciler", "postmortem", "release_editor"]

# Tools each phase is permitted to invoke. Conservative defaults — broaden
# only when the phase legitimately needs more.
PHASE_TOOLS: Dict[str, List[str]] = {
    "extractor": ["Read", "Write", "Edit", "Grep", "Glob"],
    "architect": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    "coder": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    "reconciler": ["Read", "Edit", "Bash", "Grep", "Glob"],
    "postmortem": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    "release_editor": ["Read", "Write", "Bash", "Grep", "Glob"],
}


@dataclass
class PhaseUsage:
    phase: str
    mode: str
    provider: str = "claude"
    model: str = "(unknown)"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    turns: int = 0
    duration_ms: int = 0
    notes: List[str] = field(default_factory=list)


# Pin per-phase. CLI default is Sonnet 4.6 (200K) which blew up on issue #6.
# Coder stays on Sonnet — per-module context fits 200K and Orchestrator has
# its own Opus fallback after repeated cargo-check failures.
PHASE_DEFAULT_MODEL = {
    "extractor": "claude-opus-4-7[1m]",
    "architect": "claude-opus-4-7[1m]",
    "coder": "sonnet",
    "reconciler": "claude-opus-4-7[1m]",
    "postmortem": "claude-opus-4-7[1m]",
    "release_editor": "claude-opus-4-7[1m]",
}


def codex_command(phase: str, model: Optional[str], repo_root: Path) -> List[str]:
    if phase == "extractor":
        raise ValueError(
            "Codex Extractor is not supported: the existing no-shell tool policy "
            "has no verified equivalent. Use --provider claude for extraction."
        )
    cmd = [
        "codex", "exec", "--json", "--ephemeral", "--color", "never",
        "--sandbox", "workspace-write", "--cd", str(repo_root),
        "-c", 'approval_policy="never"',
        "-c", 'shell_environment_policy.exclude=["CODEX_API_KEY","OPENAI_API_KEY",'
        '"CLAUDE_CODE_OAUTH_TOKEN"]',
    ]
    if os.environ.get("GITHUB_ACTIONS") == "true":
        # Cargo fetch/check and Release Editor's gh queries need network access.
        # Permit the existing Cargo cache without granting general home writes.
        cmd.extend([
            "-c", "sandbox_workspace_write.network_access=true",
            "--add-dir", os.environ.get("CARGO_HOME") or str(Path.home() / ".cargo"),
        ])
    if model:
        cmd.extend(["--model", model])
    cmd.append("-")
    return cmd


def build_command(
    provider: str, phase: str, model: Optional[str], max_turns: int, repo_root: Path
) -> List[str]:
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}")
    if provider == "claude":
        return claude_command(phase, model, max_turns)
    if provider == "codex":
        return codex_command(phase, model, repo_root)
    raise ValueError(f"Unknown provider: {provider}")


def _token_count(usage: dict, name: str) -> int:
    value = usage.get(name)
    if type(value) is not int or value < 0:
        raise ValueError(f"Codex usage requires a non-negative integer {name}")
    return value


def parse_codex_result(stdout: str, phase: str, mode: str, model: Optional[str]) -> PhaseUsage:
    result = PhaseUsage(phase=phase, mode=mode, provider="codex", model=model or "(CLI default)")
    result.notes = [
        "Codex input_tokens excludes cached_input_tokens after normalization.",
        "Codex does not report cache creation separately; cache_creation is 0.",
        "Codex turns counts completed CLI turns, not internal tool steps; "
        "--max-turns is Claude-only. Use --timeout-seconds for either provider.",
    ]
    last_turn = None
    for lineno, line in enumerate(stdout.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid Codex JSONL at line {lineno}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"Codex event at line {lineno} must be an object")
        kind = event.get("type")
        if kind in ("error", "turn.failed"):
            raise ValueError(f"Codex reported {kind}; see the phase transcript")
        if kind == "turn.started":
            last_turn = "started"
        if kind != "turn.completed":
            continue
        usage = event.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("Codex completion is missing usage")
        total_input = _token_count(usage, "input_tokens")
        cached = _token_count(usage, "cached_input_tokens")
        if cached > total_input:
            raise ValueError("Codex cached input exceeds total input")
        result.input_tokens += total_input - cached
        result.cache_read += cached
        result.output_tokens += _token_count(usage, "output_tokens")
        result.turns += 1
        last_turn = "completed"
    if last_turn != "completed":
        raise ValueError("Codex stream has no final completed turn")
    return result


def parse_result(
    provider: str, stdout: str, phase: str, mode: str, model: Optional[str]
) -> PhaseUsage:
    if provider == "claude":
        return parse_usage_from_json(stdout, phase, mode)
    if provider == "codex":
        return parse_codex_result(stdout, phase, mode, model)
    raise ValueError(f"Unknown provider: {provider}")


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
        # No fallback: argparse already restricts `--phase` to PHASES, and every
        # PHASES entry must have an explicit allowlist. A silent fallback (esp.
        # one containing Bash) would let a future typo or refactor quietly
        # re-introduce Bash to a phase that consumes attacker-controlled input.
        ",".join(PHASE_TOOLS[phase]),
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
        raise ValueError("Claude returned no result")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Claude JSON result: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Claude result must be an object")
    if payload.get("is_error") or str(payload.get("subtype", "")).startswith("error"):
        raise ValueError(f"Claude phase failed: {payload.get('subtype', 'is_error')}")
    if payload.get("type") != "result" or payload.get("subtype") != "success":
        raise ValueError("Claude output is not a successful result")

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
