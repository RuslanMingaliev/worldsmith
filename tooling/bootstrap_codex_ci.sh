#!/usr/bin/env bash
# Creates a dedicated CI login; never copies the user's normal auth.json.
set -euo pipefail
set +x
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
owner=${repo%%/*}
test "$(gh api user --jq .login)" = "$owner" || { echo 'Only the repository owner may bootstrap CI' >&2; exit 1; }
echo "Target: $repo, environment: agent-ci"
echo 'Finish or cancel session-consuming workflows before replacing a CI session.'
umask 077
session_dir=$(mktemp -d "${TMPDIR:-/tmp}/worldsmith-codex-ci.XXXXXXXX")
trap 'rm -rf -- "$session_dir"' EXIT
printf 'cli_auth_credentials_store = "file"\n' > "$session_dir/config.toml"
env -u OPENAI_API_KEY -u CODEX_API_KEY CODEX_HOME="$session_dir" codex login
python3 "$script_dir/codex_session.py" validate "$session_dir/auth.json"
gh secret set CODEX_AUTH_JSON --repo "$repo" --env agent-ci < "$session_dir/auth.json"
echo 'Dedicated session saved directly to the agent-ci environment secret.'
