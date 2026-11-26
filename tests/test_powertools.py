import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knobu.modules.powertools import (
    PowerToolsModule,
    build_compress_cmd,
    build_gif_cmd,
    build_image_convert_cmd,
    clean_target,
    convert_images,
    format_bytes,
    kill_process,
    parse_ss_output,
    scan_cleanup_targets,
    uninstall_package,
)

SAMPLE_SS = """\
udp   UNCONN 0  0  0.0.0.0:5353  0.0.0.0:*  users:(("avahi-daemon",pid=812,fd=12))
tcp   LISTEN 0  4096  127.0.0.1:8080  0.0.0.0:*  users:(("python3",pid=4201,fd=5))
tcp   LISTEN 0  511   [fe80::1%eth0]:546  [::]:*  users:(("dhclient",pid=999,fd=9))
tcp   LISTEN 0  128   *:22  *:*
"""


class TestPowerTools(unittest.TestCase):
    def test_module_defaults(self):
        self.assertEqual(PowerToolsModule.id, "powertools")
        self.assertEqual(PowerToolsModule.command, "cleaning-mode")
        self.assertEqual(PowerToolsModule.defaults["hotkey"], "super+alt+k")
        self.assertEqual(PowerToolsModule.defaults["cleaning_duration"], 30)

    def test_parse_ss_output(self):
        entries = parse_ss_output(SAMPLE_SS)
        self.assertEqual(len(entries), 4)
        by_port = {e.port: e for e in entries}
        self.assertEqual(by_port[22].process, "system")
        self.assertIsNone(by_port[22].pid)
        self.assertEqual(by_port[546].address, "fe80::1%eth0")
        self.assertEqual(by_port[8080].process, "python3")
        self.assertEqual(by_port[8080].pid, 4201)
        self.assertEqual(by_port[5353].proto, "udp")

    def test_kill_process_safety_and_missing_pid(self):
        ok, msg = kill_process(1)
        self.assertFalse(ok)
        self.assertIn("system", msg.lower())

        with patch("os.kill", side_effect=ProcessLookupError):
            ok2, msg2 = kill_process(999999)
            self.assertTrue(ok2)
            self.assertIn("exited", msg2)

    def test_cleaner_scan_and_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            thumbs = home / ".cache" / "thumbnails" / "normal"
            app_cache = home / ".cache" / "someapp"
            thumbs.mkdir(parents=True)
            app_cache.mkdir(parents=True)
            (thumbs / "a.png").write_bytes(b"x" * 1024)
            (app_cache / "blob.bin").write_bytes(b"y" * 2048)

            targets = {t.id: t for t in scan_cleanup_targets(home=home, var_crash=home / "noc", apt_archives=home / "noapt")}
            self.assertEqual(targets["thumbnails"].size_bytes, 1024)
            self.assertEqual(targets["user_cache"].size_bytes, 2048)

            ok, _, freed = clean_target("thumbnails", home=home)
            self.assertTrue(ok)
            self.assertEqual(freed, 1024)
            self.assertTrue((app_cache / "blob.bin").exists())

            ok2, _, freed2 = clean_target("user_cache", home=home)
            self.assertTrue(ok2)
            self.assertEqual(freed2, 2048)

    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(2048), "2.0 KB")
        self.assertEqual(format_bytes(5 * 1024 * 1024), "5.0 MB")

    def test_uninstall_rejects_bad_package_name(self):
        ok, _ = uninstall_package("bad; rm -rf /")
        self.assertFalse(ok)

    def test_media_ffmpeg_command_builders(self):
        src = Path("/tmp/demo.mkv")
        comp = build_compress_cmd(src, Path("/tmp/demo_compressed.mp4"), crf=20)
        self.assertEqual(comp[0], "ffmpeg")
        self.assertIn("20", comp)
        self.assertIn("libx264", comp)

        gif = build_gif_cmd(src, Path("/tmp/demo.gif"), fps=15, width=480)
        self.assertIn("palettegen", " ".join(gif))
        self.assertIn("fps=15,scale=480:-1", " ".join(gif))

        img = build_image_convert_cmd(Path("/tmp/a.png"), Path("/tmp/a.webp"))
        self.assertEqual(img, ["ffmpeg", "-y", "-i", "/tmp/a.png", "/tmp/a.webp"])

        ok, msg, outs = convert_images([Path("/tmp/a.png")], "exe")
        self.assertFalse(ok)
        self.assertEqual(outs, [])
        self.assertIn("Unsupported", msg)

    def test_ui_powertools_page_builds(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        Adw.init()
        from knobu.ui.pages import powertools_page
        from knobu.ui.store import SettingsStore

        widget = powertools_page(SettingsStore(), lambda _x: None)
        self.assertIsNotNone(widget)


if __name__ == "__main__":
    unittest.main()
