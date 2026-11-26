"""Quick Accent: floating accented character picker popup for Knobu."""

from __future__ import annotations

import threading
from gi.repository import Gdk, Gtk

from knobu import APP_ID
from knobu.modules.clipboard import set_clipboard, simulate_paste
from knobu.ui import style
from knobu.ui.tools import ToolApp

ACCENT_GROUPS: list[tuple[str, str]] = [
    ("a", "á à â ä ã å æ"),
    ("e", "é è ê ë €"),
    ("i", "í ì î ï"),
    ("o", "ó ò ô ö õ ø"),
    ("u", "ú ù û ü"),
    ("other", "ñ ç ß ¿ ¡ ° — • …"),
]


class QuickAccentWindow(Gtk.Window):
    def __init__(self, application=None, initial_char: str = ""):
        super().__init__(application=application, title="Quick Accent")
        self.set_default_size(360, 260)
        self.set_icon_name(APP_ID)
        style.apply()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        box.append(Gtk.Label(label="Quick Accent — click a character to paste",
                             xalign=0, css_classes=["heading"]))

        q = initial_char.strip().lower()
        groups = [g for g in ACCENT_GROUPS if not q or g[0] == q] or ACCENT_GROUPS
        for _base, chars in groups:
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, min_children_per_line=7,
                               max_children_per_line=9, column_spacing=4, row_spacing=4)
            for ch in chars.split():
                btn = Gtk.Button(label=ch, css_classes=["flat"])
                btn.connect("clicked", lambda _b, c=ch: self._pick(c))
                flow.append(btn)
            box.append(flow)

        self.set_child(box)
        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", lambda _c, kv, _kc, _st: (self.close(), True)[1] if kv == Gdk.KEY_Escape else False)
        self.add_controller(ctrl)

    def _pick(self, ch: str) -> None:
        self.close()
        set_clipboard(ch)
        threading.Thread(target=simulate_paste, daemon=True).start()


class QuickAccentApp(ToolApp):
    suffix = "quick_accent"

    def do_activate(self):
        QuickAccentWindow(application=self).present()


def main() -> int:
    return QuickAccentApp().run([])
