"""On-screen volume popup, using the desktop's own OSD where one is reachable.

Supports KDE Plasma over D-Bus and GNOME Shell via freedesktop notifications.
"""

from __future__ import annotations

import os
import subprocess


class VolumeOsd:
    def __init__(self, enabled: bool = True):
        self.backend = _detect() if enabled else None
        self._last_nid = 0

    @property
    def available(self) -> bool:
        return self.backend is not None

    def show(self, percent: int, maximum: int = 100) -> None:
        """Show the volume level on a 0..maximum scale; 0 renders as the muted icon."""
        if not self.backend:
            return

        if self.backend == "kde":
            # Fire-and-forget so a slow D-Bus round trip never stalls a gesture.
            subprocess.Popen(
                ["busctl", "--user", "call", "org.kde.plasmashell", "/org/kde/osdService",
                 "org.kde.osdService", "volumeChanged", "ii", str(percent), str(maximum)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif self.backend == "gnome":
            if percent <= 0:
                icon = "audio-volume-muted-symbolic"
            elif percent < 33:
                icon = "audio-volume-low-symbolic"
            elif percent < 67:
                icon = "audio-volume-medium-symbolic"
            else:
                icon = "audio-volume-high-symbolic"

            try:
                from gi.repository import GLib
                from knobu import APP_ID
                from knobu.system import notify

                scale = max(1, maximum)
                val_int = max(0, min(100, int(percent * 100 / scale)))
                hints = {
                    "desktop-entry": GLib.Variant("s", APP_ID),
                    "value": GLib.Variant("i", val_int),
                    "x-canonical-private-synchronous": GLib.Variant("s", "volume"),
                }
                reply = notify._call("Notify", GLib.Variant("(susssasa{sv}i)", (
                    "Knobu", self._last_nid, icon, "Volume", f"{percent}%", [], hints, 1200
                )))
                if reply:
                    self._last_nid = reply.unpack()[0]
            except Exception:
                pass


def _detect() -> str | None:
    try:
        r = subprocess.run(["busctl", "--user", "status", "org.kde.plasmashell"],
                           capture_output=True, timeout=1, check=False)
        if r.returncode == 0:
            return "kde"
    except (OSError, subprocess.TimeoutExpired):
        pass

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    if any(d in desktop for d in ("GNOME", "UBUNTU", "UNITY")):
        return "gnome"

    return "gnome"
