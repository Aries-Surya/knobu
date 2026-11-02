"""On-screen volume popup, using the desktop's own OSD where one is reachable.

KDE Plasma exposes its OSD over D-Bus. GNOME Shell restricts its ShowOSD method to
allow-listed callers, so on GNOME-based flavours there is no popup yet.
"""

import subprocess


class VolumeOsd:
    def __init__(self, enabled: bool = True):
        self.backend = _detect() if enabled else None

    @property
    def available(self) -> bool:
        return self.backend is not None

    def show(self, percent: int, maximum: int = 100) -> None:
        """Show the volume level on a 0..maximum scale; 0 renders as the muted icon."""
        if self.backend == "kde":
            # Fire-and-forget so a slow D-Bus round trip never stalls a gesture.
            subprocess.Popen(
                ["busctl", "--user", "call", "org.kde.plasmashell", "/org/kde/osdService",
                 "org.kde.osdService", "volumeChanged", "ii", str(percent), str(maximum)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _detect() -> str | None:
    try:
        r = subprocess.run(["busctl", "--user", "status", "org.kde.plasmashell"],
                           capture_output=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return "kde" if r.returncode == 0 else None
