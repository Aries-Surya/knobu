"""Unit tests for Milestone 11 Rule-Based Automation Engine."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knobu.modules.automation.engine import (
    AutomationAction,
    AutomationRule,
    SystemSnapshot,
    check_condition,
    evaluate_rule_trigger,
    load_history,
    load_rules,
    run_rule_now,
    save_rules,
)


class TestAutomationEngine(unittest.TestCase):
    def test_rules_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "automations.json"
            rule = AutomationRule(
                id="r1",
                name="Office WiFi",
                enabled=True,
                trigger_type="wifi_ssid",
                trigger_value="Office-5G",
                condition_type="always",
                actions=[AutomationAction(type="set_theme", value="light")],
            )
            save_rules([rule], p)
            loaded = load_rules(p)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].name, "Office WiFi")
            self.assertEqual(loaded[0].actions[0].type, "set_theme")

    def test_trigger_transitions_and_conditions(self):
        rule_wifi = AutomationRule(
            id="w1", name="Work", trigger_type="wifi_ssid", trigger_value="Office",
            condition_type="on_ac",
        )
        prev = SystemSnapshot(wifi_ssid="Home", ac_online=True)
        cur = SystemSnapshot(wifi_ssid="Office", ac_online=True)
        self.assertTrue(evaluate_rule_trigger(rule_wifi, prev, cur))
        self.assertFalse(evaluate_rule_trigger(rule_wifi, cur, cur))  # edge-triggered only
        self.assertTrue(check_condition(rule_wifi, cur))
        self.assertFalse(check_condition(rule_wifi, SystemSnapshot(wifi_ssid="Office", ac_online=False)))

        rule_bat = AutomationRule(id="b1", name="Low", trigger_type="battery_below", trigger_value="20")
        self.assertTrue(evaluate_rule_trigger(
            rule_bat, SystemSnapshot(battery_percent=22), SystemSnapshot(battery_percent=18)
        ))
        self.assertFalse(evaluate_rule_trigger(
            rule_bat, SystemSnapshot(battery_percent=18), SystemSnapshot(battery_percent=15)
        ))

    def test_run_rule_now_logs_history(self):
        with tempfile.TemporaryDirectory() as d:
            hp = Path(d) / "hist.json"
            rule = AutomationRule(
                id="n1", name="Notify Test", trigger_type="time_of_day", trigger_value="10:00",
                actions=[AutomationAction(type="notify", value="Hello!")],
            )
            with patch("knobu.system.notify.notify") as mock_notify:
                ok, msg = run_rule_now(rule, hist_path=hp)
                self.assertTrue(ok)
                self.assertIn("notified", msg)
                mock_notify.assert_called_once()
            hist = load_history(hp)
            self.assertEqual(len(hist), 1)
            self.assertEqual(hist[0].rule_name, "Notify Test")

    def test_ui_automation_page_builds(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gdk, Gtk
        Gtk.init()
        if Gdk.Display.get_default() is None:
            self.skipTest("Headless environment: no display server available")
        Adw.init()
        from knobu.ui.pages import automation_page
        from knobu.ui.store import SettingsStore
        w = automation_page(SettingsStore(), lambda _x: None)
        self.assertIsNotNone(w)


if __name__ == "__main__":
    unittest.main()
