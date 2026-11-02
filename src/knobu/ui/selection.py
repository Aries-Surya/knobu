"""Quiet area selection over a silent screenshot, for Text Extractor.

It opens looking exactly like the screen (no dimming, bars or menus); only the cursor
turns into a crosshair. The rest of the screen dims only while dragging, and the area
is captured as soon as the mouse is released. Esc or right-click cancels.
"""

from gi.repository import Gdk, Gtk

from knobu.ui.capture import desktop_layout

MIN_SIZE = 4  # smaller drags count as accidental clicks


class AreaSelection:
    """Calls on_done(cropped GdkPixbuf) or on_done(None) if cancelled."""

    def __init__(self, app: Gtk.Application, pixbuf, on_done):
        self.app = app
        self.pixbuf = pixbuf
        self.on_done = on_done
        self.drag = None  # (area, x0, y0, x1, y1)
        self.finished = False
        layout, left, top, width = desktop_layout()
        self.scale = pixbuf.get_width() / width
        app.hold()
        self.windows = [self._window(m, g.x - left, g.y - top, g.width, g.height)
                        for m, g in layout]

    def _window(self, monitor, ox, oy, w, h) -> Gtk.Window:
        s = self.scale
        x0, y0 = int(ox * s), int(oy * s)
        part = self.pixbuf.new_subpixbuf(
            x0, y0, min(int(w * s), self.pixbuf.get_width() - x0),
            min(int(h * s), self.pixbuf.get_height() - y0))
        picture = Gtk.Picture(paintable=Gdk.Texture.new_for_pixbuf(part),
                              content_fit=Gtk.ContentFit.FILL, can_shrink=True)
        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.origin = (ox, oy)
        area.set_draw_func(self._draw)
        overlay = Gtk.Overlay(child=picture)
        overlay.add_overlay(area)

        win = Gtk.Window(application=self.app, decorated=False, title="Knobu", child=overlay)
        win.set_cursor_from_name("crosshair")

        drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
        drag.connect("drag-begin", lambda _g, x, y: self._begin(area, x, y))
        drag.connect("drag-update", lambda _g, dx, dy: self._update(dx, dy))
        drag.connect("drag-end", lambda _g, dx, dy: self._end(dx, dy))
        area.add_controller(drag)

        right = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right.connect("released", lambda *_a: self._finish(None))
        area.add_controller(right)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, keyval, *_a:
                     self._finish(None) or True if keyval == Gdk.KEY_Escape else False)
        win.add_controller(keys)

        win.fullscreen_on_monitor(monitor)
        win.present()
        return win

    def _finish(self, result) -> None:
        if self.finished:
            return
        self.finished = True
        for win in self.windows:
            win.destroy()
        self.on_done(result)
        self.app.release()

    def _begin(self, area, x, y):
        self.drag = (area, x, y, x, y)

    def _update(self, dx, dy):
        if self.drag:
            area, x0, y0, _, _ = self.drag
            self.drag = (area, x0, y0, x0 + dx, y0 + dy)
            area.queue_draw()

    def _end(self, dx, dy):
        if not self.drag:
            return
        area, x0, y0, _, _ = self.drag
        if abs(dx) < MIN_SIZE or abs(dy) < MIN_SIZE:
            self.drag = None
            area.queue_draw()
            return
        ox, oy = area.origin
        s = self.scale
        ax = int((ox + min(x0, x0 + dx)) * s)
        ay = int((oy + min(y0, y0 + dy)) * s)
        w = min(int(abs(dx) * s), self.pixbuf.get_width() - ax)
        h = min(int(abs(dy) * s), self.pixbuf.get_height() - ay)
        self._finish(self.pixbuf.new_subpixbuf(max(ax, 0), max(ay, 0), max(w, 1), max(h, 1)).copy())

    def _draw(self, area, cr, width, height):
        if not (self.drag and self.drag[0] is area):
            return  # looks exactly like the screen until a drag starts
        _, x0, y0, x1, y1 = self.drag
        x, y, w, h = min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.rectangle(0, 0, width, height)
        cr.rectangle(x, y, w, h)
        cr.set_fill_rule(1)  # even-odd: dim everything except the selection
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.set_line_width(2)
        cr.rectangle(x, y, w, h)
        cr.stroke()
