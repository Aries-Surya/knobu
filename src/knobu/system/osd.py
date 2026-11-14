"""On-screen volume popup, using the desktop's native OSD.

Invokes hardware media keys (VolUp, VolDown, Mute) to trigger GNOME/KDE's default
on-screen volume slider without creating notification banners.
"""

from __future__ import annotations

import os
import shutil
import subprocess


def trigger_native_key(code: int) -> bool:
    """Emits hardware media key (115=VolUp, 114=VolDown, 113=Mute) to summon native OS volume slider."""
    if shutil.which("ydotool"):
        try:
            env = dict(os.environ)
            env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
            subprocess.Popen(
                ["ydotool", "key", f"{code}:1", f"{code}:0"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            return True
        except Exception:
            pass
    return False


def native_volume_up() -> bool:
    return trigger_native_key(115)


def native_volume_down() -> bool:
    return trigger_native_key(114)


def native_mute_toggle() -> bool:
    return trigger_native_key(113)


class VolumeOsd:
    def __init__(self, enabled: bool = True):
        self.backend = _detect() if enabled else None

    @property
    def available(self) -> bool:
        return self.backend is not None

    def show(self, percent: int, maximum: int = 100) -> None:
        """Show volume on native OSD; suppresses intrusive notification popups."""
        if not self.backend:
            return

        if self.backend == "kde":
            subprocess.Popen(
                ["busctl", "--user", "call", "org.kde.plasmashell", "/org/kde/osdService",
                 "org.kde.osdService", "volumeChanged", "ii", str(percent), str(maximum)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _detect() -> str | None:
    try:
        r = subprocess.run(["busctl", "--user", "status", "org.kde.plasmashell"],
                           capture_output=True, timeout=1, check=False)
        if r.returncode == 0:
            return "kde"
    except (OSError, subprocess.TimeoutExpired):
        pass

    return "gnome"
