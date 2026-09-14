"""Owner-operated ChatGPT session storage for GitHub-hosted runners.

Environment secrets are read when a job starts. All consumers must use the same
workflow concurrency group, and save the refreshed session before releasing it.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

ENVIRONMENT = "agent-ci"
SECRET = "CODEX_AUTH_JSON"


def validate(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("Invalid Codex session JSON") from None
    if not isinstance(data, dict) or data.get("auth_mode") != "chatgpt":
        raise ValueError("Use a separate managed ChatGPT login for CI")
    tokens = data.get("tokens")
    if not isinstance(tokens, dict) or not all(
        isinstance(tokens.get(k), str) and tokens[k].strip()
        for k in ("access_token", "refresh_token", "id_token", "account_id")
    ) or len(raw.encode()) > 32768 or data.get("OPENAI_API_KEY"):
        raise ValueError("Incomplete or oversized managed Codex session")
    return data


def read_auth(path: Path) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Session must be a regular file with one link")
        raw = handle.read(32769)
    validate(raw)
    return raw


def owner_event(repo: str, actor: str, triggering_actor: str, event: dict) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        return False
    owner = repo.split('/')[0]
    if actor != owner or triggering_actor != owner:
        return False
    if 'pull_request' in event:
        pr = event['pull_request']
        return (pr.get('user', {}).get('login') == owner
                and pr.get('head', {}).get('repo', {}).get('full_name') == repo)
    if 'issue' in event:
        return event['issue'].get('user', {}).get('login') == owner
    return True


def require_owner() -> str:
    repo = os.environ['GITHUB_REPOSITORY']
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    if not owner_event(repo, os.environ['GITHUB_ACTOR'],
                       os.environ['GITHUB_TRIGGERING_ACTOR'], event):
        raise ValueError("Codex session is limited to owner-operated trusted jobs")
    return repo


def mask(raw: str) -> None:
    values = [raw, *validate(raw)['tokens'].values()]
    for value in values:
        if isinstance(value, str) and value:
            escaped = value.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print(f'::add-mask::{escaped}')


def secret_set(repo: str, raw: str) -> None:
    if not os.environ.get('GH_TOKEN'):
        raise ValueError("CODEX_SESSION_WRITER_TOKEN is required for session persistence")
    result = subprocess.run(
        ['gh', 'secret', 'set', SECRET, '--repo', repo, '--env', ENVIRONMENT],
        input=raw, text=True, capture_output=True,
    )
    if result.returncode:
        raise ValueError("Cannot save Codex session: check writer token Environments permission and expiry")


def restore() -> None:
    repo = require_owner()
    raw = os.environ.get(SECRET, '')
    validate(raw)
    mask(raw)
    # Probe write permission before consuming a potentially rotating credential.
    secret_set(repo, raw)
    directory = Path(os.environ['RUNNER_TEMP']) / 'worldsmith-codex-session'
    directory.mkdir(mode=0o700, exist_ok=False)
    for name in ('auth.json', 'initial-auth.json'):
        fd = os.open(directory / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(raw)
    (directory / 'config.toml').write_text('cli_auth_credentials_store = "file"\n')
    with open(os.environ['GITHUB_ENV'], 'a') as handle:
        print(f'CODEX_HOME={directory}', file=handle)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as handle:
        print('ready=true', file=handle)


def redact(text: str, *sessions: str) -> str:
    for raw in sessions:
        for value in validate(raw)['tokens'].values():
            if isinstance(value, str) and value:
                for form in (value, json.dumps(value)[1:-1], base64.b64encode(value.encode()).decode()):
                    text = text.replace(form, '[REDACTED]')
    return text


def check_exports(root: Path, *sessions: str) -> None:
    # Defense in depth for known values. This does not prove arbitrary generated
    # code safe or detect deliberately obfuscated exfiltration.
    for name in ('artifacts', 'generated', 'work', 'specs', 'knowledge', 'ir'):
        directory = root / name
        if directory.is_symlink():
            raise ValueError("Refusing linked export directory")
        if not directory.exists():
            continue
        for path in directory.rglob('*'):
            if 'target' in path.relative_to(directory).parts:
                continue
            if path.is_symlink():
                raise ValueError("Refusing linked output after a session-backed run")
            if not path.is_file():
                continue
            # Large binaries are generated only after the session is removed.
            if path.stat().st_size > 20_000_000:
                raise ValueError("Oversized output requires review before publishing")
            data = path.read_bytes()
            text = data.decode('utf-8', errors='surrogateescape')
            if redact(text, *sessions) != text:
                raise ValueError("Credential detected in generated output; publication stopped")


def save() -> None:
    directory = Path(os.environ['CODEX_HOME'])
    try:
        repo = require_owner()
        current = read_auth(directory / 'auth.json')
        initial = read_auth(directory / 'initial-auth.json')
        mask(current)
        if validate(current)['tokens']['account_id'] != validate(initial)['tokens']['account_id']:
            raise ValueError("Refusing to replace the session with a different account")
        secret_set(repo, current)
        check_exports(Path(os.environ['GITHUB_WORKSPACE']), initial, current)
    finally:
        # Never rescue a failed refresh into a public artifact. Re-login if a
        # runner dies after rotation or the final secret write fails.
        expected = Path(os.environ['RUNNER_TEMP']) / 'worldsmith-codex-session'
        if directory == expected and not directory.is_symlink():
            shutil.rmtree(directory, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('restore', 'save', 'validate'))
    parser.add_argument('path', nargs='?')
    args = parser.parse_args()
    try:
        if args.command == 'restore':
            restore()
        elif args.command == 'save':
            save()
        else:
            read_auth(Path(args.path))
    except (OSError, KeyError, ValueError, TypeError) as exc:
        if isinstance(exc, (OSError, KeyError, json.JSONDecodeError)):
            raise SystemExit('Codex session operation failed: missing input or inaccessible file') from None
        raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()
