"""AWS CLI configuration reader & active profile switcher."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

from knobu.modules.powertools.envvars import EnvEntry, load_profiles, save_profiles

AWS_DIR = Path.home() / ".aws"


@dataclass(frozen=True)
class AwsProfile:
    name: str
    region: str = ""
    output: str = ""
    has_sso: bool = False
    role_arn: str = ""
    has_keys: bool = False


def parse_aws_files(config_text: str, creds_text: str) -> list[AwsProfile]:
    """Parse ~/.aws/config and ~/.aws/credentials without ever exposing secret values."""
    cfg = configparser.ConfigParser()
    cfg.read_string(config_text)
    creds = configparser.ConfigParser()
    creds.read_string(creds_text)

    names: list[str] = []
    seen: set[str] = set()

    for sec in cfg.sections():
        name = sec[8:].strip() if sec.startswith("profile ") else sec.strip()
        if name and name not in seen and not sec.startswith("sso-session "):
            seen.add(name)
            names.append(name)

    for sec in creds.sections():
        name = sec.strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    profiles: list[AwsProfile] = []
    for name in names:
        cfg_sec = "default" if name == "default" else f"profile {name}"
        sec_data = cfg[cfg_sec] if cfg_sec in cfg else (cfg[name] if name in cfg else {})
        cred_data = creds[name] if name in creds else {}
        profiles.append(AwsProfile(
            name=name,
            region=str(sec_data.get("region", "")),
            output=str(sec_data.get("output", "")),
            has_sso=bool(sec_data.get("sso_start_url") or sec_data.get("sso_session")),
            role_arn=str(sec_data.get("role_arn", "")),
            has_keys=bool(cred_data.get("aws_access_key_id")),
        ))
    return profiles


def load_aws_profiles(aws_dir: Path = AWS_DIR) -> list[AwsProfile]:
    cfg_p = aws_dir / "config"
    cred_p = aws_dir / "credentials"
    cfg_txt = cfg_p.read_text(encoding="utf-8", errors="ignore") if cfg_p.is_file() else ""
    cred_txt = cred_p.read_text(encoding="utf-8", errors="ignore") if cred_p.is_file() else ""
    return parse_aws_files(cfg_txt, cred_txt)


def get_active_aws_profile() -> str:
    """Return the active AWS CLI profile from systemd user env, environment.d, or process env."""
    if shutil.which("systemctl"):
        try:
            r = subprocess.run(["systemctl", "--user", "show-environment"],
                               capture_output=True, text=True, timeout=2, check=False)
            if r.returncode == 0:
                env_map = {}
                for ln in r.stdout.splitlines():
                    if "=" in ln:
                        k, v = ln.split("=", 1)
                        env_map[k] = v
                if env_map.get("AWS_PROFILE"):
                    return env_map["AWS_PROFILE"]
                if env_map.get("AWS_DEFAULT_PROFILE"):
                    return env_map["AWS_DEFAULT_PROFILE"]
        except (OSError, subprocess.TimeoutExpired):
            pass

    active_prof, profs = load_profiles()
    for item in profs.get(active_prof, []):
        if item.enabled and item.key in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE") and item.value:
            return item.value

    return os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE") or "default"


def set_active_aws_profile(profile: str, region: str = "") -> tuple[bool, str]:
    """Set active AWS_PROFILE (and optional region) via environment.d and live user session."""
    active_name, profs = load_profiles()
    entries = profs.setdefault(active_name, [])

    def upsert(key: str, val: str, enable: bool = True) -> None:
        for item in entries:
            if item.key == key:
                item.value = val
                item.enabled = enable
                return
        entries.append(EnvEntry(key=key, value=val, enabled=enable))

    upsert("AWS_PROFILE", profile, True)
    if region:
        upsert("AWS_DEFAULT_REGION", region, True)
    return save_profiles(active_name, profs, apply_live=True)
