"""Unit tests for Milestone 14 System Preferences & UI Architecture Reorganization."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knobu.modules.system_prefs import (
    add_startup_app,
    discover_sound_themes,
    discover_themes,
    list_startup_apps,
    parse_xrandr_monitors,
    remove_startup_app,
    set_startup_app_enabled,
)

SAMPLE_XRANDR = """\
Screen 0: minimum 320 x 200, current 1920 x 1080, maximum 16384 x 16384
eDP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 309mm x 174mm
   1920x1080     60.00*+  48.00
   1280x720      60.00
HDMI-1 disconnected (normal left inverted right x axis y axis)
"""


class TestSystemPrefs(unittest.TestCase):
    def test_startup_apps_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            u_dir = d / "user_autostart"
            s_dir = d / "sys_autostart"
            s_dir.mkdir()
            (s_dir / "sys-tool.desktop").write_text(
                "[Desktop Entry]\nName=System Tool\nExec=/usr/bin/sys-tool\nX-GNOME-Autostart-enabled=true\n"
            )

            apps = list_startup_apps(user_dir=u_dir, system_dirs=[s_dir])
            self.assertEqual(len(apps), 1)
            self.assertTrue(apps[0].enabled)

            ok, _ = set_startup_app_enabled("sys-tool.desktop", False, user_dir=u_dir, system_dirs=[s_dir])
            self.assertTrue(ok)
            apps2 = list_startup_apps(user_dir=u_dir, system_dirs=[s_dir])
            self.assertFalse(apps2[0].enabled)

            ok_add, _ = add_startup_app("Docker Helper", "/usr/bin/dockerd", user_dir=u_dir)
            self.assertTrue(ok_add)
            self.assertTrue((u_dir / "knobu-docker-helper.desktop").is_file())

            ok_rm, _ = remove_startup_app("knobu-docker-helper.desktop", user_dir=u_dir)
            self.assertTrue(ok_rm)

    def test_theme_and_sound_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "icons" / "Bibata-Cursor" / "cursors").mkdir(parents=True)
            (root / "icons" / "Papirus" / "apps").mkdir(parents=True)
            (root / "icons" / "Papirus" / "index.theme").write_text("[Icon Theme]\n")
            (root / "themes" / "Tokyonight" / "gtk-3.0").mkdir(parents=True)
            (root / "sounds" / "Ocean" / "stereo").mkdir(parents=True)

            self.assertEqual(discover_themes("cursor", [root / "icons"]), ["Bibata-Cursor"])
            self.assertEqual(discover_themes("icon", [root / "icons"]), ["Papirus"])
            self.assertEqual(discover_themes("gtk", [root / "themes"]), ["Tokyonight"])
            self.assertEqual(discover_sound_themes([root / "sounds"]), ["Ocean"])

    def test_xrandr_monitor_parser(self):
        mons = parse_xrandr_monitors(SAMPLE_XRANDR)
        self.assertEqual(len(mons), 1)
        self.assertEqual(mons[0].connector, "eDP-1")
        self.assertTrue(mons[0].is_primary)
        self.assertEqual(mons[0].current_mode, "1920x1080@60.000")
        self.assertEqual(len(mons[0].modes), 3)

    def test_reorganized_ui_pages_build(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gdk, Gtk
        Gtk.init()
        if Gdk.Display.get_default() is None:
            self.skipTest("Headless environment: no display server available")
        Adw.init()
        from knobu.ui.pages import PAGES, devops_page, general_page, powertools_page
        from knobu.ui.system_pages import preferences_page, systools_page
        from knobu.ui.store import SettingsStore

        store = SettingsStore()
        self.assertIn("systools", [p[0] for p in PAGES])
        self.assertIn("preferences", [p[0] for p in PAGES])
        for fn in (devops_page, powertools_page, systools_page, preferences_page, general_page):
            self.assertIsNotNone(fn(store, lambda _x: None))


if __name__ == "__main__":
    unittest.main()
