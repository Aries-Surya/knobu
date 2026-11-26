"""Screen Ruler: measure pixel distances, box dimensions, and alignment spacing on screen."""

from __future__ import annotations

import math
import cairo
import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from knobu.system import notify
from knobu.ui.capture import capture_screen, desktop_layout
from knobu.ui.tools import ToolApp, copy_text


def measure_box(x0: float, y0: float, x1: float, y1: float) -> tuple[int, int, int]:
    """Return (width_px, height_px, diagonal_px) rounded to integers."""
    w = abs(round(x1 - x0))
    h = abs(round(y1 - y0))
    diag = round(math.hypot(x1 - x0, y1 - y0))
    return w, h, diag


class ScreenRulerOverlay:
    """Fullscreen measurement overlay showing cursor crosshairs and drag box dimensions."""

    def __init__(self, app: Gtk.Application, pixbuf, on_done):
        self.app = app
        self.pixbuf = pixbuf
        self.on_done = on_done
        self.finished = False
        self.pointer: tuple[Gtk.DrawingArea, float, float] | None = None
        self.drag: tuple[Gtk.DrawingArea, float, float, float, float] | None = None
        self.last_measurement: str = ""

        layout, left, top, width = desktop_layout()
        self.scale = (pixbuf.get_width() / width) if pixbuf else 1.0
        app.hold()
        self.windows = [self._window(m, g.x - left, g.y - top, g.width, g.height)
                        for m, g in layout]

    def _window(self, monitor, ox: int, oy: int, w: int, h: int) -> Gtk.Window:
        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.set_draw_func(self._draw)

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

        win = Gtk.Window(application=self.app, decorated=False, title="Knobu Screen Ruler", child=child)
        win.set_cursor_from_name("crosshair")

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda _m, x, y, a=area: self._on_motion(a, x, y))
        area.add_controller(motion)

        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", lambda _g, x, y, a=area: self._on_drag_begin(a, x, y))
        drag.connect("drag-update", lambda _g, dx, dy: self._on_drag_update(dx, dy))
        drag.connect("drag-end", lambda _g, dx, dy: self._on_drag_end(dx, dy))
        area.add_controller(drag)

        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("released", lambda *_a: self._finish())
        area.add_controller(right)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        win.add_controller(keys)

        win.fullscreen_on_monitor(monitor)
        win.present()
        return win

    def _on_key(self, _ctrl, keyval, _keycode, state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._finish()
            return True
        if keyval == Gdk.KEY_c and (state & Gdk.ModifierType.CONTROL_MASK) and self.last_measurement:
            copy_text(self.windows[0], self.last_measurement)
            notify.notify("Screen Ruler", f"Copied {self.last_measurement}", timeout_ms=2000)
            self._finish()
            return True
        return False

    def _on_motion(self, area: Gtk.DrawingArea, x: float, y: float) -> None:
        self.pointer = (area, x, y)
        area.queue_draw()

    def _on_drag_begin(self, area: Gtk.DrawingArea, x: float, y: float) -> None:
        self.drag = (area, x, y, x, y)
        area.queue_draw()

    def _on_drag_update(self, dx: float, dy: float) -> None:
        if self.drag:
            area, x0, y0, _, _ = self.drag
            self.drag = (area, x0, y0, x0 + dx, y0 + dy)
            w, h, diag = measure_box(x0 * self.scale, y0 * self.scale,
                                     (x0 + dx) * self.scale, (y0 + dy) * self.scale)
            self.last_measurement = f"{w} x {h} px (diag {diag} px)"
            area.queue_draw()

    def _on_drag_end(self, dx: float, dy: float) -> None:
        if self.drag and (abs(dx) >= 4 or abs(dy) >= 4) and self.last_measurement:
            copy_text(self.windows[0], self.last_measurement)
            notify.notify("Screen Ruler", f"Copied {self.last_measurement}", timeout_ms=2000)

    def _finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        for w in self.windows:
            w.destroy()
        self.on_done()
        self.app.release()

    def _draw_pill(self, cr: cairo.Context, cx: float, cy: float, label: str) -> None:
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(13)
        ext = cr.text_extents(label)
        pw, ph = ext.width + 18, ext.height + 12
        px, py = max(8.0, cx - pw / 2), max(8.0, cy - ph / 2)
        cr.set_source_rgba(0.08, 0.08, 0.11, 0.9)
        cr.rectangle(px, py, pw, ph)
        cr.fill()
        cr.set_source_rgba(0.35, 0.75, 1.0, 0.95)
        cr.set_line_width(1)
        cr.rectangle(px, py, pw, ph)
        cr.stroke()
        cr.set_source_rgba(1, 1, 1, 1)
        cr.move_to(px + 9, py + ph - 6)
        cr.show_text(label)

    def _draw(self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        if not self.pixbuf:
            cr.set_source_rgba(0, 0, 0, 0.35)
            cr.rectangle(0, 0, width, height)
            cr.fill()

        if self.pointer and self.pointer[0] is area:
            _, px, py = self.pointer
            cr.set_source_rgba(0.25, 0.72, 1.0, 0.75)
            cr.set_line_width(1)
            cr.move_to(0, py)
            cr.line_to(width, py)
            cr.move_to(px, 0)
            cr.line_to(px, height)
            cr.stroke()
            if not self.drag:
                self._draw_pill(cr, min(width - 90, px + 70), max(24, py - 24),
                                f"{round(px * self.scale)}, {round(py * self.scale)} px")

        if self.drag and self.drag[0] is area:
            _, x0, y0, x1, y1 = self.drag
            x, y, rw, rh = min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
            cr.set_source_rgba(0.25, 0.72, 1.0, 0.16)
            cr.rectangle(x, y, rw, rh)
            cr.fill()
            cr.set_source_rgba(0.35, 0.8, 1.0, 0.95)
            cr.set_line_width(2)
            cr.rectangle(x, y, rw, rh)
            cr.stroke()
            # Diagonal ruler line
            cr.set_dash([5.0, 4.0])
            cr.move_to(x0, y0)
            cr.line_to(x1, y1)
            cr.stroke()
            cr.set_dash([])
            w_px, h_px, diag_px = measure_box(x0 * self.scale, y0 * self.scale,
                                              x1 * self.scale, y1 * self.scale)
            self._draw_pill(cr, x + rw / 2, max(28, y - 16),
                            f"{w_px} × {h_px} px  (diag {diag_px} px)")


class ScreenRulerApp(ToolApp):
    suffix = "ScreenRuler"

    def do_activate(self):
        self.hold()
        capture_screen(self._on_screen)

    def _on_screen(self, pixbuf):
        ScreenRulerOverlay(self, pixbuf, self.release)


def main() -> int:
    return ScreenRulerApp().run([])
