"""Session lifecycle checks use dummy strings; no actual login or network."""
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
import codex_session as session


def auth(refresh='old-refresh-test-value', account='dummy-account-value'):
    return json.dumps({'auth_mode': 'chatgpt', 'tokens': {
        'access_token': 'dummy-access-test-value', 'refresh_token': refresh,
        'id_token': 'dummy-id-test-value', 'account_id': account,
    }})


class OwnerTests(unittest.TestCase):
    def test_only_owner_can_start_or_rerun(self):
        self.assertTrue(session.owner_event('alice/game', 'alice', 'alice', {}))
        for actor, triggering in [('bob', 'alice'), ('alice', 'bob'), ('bob', 'bob')]:
            self.assertFalse(session.owner_event('alice/game', actor, triggering, {}))

    def test_forks_and_foreign_authored_inputs_do_not_receive_session(self):
        event = {'pull_request': {'user': {'login': 'alice'}, 'head': {'repo': {'full_name': 'alice/game'}}}}
        self.assertTrue(session.owner_event('alice/game', 'alice', 'alice', event))
        event['pull_request']['head']['repo']['full_name'] = 'bob/game'
        self.assertFalse(session.owner_event('alice/game', 'alice', 'alice', event))
        event = {'issue': {'user': {'login': 'bob'}}}
        self.assertFalse(session.owner_event('alice/game', 'alice', 'alice', event))

    def test_fork_owner_can_use_their_own_repository_session(self):
        self.assertTrue(session.owner_event('bob/game', 'bob', 'bob', {}))


class SessionTests(unittest.TestCase):
    def test_external_host_auth_and_incomplete_sessions_rejected(self):
        for raw in ('{}', 'not json', '[]', '{"auth_mode":"chatgptAuthTokens"}',
                    '{"auth_mode":"chatgpt","tokens":{}}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                session.validate(raw)

    def test_validation_does_not_echo_invalid_json(self):
        with self.assertRaises(ValueError) as error:
            session.validate('private-token-that-must-not-appear')
        self.assertNotIn('private-token', str(error.exception))

    def test_links_are_not_accepted_as_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'auth').write_text(auth())
            (root / 'symlink').symlink_to(root / 'auth')
            with self.assertRaises(OSError):
                session.read_auth(root / 'symlink')
            os.link(root / 'auth', root / 'hardlink')
            with self.assertRaises(ValueError):
                session.read_auth(root / 'hardlink')

    def test_redacts_old_and_refreshed_tokens_in_transcript(self):
        old, new = auth(), auth('fresh-refresh-test-value')
        text = 'old-refresh-test-value and fresh-refresh-test-value'
        self.assertEqual(session.redact(text, old, new), '[REDACTED] and [REDACTED]')

    def test_failed_write_probe_never_creates_local_auth(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {'RUNNER_TEMP': temp, 'CODEX_AUTH_JSON': auth()}), \
                 patch.object(session, 'require_owner', return_value='alice/game'), \
                 patch.object(session, 'secret_set', side_effect=ValueError('denied')), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    session.restore()
            self.assertFalse((Path(temp) / 'worldsmith-codex-session').exists())

    def test_save_persists_new_value_then_removes_local_session(self):
        for storage_failure in (False, True):
            with self.subTest(storage_failure=storage_failure), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                directory = root / 'worldsmith-codex-session'
                directory.mkdir()
                (directory / 'initial-auth.json').write_text(auth())
                fresh = auth('fresh-refresh-test-value')
                (directory / 'auth.json').write_text(fresh)
                with patch.dict(os.environ, {'RUNNER_TEMP': temp, 'CODEX_HOME': str(directory), 'GITHUB_WORKSPACE': temp}), \
                     patch.object(session, 'require_owner', return_value='alice/game'), \
                     patch.object(session, 'secret_set', side_effect=ValueError('denied') if storage_failure else None) as put, \
                     contextlib.redirect_stdout(io.StringIO()):
                    if storage_failure:
                        with self.assertRaises(ValueError):
                            session.save()
                    else:
                        session.save()
                    put.assert_called_once_with('alice/game', fresh)
                self.assertFalse(directory.exists())

    def test_detected_token_blocks_export_but_still_saves_refreshed_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / 'worldsmith-codex-session'
            directory.mkdir()
            fresh = auth('fresh-refresh-test-value')
            (directory / 'auth.json').write_text(fresh)
            (directory / 'initial-auth.json').write_text(auth())
            (root / 'artifacts').mkdir()
            (root / 'artifacts/leak.txt').write_text('fresh-refresh-test-value')
            with patch.dict(os.environ, {'RUNNER_TEMP': temp, 'CODEX_HOME': str(directory), 'GITHUB_WORKSPACE': temp}), \
                 patch.object(session, 'require_owner', return_value='alice/game'), \
                 patch.object(session, 'secret_set') as put, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'Credential detected'):
                    session.save()
                put.assert_called_once_with('alice/game', fresh)
            self.assertFalse(directory.exists())


if __name__ == '__main__':
    unittest.main()
