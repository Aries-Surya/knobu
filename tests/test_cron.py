"""Unit tests for local cron job inspection & DevOps on Cloud page."""

import unittest
from unittest.mock import MagicMock, patch

from knobu.modules.powertools.cron import is_valid_schedule, parse_crontab


class TestCronManager(unittest.TestCase):
    def test_parse_crontab_active_and_disabled(self):
        raw = (
            "# Workstation State Daily Backup\n"
            "0 12 * * * /bin/bash /tmp/linuxBackup.sh\n"
            "#DISABLED# @hourly /usr/bin/echo hello\n"
        )
        jobs = parse_crontab(raw)
        self.assertEqual(len(jobs), 2)
        self.assertTrue(jobs[0].enabled)
        self.assertEqual(jobs[0].schedule, "0 12 * * *")
        self.assertEqual(jobs[0].comment, "Workstation State Daily Backup")
        self.assertFalse(jobs[1].enabled)
        self.assertEqual(jobs[1].schedule, "@hourly")

    def test_schedule_validation(self):
        self.assertTrue(is_valid_schedule("0 12 * * *"))
        self.assertTrue(is_valid_schedule("@daily"))
        self.assertFalse(is_valid_schedule("0 12 *"))
        self.assertFalse(is_valid_schedule(""))

    def test_ui_devops_page_builds(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gdk, Gtk
        Gtk.init()
        if Gdk.Display.get_default() is None:
            self.skipTest("Headless environment: no display server available")
        Adw.init()
        from knobu.ui.pages import devops_page
        from knobu.ui.store import SettingsStore
        w = devops_page(SettingsStore(), lambda _x: None)
        self.assertIsNotNone(w)


if __name__ == "__main__":
    unittest.main()
