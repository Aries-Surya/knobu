"""System Monitor & Hardware Alerts (Milestone 7): CPU, RAM, thermals, net speed, and health alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
import time

from knobu.modules.automation.engine import _read_power_supply
from knobu.modules.base import Module
from knobu.system import notify


@dataclass(frozen=True)
class SystemMetrics:
    cpu_percent: float
    per_core: list[float] = field(default_factory=list)
    mem_used_gb: float = 0.0
    mem_total_gb: float = 0.0
    mem_percent: float = 0.0
    max_temp_c: float = 0.0
    net_rx_kbps: float = 0.0
    net_tx_kbps: float = 0.0
    battery_percent: int = 100
    ac_online: bool = True


def parse_proc_stat(text: str) -> dict[str, tuple[int, int]]:
    """Parse /proc/stat into {cpu_label: (total_jiffies, idle_jiffies)}."""
    out: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        if not line.startswith("cpu"):
            continue
        parts = line.split()
        label = parts[0]
        vals = [int(x) for x in parts[1:] if x.isdigit()]
        if len(vals) >= 4:
            idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
            total = sum(vals)
            out[label] = (total, idle)
    return out


def compute_cpu_usage(
    prev: dict[str, tuple[int, int]],
    cur: dict[str, tuple[int, int]],
) -> tuple[float, list[float]]:
    """Compute overall CPU % and per-core % from two /proc/stat snapshots."""
    def pct(lbl: str) -> float:
        if lbl not in prev or lbl not in cur:
            return 0.0
        dt = cur[lbl][0] - prev[lbl][0]
        di = cur[lbl][1] - prev[lbl][1]
        if dt <= 0:
            return 0.0
        return round(max(0.0, min(100.0, 100.0 * (dt - di) / dt)), 1)

    overall = pct("cpu")
    cores = [pct(k) for k in sorted(cur.keys(), key=lambda x: int(x[3:]) if x[3:].isdigit() else -1) if k != "cpu"]
    return overall, cores


def parse_meminfo(text: str) -> tuple[float, float, float]:
    """Parse /proc/meminfo into (used_gb, total_gb, used_percent)."""
    vals: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, rest = line.split(":", 1)
        num = rest.strip().split()[0]
        if num.isdigit():
            vals[k.strip()] = int(num)  # kB
    total_kb = vals.get("MemTotal", 0)
    avail_kb = vals.get("MemAvailable", vals.get("MemFree", 0))
    if total_kb <= 0:
        return 0.0, 0.0, 0.0
    used_kb = max(0, total_kb - avail_kb)
    total_gb = round(total_kb / (1024 * 1024), 2)
    used_gb = round(used_kb / (1024 * 1024), 2)
    pct = round(100.0 * used_kb / total_kb, 1)
    return used_gb, total_gb, pct


def read_max_temp_c(hwmon_root: Path = Path("/sys/class/hwmon")) -> float:
    """Read maximum reported thermal sensor temperature in Celsius."""
    max_c = 0.0
    if not hwmon_root.is_dir():
        return max_c
    for d in hwmon_root.iterdir():
        for tf in d.glob("temp*_input"):
            try:
                milli = int(tf.read_text().strip())
                c = round(milli / 1000.0, 1)
                if 0 < c < 130 and c > max_c:
                    max_c = c
            except (OSError, ValueError):
                pass
    return max_c


def read_net_dev_bytes(text: str | None = None) -> tuple[int, int]:
    """Return total (rx_bytes, tx_bytes) across non-loopback interfaces."""
    if text is None:
        try:
            text = Path("/proc/net/dev").read_text(encoding="utf-8")
        except OSError:
            return 0, 0
    rx = tx = 0
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        if iface.strip() == "lo":
            continue
        cols = rest.split()
        if len(cols) >= 9:
            rx += int(cols[0])
            tx += int(cols[8])
    return rx, tx


def collect_metrics(sample_sec: float = 0.2) -> SystemMetrics:
    """Sample live CPU, memory, thermal, network, and battery metrics."""
    try:
        s1 = parse_proc_stat(Path("/proc/stat").read_text(encoding="utf-8"))
    except OSError:
        s1 = {}
    rx1, tx1 = read_net_dev_bytes()
    time.sleep(sample_sec)
    try:
        s2 = parse_proc_stat(Path("/proc/stat").read_text(encoding="utf-8"))
    except OSError:
        s2 = {}
    rx2, tx2 = read_net_dev_bytes()

    cpu_pct, per_core = compute_cpu_usage(s1, s2)
    try:
        mem_used, mem_total, mem_pct = parse_meminfo(Path("/proc/meminfo").read_text(encoding="utf-8"))
    except OSError:
        mem_used, mem_total, mem_pct = 0.0, 0.0, 0.0

    rx_kbps = round(max(0, rx2 - rx1) / max(0.05, sample_sec) / 1024.0, 1)
    tx_kbps = round(max(0, tx2 - tx1) / max(0.05, sample_sec) / 1024.0, 1)
    bat_pct, ac_on = _read_power_supply()

    return SystemMetrics(
        cpu_percent=cpu_pct,
        per_core=per_core,
        mem_used_gb=mem_used,
        mem_total_gb=mem_total,
        mem_percent=mem_pct,
        max_temp_c=read_max_temp_c(),
        net_rx_kbps=rx_kbps,
        net_tx_kbps=tx_kbps,
        battery_percent=bat_pct,
        ac_online=ac_on,
    )


def evaluate_health_alerts(
    metrics: SystemMetrics,
    cpu_thresh: float = 90.0,
    mem_thresh: float = 95.0,
    bat_thresh: int = 15,
) -> list[tuple[str, str]]:
    """Return list of (title, body) alerts triggered by current metrics."""
    alerts: list[tuple[str, str]] = []
    if metrics.cpu_percent >= cpu_thresh:
        alerts.append(("High CPU Load", f"CPU usage is at {metrics.cpu_percent:.0f}% (threshold {cpu_thresh:.0f}%)"))
    if metrics.mem_percent >= mem_thresh:
        alerts.append(("Memory Pressure", f"RAM usage is at {metrics.mem_percent:.0f}% ({metrics.mem_used_gb}/{metrics.mem_total_gb} GB)"))
    if not metrics.ac_online and metrics.battery_percent <= bat_thresh:
        alerts.append(("Low Battery", f"Battery is at {metrics.battery_percent}% — plug in power adapter"))
    return alerts


class SystemMonitorModule(Module):
    id = "sysmon"
    name = "System Monitor"
    description = "Real-time CPU, RAM, thermal, network bandwidth monitoring, and hardware health alerts."
    icon = "utilities-system-monitor-symbolic"
    defaults = {
        "enabled": True,
        "bypass": False,
        "top_bar_metrics": True,
        "alerts_enabled": True,
        "cpu_alert_percent": 90,
        "mem_alert_percent": 95,
        "battery_alert_percent": 15,
        "poll_seconds": 10,
    }

    def run(self, stop: threading.Event) -> None:
        poll = max(3, int(self.settings.get("poll_seconds", 10)))
        last_alert_ts: dict[str, float] = {}
        high_cpu_streak = 0

        while not stop.wait(poll):
            if not bool(self.settings.get("alerts_enabled", True)):
                continue
            m = collect_metrics(sample_sec=0.2)
            cpu_t = float(self.settings.get("cpu_alert_percent", 90))
            mem_t = float(self.settings.get("mem_alert_percent", 95))
            bat_t = int(self.settings.get("battery_alert_percent", 15))

            high_cpu_streak = high_cpu_streak + 1 if m.cpu_percent >= cpu_t else 0
            alerts = evaluate_health_alerts(m, cpu_t, mem_t, bat_t)
            now = time.monotonic()
            for title, body in alerts:
                if title == "High CPU Load" and high_cpu_streak < 2:
                    continue  # require sustained CPU load across 2 polls
                if (now - last_alert_ts.get(title, 0.0)) >= 300:
                    notify.notify(title, body, timeout_ms=4000)
                    last_alert_ts[title] = now
