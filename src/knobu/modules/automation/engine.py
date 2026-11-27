"""Rule-Based Automation Engine (Mac Shortcuts style): triggers, conditions, and actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from knobu import config, service
from knobu.modules.powertools.aws_cli import set_active_aws_profile
from knobu.modules.powertools.devops import switch_kube_context
from knobu.modules.powertools.network import get_network_status
from knobu.modules.powertools.theme import parse_hm, set_theme
from knobu.modules.powertools.workspaces import launch_workspace
from knobu.system import notify

TRIGGER_TYPES: list[tuple[str, str]] = [
    ("wifi_ssid", "Wi-Fi SSID Connected"),
    ("wifi_disconnect", "Wi-Fi Disconnected"),
    ("vpn_connected", "VPN Connected"),
    ("vpn_disconnect", "VPN Disconnected"),
    ("battery_below", "Battery Below (%)"),
    ("battery_above", "Battery Charged Above (%)"),
    ("ac_power", "Power Adapter (Plugged / Unplugged)"),
    ("app_running", "App Launched / Running"),
    ("app_closed", "App Closed / Exited"),
    ("screen_lock", "Screen Lock State (locked / unlocked)"),
    ("folder_new_file", "New File in Folder"),
    ("time_of_day", "Time of Day (HH:MM)"),
    ("interval", "Periodic Interval (minutes)"),
]

CONDITION_TYPES: list[tuple[str, str]] = [
    ("always", "Always (No Condition)"),
    ("wifi_is", "Wi-Fi SSID Is"),
    ("wifi_in", "Wi-Fi SSID In List (comma-separated)"),
    ("vpn_active", "VPN Is Active"),
    ("vpn_inactive", "VPN Is Disconnected"),
    ("battery_below", "Battery Is Below (%)"),
    ("battery_range", "Battery Between (min-max %)"),
    ("on_ac", "On AC Power"),
    ("on_battery", "On Battery Power"),
    ("app_is_running", "Process / App Is Running"),
    ("time_window", "Within Time Window (HH:MM-HH:MM)"),
]

ACTION_TYPES: list[tuple[str, str]] = [
    ("notify", "Send Notification"),
    ("set_theme", "Set Theme (dark / light / toggle)"),
    ("switch_aws", "Switch AWS Profile"),
    ("switch_kube", "Switch Kubernetes Context"),
    ("set_bypass", "Set Master Bypass (on / off)"),
    ("set_awake", "Set Awake (on / off)"),
    ("set_dnd", "Set Do Not Disturb (on / off)"),
    ("mute_mic", "Microphone Mute (on / off / toggle)"),
    ("launch_workspace", "Launch Workspace Group"),
    ("run_command", "Run Shell Command"),
]

AUTOMATION_TEMPLATES: list[dict] = [
    {
        "id": "devops_workday",
        "name": "DevOps Workday",
        "description": "When corporate VPN connects, switch theme to light and notify.",
        "trigger_type": "vpn_connected",
        "trigger_value": "",
        "condition_type": "always",
        "condition_value": "",
        "actions": [
            {"type": "switch_aws", "value": "default"},
            {"type": "notify", "value": "DevOps Workday environment active"},
        ],
    },
    {
        "id": "gaming_passthrough",
        "name": "Gaming Passthrough",
        "description": "Enable Master Bypass and Do Not Disturb when Steam launches.",
        "trigger_type": "app_running",
        "trigger_value": "steam",
        "condition_type": "always",
        "condition_value": "",
        "actions": [
            {"type": "set_bypass", "value": "on"},
            {"type": "set_dnd", "value": "on"},
            {"type": "notify", "value": "Gaming Passthrough active"},
        ],
    },
    {
        "id": "low_battery_saver",
        "name": "Low Battery Saver",
        "description": "Switch to dark theme and turn off Awake when battery drops below 20%.",
        "trigger_type": "battery_below",
        "trigger_value": "20",
        "condition_type": "on_battery",
        "condition_value": "",
        "actions": [
            {"type": "set_theme", "value": "dark"},
            {"type": "set_awake", "value": "off"},
            {"type": "notify", "value": "Battery below 20%: Power Saver applied"},
        ],
    },
    {
        "id": "secure_screen_lock",
        "name": "Secure Screen Lock",
        "description": "Automatically mute microphone when workstation screen locks.",
        "trigger_type": "screen_lock",
        "trigger_value": "locked",
        "condition_type": "always",
        "condition_value": "",
        "actions": [
            {"type": "mute_mic", "value": "on"},
            {"type": "notify", "value": "Microphone muted on screen lock"},
        ],
    },
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
    locked: bool = False
    tick_minute: int = 0


def rules_path() -> Path:
    return config.config_path().parent / "automations.json"


def history_path() -> Path:
    return config.config_path().parent / "automation_history.json"


def create_rule_from_template(template_id: str) -> AutomationRule | None:
    tpl = next((t for t in AUTOMATION_TEMPLATES if t["id"] == template_id), None)
    if not tpl:
        return None
    return AutomationRule(
        id=uuid.uuid4().hex[:8],
        name=tpl["name"],
        enabled=True,
        trigger_type=tpl["trigger_type"],
        trigger_value=tpl["trigger_value"],
        condition_type=tpl["condition_type"],
        condition_value=tpl["condition_value"],
        actions=[AutomationAction(type=a["type"], value=a["value"]) for a in tpl["actions"]],
    )


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


def _is_screen_locked() -> bool:
    if shutil.which("gdbus"):
        try:
            r = subprocess.run(
                ["gdbus", "call", "--session", "--dest", "org.freedesktop.ScreenSaver",
                 "--object-path", "/org/freedesktop/ScreenSaver",
                 "--method", "org.freedesktop.ScreenSaver.GetActive"],
                capture_output=True, text=True, timeout=1.5, check=False,
            )
            if r.returncode == 0:
                return "true" in r.stdout.lower()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return False


def capture_snapshot(watched_folders: list[str] | None = None, check_lock: bool = False) -> SystemSnapshot:
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
    now = datetime.datetime.now()
    return SystemSnapshot(
        wifi_ssid=net.connection_name if net.connection_type == "wifi" else "",
        vpn_active=net.vpn_active,
        vpn_name=net.vpn_name,
        battery_percent=pct,
        ac_online=ac,
        time_hm=now.strftime("%H:%M"),
        running_procs=_list_proc_names(),
        folder_files=folders,
        locked=_is_screen_locked() if check_lock else False,
        tick_minute=int(time.time() // 60),
    )


def evaluate_rule_trigger(rule: AutomationRule, prev: SystemSnapshot, cur: SystemSnapshot) -> bool:
    """Return True on edge transition matching the rule trigger."""
    val = rule.trigger_value.strip()
    t = rule.trigger_type

    if t == "wifi_ssid":
        return bool(val) and cur.wifi_ssid.lower() == val.lower() and prev.wifi_ssid.lower() != val.lower()
    if t == "wifi_disconnect":
        if not prev.wifi_ssid:
            return False
        if val:
            return prev.wifi_ssid.lower() == val.lower() and cur.wifi_ssid.lower() != val.lower()
        return not cur.wifi_ssid
    if t == "vpn_connected":
        if not cur.vpn_active:
            return False
        if val:
            return val.lower() in cur.vpn_name.lower() and (not prev.vpn_active or val.lower() not in prev.vpn_name.lower())
        return not prev.vpn_active
    if t == "vpn_disconnect":
        if not prev.vpn_active:
            return False
        if val:
            return val.lower() in prev.vpn_name.lower() and (not cur.vpn_active or val.lower() not in cur.vpn_name.lower())
        return not cur.vpn_active
    if t == "battery_below":
        try:
            thresh = int(val)
        except ValueError:
            return False
        return cur.battery_percent < thresh and prev.battery_percent >= thresh
    if t == "battery_above":
        try:
            thresh = int(val)
        except ValueError:
            return False
        return cur.battery_percent >= thresh and prev.battery_percent < thresh
    if t == "ac_power":
        want_ac = val.lower() in ("on", "plugged", "ac", "true", "1")
        return cur.ac_online == want_ac and prev.ac_online != want_ac
    if t == "app_running":
        if not val:
            return False
        v = val.lower()
        return any(v in p for p in cur.running_procs) and not any(v in p for p in prev.running_procs)
    if t == "app_closed":
        if not val:
            return False
        v = val.lower()
        return any(v in p for p in prev.running_procs) and not any(v in p for p in cur.running_procs)
    if t == "screen_lock":
        want_locked = val.lower() in ("", "locked", "lock", "on", "true", "1")
        return cur.locked == want_locked and prev.locked != want_locked
    if t == "folder_new_file":
        if not val or val not in cur.folder_files or val not in prev.folder_files:
            return False
        return bool(cur.folder_files[val] - prev.folder_files[val])
    if t == "time_of_day":
        return bool(val) and cur.time_hm == val and prev.time_hm != val
    if t == "interval":
        try:
            mins = max(1, int(val))
        except ValueError:
            return False
        return cur.tick_minute > prev.tick_minute and (cur.tick_minute % mins) == 0
    return False


def check_condition(rule: AutomationRule, snap: SystemSnapshot) -> bool:
    c = rule.condition_type
    val = rule.condition_value.strip()
    if c == "always":
        return True
    if c == "wifi_is":
        return snap.wifi_ssid.lower() == val.lower()
    if c == "wifi_in":
        items = [s.strip().lower() for s in val.split(",") if s.strip()]
        return bool(snap.wifi_ssid) and snap.wifi_ssid.lower() in items
    if c == "vpn_active":
        return snap.vpn_active
    if c == "vpn_inactive":
        return not snap.vpn_active
    if c == "battery_below":
        try:
            return snap.battery_percent < int(val)
        except ValueError:
            return False
    if c == "battery_range":
        parts = val.split("-", 1)
        if len(parts) != 2:
            return False
        try:
            lo, hi = int(parts[0].strip()), int(parts[1].strip())
            return lo <= snap.battery_percent <= hi
        except ValueError:
            return False
    if c == "on_ac":
        return snap.ac_online
    if c == "on_battery":
        return not snap.ac_online
    if c == "app_is_running":
        v = val.lower()
        return bool(v) and any(v in p for p in snap.running_procs)
    if c == "time_window":
        parts = val.split("-", 1)
        if len(parts) != 2:
            return False
        start_m, end_m, cur_m = parse_hm(parts[0]), parse_hm(parts[1]), parse_hm(snap.time_hm)
        if start_m is None or end_m is None or cur_m is None:
            return False
        if start_m <= end_m:
            return start_m <= cur_m <= end_m
        return cur_m >= start_m or cur_m <= end_m
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
        elif t == "switch_kube":
            ok, msg = switch_kube_context(v)
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
        elif t == "set_dnd":
            data = config.load()
            data.setdefault("notifications", {})["dnd"] = v.lower() in ("on", "true", "1")
            config.save(data)
            service.reload()
            results.append(f"dnd={v}")
        elif t == "mute_mic":
            arg = "1" if v.lower() in ("on", "mute", "true", "1") else ("0" if v.lower() in ("off", "unmute", "false") else "toggle")
            if shutil.which("wpctl"):
                r = subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", arg],
                                   capture_output=True, text=True, timeout=2, check=False)
                ok = r.returncode == 0
                all_ok = all_ok and ok
                results.append(f"mic_mute={arg}")
            else:
                all_ok = False
                results.append("wpctl not found")
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
