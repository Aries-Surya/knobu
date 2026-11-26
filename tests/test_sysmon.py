"""Hardcore unit & integration tests for Milestone 7: System Monitor & Hardware Alerts."""

import tempfile
import unittest
from pathlib import Path

from knobu.modules.sysmon import (
    SystemMetrics,
    collect_metrics,
    compute_cpu_usage,
    evaluate_health_alerts,
    parse_meminfo,
    parse_proc_stat,
    read_max_temp_c,
    read_net_dev_bytes,
)


SAMPLE_STAT_1 = "cpu  1000 0 200 8800 0 0 0 0 0 0\ncpu0 500 0 100 4400 0 0 0 0 0 0\ncpu1 500 0 100 4400 0 0 0 0 0 0\n"
SAMPLE_STAT_2 = "cpu  1800 0 200 9000 0 0 0 0 0 0\ncpu0 900 0 100 4500 0 0 0 0 0 0\ncpu1 900 0 100 4500 0 0 0 0 0 0\n"

SAMPLE_MEMINFO = """MemTotal:       16384000 kB
MemFree:         2000000 kB
MemAvailable:    4096000 kB
"""

SAMPLE_NET_DEV = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000000     100    0    0    0     0          0         0  1000000     100    0    0    0     0       0          0
wlp0s20f3: 5242880  5000    0    0    0     0          0         0  1048576    2000    0    0    0     0       0          0
"""


class TestSystemMonitor(unittest.TestCase):
    def test_cpu_usage_calculation(self):
        s1 = parse_proc_stat(SAMPLE_STAT_1)
        s2 = parse_proc_stat(SAMPLE_STAT_2)
        overall, cores = compute_cpu_usage(s1, s2)
        self.assertEqual(overall, 80.0)
        self.assertEqual(cores, [80.0, 80.0])

    def test_meminfo_and_net_dev(self):
        used_gb, total_gb, pct = parse_meminfo(SAMPLE_MEMINFO)
        self.assertEqual(pct, 75.0)
        self.assertGreater(total_gb, used_gb)
        rx, tx = read_net_dev_bytes(SAMPLE_NET_DEV)
        self.assertEqual(rx, 5242880)
        self.assertEqual(tx, 1048576)

    def test_hwmon_thermal_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            hw = Path(d) / "hwmon0"
            hw.mkdir()
            (hw / "temp1_input").write_text("54000\n")
            (hw / "temp2_input").write_text("67500\n")
            self.assertEqual(read_max_temp_c(Path(d)), 67.5)

    def test_health_alerts_thresholds(self):
        m = SystemMetrics(cpu_percent=94.0, mem_percent=96.0, battery_percent=12, ac_online=False)
        alerts = evaluate_health_alerts(m, cpu_thresh=90.0, mem_thresh=95.0, bat_thresh=15)
        titles = [t for t, _ in alerts]
        self.assertEqual(titles, ["High CPU Load", "Memory Pressure", "Low Battery"])

        # On AC, low battery should not alert
        m_ac = SystemMetrics(cpu_percent=20.0, mem_percent=40.0, battery_percent=10, ac_online=True)
        self.assertEqual(evaluate_health_alerts(m_ac), [])

    def test_live_collect_metrics_smoke(self):
        m = collect_metrics(sample_sec=0.05)
        self.assertGreater(m.mem_total_gb, 0.0)
        self.assertTrue(0.0 <= m.cpu_percent <= 100.0)

    def test_ui_sysmon_page_builds(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gdk, Gtk
        Gtk.init()
        if Gdk.Display.get_default() is None:
            self.skipTest("Headless environment: no display server available")
        Adw.init()
        from knobu.ui.pages import sysmon_page
        from knobu.ui.store import SettingsStore
        w = sysmon_page(SettingsStore(), lambda _x: None)
        self.assertIsNotNone(w)


if __name__ == "__main__":
    unittest.main()
