import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
