"""Unit tests for Milestone 13 GitHub Gist cloud backup & sync."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knobu import config
from knobu.modules.cloud_backup import (
    BACKUP_FILENAME,
    CloudSyncConfig,
    apply_backup_bundle,
    build_backup_bundle,
    load_sync_config,
    pull_from_gist,
    push_to_gist,
    save_sync_config,
    verify_github_token,
)


class _FakeResponse:
    def __init__(self, code: int, body: dict):
        self._code = code
        self._raw = json.dumps(body).encode("utf-8")

    def getcode(self) -> int:
        return self._code

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class TestCloudBackup(unittest.TestCase):
    def test_sync_config_isolation_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sync_p = d / "cloud_sync.json"
            cfg_p = d / "config.toml"
            config.save({"general": {"bypass": False}, "awake": {"enabled": True}}, cfg_p)
            save_sync_config(CloudSyncConfig(
                github_token="ghp_secret_token_123",
                github_user="tester",
                gist_id="abc123",
                auto_sync_on_change=True,
                sync_interval_minutes=15,
            ), sync_p)

            mode = os.stat(sync_p).st_mode & 0o777
            self.assertEqual(mode, 0o600)
            loaded = load_sync_config(sync_p)
            self.assertEqual(loaded.github_token, "ghp_secret_token_123")
            self.assertEqual(loaded.sync_interval_minutes, 15)

            # Verify token never leaks into uploaded backup bundle
            bundle = build_backup_bundle(d)
            raw_bundle = json.dumps(bundle)
            self.assertNotIn("ghp_secret_token_123", raw_bundle)
            self.assertEqual(bundle["config"]["awake"]["enabled"], True)

    def test_push_pull_and_verify_github_mocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            sync_p = d / "cloud_sync.json"
            config.save({"powertools": {"cleaning_duration": 45}}, d / "config.toml")
            (d / "automations.json").write_text(json.dumps([{"id": "a1", "name": "Demo"}]))

            with patch("urllib.request.urlopen", return_value=_FakeResponse(200, {"login": "surya"})):
                ok, msg = verify_github_token("ghp_test")
                self.assertTrue(ok)
                self.assertIn("@surya", msg)

            with patch("urllib.request.urlopen", return_value=_FakeResponse(
                201, {"id": "gist999", "owner": {"login": "surya"}}
            )):
                ok, gid, _ = push_to_gist(token="ghp_test", sync_path=sync_p, cfg_dir=d)
                self.assertTrue(ok)
                self.assertEqual(gid, "gist999")

            # Clear local config & pull back
            config.save({}, d / "config.toml")
            bundle_payload = build_backup_bundle(d)
            bundle_payload["config"] = {"powertools": {"cleaning_duration": 90}}
            with patch("urllib.request.urlopen", return_value=_FakeResponse(
                200, {"id": "gist999", "files": {BACKUP_FILENAME: {"content": json.dumps(bundle_payload)}}}
            )):
                ok2, restored, _ = pull_from_gist(
                    token="ghp_test", gist_id="gist999", sync_path=sync_p, cfg_dir=d, reload_service=False
                )
                self.assertTrue(ok2)
                self.assertEqual(restored["powertools"]["cleaning_duration"], 90)
                self.assertEqual(config.load(d / "config.toml")["powertools"]["cleaning_duration"], 90)


if __name__ == "__main__":
    unittest.main()
