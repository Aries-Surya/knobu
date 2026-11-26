"""FancyZones layout math and Unified Desktop Window Bridge (wmctrl / KWin / GNOME)."""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess


@dataclass(frozen=True)
class ZoneRect:
    index: int
    x: int
    y: int
    width: int
    height: int


ZONE_PRESETS: list[tuple[str, str]] = [
    ("2col", "2 Columns (50 / 50)"),
    ("3col", "3 Columns (33 / 33 / 33)"),
    ("2x2", "2x2 Grid (4 Quadrants)"),
    ("priority", "Priority Grid (25 / 50 / 25)"),
    ("left_main", "Focus + Stack (65 / 35 split)"),
]


def compute_zones(
    preset: str,
    screen_w: int,
    screen_h: int,
    gap: int = 8,
    work_x: int = 0,
    work_y: int = 0,
) -> list[ZoneRect]:
    """Compute pixel rectangles for a FancyZones preset with uniform outer & inner gap."""
    g = max(0, int(gap))
    usable_w = max(100, screen_w - 2 * g)
    usable_h = max(100, screen_h - 2 * g)
    x0 = work_x + g
    y0 = work_y + g

    if preset == "3col":
        w = (usable_w - 2 * g) // 3
        return [
            ZoneRect(0, x0, y0, w, usable_h),
            ZoneRect(1, x0 + w + g, y0, w, usable_h),
            ZoneRect(2, x0 + 2 * (w + g), y0, usable_w - 2 * (w + g), usable_h),
        ]

    if preset == "2x2":
        w = (usable_w - g) // 2
        h = (usable_h - g) // 2
        return [
            ZoneRect(0, x0, y0, w, h),
            ZoneRect(1, x0 + w + g, y0, usable_w - w - g, h),
            ZoneRect(2, x0, y0 + h + g, w, usable_h - h - g),
            ZoneRect(3, x0 + w + g, y0 + h + g, usable_w - w - g, usable_h - h - g),
        ]

    if preset == "priority":
        w_side = int((usable_w - 2 * g) * 0.25)
        w_mid = usable_w - 2 * w_side - 2 * g
        return [
            ZoneRect(0, x0, y0, w_side, usable_h),
            ZoneRect(1, x0 + w_side + g, y0, w_mid, usable_h),
            ZoneRect(2, x0 + w_side + w_mid + 2 * g, y0, w_side, usable_h),
        ]

    if preset == "left_main":
        w_left = int((usable_w - g) * 0.65)
        w_right = usable_w - w_left - g
        h_half = (usable_h - g) // 2
        return [
            ZoneRect(0, x0, y0, w_left, usable_h),
            ZoneRect(1, x0 + w_left + g, y0, w_right, h_half),
            ZoneRect(2, x0 + w_left + g, y0 + h_half + g, w_right, usable_h - h_half - g),
        ]

    # Default: 2col
    w = (usable_w - g) // 2
    return [
        ZoneRect(0, x0, y0, w, usable_h),
        ZoneRect(1, x0 + w + g, y0, usable_w - w - g, usable_h),
    ]


def _active_wmctrl_title() -> str:
    if not shutil.which("xdotool"):
        return ""
    r = subprocess.run(["xdotool", "getactivewindow", "getwindowname"],
                       capture_output=True, text=True, timeout=1, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def _primary_screen_size() -> tuple[int, int]:
    """Read primary display dimensions via Gdk or fallback 1920x1080."""
    try:
        import gi
        gi.require_version("Gdk", "4.0")
        from gi.repository import Gdk
        disp = Gdk.Display.get_default()
        if disp:
            mons = disp.get_monitors()
            if mons.get_n_items() > 0:
                geo = mons.get_item(0).get_geometry()
                return geo.width, geo.height
    except Exception:
        pass
    return 1920, 1080


def toggle_always_on_top(excluded_apps: list[str] | None = None) -> tuple[bool, str]:
    """Pin or unpin the active window above all other windows."""
    title = _active_wmctrl_title()
    for ex in (excluded_apps or []):
        if ex.strip() and ex.strip().lower() in title.lower():
            return False, f"Skipped excluded app: {title}"

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    if "KDE" in desktop and shutil.which("qdbus"):
        r = subprocess.run(
            ["qdbus", "org.kde.KWin", "/KWin", "org.kde.KWin.toggleKeepAbove"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if r.returncode == 0:
            return True, "Toggled Always on Top (KWin)"

    if shutil.which("wmctrl"):
        r = subprocess.run(
            ["wmctrl", "-r", ":ACTIVE:", "-b", "toggle,above"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if r.returncode == 0:
            return True, f"Toggled Always on Top{f' ({title})' if title else ''}"

    return False, "Active window does not expose EWMH handle (native Wayland app)"


def snap_active_window(zone_index: int, preset: str = "2col", gap: int = 8) -> tuple[bool, str]:
    """Snap active window into the given FancyZones zone index."""
    sw, sh = _primary_screen_size()
    zones = compute_zones(preset, sw, sh, gap=gap)
    if not zones:
        return False, "No zones in layout"
    z = zones[zone_index % len(zones)]

    if shutil.which("wmctrl"):
        # Unmaximize first so wmctrl -e resize/move takes effect cleanly
        subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-b", "remove,maximized_vert,maximized_horz"],
                       capture_output=True, timeout=1, check=False)
        r = subprocess.run(
            ["wmctrl", "-r", ":ACTIVE:", "-e", f"0,{z.x},{z.y},{z.width},{z.height}"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if r.returncode == 0:
            return True, f"Snapped to Zone {z.index + 1} ({z.width}x{z.height})"

    return False, "Window snap requires X11/XWayland window handle or KWin"


def maximize_active_window() -> tuple[bool, str]:
    """Maximize active window cleanly without fullscreen displacement."""
    if shutil.which("wmctrl"):
        r = subprocess.run(
            ["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if r.returncode == 0:
            return True, "Maximized active window"
    return False, "Maximize failed (no active EWMH window)"
