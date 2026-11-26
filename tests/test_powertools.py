import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knobu.modules.powertools import (
    EnvEntry,
    HostEntry,
    PowerToolsModule,
    build_compress_cmd,
    build_gif_cmd,
    build_image_convert_cmd,
    build_image_resize_cmd,
    clean_target,
    convert_images,
    find_file_locks,
    format_bytes,
    join_path_value,
    kill_process,
    load_profiles,
    parse_env_file,
    parse_hosts,
    parse_ss_output,
    render_env_file,
    render_hosts,
    resize_images,
    save_hosts,
    save_profiles,
    scan_cleanup_targets,
    split_path_value,
    uninstall_package,
    validate_host_entry,
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
        self.assertEqual(PowerToolsModule.defaults["hotkey"], "super+alt+k")
        self.assertEqual(PowerToolsModule.defaults["ruler_hotkey"], "super+shift+m")
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
        ok2, _ = uninstall_package("../escape", source="npm")
        self.assertFalse(ok2)

    def test_multi_source_package_discovery(self):
        from knobu.modules.powertools import cleaner
        fake_sources = {
            "snap": ("snap", lambda: [cleaner.PackageInfo("code", "snap", "1.9", 0, "vscode")], ["pkexec", "snap", "remove"]),
            "brew": ("brew", lambda: [cleaner.PackageInfo("bat", "brew", "0.24", 0, "brew")], ["brew", "uninstall"]),
            "apt": ("dpkg-query", lambda: [cleaner.PackageInfo("vim", "apt", "9.0", 5000, "editor")], ["pkexec", "apt-get", "remove", "-y"]),
        }
        with patch.object(cleaner, "_PACKAGE_SOURCES", fake_sources):
            all_pkgs = cleaner.list_installed_packages()
            self.assertEqual({p.source for p in all_pkgs}, {"snap", "brew", "apt"})
            brew_only = cleaner.list_installed_packages(source="brew")
            self.assertEqual([p.name for p in brew_only], ["bat"])

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
        from gi.repository import Adw, Gdk, Gtk
        Gtk.init()
        if Gdk.Display.get_default() is None:
            self.skipTest("Headless environment: no display server available")
        Adw.init()
        from knobu.ui.pages import mouse_page, powertools_page
        from knobu.ui.store import SettingsStore

        widget = powertools_page(SettingsStore(), lambda _x: None)
        self.assertIsNotNone(widget)
        self.assertIsNotNone(mouse_page(SettingsStore(), lambda _x: None))

    def test_envvars_parse_render_and_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            conf = t / "90-knobu.conf"
            prof = t / "env_profiles.json"
            entries = [
                EnvEntry("JAVA_HOME", "/usr/lib/jvm/java-21", True),
                EnvEntry("DEBUG_MSG", "hello world", False),
            ]
            ok, _ = save_profiles("Work", {"Work": entries}, profiles_path=prof, conf_path=conf, apply_live=False)
            self.assertTrue(ok)
            parsed = parse_env_file(conf.read_text())
            self.assertEqual(len(parsed), 2)
            self.assertTrue(parsed[0].enabled)
            self.assertFalse(parsed[1].enabled)
            self.assertEqual(parsed[1].value, "hello world")

            active, loaded = load_profiles(profiles_path=prof, conf_path=conf)
            self.assertEqual(active, "Work")
            self.assertEqual(loaded["Work"][0].key, "JAVA_HOME")

        parts = split_path_value("/usr/bin:/opt/bin:/usr/bin")
        self.assertEqual(join_path_value(parts), "/usr/bin:/opt/bin")
        self.assertIn("JAVA_HOME=", render_env_file([EnvEntry("JAVA_HOME", "/opt/jdk")]))

    def test_hosts_parse_validate_and_save(self):
        sample = "# comment\n127.0.0.1 localhost\n# 10.0.0.5 api.local  # staging\n"
        entries, preserved = parse_hosts(sample)
        self.assertEqual(preserved, ["# comment"])
        self.assertEqual(len(entries), 2)
        self.assertTrue(entries[0].enabled)
        self.assertFalse(entries[1].enabled)
        self.assertEqual(entries[1].comment, "staging")
        self.assertIsNotNone(validate_host_entry("999.999.0.1", ["bad"]))
        self.assertIsNone(validate_host_entry("127.0.0.1", ["my.local"]))

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "hosts"
            bak = Path(tmp) / "hosts.bak"
            p.write_text("127.0.0.1 localhost\n")
            ok, _ = save_hosts([HostEntry("127.0.0.1", ["localhost", "dev.local"], enabled=True)],
                               preserved=["# header"], path=p, backup_path=bak)
            self.assertTrue(ok)
            self.assertTrue(bak.is_file())
            self.assertIn("dev.local", render_hosts([HostEntry("127.0.0.1", ["dev.local"])]))

    def test_file_locksmith_proc_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "locked.db"
            target.write_text("data")
            fd_dir = root / "proc" / "4242" / "fd"
            fd_dir.mkdir(parents=True)
            (root / "proc" / "4242" / "comm").write_text("sqlite3\n")
            (fd_dir / "7").symlink_to(target)

            locks = find_file_locks(target, proc_root=root / "proc")
            self.assertEqual(len(locks), 1)
            self.assertEqual(locks[0].pid, 4242)
            self.assertEqual(locks[0].process, "sqlite3")

    def test_media_resize_and_screen_ruler_math(self):
        from knobu.ui.ruler import measure_box
        self.assertEqual(measure_box(10, 20, 40, 60), (30, 40, 50))
        cmd = build_image_resize_cmd(Path("/tmp/a.png"), Path("/tmp/a_small.png"), 854)
        self.assertIn("min(iw,854)", " ".join(cmd))
        ok, _, outs = resize_images([Path("/tmp/a.png")], preset="bogus")
        self.assertFalse(ok)
        self.assertEqual(outs, [])


if __name__ == "__main__":
    unittest.main()
