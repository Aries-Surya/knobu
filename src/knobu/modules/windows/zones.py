"""FancyZones layout math and Unified Desktop Window Bridge (wmctrl / KWin / GNOME)."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

GNOME_EXT_UUID = "knobu-window-bridge@knobu.org"
GNOME_BUS_NAME = "org.knobu.WindowBridge"
GNOME_OBJ_PATH = "/org/knobu/WindowBridge"


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


def _is_gnome_desktop() -> bool:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    return "GNOME" in desktop or "UBUNTU" in desktop


def _gnome_bridge_call(method: str, params_variant=None):
    """Call a method on org.knobu.WindowBridge over session D-Bus."""
    try:
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync(
            GNOME_BUS_NAME,
            GNOME_OBJ_PATH,
            GNOME_BUS_NAME,
            method,
            params_variant,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            1000,
            None,
        )
        return res.unpack()
    except Exception:
        return None


def ensure_gnome_bridge_installed() -> tuple[bool, str]:
    """Install and enable the bundled GNOME Shell Window Bridge extension."""
    src_dir = Path(__file__).parent / "gnome_extension"
    if not src_dir.is_dir():
        return False, "Bundled GNOME extension files not found"
    dest_dir = Path.home() / ".local" / "share" / "gnome-shell" / "extensions" / GNOME_EXT_UUID
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        for fname in ("metadata.json", "extension.js"):
            src = src_dir / fname
            dst = dest_dir / fname
            if src.exists() and (not dst.exists() or src.read_bytes() != dst.read_bytes()):
                shutil.copy2(src, dst)
        if shutil.which("gnome-extensions"):
            subprocess.run(["gnome-extensions", "enable", GNOME_EXT_UUID],
                           capture_output=True, text=True, timeout=3, check=False)
        return True, "Knobu GNOME Window Bridge enabled — log out and back in once to activate Wayland window controls"
    except OSError as err:
        return False, f"Failed to install GNOME bridge: {err}"


def get_cursor_position() -> tuple[int, int] | None:
    """Return global (x, y) cursor coordinates via GNOME bridge or xdotool."""
    if _is_gnome_desktop():
        res = _gnome_bridge_call("GetCursorPosition")
        if res and len(res) == 2:
            return int(res[0]), int(res[1])
    if shutil.which("xdotool"):
        r = subprocess.run(["xdotool", "getmouselocation", "--shell"],
                           capture_output=True, text=True, timeout=1, check=False)
        if r.returncode == 0:
            coords: dict[str, int] = {}
            for line in r.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k in ("X", "Y") and v.isdigit():
                        coords[k] = int(v)
            if "X" in coords and "Y" in coords:
                return coords["X"], coords["Y"]
    return None


def _active_wmctrl_title() -> str:
    if _is_gnome_desktop():
        res = _gnome_bridge_call("GetFocusedTitle")
        if res and res[0]:
            return str(res[0])
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

    if _is_gnome_desktop():
        res = _gnome_bridge_call("ToggleAlwaysOnTop")
        if res and len(res) == 2:
            return bool(res[0]), str(res[1])

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

    if _is_gnome_desktop():
        _ok, msg = ensure_gnome_bridge_installed()
        return False, msg

    return False, "Active window does not expose EWMH handle (native Wayland app)"


def snap_active_window(zone_index: int, preset: str = "2col", gap: int = 8) -> tuple[bool, str]:
    """Snap active window into the given FancyZones zone index."""
    sw, sh = _primary_screen_size()
    zones = compute_zones(preset, sw, sh, gap=gap)
    if not zones:
        return False, "No zones in layout"
    z = zones[zone_index % len(zones)]

    if _is_gnome_desktop():
        from gi.repository import GLib
        res = _gnome_bridge_call("SnapWindow", GLib.Variant("(iiii)", (z.x, z.y, z.width, z.height)))
        if res and len(res) == 2:
            return bool(res[0]), f"Snapped to Zone {z.index + 1} ({z.width}x{z.height})" if res[0] else str(res[1])

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

    if _is_gnome_desktop():
        _ok, msg = ensure_gnome_bridge_installed()
        return False, msg

    return False, "Window snap requires X11/XWayland window handle or KWin"


def maximize_active_window() -> tuple[bool, str]:
    """Maximize active window cleanly without fullscreen displacement."""
    if _is_gnome_desktop():
        res = _gnome_bridge_call("MaximizeWindow")
        if res and len(res) == 2:
            return bool(res[0]), str(res[1])

    if shutil.which("wmctrl"):
        r = subprocess.run(
            ["wmctrl", "-r", ":ACTIVE:", "-b", "add,maximized_vert,maximized_horz"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if r.returncode == 0:
            return True, "Maximized active window"

    if _is_gnome_desktop():
        _ok, msg = ensure_gnome_bridge_installed()
        return False, msg

    return False, "Maximize failed (no active EWMH window)"
