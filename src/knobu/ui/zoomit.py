"""ZoomIt: screen freeze-zoom & quick pen/arrow/box annotation over captured desktop."""

from __future__ import annotations

import math
import cairo
import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk

from knobu.system import notify
from knobu.ui.capture import capture_screen, desktop_layout
from knobu.ui.tools import ToolApp


class ZoomItOverlay:
    """Fullscreen frozen-screen zoom + annotation overlay (Pen / Arrow / Box)."""

    def __init__(self, app: Gtk.Application, pixbuf, on_done):
        self.app = app
        self.pixbuf = pixbuf
        self.on_done = on_done
        self.finished = False
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.mode = "pen"  # pen | arrow | box
        self.strokes: list[tuple[str, list[tuple[float, float]]]] = []
        self.active_stroke: tuple[str, list[tuple[float, float]]] | None = None

        layout, left, top, width = desktop_layout()
        self.scale = (pixbuf.get_width() / width) if pixbuf else 1.0
        app.hold()
        self.windows = [self._window(m, g.x - left, g.y - top, g.width, g.height) for m, g in layout]

    def _window(self, monitor, ox: int, oy: int, w: int, h: int) -> Gtk.Window:
        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.set_draw_func(lambda a, cr, aw, ah: self._draw(cr, aw, ah, ox, oy))

        win = Gtk.Window(application=self.app, decorated=False, title="Knobu ZoomIt", child=area)
        win.set_cursor_from_name("crosshair")

        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", lambda _s, _dx, dy: self._on_scroll(dy, area))
        area.add_controller(scroll)

        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", lambda _g, x, y: self._drag_begin(x, y, area))
        drag.connect("drag-update", lambda _g, dx, dy: self._drag_update(dx, dy, area))
        drag.connect("drag-end", lambda _g, dx, dy: self._drag_end(area))
        area.add_controller(drag)

        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("released", lambda *_a: self._finish())
        area.add_controller(right)

        keys_ctrl = Gtk.EventControllerKey()
        keys_ctrl.connect("key-pressed", lambda _c, kv, _kc, st: self._on_key(kv, st, area))
        win.add_controller(keys_ctrl)

        win.fullscreen_on_monitor(monitor)
        win.present()
        return win

    def _on_scroll(self, dy: float, area: Gtk.DrawingArea) -> bool:
        factor = 1.15 if dy < 0 else (1.0 / 1.15)
        self.zoom = max(1.0, min(6.0, self.zoom * factor))
        area.queue_draw()
        return True

    def _to_canvas(self, sx: float, sy: float) -> tuple[float, float]:
        return (sx / self.zoom + self.pan_x, sy / self.zoom + self.pan_y)

    def _drag_begin(self, x: float, y: float, area: Gtk.DrawingArea) -> None:
        self._drag_origin = (x, y)
        pt = self._to_canvas(x, y)
        self.active_stroke = (self.mode, [pt])
        area.queue_draw()

    def _drag_update(self, dx: float, dy: float, area: Gtk.DrawingArea) -> None:
        if not self.active_stroke:
            return
        pt = self._to_canvas(self._drag_origin[0] + dx, self._drag_origin[1] + dy)
        if self.mode == "pen":
            self.active_stroke[1].append(pt)
        else:
            self.active_stroke[1][1:] = [pt]
        area.queue_draw()

    def _drag_end(self, area: Gtk.DrawingArea) -> None:
        if self.active_stroke and len(self.active_stroke[1]) >= 2:
            self.strokes.append(self.active_stroke)
        self.active_stroke = None
        area.queue_draw()

    def _on_key(self, keyval: int, state: Gdk.ModifierType, area: Gtk.DrawingArea) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._finish()
            return True
        if keyval in (Gdk.KEY_1, Gdk.KEY_p):
            self.mode = "pen"
        elif keyval in (Gdk.KEY_2, Gdk.KEY_a):
            self.mode = "arrow"
        elif keyval in (Gdk.KEY_3, Gdk.KEY_b, Gdk.KEY_r):
            self.mode = "box"
        elif keyval == Gdk.KEY_c:
            self.strokes.clear()
        elif keyval == Gdk.KEY_z and (state & Gdk.ModifierType.CONTROL_MASK) and self.strokes:
            self.strokes.pop()
        area.queue_draw()
        return False

    def _draw(self, cr: cairo.Context, w: int, h: int, ox: int, oy: int) -> None:
        cr.save()
        cr.scale(self.zoom, self.zoom)
        if self.pixbuf:
            s = self.scale
            x0, y0 = int(ox * s), int(oy * s)
            part = self.pixbuf.new_subpixbuf(
                x0, y0, min(int(w * s), self.pixbuf.get_width() - x0),
                min(int(h * s), self.pixbuf.get_height() - y0))
            cr.save()
            cr.scale(1.0 / s, 1.0 / s)
            Gdk.cairo_set_source_pixbuf(cr, part, 0, 0)
            cr.paint()
            cr.restore()

        cr.set_source_rgba(0.95, 0.25, 0.25, 0.95)
        cr.set_line_width(3.0 / self.zoom)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        all_strokes = [*self.strokes, *([self.active_stroke] if self.active_stroke else [])]
        for kind, pts in all_strokes:
            if len(pts) < 2:
                continue
            if kind == "pen":
                cr.move_to(*pts[0])
                for p in pts[1:]:
                    cr.line_to(*p)
                cr.stroke()
            elif kind == "box":
                x1, y1 = pts[0]
                x2, y2 = pts[-1]
                cr.rectangle(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
                cr.stroke()
            elif kind == "arrow":
                x1, y1 = pts[0]
                x2, y2 = pts[-1]
                cr.move_to(x1, y1)
                cr.line_to(x2, y2)
                cr.stroke()
                ang = math.atan2(y2 - y1, x2 - x1)
                head = 16.0 / self.zoom
                for side in (ang + 2.6, ang - 2.6):
                    cr.move_to(x2, y2)
                    cr.line_to(x2 + head * math.cos(side), y2 + head * math.sin(side))
                    cr.stroke()
        cr.restore()

        # Compact HUD hint pill
        cr.set_source_rgba(0.1, 0.1, 0.12, 0.85)
        cr.rectangle(16, 16, 410, 32)
        cr.fill()
        cr.set_source_rgb(0.95, 0.95, 0.98)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12)
        cr.move_to(26, 36)
        cr.show_text(f"Zoom {self.zoom:.1f}x · Mode: {self.mode.upper()}  (1:Pen 2:Arrow 3:Box · Scroll:Zoom · Esc:Exit)")

    def _finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        for w in self.windows:
            w.close()
        self.app.release()
        self.on_done()


class ZoomItApp(ToolApp):
    suffix = "zoomit"

    def do_activate(self):
        pixbuf = capture_screen()
        if not pixbuf:
            notify.notify("ZoomIt", "Could not capture screen for ZoomIt.", timeout_ms=2500)
        ZoomItOverlay(self, pixbuf, lambda: None)


def main() -> int:
    return ZoomItApp().run([])
