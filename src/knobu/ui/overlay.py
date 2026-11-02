"""A full-screen overlay over a frozen screenshot, for picking a pixel or selecting an area.

The screen is captured silently first, then shown full-screen on every monitor with
Knobu's own tools on top: a magnifier for picking colours, or a selection box for
selecting text. Nothing of the desktop's own screenshot UI appears.
"""

import os
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import unquote, urlparse

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from knobu.system import portal

MAGNIFIER_CELLS = 15     # pixels shown across the magnifier (odd, so one is centred)
MAGNIFIER_ZOOM = 9       # on-screen size of each magnified pixel
MAGNIFIER_OFFSET = 24    # distance between the cursor and the magnifier
MIN_SELECTION = 4        # smaller drags count as accidental clicks


def is_kde() -> bool:
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "")


def capture_screen(callback) -> None:
    """Silently capture the whole desktop; callback(GdkPixbuf.Pixbuf or None)."""
    if is_kde() and shutil.which("spectacle"):
        fd, path = tempfile.mkstemp(prefix="knobu-", suffix=".png")
        os.close(fd)
        os.unlink(path)  # spectacle creates it; a missing file means it failed

        def run():
            subprocess.run(["spectacle", "--background", "--fullscreen", "--nonotify",
                            "--output", path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            GLib.idle_add(_load, path, True, callback)
        threading.Thread(target=run, daemon=True).start()
    else:
        portal.screenshot(lambda uri: _load(unquote(urlparse(uri).path), False, callback)
                          if uri else callback(None), interactive=False)


def _load(path: str, temporary: bool, callback) -> bool:
    pixbuf = None
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
    except GLib.Error:
        pass
    finally:
        if temporary and os.path.exists(path):
            os.unlink(path)
    callback(pixbuf)
    return GLib.SOURCE_REMOVE


class ScreenOverlay:
    """Shows `pixbuf` full-screen on every monitor.

    mode "pick":   on_done((r, g, b)) with 0..255 ints when a pixel is clicked.
    mode "select": on_done(cropped Pixbuf) when an area is dragged.
    on_done(None) when cancelled with Esc or right-click.
    """

    def __init__(self, app: Gtk.Application, pixbuf: GdkPixbuf.Pixbuf, mode: str, hint: str,
                 on_done):
        self.app = app
        self.pixbuf = pixbuf
        self.mode = mode
        self.on_done = on_done
        self.pixels = pixbuf.read_pixel_bytes().get_data()
        self.rowstride = pixbuf.get_rowstride()
        self.channels = pixbuf.get_n_channels()
        self.pointer = None    # (area, x, y) in that monitor's logical coordinates
        self.nudge = (0, 0)    # arrow-key fine-tuning, in screenshot pixels
        self.drag = None       # (area, x0, y0, x1, y1) while selecting
        self.finished = False

        monitors = list(Gdk.Display.get_default().get_monitors())
        geometries = [m.get_geometry() for m in monitors]
        left = min(g.x for g in geometries)
        top = min(g.y for g in geometries)
        width = max(g.x + g.width for g in geometries) - left
        # Screenshot pixels per logical pixel (assumes one scale for all monitors).
        self.scale = pixbuf.get_width() / width

        app.hold()
        self.windows = [self._window(m, g.x - left, g.y - top, g.width, g.height, hint)
                        for m, g in zip(monitors, geometries)]

    # ------------------------------------------------------------------ windows

    def _window(self, monitor, ox, oy, w, h, hint) -> Gtk.Window:
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

        label = Gtk.Label(label=hint)
        bar = Gtk.Box(css_classes=["osd", "toolbar"], halign=Gtk.Align.CENTER,
                      valign=Gtk.Align.START, margin_top=24, can_target=False)
        bar.append(label)

        overlay = Gtk.Overlay(child=picture)
        overlay.add_overlay(area)
        overlay.add_overlay(bar)

        win = Gtk.Window(application=self.app, decorated=False, title="Knobu", child=overlay)
        win.set_cursor_from_name("crosshair")

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda _c, x, y: self._on_motion(area, x, y))
        motion.connect("leave", lambda _c: self._on_leave(area))
        area.add_controller(motion)

        click = Gtk.GestureClick(button=0)
        click.connect("released", lambda g, _n, x, y: self._on_click(g, area, x, y))
        area.add_controller(click)

        if self.mode == "select":
            drag = Gtk.GestureDrag(button=Gdk.BUTTON_PRIMARY)
            drag.connect("drag-begin", lambda _g, x, y: self._drag_begin(area, x, y))
            drag.connect("drag-update", lambda _g, dx, dy: self._drag_update(dx, dy))
            drag.connect("drag-end", lambda _g, dx, dy: self._drag_end(dx, dy))
            area.add_controller(drag)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
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

    # ------------------------------------------------------------------ input

    def _image_xy(self, area, x, y) -> tuple[int, int]:
        ox, oy = area.origin
        ix = int((ox + x) * self.scale) + self.nudge[0]
        iy = int((oy + y) * self.scale) + self.nudge[1]
        return (min(max(ix, 0), self.pixbuf.get_width() - 1),
                min(max(iy, 0), self.pixbuf.get_height() - 1))

    def pixel(self, ix: int, iy: int) -> tuple[int, int, int]:
        offset = iy * self.rowstride + ix * self.channels
        return tuple(self.pixels[offset:offset + 3])

    def _on_motion(self, area, x, y):
        self.pointer = (area, x, y)
        self.nudge = (0, 0)
        if self.mode == "pick":
            area.queue_draw()

    def _on_leave(self, area):
        if self.pointer and self.pointer[0] is area:
            self.pointer = None
            area.queue_draw()

    def _on_click(self, gesture, area, x, y):
        button = gesture.get_current_button()
        if button == Gdk.BUTTON_SECONDARY:
            self._finish(None)
        elif button == Gdk.BUTTON_PRIMARY and self.mode == "pick":
            self.pointer = (area, x, y)
            self._finish(self.pixel(*self._image_xy(area, x, y)))

    def _on_key(self, _ctrl, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape:
            self._finish(None)
            return True
        if self.mode != "pick" or not self.pointer:
            return False
        moves = {Gdk.KEY_Left: (-1, 0), Gdk.KEY_Right: (1, 0),
                 Gdk.KEY_Up: (0, -1), Gdk.KEY_Down: (0, 1)}
        if keyval in moves:
            dx, dy = moves[keyval]
            self.nudge = (self.nudge[0] + dx, self.nudge[1] + dy)
            self.pointer[0].queue_draw()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._finish(self.pixel(*self._image_xy(*self.pointer)))
            return True
        return False

    def _drag_begin(self, area, x, y):
        self.drag = (area, x, y, x, y)

    def _drag_update(self, dx, dy):
        if self.drag:
            area, x0, y0, _, _ = self.drag
            self.drag = (area, x0, y0, x0 + dx, y0 + dy)
            area.queue_draw()

    def _drag_end(self, dx, dy):
        if not self.drag:
            return
        area, x0, y0, _, _ = self.drag
        x1, y1 = x0 + dx, y0 + dy
        if abs(dx) < MIN_SELECTION or abs(dy) < MIN_SELECTION:
            self.drag = None
            area.queue_draw()
            return
        ax, ay = self._image_xy(area, min(x0, x1), min(y0, y1))
        bx, by = self._image_xy(area, max(x0, x1), max(y0, y1))
        crop = self.pixbuf.new_subpixbuf(ax, ay, max(bx - ax, 1), max(by - ay, 1)).copy()
        self._finish(crop)

    # ------------------------------------------------------------------ drawing

    def _draw(self, area, cr, width, height):
        if self.mode == "select":
            self._draw_selection(area, cr, width, height)
        elif self.pointer and self.pointer[0] is area:
            self._draw_magnifier(cr, width, height, *self.pointer[1:], area)

    def _draw_selection(self, area, cr, width, height):
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.rectangle(0, 0, width, height)
        if self.drag and self.drag[0] is area:
            _, x0, y0, x1, y1 = self.drag
            x, y, w, h = min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
            cr.rectangle(x, y, w, h)
            cr.set_fill_rule(1)  # even-odd: dim everything except the selection
            cr.fill()
            cr.set_source_rgba(1, 1, 1, 0.95)
            cr.set_line_width(2)
            cr.rectangle(x, y, w, h)
            cr.stroke()
        else:
            cr.fill()

    def _draw_magnifier(self, cr, width, height, x, y, area):
        cx, cy = self._image_xy(area, x, y)
        size = MAGNIFIER_CELLS * MAGNIFIER_ZOOM
        label_h = 30
        # Sit below-right of the cursor, flipping near the screen edges.
        mx = x + MAGNIFIER_OFFSET if x + MAGNIFIER_OFFSET + size < width else x - MAGNIFIER_OFFSET - size
        my = y + MAGNIFIER_OFFSET
        if my + size + label_h > height:
            my = y - MAGNIFIER_OFFSET - size - label_h

        half = MAGNIFIER_CELLS // 2
        cr.save()
        _rounded(cr, mx, my, size, size, 12)
        cr.clip()
        for row in range(MAGNIFIER_CELLS):
            for col in range(MAGNIFIER_CELLS):
                ix, iy = cx + col - half, cy + row - half
                if 0 <= ix < self.pixbuf.get_width() and 0 <= iy < self.pixbuf.get_height():
                    r, g, b = self.pixel(ix, iy)
                    cr.set_source_rgb(r / 255, g / 255, b / 255)
                else:
                    cr.set_source_rgb(0.1, 0.1, 0.1)
                cr.rectangle(mx + col * MAGNIFIER_ZOOM, my + row * MAGNIFIER_ZOOM,
                             MAGNIFIER_ZOOM, MAGNIFIER_ZOOM)
                cr.fill()
        # Faint pixel grid.
        cr.set_source_rgba(0, 0, 0, 0.12)
        cr.set_line_width(1)
        for i in range(1, MAGNIFIER_CELLS):
            cr.move_to(mx + i * MAGNIFIER_ZOOM + 0.5, my)
            cr.line_to(mx + i * MAGNIFIER_ZOOM + 0.5, my + size)
            cr.move_to(mx, my + i * MAGNIFIER_ZOOM + 0.5)
            cr.line_to(mx + size, my + i * MAGNIFIER_ZOOM + 0.5)
        cr.stroke()
        cr.restore()

        # Centre pixel: black and white outline so it shows on any colour.
        px, py = mx + half * MAGNIFIER_ZOOM, my + half * MAGNIFIER_ZOOM
        cr.set_line_width(2)
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(px - 1, py - 1, MAGNIFIER_ZOOM + 2, MAGNIFIER_ZOOM + 2)
        cr.stroke()
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(px - 3, py - 3, MAGNIFIER_ZOOM + 6, MAGNIFIER_ZOOM + 6)
        cr.stroke()

        # Border.
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.set_line_width(2)
        _rounded(cr, mx, my, size, size, 12)
        cr.stroke()

        # Colour value under the magnifier.
        r, g, b = self.pixel(cx, cy)
        text = f"#{r:02X}{g:02X}{b:02X}"
        ly = my + size + 6
        cr.set_source_rgba(0, 0, 0, 0.75)
        _rounded(cr, mx, ly, size, label_h - 6, 8)
        cr.fill()
        cr.set_source_rgb(r / 255, g / 255, b / 255)
        _rounded(cr, mx + 6, ly + 5, 14, 14, 3)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.select_font_face("Monospace", 0, 1)
        cr.set_font_size(13)
        cr.move_to(mx + 28, ly + 17)
        cr.show_text(text)


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    cr.arc(x + r, y + r, r, 3.1416, 4.7124)
    cr.close_path()
