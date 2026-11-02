"""A small magnifier window that follows the cursor while the desktop's picker is active,
like PowerToys' Color Picker on Windows.

Wayland doesn't let apps read the cursor position or move their windows, but KWin
scripts can do both: a temporary script reports the cursor to us over D-Bus and keeps
the magnifier next to it, on top. Pixels come from a silent screenshot taken just
before, so nothing covers or freezes the screen. KDE only; elsewhere there's no
magnifier.
"""

import os
from pathlib import Path

from gi.repository import Gdk, Gio, GLib, Gtk

from knobu.ui.capture import Pixels, desktop_layout

CELLS = 15      # pixels across (odd, so one sits in the middle)
ZOOM = 9        # on-screen size of each pixel
LABEL = 30      # height of the colour label under the zoom
OFFSET = 24     # gap between cursor and magnifier

INTERFACE = "io.github.Saad_1719.Knobu.Magnifier"
INTERFACE_XML = f"""<node><interface name="{INTERFACE}">
  <method name="Cursor"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
</interface></node>"""

KWIN_SCRIPT = """
const title = %(title)s;
const offset = %(offset)d;
let win = null;

function update() {
    const p = workspace.cursorPos;
    callDBus(%(service)s, "/magnifier", %(iface)s, "Cursor", p.x, p.y);
    if (!win) {
        win = workspace.windowList().find(w => w.caption === title) || null;
        if (!win) return;
        win.keepAbove = true;
        win.skipTaskbar = true;
        win.skipPager = true;
        win.skipSwitcher = true;
        win.noBorder = true;
    }
    const g = win.frameGeometry;
    const screen = workspace.virtualScreenGeometry;
    let x = p.x + offset, y = p.y + offset;
    if (x + g.width > screen.x + screen.width) x = p.x - offset - g.width;
    if (y + g.height > screen.y + screen.height) y = p.y - offset - g.height;
    win.frameGeometry = {x: x, y: y, width: g.width, height: g.height};
}

workspace.cursorPosChanged.connect(update);
workspace.windowAdded.connect(update);
update();
"""

CSS = b".knobu-magnifier { background: transparent; }"


class Magnifier:
    def __init__(self, app: Gtk.Application, pixbuf):
        self.pixels = Pixels(pixbuf)
        _layout, self.left, self.top, width = desktop_layout()
        self.scale = pixbuf.get_width() / width  # screenshot pixels per logical pixel
        self.cursor: tuple[int, int] | None = None
        self.title = f"Knobu Magnifier {os.getpid()}"
        self.plugin = f"knobu-magnifier-{os.getpid()}"
        self.script_path = Path(GLib.get_user_runtime_dir()) / f"{self.plugin}.js"
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        size = CELLS * ZOOM
        self.area = Gtk.DrawingArea(content_width=size, content_height=size + LABEL)
        self.area.set_draw_func(self._draw)
        self.window = Gtk.Window(application=app, title=self.title, decorated=False,
                                 resizable=False, child=self.area, css_classes=["knobu-magnifier"],
                                 can_focus=False)
        self.window.set_opacity(0)  # stay invisible until KWin has moved it to the cursor

        info = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML).interfaces[0]
        self.registration = self.bus.register_object_with_closures2(
            "/magnifier", info, self._on_call, None, None)
        self.window.present()
        self.loaded = self._load_script()

    def stop(self) -> None:
        if self.loaded:
            self._kwin("unloadScript", GLib.Variant("(s)", (self.plugin,)))
        self.script_path.unlink(missing_ok=True)
        self.bus.unregister_object(self.registration)
        self.window.destroy()

    # ------------------------------------------------------------------ KWin

    def _kwin(self, method: str, args: GLib.Variant | None = None, path: str = "/Scripting",
              iface: str = "org.kde.kwin.Scripting"):
        try:
            return self.bus.call_sync("org.kde.KWin", path, iface, method, args, None,
                                      Gio.DBusCallFlags.NONE, 3000, None)
        except GLib.Error:
            return None

    def _load_script(self) -> bool:
        def js(s: str) -> str:
            return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
        self.script_path.write_text(KWIN_SCRIPT % {
            "title": js(self.title), "offset": OFFSET,
            "service": js(self.bus.get_unique_name()), "iface": js(INTERFACE)})
        reply = self._kwin("loadScript", GLib.Variant("(ss)", (str(self.script_path), self.plugin)))
        if reply is None:
            return False
        script_id = reply.unpack()[0]
        if self._kwin("run", path=f"/Scripting/Script{script_id}",
                      iface="org.kde.kwin.Script") is None:
            self._kwin("start")
        return True

    def _on_call(self, _conn, _sender, _path, _iface, method, params, invocation):
        if method == "Cursor":
            self.cursor = params.unpack()
            if self.window.get_opacity() == 0:
                GLib.timeout_add(50, lambda: self.window.set_opacity(1) or False)
            self.area.queue_draw()
        invocation.return_value(None)

    # ------------------------------------------------------------------ drawing

    def _draw(self, _area, cr, width, _height):
        if self.cursor is None:
            return
        cx = int((self.cursor[0] - self.left) * self.scale)
        cy = int((self.cursor[1] - self.top) * self.scale)
        size = CELLS * ZOOM
        half = CELLS // 2

        cr.save()
        _rounded(cr, 1, 1, size - 2, size - 2, 12)
        cr.clip()
        for row in range(CELLS):
            for col in range(CELLS):
                rgb = self.pixels.get(cx + col - half, cy + row - half)
                r, g, b = rgb if rgb else (20, 20, 20)
                cr.set_source_rgb(r / 255, g / 255, b / 255)
                cr.rectangle(col * ZOOM, row * ZOOM, ZOOM, ZOOM)
                cr.fill()
        cr.set_source_rgba(0, 0, 0, 0.12)  # faint pixel grid
        cr.set_line_width(1)
        for i in range(1, CELLS):
            cr.move_to(i * ZOOM + 0.5, 0)
            cr.line_to(i * ZOOM + 0.5, size)
            cr.move_to(0, i * ZOOM + 0.5)
            cr.line_to(size, i * ZOOM + 0.5)
        cr.stroke()
        cr.restore()

        # Centre pixel outlined in black and white so it shows on any colour.
        p = half * ZOOM
        cr.set_line_width(2)
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(p - 1, p - 1, ZOOM + 2, ZOOM + 2)
        cr.stroke()
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(p - 3, p - 3, ZOOM + 6, ZOOM + 6)
        cr.stroke()
        cr.set_source_rgba(1, 1, 1, 0.9)
        _rounded(cr, 1, 1, size - 2, size - 2, 12)
        cr.stroke()

        # Colour value.
        r, g, b = self.pixels.get(cx, cy) or (0, 0, 0)
        y = size + 4
        cr.set_source_rgba(0.1, 0.1, 0.1, 0.85)
        _rounded(cr, 0, y, width, LABEL - 4, 8)
        cr.fill()
        cr.set_source_rgb(r / 255, g / 255, b / 255)
        _rounded(cr, 7, y + 6, 14, 14, 3)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.select_font_face("Monospace", 0, 1)
        cr.set_font_size(13)
        cr.move_to(30, y + 18)
        cr.show_text(f"#{r:02X}{g:02X}{b:02X}")


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    cr.arc(x + r, y + r, r, 3.1416, 4.7124)
    cr.close_path()
