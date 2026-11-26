"""Rule-Based Automation Engine (Mac Shortcuts style): triggers, conditions, and actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import datetime
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from knobu import config, service
from knobu.modules.powertools.aws_cli import set_active_aws_profile
from knobu.modules.powertools.network import get_network_status
from knobu.modules.powertools.theme import set_theme
from knobu.modules.powertools.workspaces import launch_workspace
from knobu.system import notify

TRIGGER_TYPES: list[tuple[str, str]] = [
    ("wifi_ssid", "Wi-Fi SSID Connected"),
    ("vpn_connected", "VPN Connected"),
    ("battery_below", "Battery Below (%)"),
    ("ac_power", "Power Adapter (Plugged / Unplugged)"),
    ("app_running", "App Launched / Running"),
    ("folder_new_file", "New File in Folder"),
    ("time_of_day", "Time of Day (HH:MM)"),
]

CONDITION_TYPES: list[tuple[str, str]] = [
    ("always", "Always (No Condition)"),
    ("wifi_is", "Wi-Fi SSID Is"),
    ("vpn_active", "VPN Is Active"),
    ("battery_below", "Battery Is Below (%)"),
    ("on_ac", "On AC Power"),
]

ACTION_TYPES: list[tuple[str, str]] = [
    ("notify", "Send Notification"),
    ("set_theme", "Set Theme (dark / light / toggle)"),
    ("switch_aws", "Switch AWS Profile"),
    ("set_bypass", "Set Master Bypass (on / off)"),
    ("set_awake", "Set Awake (on / off)"),
    ("launch_workspace", "Launch Workspace Group"),
    ("run_command", "Run Shell Command"),
]


@dataclass
class AutomationAction:
    type: str
    value: str = ""


@dataclass
class AutomationRule:
    id: str
    name: str
    enabled: bool = True
    trigger_type: str = "wifi_ssid"
    trigger_value: str = ""
    condition_type: str = "always"
    condition_value: str = ""
    actions: list[AutomationAction] = field(default_factory=list)


@dataclass
class AutomationLogEntry:
    timestamp: float
    rule_name: str
    trigger: str
    result: str
    ok: bool = True


@dataclass
class SystemSnapshot:
    wifi_ssid: str = ""
    vpn_active: bool = False
    vpn_name: str = ""
    battery_percent: int = 100
    ac_online: bool = True
    time_hm: str = ""
    running_procs: set[str] = field(default_factory=set)
    folder_files: dict[str, set[str]] = field(default_factory=dict)


def rules_path() -> Path:
    return config.config_path().parent / "automations.json"


def history_path() -> Path:
    return config.config_path().parent / "automation_history.json"


def load_rules(path: Path | None = None) -> list[AutomationRule]:
    p = path or rules_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        rules: list[AutomationRule] = []
        for r in raw:
            if not isinstance(r, dict):
                continue
            acts = [
                AutomationAction(type=str(a.get("type", "notify")), value=str(a.get("value", "")))
                for a in r.get("actions", [])
                if isinstance(a, dict)
            ]
            rules.append(AutomationRule(
                id=str(r.get("id") or uuid.uuid4().hex[:8]),
                name=str(r.get("name") or "Untitled Rule"),
                enabled=bool(r.get("enabled", True)),
                trigger_type=str(r.get("trigger_type", "wifi_ssid")),
                trigger_value=str(r.get("trigger_value", "")),
                condition_type=str(r.get("condition_type", "always")),
                condition_value=str(r.get("condition_value", "")),
                actions=acts,
            ))
        return rules
    except (FileNotFoundError, ValueError):
        return []


def save_rules(rules: list[AutomationRule], path: Path | None = None) -> None:
    p = path or rules_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(r) for r in rules]
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_history(path: Path | None = None, limit: int = 30) -> list[AutomationLogEntry]:
    p = path or history_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        entries = [
            AutomationLogEntry(
                timestamp=float(e.get("timestamp", 0)),
                rule_name=str(e.get("rule_name", "")),
                trigger=str(e.get("trigger", "")),
                result=str(e.get("result", "")),
                ok=bool(e.get("ok", True)),
            )
            for e in raw[-limit:]
            if isinstance(e, dict)
        ]
        entries.reverse()
        return entries
    except (FileNotFoundError, ValueError):
        return []


def append_history(entry: AutomationLogEntry, path: Path | None = None, max_items: int = 100) -> None:
    p = path or history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raw = []
    except (FileNotFoundError, ValueError):
        raw = []
    raw.append(asdict(entry))
    p.write_text(json.dumps(raw[-max_items:], indent=2) + "\n", encoding="utf-8")


def _read_power_supply() -> tuple[int, bool]:
    pct = 100
    ac = True
    ps_dir = Path("/sys/class/power_supply")
    if not ps_dir.is_dir():
        return pct, ac
    for entry in ps_dir.iterdir():
        name = entry.name.upper()
        if name.startswith("BAT"):
            try:
                pct = int((entry / "capacity").read_text().strip())
                st = (entry / "status").read_text().strip().lower()
                if st == "discharging":
                    ac = False
            except OSError:
                pass
        elif name.startswith(("AC", "ADP")):
            try:
                ac = (entry / "online").read_text().strip() == "1"
            except OSError:
                pass
    return pct, ac


def _list_proc_names() -> set[str]:
    names: set[str] = set()
    proc = Path("/proc")
    if not proc.is_dir():
        return names
    for p in proc.iterdir():
        if not p.name.isdigit():
            continue
        try:
            names.add((p / "comm").read_text().strip().lower())
        except OSError:
            pass
    return names


def capture_snapshot(watched_folders: list[str] | None = None) -> SystemSnapshot:
    net = get_network_status()
    pct, ac = _read_power_supply()
    folders: dict[str, set[str]] = {}
    for raw in (watched_folders or []):
        fp = Path(os.path.expanduser(raw.strip()))
        if fp.is_dir():
            try:
                folders[raw] = {e.name for e in fp.iterdir() if not e.name.startswith(".")}
            except OSError:
                pass
    return SystemSnapshot(
        wifi_ssid=net.connection_name if net.connection_type == "wifi" else "",
        vpn_active=net.vpn_active,
        vpn_name=net.vpn_name,
        battery_percent=pct,
        ac_online=ac,
        time_hm=datetime.datetime.now().strftime("%H:%M"),
        running_procs=_list_proc_names(),
        folder_files=folders,
    )


def evaluate_rule_trigger(rule: AutomationRule, prev: SystemSnapshot, cur: SystemSnapshot) -> bool:
    """Return True on edge transition matching the rule trigger."""
    val = rule.trigger_value.strip()
    t = rule.trigger_type

    if t == "wifi_ssid":
        return bool(val) and cur.wifi_ssid.lower() == val.lower() and prev.wifi_ssid.lower() != val.lower()
    if t == "vpn_connected":
        if not cur.vpn_active:
            return False
        if val:
            return val.lower() in cur.vpn_name.lower() and (not prev.vpn_active or val.lower() not in prev.vpn_name.lower())
        return not prev.vpn_active
    if t == "battery_below":
        try:
            thresh = int(val)
        except ValueError:
            return False
        return cur.battery_percent < thresh and prev.battery_percent >= thresh
    if t == "ac_power":
        want_ac = val.lower() in ("on", "plugged", "ac", "true", "1")
        return cur.ac_online == want_ac and prev.ac_online != want_ac
    if t == "app_running":
        if not val:
            return False
        v = val.lower()
        return any(v in p for p in cur.running_procs) and not any(v in p for p in prev.running_procs)
    if t == "folder_new_file":
        if not val or val not in cur.folder_files or val not in prev.folder_files:
            return False
        return bool(cur.folder_files[val] - prev.folder_files[val])
    if t == "time_of_day":
        return bool(val) and cur.time_hm == val and prev.time_hm != val
    return False


def check_condition(rule: AutomationRule, snap: SystemSnapshot) -> bool:
    c = rule.condition_type
    val = rule.condition_value.strip()
    if c == "always":
        return True
    if c == "wifi_is":
        return snap.wifi_ssid.lower() == val.lower()
    if c == "vpn_active":
        return snap.vpn_active
    if c == "battery_below":
        try:
            return snap.battery_percent < int(val)
        except ValueError:
            return False
    if c == "on_ac":
        return snap.ac_online
    return True


def execute_actions(actions: list[AutomationAction]) -> tuple[bool, str]:
    results: list[str] = []
    all_ok = True
    for act in actions:
        t = act.type
        v = act.value.strip()
        if t == "notify":
            notify.notify("Knobu Automation", v or "Rule triggered", timeout_ms=3000)
            results.append("notified")
        elif t == "set_theme":
            ok, msg = set_theme(v or "toggle")
            all_ok = all_ok and ok
            results.append(msg)
        elif t == "switch_aws":
            ok, msg = set_active_aws_profile(v or "default")
            all_ok = all_ok and ok
            results.append(msg)
        elif t == "set_bypass":
            data = config.load()
            data.setdefault("general", {})["bypass"] = v.lower() in ("on", "true", "1")
            config.save(data)
            service.reload()
            results.append(f"bypass={v}")
        elif t == "set_awake":
            data = config.load()
            data.setdefault("awake", {})["enabled"] = v.lower() in ("on", "true", "1")
            config.save(data)
            service.reload()
            results.append(f"awake={v}")
        elif t == "launch_workspace":
            ok, msg = launch_workspace(v)
            all_ok = all_ok and ok
            results.append(msg)
        elif t == "run_command":
            if v:
                subprocess.Popen(["sh", "-c", v], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                results.append(f"ran: {v}")
        else:
            all_ok = False
            results.append(f"unknown action: {t}")
    return all_ok, "; ".join(results) if results else "no actions"


def run_rule_now(rule: AutomationRule, hist_path: Path | None = None) -> tuple[bool, str]:
    ok, summary = execute_actions(rule.actions)
    append_history(
        AutomationLogEntry(
            timestamp=time.time(),
            rule_name=rule.name,
            trigger=f"{rule.trigger_type}:{rule.trigger_value}",
            result=summary,
            ok=ok,
        ),
        path=hist_path,
    )
    return ok, summary
