"""Managing the knobu daemon as a systemd user service."""

import subprocess
import sys
from pathlib import Path

UNIT = "knobu.service"
# Installed by the .deb package (from data/knobu.service).
PACKAGED_UNIT = Path("/usr/lib/systemd/user") / UNIT

UNIT_TEMPLATE = """\
[Unit]
Description=Knobu background service
After=graphical-session.target
PartOf=graphical-session.target

[Service]
ExecStart={python} -m knobu daemon
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=graphical-session.target
"""


def unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / UNIT


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True,
                          check=False)


def install_unit() -> None:
    """Write a user unit pointing at the Python that runs Knobu right now (e.g. a venv
    when running from source). Packaged installs already ship one, so skip it there."""
    if PACKAGED_UNIT.exists():
        return
    path = unit_path()
    content = UNIT_TEMPLATE.format(python=sys.executable)
    if not path.exists() or path.read_text() != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        _systemctl("daemon-reload")


def uninstall_unit() -> None:
    """Stop and disable the service; only removes the user's own copy of the unit,
    never the packaged one."""
    _systemctl("disable", "--now", UNIT)
    unit_path().unlink(missing_ok=True)
    _systemctl("daemon-reload")


def is_active() -> bool:
    return _systemctl("is-active", UNIT).stdout.strip() == "active"


def is_enabled() -> bool:
    return _systemctl("is-enabled", UNIT).stdout.strip() == "enabled"


def start() -> None:
    install_unit()
    _systemctl("start", UNIT)


def stop() -> None:
    _systemctl("stop", UNIT)


def set_autostart(enabled: bool) -> None:
    install_unit()
    _systemctl("enable" if enabled else "disable", UNIT)


def reload() -> None:
    """Make a running daemon pick up config changes."""
    if is_active():
        _systemctl("reload", UNIT)
