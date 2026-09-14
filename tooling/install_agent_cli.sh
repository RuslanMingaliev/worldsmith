#!/usr/bin/env bash
# GitHub-hosted Linux runner setup. agent-intake also needs Claude for Extractor.
set -euo pipefail

provider=${WORLDSMITH_AGENT_PROVIDER:-claude}
case "$provider" in
  claude|codex) ;;
  *) echo "Unsupported WORLDSMITH_AGENT_PROVIDER: $provider" >&2; exit 2 ;;
esac

if [[ "$provider" == claude || "${1:-}" == --include-extractor ]]; then
  sudo npm install -g @anthropic-ai/claude-code
  claude --version
fi
if [[ "$provider" == codex ]]; then
  mkdir -p "${CARGO_HOME:-$HOME/.cargo}"
  sudo npm install -g "@openai/codex@${WORLDSMITH_CODEX_CLI_VERSION:-0.153.4}"
  codex --version
fi
