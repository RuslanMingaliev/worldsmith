"""Provider protocol and subprocess checks; never invoke a real model."""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_providers as providers
import orchestrator_run as runner
import compose_release_notes as notes


def completed(inputs=100, cached=60, outputs=10):
    return {"type": "turn.completed", "usage": {
        "input_tokens": inputs, "cached_input_tokens": cached, "output_tokens": outputs,
    }}


def stream(*events):
    return "\n".join(json.dumps(event) for event in events)


class ProviderProtocolTests(unittest.TestCase):
    def test_codex_normalizes_cache_without_double_counting(self):
        result = providers.parse_result("codex", stream(
            {"type": "thread.started", "thread_id": "test"},
            {"type": "turn.started"}, completed(),
            {"type": "turn.started"}, completed(50, 20, 5),
        ), "coder", "release", "chosen-model")
        self.assertEqual((result.input_tokens, result.cache_read, result.output_tokens), (70, 80, 15))
        self.assertEqual((result.provider, result.model, result.turns), ("codex", "chosen-model", 2))

    def test_codex_rejects_failures_incomplete_streams_and_invalid_accounting(self):
        for output in (
            "", "not-json", "[]", stream({"type": "turn.started"}),
            stream({"type": "turn.failed"}), stream({"type": "error"}),
            stream(completed(), {"type": "turn.started"}),
            stream(completed(), {"type": "turn.failed"}),
            stream(completed(cached=101)), stream(completed(inputs=-1)),
            stream(completed(outputs="10")), stream({"type": "turn.completed"}),
        ):
            with self.subTest(output=output), self.assertRaises(ValueError):
                providers.parse_result("codex", output, "coder", "release", None)

    def test_claude_success_and_primary_model_accounting_stay_compatible(self):
        output = json.dumps({
            "type": "result", "subtype": "success", "is_error": False,
            "num_turns": 4, "duration_ms": 1200,
            "modelUsage": {"primary": {"cacheReadInputTokens": 200}, "helper": {"outputTokens": 20}},
            "usage": {"input_tokens": 50, "output_tokens": 20, "cache_read_input_tokens": 200},
        })
        result = providers.parse_result("claude", output, "coder", "release", None)
        self.assertEqual((result.provider, result.model, result.turns), ("claude", "primary", 4))
        self.assertEqual((result.input_tokens, result.output_tokens, result.cache_read), (50, 20, 200))

    def test_claude_errors_do_not_pass_with_zero_usage(self):
        for output in ("", "[]", "{}", "invalid", json.dumps({
            "type": "result", "subtype": "error_max_turns", "is_error": True,
        })):
            with self.subTest(output=output), self.assertRaises(ValueError):
                providers.parse_result("claude", output, "coder", "release", None)

    def test_commands_preserve_provider_specific_restrictions(self):
        claude = providers.build_command("claude", "extractor", None, 12, Path("/tmp/repo"))
        self.assertNotIn("Bash", claude[claude.index("--allowedTools") + 1])
        self.assertEqual(claude[claude.index("--max-turns") + 1], "12")
        codex = providers.build_command("codex", "coder", "custom", 12, Path("/tmp/repo"))
        self.assertEqual(codex[:3], ["codex", "exec", "--json"])
        self.assertEqual(codex[codex.index("--sandbox") + 1], "workspace-write")
        self.assertEqual(codex[codex.index("--model") + 1], "custom")
        self.assertEqual(codex[-1], "-")
        self.assertNotIn("--max-turns", codex)
        self.assertNotIn("--allowedTools", codex)
        with self.assertRaisesRegex(ValueError, "no-shell"):
            providers.build_command("codex", "extractor", None, 12, Path("/tmp/repo"))

    def test_release_table_supports_historical_and_codex_records(self):
        old = notes.PhaseUsage.from_record({"phase": "coder", "model": "sonnet"})
        new = notes.PhaseUsage.from_record({"phase": "reconciler", "provider": "codex", "model": "chosen"})
        table = notes.render_tokens_table([old, new])
        self.assertIn("| coder | claude | `sonnet` |", table)
        self.assertIn("| reconciler | codex | `chosen` |", table)

    def test_only_ci_explicitly_enables_network_and_cargo_cache_writes(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "CARGO_HOME": "/tmp/cargo"}, clear=True):
            ci = providers.build_command("codex", "coder", None, 12, Path("/tmp/repo"))
        self.assertIn("sandbox_workspace_write.network_access=true", ci)
        self.assertEqual(ci[ci.index("--add-dir") + 1], "/tmp/cargo")
        with patch.dict(os.environ, {}, clear=True):
            local = providers.build_command("codex", "coder", None, 12, Path("/tmp/repo"))
        self.assertNotIn("--add-dir", local)
        self.assertNotIn("sandbox_workspace_write.network_access=true", local)

    def test_cli_override_beats_repo_default_and_uses_provider_model(self):
        with patch.dict(os.environ, {"WORLDSMITH_AGENT_PROVIDER": "claude", "WORLDSMITH_CODEX_MODEL": "codex-model"}, clear=True):
            with patch.object(sys, "argv", ["run", "--provider", "codex", "--phase", "coder", "--mode", "release"]):
                args = runner.parse_args()
        self.assertEqual((args.provider, args.model), ("codex", "codex-model"))

    def test_invalid_provider_environment_and_empty_targets_are_rejected(self):
        for env, extra in (({"WORLDSMITH_AGENT_PROVIDER": "typo"}, []), ({}, ["--target-modules"])):
            with self.subTest(env=env, extra=extra), patch.dict(os.environ, env, clear=True):
                with patch.object(sys, "argv", ["run", "--phase", "coder", "--mode", "release", *extra]):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        runner.parse_args()


FAKE_CLI = '''import json, os, pathlib, shutil, sys, time
root = pathlib.Path.cwd()
(root / "received-prompt.txt").write_text(sys.stdin.read())
mode = os.environ.get("FAKE_MODE", "success")
if mode == "timeout":
    print(json.dumps({"type": "turn.started"}), flush=True)
    time.sleep(20)
src = root / "generated/game/src"
if mode == "delete-tree":
    shutil.rmtree(src)
else:
    (src / "chosen.rs").write_text("new chosen")
    (src / "untouched.rs").write_text("out of scope")
    (src / "extra.rs").write_text("new out of scope")
if mode != "stale":
    (root / "artifacts/coder_report.md").write_text("Fresh coder report")
if mode == "bad-framing":
    (root / "artifacts/coder_report.md").write_text("carried from a pre-existing baseline")
if mode == "blocker":
    (root / "artifacts/blocker.md").write_text("Cannot implement the contract")
if pathlib.Path(sys.argv[0]).name == "claude":
    event = {"type":"result", "subtype":"success", "usage":{"input_tokens":40,"output_tokens":10}}
else:
    event = {"type":"turn.completed", "usage":{"input_tokens":100,"cached_input_tokens":60,"output_tokens":10}}
if mode == "failed":
    event = {"type":"turn.failed"}
print(json.dumps(event))
if mode == "exit-error":
    sys.exit(7)
'''


class PhaseRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / "generated/game/src"
        self.src.mkdir(parents=True)
        (self.src / "chosen.rs").write_text("old chosen")
        (self.src / "untouched.rs").write_text("keep me")
        (self.root / "artifacts").mkdir()
        agents = self.root / "tooling/agents"
        agents.mkdir(parents=True)
        (agents / "coder.md").write_text("Repair chosen and write artifacts/coder_report.md.")
        for name in ("claude", "codex"):
            cli = self.root / name
            cli.write_text(f"#!{sys.executable}\n" + FAKE_CLI)
            cli.chmod(0o755)
        for attribute, value in {
            "REPO_ROOT": self.root, "AGENTS_DIR": agents,
            "GENERATED_SRC_DIR": self.src, "DEFAULT_USAGE": self.root / "artifacts/usage.jsonl",
        }.items():
            self.enterContext(patch.object(runner, attribute, value))
        self.enterContext(patch.dict(os.environ, {"PATH": str(self.root)}, clear=True))

    def run_phase(self, provider="codex", mode="success"):
        argv = ["run", "--phase", "coder", "--provider", provider, "--mode", "release",
                "--target-modules", "chosen", "--timeout-seconds", "1"]
        with patch.object(sys, "argv", argv), patch.dict(os.environ, {"FAKE_MODE": mode}):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return runner.main()

    def assert_scope_restored(self):
        self.assertEqual((self.src / "untouched.rs").read_text(), "keep me")
        self.assertFalse((self.src / "extra.rs").exists())

    def test_codex_subprocess_saves_usage_and_restores_out_of_scope_files(self):
        self.assertEqual(self.run_phase(), 0)
        self.assert_scope_restored()
        self.assertEqual((self.src / "chosen.rs").read_text(), "new chosen")
        usage = json.loads((self.root / "artifacts/usage.jsonl").read_text())
        self.assertEqual((usage["provider"], usage["input_tokens"], usage["cache_read"]), ("codex", 40, 60))
        self.assertTrue((self.root / "artifacts/coder.codex.jsonl").exists())
        self.assertIn("Codex runtime", (self.root / "received-prompt.txt").read_text())

    def test_codex_ci_uses_managed_session_without_an_api_key(self):
        auth = json.dumps({'auth_mode': 'chatgpt', 'tokens': {
            'access_token': 'dummy-access', 'refresh_token': 'dummy-refresh',
            'id_token': 'dummy-id', 'account_id': 'dummy-account',
        }})
        home = self.root / 'session'
        home.mkdir()
        for name in ('auth.json', 'initial-auth.json'):
            (home / name).write_text(auth)
        event = self.root / 'event.json'
        event.write_text('{}')
        with patch.dict(os.environ, {
            'GITHUB_ACTIONS': 'true', 'WORLDSMITH_CODEX_AUTH': 'chatgpt',
            'CODEX_HOME': str(home), 'GITHUB_REPOSITORY': 'alice/game',
            'GITHUB_ACTOR': 'alice', 'GITHUB_TRIGGERING_ACTOR': 'alice',
            'GITHUB_EVENT_PATH': str(event),
        }):
            self.assertEqual(self.run_phase(), 0)
        self.assert_scope_restored()

    def test_claude_subprocess_keeps_the_same_output_guard(self):
        self.assertEqual(self.run_phase(provider="claude"), 0)
        self.assert_scope_restored()

    def test_failed_codex_turn_restores_scope_and_keeps_failure_transcript(self):
        with self.assertRaises(SystemExit):
            self.run_phase(mode="failed")
        self.assert_scope_restored()
        self.assertIn("turn.failed", (self.root / "artifacts/coder.codex.jsonl").read_text())

    def test_nonzero_exit_is_not_success_even_with_completion_event(self):
        with self.assertRaisesRegex(SystemExit, "exited 7"):
            self.run_phase(mode="exit-error")
        self.assert_scope_restored()

    def test_timeout_preserves_partial_transcript(self):
        with self.assertRaisesRegex(SystemExit, "exceeded 1s"):
            self.run_phase(mode="timeout")
        self.assert_scope_restored()
        self.assertIn("turn.started", (self.root / "artifacts/coder.codex.jsonl").read_text())

    def test_deleted_source_tree_does_not_disable_scope_guard(self):
        self.assertEqual(self.run_phase(mode="delete-tree"), 0)
        self.assert_scope_restored()

    def test_unchanged_unselected_files_are_not_reported_as_reverted(self):
        baseline = runner._snapshot_src(self.src)
        (self.src / "chosen.rs").write_text("allowed edit")
        self.assertEqual(runner._revert_out_of_scope(self.src, baseline, ["chosen"]), [])

    def test_stale_report_and_new_blocker_fail_the_phase(self):
        (self.root / "artifacts/coder_report.md").write_text("Old report")
        self.assertEqual(self.run_phase(mode="stale"), 1)
        self.assertEqual(self.run_phase(mode="blocker"), 1)

    def test_existing_token_cap_applies_to_codex(self):
        with patch.dict(os.environ, {"WORLDSMITH_MAX_TOKENS_PER_RUN": "49"}):
            self.assertEqual(self.run_phase(), 1)

    def test_upstream_report_content_gate_applies_to_both_providers(self):
        for provider in providers.PROVIDERS:
            with self.subTest(provider=provider):
                self.assertEqual(self.run_phase(provider=provider, mode="bad-framing"), 1)

    def test_codex_ci_requires_its_own_credential(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "CLAUDE_CODE_OAUTH_TOKEN": "fake"}):
            with self.assertRaisesRegex(SystemExit, "CODEX_API_KEY"):
                self.run_phase()


if __name__ == "__main__":
    unittest.main()
