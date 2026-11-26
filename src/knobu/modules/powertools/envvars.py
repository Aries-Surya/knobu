"""Environment Variables Manager: ~/.config/environment.d/ + live systemd user session sync."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_CONF = Path.home() / ".config" / "environment.d" / "90-knobu.conf"
PROFILES_FILE = Path.home() / ".config" / "knobu" / "env_profiles.json"


@dataclass
class EnvEntry:
    key: str
    value: str
    enabled: bool = True


def is_valid_key(key: str) -> bool:
    return bool(_KEY_RE.fullmatch(key.strip()))


def split_path_value(val: str) -> list[str]:
    return [p for p in val.split(":") if p]


def join_path_value(parts: list[str]) -> str:
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        p = part.strip()
        if p and p not in seen:
            seen.add(p)
            unique.append(p)
    return ":".join(unique)


def parse_env_file(text: str) -> list[EnvEntry]:
    """Parse systemd environment.d lines (active and `# KEY=VAL` disabled entries)."""
    entries: list[EnvEntry] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        enabled = True
        if line.startswith("#"):
            candidate = line[1:].strip()
            if "=" not in candidate:
                continue
            k_cand = candidate.split("=", 1)[0].strip()
            if not is_valid_key(k_cand):
                continue
            enabled = False
            line = candidate
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if not is_valid_key(key):
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        entries.append(EnvEntry(key=key, value=val, enabled=enabled))
    return entries


def render_env_file(entries: list[EnvEntry]) -> str:
    lines = ["# Managed by Knobu Environment Variables Manager (systemd environment.d)"]
    for e in entries:
        if not is_valid_key(e.key):
            continue
        safe_val = e.value.replace("\n", " ")
        needs_quote = any(c in safe_val for c in (' ', '\t', '#', '"', '$'))
        formatted = f'"{safe_val.replace(chr(34), chr(92) + chr(34))}"' if needs_quote else safe_val
        prefix = "" if e.enabled else "# "
        lines.append(f"{prefix}{e.key}={formatted}")
    return "\n".join(lines) + "\n"


def load_profiles(profiles_path: Path = PROFILES_FILE, conf_path: Path = DEFAULT_CONF) -> tuple[str, dict[str, list[EnvEntry]]]:
    """Load named environment profiles; falls back to Default profile seeded from 90-knobu.conf."""
    if profiles_path.is_file():
        try:
            raw = json.loads(profiles_path.read_text(encoding="utf-8"))
            active = str(raw.get("active", "Default"))
            profiles: dict[str, list[EnvEntry]] = {}
            for name, items in raw.get("profiles", {}).items():
                profiles[name] = [
                    EnvEntry(str(i["key"]), str(i["value"]), bool(i.get("enabled", True)))
                    for i in items if isinstance(i, dict) and is_valid_key(str(i.get("key", "")))
                ]
            if profiles:
                if active not in profiles:
                    active = next(iter(profiles))
                return active, profiles
        except (OSError, ValueError, KeyError):
            pass

    initial = parse_env_file(conf_path.read_text(encoding="utf-8")) if conf_path.is_file() else []
    return "Default", {"Default": initial}


def apply_live_session(entries: list[EnvEntry], previous_keys: set[str] = frozenset()) -> tuple[bool, str]:
    """Sync enabled variables to active systemd user manager & D-Bus activation environment."""
    active = {e.key: e.value for e in entries if e.enabled and is_valid_key(e.key)}
    to_unset = sorted(k for k in previous_keys if k not in active and is_valid_key(k))

    if not shutil.which("systemctl"):
        return True, "Saved to environment.d (systemctl unavailable for live sync)."

    try:
        if active:
            assignments = [f"{k}={v}" for k, v in active.items()]
            r = subprocess.run(["systemctl", "--user", "set-environment", *assignments],
                               capture_output=True, text=True, timeout=5, check=False)
            if r.returncode != 0:
                return False, r.stderr.strip() or "systemctl set-environment failed"
            if shutil.which("dbus-update-activation-environment"):
                subprocess.run(["dbus-update-activation-environment", "--systemd", *assignments],
                               capture_output=True, text=True, timeout=5, check=False)
        if to_unset:
            subprocess.run(["systemctl", "--user", "unset-environment", *to_unset],
                           capture_output=True, text=True, timeout=5, check=False)
        return True, f"Applied {len(active)} active variable(s) to environment.d and user session."
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)


def save_profiles(
    active: str,
    profiles: dict[str, list[EnvEntry]],
    profiles_path: Path = PROFILES_FILE,
    conf_path: Path = DEFAULT_CONF,
    apply_live: bool = True,
) -> tuple[bool, str]:
    """Persist profiles, write active profile to 90-knobu.conf, and sync live session."""
    prev_keys: set[str] = set()
    if conf_path.is_file():
        try:
            prev_keys = {e.key for e in parse_env_file(conf_path.read_text(encoding="utf-8")) if e.enabled}
        except OSError:
            pass

    entries = profiles.get(active, [])
    conf_path.parent.mkdir(parents=True, exist_ok=True)
    conf_path.write_text(render_env_file(entries), encoding="utf-8")

    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "active": active,
        "profiles": {
            name: [{"key": e.key, "value": e.value, "enabled": e.enabled} for e in lst]
            for name, lst in profiles.items()
        },
    }
    profiles_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if apply_live:
        return apply_live_session(entries, prev_keys)
    return True, f"Saved profile '{active}' ({len(entries)} entries)."


def system_env_snapshot() -> list[tuple[str, str]]:
    """Return sorted read-only snapshot of inherited process environment variables."""
    return sorted(os.environ.items(), key=lambda kv: kv[0].lower())
