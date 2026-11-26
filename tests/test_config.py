import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knobu import config


class ConfigTests(unittest.TestCase):
    def test_round_trip(self):
        data = {"touchpad": {"enabled": False, "fingers": 4, "percent_per_cm": 12.5,
                             "device": 'path "quoted"'}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "knobu" / "config.toml"
            config.save(data, path)
            self.assertEqual(config.load(path), data)

    def test_missing_file_is_empty(self):
        self.assertEqual(config.load(Path("/nonexistent/knobu.toml")), {})

    def test_defaults_fill_missing_keys(self):
        merged = config.module_settings({"touchpad": {"fingers": 4}}, "touchpad",
                                        {"fingers": 3, "enabled": True})
        self.assertEqual(merged, {"fingers": 4, "enabled": True})

    def test_json_backup_and_restore(self):
        sample = {
            "touchpad": {"enabled": True, "swipe3_up": "volume_up"},
            "awake": {"enabled": True, "mode": "indefinite"},
            "general": {"bypass": False},
        }
        with tempfile.TemporaryDirectory() as d:
            cfg_path = Path(d) / "config.toml"
            backup_path = Path(d) / "backup.json"
            config.save(sample, cfg_path)

            # Test backup export
            with patch("knobu.config.config_path", return_value=cfg_path):
                out = config.export_json(backup_path)
                self.assertEqual(out, backup_path)
                self.assertTrue(backup_path.exists())

                # Clear config
                config.save({}, cfg_path)
                self.assertEqual(config.load(cfg_path), {})

                # Test restore import
                restored = config.import_json(backup_path)
                self.assertEqual(restored, sample)
                self.assertEqual(config.load(cfg_path), sample)


if __name__ == "__main__":
    unittest.main()
