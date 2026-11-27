"""Desktop Customization, Appearance & System Preferences backend (Milestone 14)."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess

log = logging.getLogger("knobu.system_prefs")

IFACE_SCHEMA = "org.gnome.desktop.interface"
BG_SCHEMA = "org.gnome.desktop.background"
SOUND_SCHEMA = "org.gnome.desktop.sound"
NOTIF_SCHEMA = "org.gnome.desktop.notifications"
MUTTER_DEST = "org.gnome.Mutter.DisplayConfig"
MUTTER_PATH = "/org/gnome/Mutter/DisplayConfig"


@dataclass
class StartupApp:
    desktop_id: str
    name: str
    exec_cmd: str
    comment: str = ""
    icon: str = "application-x-executable-symbolic"
    enabled: bool = True
    is_user: bool = False
    path: str = ""


@dataclass(frozen=True)
class DisplayMode:
    mode_id: str
    width: int
    height: int
    refresh: float
    preferred_scale: float = 1.0
    supported_scales: list[float] = field(default_factory=lambda: [1.0, 1.25, 1.5, 2.0])
    is_current: bool = False


@dataclass
class MonitorState:
    connector: str
    vendor: str
    product: str
    current_mode: str
    current_scale: float
    transform: int
    is_primary: bool
    modes: list[DisplayMode] = field(default_factory=list)


@dataclass
class AppNotificationPref:
    app_id: str
    label: str
    enabled: bool
    show_banners: bool


# ---------------------------------------------------------------------- gsettings helpers

def _gsettings_get(schema: str, key: str, default: str = "") -> str:
    if not shutil.which("gsettings"):
        return default
    try:
        r = subprocess.run(["gsettings", "get", schema, key], capture_output=True, text=True, timeout=2, check=False)
        if r.returncode == 0:
            return r.stdout.strip().strip("'\"")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return default


def _gsettings_set(schema: str, key: str, value: str | bool | int | float) -> tuple[bool, str]:
    if not shutil.which("gsettings"):
        return False, "gsettings not installed"
    if isinstance(value, bool):
        arg = "true" if value else "false"
    else:
        arg = str(value)
    try:
        r = subprocess.run(["gsettings", "set", schema, key, arg], capture_output=True, text=True, timeout=2, check=False)
        return (r.returncode == 0, f"Set {key} = {arg}" if r.returncode == 0 else r.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)


# ---------------------------------------------------------------------- 1. Startup Apps Manager

def _parse_desktop_entry(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    in_entry = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_entry = (line == "[Desktop Entry]")
            continue
        if in_entry and "=" in line:
            k, v = line.split("=", 1)
            fields.setdefault(k.strip(), v.strip())
    return fields


def list_startup_apps(
    user_dir: Path | None = None,
    system_dirs: list[Path] | None = None,
) -> list[StartupApp]:
    u_dir = user_dir or (Path.home() / ".config" / "autostart")
    s_dirs = system_dirs if system_dirs is not None else [Path("/etc/xdg/autostart")]

    by_id: dict[str, StartupApp] = {}
    for d, is_user in [(sd, False) for sd in s_dirs] + [(u_dir, True)]:
        if not d.is_dir():
            continue
        for fp in sorted(d.glob("*.desktop")):
            fields = _parse_desktop_entry(fp.read_text(encoding="utf-8", errors="ignore"))
            if not fields:
                continue
            hidden = fields.get("Hidden", "false").lower() == "true"
            auto_en = fields.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
            prev = by_id.get(fp.name)
            by_id[fp.name] = StartupApp(
                desktop_id=fp.name,
                name=fields.get("Name") or (prev.name if prev else fp.stem),
                exec_cmd=fields.get("Exec") or (prev.exec_cmd if prev else ""),
                comment=fields.get("Comment") or (prev.comment if prev else ""),
                icon=fields.get("Icon") or (prev.icon if prev else "application-x-executable-symbolic"),
                enabled=(not hidden) and auto_en,
                is_user=is_user or (prev.is_user if prev else False),
                path=str(fp),
            )
    return sorted(by_id.values(), key=lambda a: a.name.lower())


def set_startup_app_enabled(
    desktop_id: str,
    enabled: bool,
    user_dir: Path | None = None,
    system_dirs: list[Path] | None = None,
) -> tuple[bool, str]:
    u_dir = user_dir or (Path.home() / ".config" / "autostart")
    s_dirs = system_dirs if system_dirs is not None else [Path("/etc/xdg/autostart")]
    u_file = u_dir / desktop_id
    src_file = u_file if u_file.is_file() else next((d / desktop_id for d in s_dirs if (d / desktop_id).is_file()), None)
    if src_file is None:
        return False, f"Startup entry not found: {desktop_id}"

    text = src_file.read_text(encoding="utf-8", errors="ignore")
    lines = [
        ln for ln in text.splitlines()
        if not ln.startswith(("X-GNOME-Autostart-enabled=", "Hidden="))
    ]
    lines.append(f"X-GNOME-Autostart-enabled={'true' if enabled else 'false'}")
    lines.append("Hidden=false")
    u_dir.mkdir(parents=True, exist_ok=True)
    u_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True, f"{'Enabled' if enabled else 'Disabled'} {desktop_id}"


def add_startup_app(name: str, exec_cmd: str, comment: str = "", user_dir: Path | None = None) -> tuple[bool, str]:
    name = name.strip()
    exec_cmd = exec_cmd.strip()
    if not name or not exec_cmd:
        return False, "Name and Command are required"
    u_dir = user_dir or (Path.home() / ".config" / "autostart")
    u_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-") or "custom-app"
    fp = u_dir / f"knobu-{slug}.desktop"
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Exec={exec_cmd}\n"
        f"Comment={comment.strip() or 'Added via Knobu'}\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Terminal=false\n"
    )
    fp.write_text(content, encoding="utf-8")
    return True, f"Added startup app: {name}"


def remove_startup_app(desktop_id: str, user_dir: Path | None = None) -> tuple[bool, str]:
    u_dir = user_dir or (Path.home() / ".config" / "autostart")
    fp = u_dir / desktop_id
    if not fp.is_file():
        return False, "Only user-created or overridden autostart entries can be removed"
    fp.unlink()
    return True, f"Removed {desktop_id}"


# ---------------------------------------------------------------------- 2. Fonts & Appearance

def discover_themes(kind: str, search_dirs: list[Path] | None = None) -> list[str]:
    """Discover installed 'cursor', 'icon', or 'gtk' themes across standard directories."""
    if search_dirs is None:
        if kind == "gtk":
            dirs = [Path.home() / ".themes", Path.home() / ".local/share/themes", Path("/usr/share/themes")]
        else:
            dirs = [Path.home() / ".icons", Path.home() / ".local/share/icons", Path("/usr/share/icons")]
    else:
        dirs = search_dirs

    found: set[str] = set()
    for base in dirs:
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if kind == "cursor":
                if (entry / "cursors").is_dir():
                    found.add(entry.name)
            elif kind == "icon":
                if (entry / "index.theme").is_file() and entry.name not in ("default", "hicolor", "locolor"):
                    if not ((entry / "cursors").is_dir() and not (entry / "apps").is_dir() and not (entry / "places").is_dir()):
                        found.add(entry.name)
            elif kind == "gtk":
                if any((entry / sub).is_dir() for sub in ("gtk-3.0", "gtk-4.0")):
                    found.add(entry.name)
    return sorted(found, key=str.lower)


def list_font_families() -> list[str]:
    if not shutil.which("fc-list"):
        return ["Ubuntu Sans", "Ubuntu Sans Mono", "Sans", "Monospace"]
    try:
        r = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=3, check=False)
        fams = {part.strip() for ln in r.stdout.splitlines() for part in ln.split(",") if part.strip()}
        return sorted(fams, key=str.lower)
    except (OSError, subprocess.TimeoutExpired):
        return ["Ubuntu Sans", "Ubuntu Sans Mono", "Sans", "Monospace"]


def get_font_settings() -> dict[str, object]:
    scale_raw = _gsettings_get(IFACE_SCHEMA, "text-scaling-factor", "1.0")
    try:
        scale = float(scale_raw)
    except ValueError:
        scale = 1.0
    return {
        "font-name": _gsettings_get(IFACE_SCHEMA, "font-name", "Ubuntu Sans 11"),
        "document-font-name": _gsettings_get(IFACE_SCHEMA, "document-font-name", "Sans 11"),
        "monospace-font-name": _gsettings_get(IFACE_SCHEMA, "monospace-font-name", "Ubuntu Sans Mono 11"),
        "text-scaling-factor": scale,
        "font-antialiasing": _gsettings_get(IFACE_SCHEMA, "font-antialiasing", "rgba"),
        "font-hinting": _gsettings_get(IFACE_SCHEMA, "font-hinting", "slight"),
    }


def set_interface_key(key: str, value: str | float | int | bool) -> tuple[bool, str]:
    return _gsettings_set(IFACE_SCHEMA, key, value)


def get_appearance_settings() -> dict[str, object]:
    csize = _gsettings_get(IFACE_SCHEMA, "cursor-size", "24")
    return {
        "color-scheme": _gsettings_get(IFACE_SCHEMA, "color-scheme", "prefer-dark"),
        "cursor-theme": _gsettings_get(IFACE_SCHEMA, "cursor-theme", "Yaru"),
        "cursor-size": int(csize) if csize.isdigit() else 24,
        "icon-theme": _gsettings_get(IFACE_SCHEMA, "icon-theme", "Yaru"),
        "gtk-theme": _gsettings_get(IFACE_SCHEMA, "gtk-theme", "Yaru"),
        "picture-uri": _gsettings_get(BG_SCHEMA, "picture-uri", ""),
        "picture-uri-dark": _gsettings_get(BG_SCHEMA, "picture-uri-dark", ""),
        "picture-options": _gsettings_get(BG_SCHEMA, "picture-options", "zoom"),
    }


def set_wallpaper(path_or_uri: str, mode: str = "both") -> tuple[bool, str]:
    val = path_or_uri.strip()
    uri = val if val.startswith("file://") else Path(val).resolve().as_uri()
    ok = True
    if mode in ("light", "both"):
        ok1, _ = _gsettings_set(BG_SCHEMA, "picture-uri", uri)
        ok = ok and ok1
    if mode in ("dark", "both"):
        ok2, _ = _gsettings_set(BG_SCHEMA, "picture-uri-dark", uri)
        ok = ok and ok2
    return ok, f"Updated wallpaper ({mode})"


def set_wallpaper_options(option: str) -> tuple[bool, str]:
    return _gsettings_set(BG_SCHEMA, "picture-options", option)


# ---------------------------------------------------------------------- 3. Display, Resolution & Scaling

def parse_xrandr_monitors(text: str) -> list[MonitorState]:
    """Parse `xrandr --query` fallback into MonitorState objects."""
    monitors: list[MonitorState] = []
    cur: MonitorState | None = None
    for line in text.splitlines():
        if " connected" in line:
            parts = line.split()
            conn = parts[0]
            cur = MonitorState(conn, "", conn, "", 1.0, 0, "primary" in line, [])
            monitors.append(cur)
        elif cur and line.startswith("   "):
            parts = line.split()
            if not parts or "x" not in parts[0]:
                continue
            dims = parts[0].split("x")
            if not (len(dims) == 2 and dims[0].isdigit() and dims[1].isdigit()):
                continue
            w, h = int(dims[0]), int(dims[1])
            for tok in parts[1:]:
                clean = tok.rstrip("*+")
                try:
                    hz = float(clean)
                except ValueError:
                    continue
                mid = f"{w}x{h}@{hz:.3f}"
                is_cur = "*" in tok
                if is_cur:
                    cur.current_mode = mid
                cur.modes.append(DisplayMode(mid, w, h, hz, is_current=is_cur))
    return monitors


def get_monitors() -> tuple[int, list[MonitorState]]:
    """Query monitor geometry & modes from Mutter D-Bus, falling back to xrandr."""
    try:
        from gi.repository import Gio
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync(MUTTER_DEST, MUTTER_PATH, MUTTER_DEST, "GetCurrentState",
                            None, None, 0, 2000, None)
        serial, raw_mons, raw_logical, _props = res.unpack()
        logical_by_conn: dict[str, tuple[float, int, bool]] = {}
        for _x, _y, scale, transform, primary, conns, _lp in raw_logical:
            for c_info in conns:
                logical_by_conn[str(c_info[0])] = (float(scale), int(transform), bool(primary))

        monitors: list[MonitorState] = []
        for mon_id, raw_modes, _mprops in raw_mons:
            conn, vendor, product = str(mon_id[0]), str(mon_id[1]), str(mon_id[2])
            scale, transform, primary = logical_by_conn.get(conn, (1.0, 0, False))
            modes: list[DisplayMode] = []
            cur_mode = ""
            seen_res: set[tuple[int, int, int]] = set()
            for m_id, w, h, hz, pref_sc, sup_sc, mprops in raw_modes:
                is_cur = bool(mprops.get("is-current", False))
                if is_cur:
                    cur_mode = str(m_id)
                key = (int(w), int(h), round(float(hz)))
                if is_cur or key not in seen_res:
                    seen_res.add(key)
                    modes.append(DisplayMode(
                        mode_id=str(m_id),
                        width=int(w),
                        height=int(h),
                        refresh=round(float(hz), 2),
                        preferred_scale=float(pref_sc),
                        supported_scales=[round(float(s), 2) for s in sup_sc] or [1.0, 2.0],
                        is_current=is_cur,
                    ))
            monitors.append(MonitorState(conn, vendor, product, cur_mode, round(scale, 2), transform, primary, modes))
        return int(serial), monitors
    except Exception:
        pass

    if shutil.which("xrandr"):
        r = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=2, check=False)
        if r.returncode == 0:
            return 0, parse_xrandr_monitors(r.stdout)
    return 0, []


def apply_monitor_config(connector: str, mode_id: str, scale: float) -> tuple[bool, str]:
    """Apply display resolution and scale via Mutter DisplayConfig (or xrandr fallback)."""
    try:
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync(MUTTER_DEST, MUTTER_PATH, MUTTER_DEST, "GetCurrentState",
                            None, None, 0, 2000, None)
        serial, _raw_mons, raw_logical, _props = res.unpack()

        new_logical = []
        for x, y, cur_scale, transform, primary, conns, _lp in raw_logical:
            mon_entries = []
            use_scale = cur_scale
            for c_info in conns:
                c_name = str(c_info[0])
                if c_name == connector:
                    use_scale = float(scale)
                    mon_entries.append((c_name, mode_id, {}))
                else:
                    # Keep unchanged monitor current mode
                    mon_entries.append((c_name, "", {}))
            new_logical.append((int(x), int(y), float(use_scale), int(transform), bool(primary), mon_entries))

        params = GLib.Variant("(uua(iiduba(ssa{sv}))a{sv})", (int(serial), 2, new_logical, {}))
        bus.call_sync(MUTTER_DEST, MUTTER_PATH, MUTTER_DEST, "ApplyMonitorsConfig",
                      params, None, 0, 3000, None)
        return True, f"Applied {mode_id} @ {int(scale * 100)}% on {connector}"
    except Exception as err:
        if shutil.which("xrandr") and "@" in mode_id:
            res_part, hz_part = mode_id.split("@", 1)
            r = subprocess.run(["xrandr", "--output", connector, "--mode", res_part, "--rate", hz_part],
                               capture_output=True, text=True, timeout=3, check=False)
            if r.returncode == 0:
                return True, f"Applied {res_part} via xrandr"
            return False, r.stderr.strip() or str(err)
        return False, str(err)


# ---------------------------------------------------------------------- 4. Sound Profiles & Notifications

def discover_sound_themes(search_dirs: list[Path] | None = None) -> list[str]:
    dirs = search_dirs if search_dirs is not None else [
        Path.home() / ".local/share/sounds", Path("/usr/share/sounds")
    ]
    themes: set[str] = set()
    for base in dirs:
        if not base.is_dir():
            continue
        for d in base.iterdir():
            if d.is_dir() and ((d / "index.theme").is_file() or (d / "stereo").is_dir()):
                themes.add(d.name)
    return sorted(themes, key=str.lower) or ["Yaru", "freedesktop"]


def get_sound_prefs() -> dict[str, object]:
    return {
        "theme-name": _gsettings_get(SOUND_SCHEMA, "theme-name", "Yaru"),
        "event-sounds": _gsettings_get(SOUND_SCHEMA, "event-sounds", "true") == "true",
        "input-feedback-sounds": _gsettings_get(SOUND_SCHEMA, "input-feedback-sounds", "true") == "true",
        "allow-volume-above-100-percent": _gsettings_get(SOUND_SCHEMA, "allow-volume-above-100-percent", "false") == "true",
    }


def set_sound_pref(key: str, value: str | bool) -> tuple[bool, str]:
    return _gsettings_set(SOUND_SCHEMA, key, value)


def preview_sound(file_path: str | None = None) -> tuple[bool, str]:
    """Play a notification sound preview using pw-play, paplay, or canberra-gtk-play."""
    target = Path(file_path) if file_path else None
    if target and target.is_file():
        for cmd in ("pw-play", "paplay"):
            if shutil.which(cmd):
                subprocess.Popen([cmd, str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True, f"Playing {target.name}"
    if shutil.which("canberra-gtk-play"):
        subprocess.Popen(["canberra-gtk-play", "--id=message-new-instant"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, "Played system notification chime"
    return False, "No audio preview player (pw-play / paplay / canberra-gtk-play) found"


def get_notification_prefs() -> dict[str, bool]:
    return {
        "show-banners": _gsettings_get(NOTIF_SCHEMA, "show-banners", "true") == "true",
        "show-in-lock-screen": _gsettings_get(NOTIF_SCHEMA, "show-in-lock-screen", "true") == "true",
    }


def set_notification_pref(key: str, enabled: bool) -> tuple[bool, str]:
    return _gsettings_set(NOTIF_SCHEMA, key, enabled)


def list_app_notifications() -> list[AppNotificationPref]:
    raw = _gsettings_get(NOTIF_SCHEMA, "application-children", "[]")
    app_ids = re.findall(r"'([^']+)'", raw)
    prefs: list[AppNotificationPref] = []
    for app_id in app_ids[:40]:
        schema_path = f"{NOTIF_SCHEMA}.application:/org/gnome/desktop/notifications/application/{app_id}/"
        en = _gsettings_get(schema_path, "enable", "true") == "true"
        banners = _gsettings_get(schema_path, "show-banners", "true") == "true"
        label = app_id.replace("-", " ").title()
        prefs.append(AppNotificationPref(app_id=app_id, label=label, enabled=en, show_banners=banners))
    return prefs


def set_app_notification_enabled(app_id: str, enabled: bool) -> tuple[bool, str]:
    schema_path = f"{NOTIF_SCHEMA}.application:/org/gnome/desktop/notifications/application/{app_id}/"
    return _gsettings_set(schema_path, "enable", enabled)
