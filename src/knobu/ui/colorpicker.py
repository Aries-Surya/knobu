"""Color Picker: pick a pixel via the desktop portal, show it in several formats, copy it."""

import colorsys
import json
import os
from pathlib import Path

from gi.repository import Adw, Gtk

from knobu.system import portal
from knobu.ui.tools import ToolApp, copy_text, copy_when_focused

HISTORY_SIZE = 12


def history_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "knobu" / "colors.json"


def load_history() -> list[str]:
    try:
        return json.loads(history_path().read_text())[:HISTORY_SIZE]
    except (OSError, ValueError):
        return []


def save_history(colors: list[str]) -> None:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(colors[:HISTORY_SIZE]))


def formats(hex_color: str) -> dict[str, str]:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return {
        "hex": hex_color,
        "rgb": f"rgb({r}, {g}, {b})",
        "hsl": f"hsl({round(h * 360)}, {round(s * 100)}%, {round(l * 100)}%)",
    }


def swatch(hex_color: str, size: int) -> Gtk.DrawingArea:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    area = Gtk.DrawingArea(content_width=size, content_height=size)

    def draw(_area, cr, width, height):
        radius = min(width, height) * 0.2
        cr.new_sub_path()
        cr.arc(width - radius, radius, radius, -1.5708, 0)
        cr.arc(width - radius, height - radius, radius, 0, 1.5708)
        cr.arc(radius, height - radius, radius, 1.5708, 3.1416)
        cr.arc(radius, radius, radius, 3.1416, 4.7124)
        cr.close_path()
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.4)  # outline keeps white/black visible
        cr.set_line_width(1)
        cr.stroke()

    area.set_draw_func(draw)
    return area


class ColorPickerApp(ToolApp):
    suffix = "ColorPicker"

    def do_activate(self):
        self.prefs = self.settings("colorpicker")
        self.history = load_history()
        self.window = None
        self.pick()

    def pick(self, *_args):
        self.hold()  # keep running while the portal's picker is on screen
        if self.window:
            self.window.set_visible(False)
        portal.pick_color(self.on_picked)

    def on_picked(self, rgb):
        self.release()
        if rgb is None:
            if self.window:
                self.window.set_visible(True)
            else:
                self.quit()
            return
        hex_color = "#" + "".join(f"{round(c * 255):02X}" for c in rgb)
        self.history = [hex_color] + [c for c in self.history if c != hex_color]
        save_history(self.history)
        self.show(hex_color, auto_copy=True)

    def show(self, hex_color: str, auto_copy: bool = False):
        if self.window:
            self.window.destroy()
        self.window = win = Adw.ApplicationWindow(application=self, title="Color Picker",
                                                  default_width=380, resizable=False)
        toasts = Adw.ToastOverlay()
        page = Adw.PreferencesPage()

        top = Adw.PreferencesGroup()
        hero = swatch(hex_color, 96)
        hero.set_halign(Gtk.Align.CENTER)
        hero.set_margin_bottom(6)
        top.add(hero)
        page.add(top)

        values = Adw.PreferencesGroup()
        for name, text in formats(hex_color).items():
            row = Adw.ActionRow(title=text, subtitle=name.upper(), title_selectable=True)
            button = Gtk.Button(icon_name="edit-copy-symbolic", valign=Gtk.Align.CENTER,
                                tooltip_text="Copy", css_classes=["flat"])
            button.connect("clicked", lambda _b, t=text: (copy_text(win, t),
                                                          toasts.add_toast(Adw.Toast(title=f"Copied {t}"))))
            row.add_suffix(button)
            row.set_activatable_widget(button)
            values.add(row)
        page.add(values)

        if len(self.history) > 1:
            recent = Adw.PreferencesGroup(title="Recent")
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8,
                               column_spacing=6, row_spacing=6)
            for color in self.history:
                b = Gtk.Button(child=swatch(color, 28), tooltip_text=color, css_classes=["flat"])
                b.connect("clicked", lambda _b, c=color: self.show(c))
                flow.append(b)
            recent.add(flow)
            page.add(recent)

        header = Adw.HeaderBar()
        again = Gtk.Button(icon_name="color-select-symbolic", tooltip_text="Pick another colour")
        again.connect("clicked", self.pick)
        header.pack_start(again)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(header)
        toasts.set_child(view)
        win.set_content(toasts)

        if auto_copy:
            fmt = self.prefs["format"]
            copy_when_focused(win, lambda: formats(hex_color).get(fmt, hex_color),
                              lambda t: toasts.add_toast(Adw.Toast(title=f"Copied {t}")))
        win.present()


def main() -> int:
    return ColorPickerApp().run([])
