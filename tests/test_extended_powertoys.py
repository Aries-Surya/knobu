"""Unit tests for Milestone 12 Extended Microsoft PowerToys for Linux."""

import datetime
import tempfile
import unittest
from pathlib import Path

from knobu.modules.clipboard.transforms import transform_text
from knobu.modules.powertools.theme import scheduled_theme_for_time
from knobu.modules.powertools.workspaces import WorkspaceGroup, load_workspaces, save_workspaces
from knobu.ui.shortcut_guide import collect_shortcuts


class TestExtendedPowerToys(unittest.TestCase):
    def test_advanced_paste_transforms(self):
        ok, js = transform_text('{"a":1,"b":2}', "json_pretty")
        self.assertTrue(ok)
        self.assertIn('\n  "a": 1', js)

        ok, b64 = transform_text("knobu", "base64_encode")
        self.assertTrue(ok)
        self.assertEqual(b64, "a25vYnU=")
        ok, dec = transform_text(b64, "base64_decode")
        self.assertTrue(ok)
        self.assertEqual(dec, "knobu")

        ok, url = transform_text("hello%20world%21", "url_decode")
        self.assertTrue(ok)
        self.assertEqual(url, "hello world!")

        self.assertEqual(transform_text("HelloWorldTest", "snake_case"), (True, "hello_world_test"))
        self.assertEqual(transform_text("hello_world_test", "camel_case"), (True, "helloWorldTest"))
        self.assertEqual(transform_text("<b>hi</b>  there", "plain"), (True, "hi there"))

    def test_light_switch_schedule(self):
        self.assertEqual(scheduled_theme_for_time(datetime.time(12, 0), "07:00", "19:00"), "light")
        self.assertEqual(scheduled_theme_for_time(datetime.time(22, 0), "07:00", "19:00"), "dark")
        self.assertEqual(scheduled_theme_for_time(datetime.time(5, 30), "07:00", "19:00"), "dark")

    def test_workspaces_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ws.json"
            save_workspaces([WorkspaceGroup("Dev Ops", ["code", "gnome-terminal"])], p)
            loaded = load_workspaces(p)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].name, "Dev Ops")
            self.assertEqual(loaded[0].commands, ["code", "gnome-terminal"])

    def test_shortcut_guide_collects_shortcuts(self):
        rows = collect_shortcuts()
        self.assertTrue(len(rows) > 0)
        self.assertTrue(any(cat == "Knobu" for cat, _t, _c in rows))


if __name__ == "__main__":
    unittest.main()
