import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knobu.modules.notifications.store import NotificationHistory
from knobu.modules.powertools.aws_cli import parse_aws_files
from knobu.modules.powertools.network import parse_network_info
from knobu.system.tray import StatusTray


class TestTrayAndNotifications(unittest.TestCase):
    def test_parse_network_info(self):
        nmcli_out = (
            "wlp0s20f3:wifi:connected:Office-5GHz\n"
            "tailscale0:tun:connected (externally):tailscale0\n"
            "enp0s31f6:ethernet:unavailable:\n"
        )
        route_json = '[{"dst":"1.1.1.1","gateway":"192.168.1.1","dev":"wlp0s20f3","prefsrc":"192.168.1.42"}]'
        addr_json = '[{"ifname":"tailscale0","addr_info":[{"family":"inet","local":"100.74.64.106"}]}]'

        st = parse_network_info(nmcli_out, route_json, addr_json)
        self.assertEqual(st.connection_name, "Office-5GHz")
        self.assertEqual(st.connection_type, "wifi")
        self.assertEqual(st.private_ip, "192.168.1.42")
        self.assertEqual(st.gateway, "192.168.1.1")
        self.assertEqual(st.vpn_ip, "100.74.64.106")

    def test_parse_aws_files_masks_secrets(self):
        cfg = "[default]\nregion = ap-south-1\noutput = json\n[profile prod]\nregion = us-east-1\nsso_start_url = https://org.awsapps.com/start\n"
        creds = "[default]\naws_access_key_id = AKIAEXAMPLE\naws_secret_access_key = SUPERSECRETKEY\n"
        profiles = parse_aws_files(cfg, creds)
        self.assertEqual([p.name for p in profiles], ["default", "prod"])
        self.assertEqual(profiles[0].region, "ap-south-1")
        self.assertTrue(profiles[0].has_keys)
        self.assertTrue(profiles[1].has_sso)
        self.assertNotIn("SUPERSECRETKEY", repr(profiles))

    def test_notification_history_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = NotificationHistory(Path(tmp) / "notifs.db")
            rec = hist.add("Slack", "Deploy done", "v0.5.0 is live")
            self.assertEqual(hist.count(), 1)
            items = hist.list_recent()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].id, rec.id)
            self.assertEqual(items[0].app_name, "Slack")
            hist.clear()
            self.assertEqual(hist.count(), 0)

    def test_tray_menu_tree_and_dbus_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = NotificationHistory(Path(tmp) / "notifs.db")
            hist.add("GitHub", "CI Passed", "All checks green")
            tray = StatusTray(history=hist, show_public_ip=True)
            tray._public_ip = "203.0.113.10"
            with patch("knobu.system.tray.get_active_aws_profile", return_value="prod"), \
                 patch("knobu.system.tray.load_aws_profiles", return_value=[]):
                root = tray.rebuild_menu()
            labels = [c.label for c in root.children if c.label]
            self.assertTrue(any("Private IP:" in lb for lb in labels))
            self.assertTrue(any("203.0.113.10" in lb for lb in labels))
            self.assertTrue(any("AWS Profile: prod" in lb for lb in labels))
            variant = root.to_variant(-1)
            self.assertEqual(variant.get_type_string(), "(ia{sv}av)")

    def test_ui_notifications_page_builds(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        Adw.init()
        from knobu.ui.pages import notifications_page
        from knobu.ui.store import SettingsStore

        widget = notifications_page(SettingsStore(), lambda _x: None)
        self.assertIsNotNone(widget)


if __name__ == "__main__":
    unittest.main()
