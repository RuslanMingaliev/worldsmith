#!/usr/bin/env python3
"""
Hygiene pass on the issue-derived scope file before it is forwarded to LLM
phases (Extractor, Architect) by `.github/workflows/agent-intake.yml`.

This is *not* a security boundary. The real injection mitigation is the
removal of `Bash` from Extractor's tool allowlist (see PHASE_TOOLS in
`tooling/orchestrator_run.py`). This helper only:

  1. Truncates the file to 4096 bytes (UTF-8 safe at the byte boundary)
     to bound prompt size.
  2. Replaces ` with ' and ~~~ with --- so issue-supplied content is
     less likely to be parsed as markdown structure (fenced blocks,
     inline code) by the downstream agent. The prompt template does not
     wrap scope in a fence, so this is a hygiene step, not a structural
     escape — adversarial heading-level content (e.g. `## Override`) is
     not addressed and is the reason this is not a security boundary.

Pure stdlib.

Usage:

    python3 tooling/sanitize_scope.py artifacts/issue_scope.md

Exit codes:
    0 — file rewritten in place (or no change needed).
    2 — usage error / file not found.
"""

from __future__ import annotations

import sys
from pathlib import Path

MAX_BYTES = 4096


def sanitize_text(text: str) -> str:
    """Replace fence-introducing characters with safe surrogates.

    `__WS_EOS__` is the heredoc-style delimiter the agent-intake workflow
    uses to push the scope into `$GITHUB_OUTPUT` (see
    `.github/workflows/agent-intake.yml`). An attacker-controlled issue
    body containing that literal would terminate the multi-line output
    early and let subsequent lines be parsed as additional step outputs;
    neutralize it here.
    """
    text = text.replace("`", "'")
    text = text.replace("~~~", "---")
    text = text.replace("__WS_EOS__", "__ws_eos_safe__")
    return text


def truncate_bytes(text: str, max_bytes: int) -> str:
    """Cap a string at `max_bytes` UTF-8 bytes without splitting a codepoint."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def sanitize_path(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    cleaned = truncate_bytes(sanitize_text(raw), MAX_BYTES)
    # The agent-intake workflow appends `cat <this file>` between two `echo`
    # lines into a `$GITHUB_OUTPUT` heredoc. If the file does not end in `\n`,
    # `cat` emits its content with no trailing newline and the next `echo`'s
    # closing `__WS_EOS__` is concatenated onto the last content line — the
    # delimiter is no longer on its own line and the heredoc never closes.
    # Truncation makes this reachable for any body whose first 4096 bytes
    # don't end at a line boundary, so guarantee a trailing newline here.
    if not cleaned.endswith("\n"):
        cleaned += "\n"
    if cleaned != raw:
        path.write_text(cleaned, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python3 tooling/sanitize_scope.py <path>", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    sanitize_path(path)


if __name__ == "__main__":
    main()
