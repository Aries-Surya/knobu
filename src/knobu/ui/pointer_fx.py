"""Pointer Utilities UI & GNOME bridge: Find My Mouse spotlight, Click Highlighter, Crosshairs."""

from __future__ import annotations

import subprocess
import time

import cairo
import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from knobu.ui.capture import desktop_layout
from knobu.ui.tools import ToolApp


def sync_gnome_locate_pointer(enabled: bool) -> bool:
    """Sync GNOME native Ctrl pointer-locator ring (`locate-pointer`)."""
    from knobu.modules.commandbar.os_shortcuts import is_gnome
    if not is_gnome():
        return False
    try:
        r = subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "locate-pointer",
             "true" if enabled else "false"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class ShakeDetector:
    """Detects rapid back-and-forth horizontal mouse shake to trigger Find My Mouse."""

    def __init__(self, reversals_needed: int = 4, window_sec: float = 0.65, min_dx: int = 12):
        self.reversals_needed = reversals_needed
        self.window_sec = window_sec
        self.min_dx = min_dx
        self._last_dir = 0
        self._flips: list[float] = []
        self._last_trigger = float("-inf")

    def feed(self, dx: int, now: float | None = None) -> bool:
        if abs(dx) < self.min_dx:
            return False
        t = time.monotonic() if now is None else now
        direction = 1 if dx > 0 else -1
        if self._last_dir and direction != self._last_dir:
            self._flips = [ft for ft in self._flips if t - ft <= self.window_sec]
            self._flips.append(t)
            if len(self._flips) >= self.reversals_needed and (t - self._last_trigger) > 1.5:
                self._flips.clear()
                self._last_trigger = t
                self._last_dir = direction
                return True
        self._last_dir = direction
        return False


class FindMyMouseOverlay:
    """Transparent fullscreen spotlight overlay tracking the live cursor until clicked or Esc pressed."""

    def __init__(self, app: Gtk.Application, on_done):
        from knobu.modules.windows.zones import get_cursor_position
        self.app = app
        self.on_done = on_done
        self.finished = False
        self.cursor: tuple[Gtk.DrawingArea, float, float] | None = None
        self._init_pos = get_cursor_position()

        css = Gtk.CssProvider()
        css.load_from_string("window.knobu-spotlight { background-color: transparent; }")
        disp = Gdk.Display.get_default()
        if disp:
            Gtk.StyleContext.add_provider_for_display(
                disp, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        layout, _left, _top, _width = desktop_layout()
        app.hold()
        self.windows = [self._window(m, g.x, g.y, g.width, g.height) for m, g in layout]

    def _window(self, monitor, mx: int, my: int, w: int, h: int) -> Gtk.Window:
        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.set_draw_func(self._draw)
        if self._init_pos:
            gx, gy = self._init_pos
            if mx <= gx < mx + w and my <= gy < my + h:
                self.cursor = (area, float(gx - mx), float(gy - my))

        win = Gtk.Window(application=self.app, decorated=False, title="Knobu Find My Mouse", child=area)
        win.add_css_class("knobu-spotlight")

        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda _m, x, y, a=area: self._on_motion(a, x, y))
        motion.connect("motion", lambda _m, x, y, a=area: self._on_motion(a, x, y))
        area.add_controller(motion)

        click = Gtk.GestureClick()
        click.connect("released", lambda *_a: self._finish())
        area.add_controller(click)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, keyval, *_a:
                     self._finish() or True if keyval == Gdk.KEY_Escape else False)
        win.add_controller(keys)

        win.fullscreen_on_monitor(monitor)
        win.present()
        return win

    def _on_motion(self, area: Gtk.DrawingArea, x: float, y: float) -> None:
        self.cursor = (area, x, y)
        for win in self.windows:
            win.queue_draw()

    def _finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        for w in self.windows:
            w.destroy()
        self.on_done()
        self.app.release()

    def _draw(self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        cr.set_source_rgba(0, 0, 0, 0.58)
        cr.rectangle(0, 0, width, height)
        if self.cursor and self.cursor[0] is area:
            _, cx, cy = self.cursor
            cr.new_sub_path()
            cr.arc(cx, cy, 95, 0, 6.28318530718)
            cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            cr.fill()
            cr.set_source_rgba(1.0, 0.85, 0.25, 0.95)
            cr.set_line_width(3)
            cr.arc(cx, cy, 95, 0, 6.28318530718)
            cr.stroke()
        else:
            cr.fill()


class FindMyMouseApp(ToolApp):
    suffix = "FindMyMouse"

    def do_activate(self):
        self.hold()
        FindMyMouseOverlay(self, self.release)


def main() -> int:
    return FindMyMouseApp().run([])
