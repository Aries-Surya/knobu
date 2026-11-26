"""Light Switch: automatic and manual Dark/Light desktop theme switching (GNOME & KDE)."""

from __future__ import annotations

import datetime
import shutil
import subprocess


def parse_hm(text: str) -> int | None:
    """Parse 'HH:MM' into minutes since midnight, or None if invalid."""
    parts = text.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
    except ValueError:
        pass
    return None


def scheduled_theme_for_time(
    now: datetime.time | None = None,
    light_start: str = "07:00",
    dark_start: str = "19:00",
) -> str:
    """Return 'light' or 'dark' based on current time and schedule."""
    if now is None:
        now = datetime.datetime.now().time()
    cur_m = now.hour * 60 + now.minute
    light_m = parse_hm(light_start)
    dark_m = parse_hm(dark_start)
    if light_m is None or dark_m is None:
        return "dark"
    if light_m < dark_m:
        return "light" if light_m <= cur_m < dark_m else "dark"
    return "dark" if dark_m <= cur_m < light_m else "light"


def get_theme() -> str:
    """Return current desktop color scheme ('dark' or 'light')."""
    if shutil.which("gsettings"):
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if r.returncode == 0:
            return "dark" if "prefer-dark" in r.stdout else "light"
    return "dark"


def set_theme(mode: str) -> tuple[bool, str]:
    """Switch desktop theme to 'dark', 'light', or 'toggle'."""
    target = mode.strip().lower()
    if target == "toggle":
        target = "light" if get_theme() == "dark" else "dark"
    if target not in ("dark", "light"):
        return False, f"Invalid theme mode: {mode}"

    changed = False
    if shutil.which("gsettings"):
        scheme = "prefer-dark" if target == "dark" else "default"
        r = subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", scheme],
            capture_output=True, text=True, timeout=3, check=False,
        )
        changed = changed or (r.returncode == 0)

    if shutil.which("plasma-apply-colorscheme"):
        scheme = "BreezeDark" if target == "dark" else "BreezeLight"
        r = subprocess.run(
            ["plasma-apply-colorscheme", scheme],
            capture_output=True, text=True, timeout=3, check=False,
        )
        changed = changed or (r.returncode == 0)

    if changed:
        return True, f"Switched desktop theme to {target}"
    return False, "No supported desktop theme backend (gsettings / plasma-apply-colorscheme) succeeded"
