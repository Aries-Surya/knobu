"""Pointer Utilities UI & GNOME bridge: Find My Mouse spotlight, Click Highlighter, Crosshairs."""

from __future__ import annotations

import subprocess
import time

import cairo
import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from knobu.ui.capture import capture_screen, desktop_layout
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
    """Fullscreen spotlight overlay dimming around the cursor until clicked or Esc pressed."""

    def __init__(self, app: Gtk.Application, pixbuf, on_done):
        self.app = app
        self.pixbuf = pixbuf
        self.on_done = on_done
        self.finished = False
        self.cursor: tuple[Gtk.DrawingArea, float, float] | None = None

        layout, left, top, width = desktop_layout()
        self.scale = (pixbuf.get_width() / width) if pixbuf else 1.0
        app.hold()
        self.windows = [self._window(m, g.x - left, g.y - top, g.width, g.height)
                        for m, g in layout]

    def _window(self, monitor, ox: int, oy: int, w: int, h: int) -> Gtk.Window:
        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.set_draw_func(self._draw)
        self.cursor = self.cursor or (area, w / 2, h / 2)

        if self.pixbuf:
            s = self.scale
            x0, y0 = int(ox * s), int(oy * s)
            part = self.pixbuf.new_subpixbuf(
                x0, y0, min(int(w * s), self.pixbuf.get_width() - x0),
                min(int(h * s), self.pixbuf.get_height() - y0))
            bg = Gtk.Picture(paintable=Gdk.Texture.new_for_pixbuf(part),
                             content_fit=Gtk.ContentFit.FILL, can_shrink=True)
            overlay = Gtk.Overlay(child=bg)
            overlay.add_overlay(area)
            child = overlay
        else:
            child = area

        win = Gtk.Window(application=self.app, decorated=False, title="Knobu Find My Mouse", child=child)
        motion = Gtk.EventControllerMotion()
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
        capture_screen(self._on_screen)

    def _on_screen(self, pixbuf):
        FindMyMouseOverlay(self, pixbuf, self.release)


def main() -> int:
    return FindMyMouseApp().run([])
