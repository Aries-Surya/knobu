"""Hardcore unit & geometry tests for Milestone 5: FancyZones & Always on Top."""

import unittest
from unittest.mock import MagicMock, patch

from knobu.modules.windows.zones import (
    compute_zones,
    maximize_active_window,
    snap_active_window,
    toggle_always_on_top,
)


class TestWindowManagement(unittest.TestCase):
    def test_compute_zones_2col_and_gap(self):
        zones = compute_zones("2col", 1920, 1080, gap=10)
        self.assertEqual(len(zones), 2)
        self.assertEqual(zones[0].x, 10)
        self.assertEqual(zones[0].y, 10)
        self.assertEqual(zones[0].height, 1060)
        self.assertEqual(zones[0].width + zones[1].width + 30, 1920)

    def test_compute_zones_3col_2x2_priority_left_main(self):
        self.assertEqual(len(compute_zones("3col", 1920, 1080, gap=8)), 3)
        z2x2 = compute_zones("2x2", 1920, 1080, gap=8)
        self.assertEqual(len(z2x2), 4)
        self.assertEqual(z2x2[3].x, z2x2[1].x)
        self.assertEqual(z2x2[3].y, z2x2[2].y)

        prio = compute_zones("priority", 1920, 1080, gap=8)
        self.assertEqual(len(prio), 3)
        self.assertGreater(prio[1].width, prio[0].width)

        lm = compute_zones("left_main", 1920, 1080, gap=8)
        self.assertEqual(len(lm), 3)
        self.assertGreater(lm[0].width, lm[1].width)

    def test_always_on_top_excluded_and_wmctrl(self):
        with patch("knobu.modules.windows.zones._active_wmctrl_title", return_value="Spotify Premium"):
            ok, msg = toggle_always_on_top(excluded_apps=["spotify"])
            self.assertFalse(ok)
            self.assertIn("excluded", msg.lower())

        with patch("knobu.modules.windows.zones._active_wmctrl_title", return_value="Terminal"), \
             patch("shutil.which", side_effect=lambda c: "/usr/bin/wmctrl" if c == "wmctrl" else None), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            ok, msg = toggle_always_on_top()
            self.assertTrue(ok)
            mock_run.assert_called_with(
                ["wmctrl", "-r", ":ACTIVE:", "-b", "toggle,above"],
                capture_output=True, text=True, timeout=2, check=False,
            )

    def test_snap_and_maximize_wmctrl(self):
        with patch("knobu.modules.windows.zones._primary_screen_size", return_value=(1920, 1080)), \
             patch("shutil.which", return_value="/usr/bin/wmctrl"), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            ok, msg = snap_active_window(1, "2col", gap=8)
            self.assertTrue(ok)
            self.assertIn("Zone 2", msg)
            self.assertTrue(any("-e" in call.args[0] for call in mock_run.call_args_list))

            ok2, _ = maximize_active_window()
            self.assertTrue(ok2)

    def test_ui_windows_page_builds(self):
        import gi
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        Adw.init()
        from knobu.ui.pages import windows_page
        from knobu.ui.store import SettingsStore
        w = windows_page(SettingsStore(), lambda _x: None)
        self.assertIsNotNone(w)


if __name__ == "__main__":
    unittest.main()
