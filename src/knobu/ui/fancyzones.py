"""FancyZones interactive zone layout overlay (`Super+Shift+Grave`)."""

from __future__ import annotations

import gi
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk
import cairo

from knobu import APP_ID, config
from knobu.modules.windows import WindowModule, compute_zones, snap_active_window
from knobu.system import notify
from knobu.ui.tools import ToolApp


class FancyZonesOverlay(Gtk.Window):
    def __init__(self, application=None):
        super().__init__(application=application, decorated=False, title="Knobu FancyZones")
        self.set_icon_name(APP_ID)
        s = config.module_settings(config.load(), WindowModule.id, WindowModule.defaults)
        self.preset = str(s.get("zone_preset", "2col"))
        self.gap = int(s.get("zone_gap", 8))
        self.hover_idx = -1

        disp = Gdk.Display.get_default()
        mon = disp.get_monitors().get_item(0) if disp and disp.get_monitors().get_n_items() > 0 else None
        geo = mon.get_geometry() if mon else None
        sw = geo.width if geo else 1280
        sh = geo.height if geo else 720
        self.zones = compute_zones(self.preset, sw, sh, gap=self.gap)

        area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        area.set_draw_func(self._draw)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda _m, x, y: self._on_motion(x, y, area))
        area.add_controller(motion)

        click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        click.connect("pressed", lambda _g, _n, x, y: self._on_click(x, y))
        area.add_controller(click)

        keys_ctrl = Gtk.EventControllerKey()
        keys_ctrl.connect("key-pressed", lambda _c, kv, _kc, _st: self._on_key(kv))
        self.add_controller(keys_ctrl)

        self.set_child(area)
        if mon:
            self.fullscreen_on_monitor(mon)

    def _hit(self, x: float, y: float) -> int:
        for z in self.zones:
            if z.x <= x <= z.x + z.width and z.y <= y <= z.y + z.height:
                return z.index
        return -1

    def _on_motion(self, x: float, y: float, area: Gtk.DrawingArea) -> None:
        idx = self._hit(x, y)
        if idx != self.hover_idx:
            self.hover_idx = idx
            area.queue_draw()

    def _on_click(self, x: float, y: float) -> None:
        idx = self._hit(x, y)
        self.close()
        if idx >= 0:
            ok, msg = snap_active_window(idx, self.preset, self.gap)
            notify.notify("FancyZones", msg, timeout_ms=2000)

    def _on_key(self, kv: int) -> bool:
        if kv == Gdk.KEY_Escape:
            self.close()
            return True
        if Gdk.KEY_1 <= kv <= Gdk.KEY_9:
            idx = kv - Gdk.KEY_1
            if idx < len(self.zones):
                self.close()
                ok, msg = snap_active_window(idx, self.preset, self.gap)
                notify.notify("FancyZones", msg, timeout_ms=2000)
                return True
        return False

    def _draw(self, _area, cr: cairo.Context, w: int, h: int) -> None:
        cr.set_source_rgba(0.08, 0.09, 0.12, 0.55)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        for z in self.zones:
            hovered = z.index == self.hover_idx
            cr.set_source_rgba(0.25, 0.55, 0.95, 0.35 if hovered else 0.18)
            cr.rectangle(z.x, z.y, z.width, z.height)
            cr.fill_preserve()
            cr.set_source_rgba(0.45, 0.72, 1.0, 0.95 if hovered else 0.55)
            cr.set_line_width(2.5)
            cr.stroke()

            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(28)
            lbl = f"Zone {z.index + 1}"
            ext = cr.text_extents(lbl)
            cr.move_to(z.x + z.width / 2 - ext.width / 2, z.y + z.height / 2 + ext.height / 2)
            cr.show_text(lbl)


class FancyZonesApp(ToolApp):
    suffix = "fancyzones"

    def do_activate(self):
        FancyZonesOverlay(application=self).present()


def main() -> int:
    return FancyZonesApp().run([])
