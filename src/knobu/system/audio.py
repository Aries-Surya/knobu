"""Default output volume control.

Uses PipeWire's wpctl (Ubuntu 22.10+ on every flavour) and falls back to pactl,
which also works against PipeWire's PulseAudio layer and older PulseAudio setups.
"""

import configparser
import os
import re
import shutil
import subprocess
from pathlib import Path

AMPLIFIED_MAX = 150  # what KDE and GNOME allow when "over-amplification" is on


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout


def system_max_volume() -> int:
    """The volume limit the desktop's own volume controls use (100, or 150 if raised)."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if "KDE" in desktop:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(Path.home() / ".config" / "plasmaparc")
        raised = parser.getboolean("General", "RaiseMaximumVolume", fallback=False)
        return AMPLIFIED_MAX if raised else 100
    if shutil.which("gsettings"):
        out = _run("gsettings", "get", "org.gnome.desktop.sound", "allow-volume-above-100-percent")
        if out.strip() == "true":
            return AMPLIFIED_MAX
    return 100


class Audio:
    def __init__(self):
        if shutil.which("wpctl"):
            self.backend = "wpctl"
        elif shutil.which("pactl"):
            self.backend = "pactl"
        else:
            raise RuntimeError("Neither wpctl nor pactl found; cannot control volume")

    def get(self) -> tuple[int, bool]:
        """Return (volume percent, muted)."""
        if self.backend == "wpctl":
            out = _run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
            m = re.search(r"([\d.]+)", out)
            return (round(float(m.group(1)) * 100) if m else 0), "MUTED" in out
        vol = re.search(r"(\d+)%", _run("pactl", "get-sink-volume", "@DEFAULT_SINK@"))
        muted = "yes" in _run("pactl", "get-sink-mute", "@DEFAULT_SINK@")
        return (int(vol.group(1)) if vol else 0), muted

    def set_volume(self, percent: int) -> None:
        if self.backend == "wpctl":
            _run("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent}%")
        else:
            _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%")

    def set_mute(self, muted: bool) -> None:
        flag = "1" if muted else "0"
        if self.backend == "wpctl":
            _run("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", flag)
        else:
            _run("pactl", "set-sink-mute", "@DEFAULT_SINK@", flag)
