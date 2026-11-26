"""Shortcut Guide: interactive cheat-sheet overlay listing all configured Knobu & OS shortcuts."""

from __future__ import annotations

from gi.repository import Gdk, Gtk

from knobu import APP_ID, config, modules
from knobu.system import keys
from knobu.ui import style
from knobu.ui.tools import ToolApp
from knobu.ui.widgets import app_icon, keycaps

DESKTOP_SHORTCUTS: list[tuple[str, str, str]] = [
    ("Desktop", "Switch Workspace Left / Right", "super+alt+left / right"),
    ("Desktop", "Show Overview / Activities", "super"),
    ("Desktop", "Lock Screen", "super+l"),
    ("Desktop", "Screenshot Tool", "print"),
]


def collect_shortcuts() -> list[tuple[str, str, str]]:
    """Collect all configured Knobu shortcuts from config + module defaults."""
    data = config.load()
    rows: list[tuple[str, str, str]] = []
    for cls in modules.MODULES:
        s = config.module_settings(data, cls.id, cls.defaults)
        if not s.get("enabled", True):
            continue
        for key_name, val in s.items():
            if (key_name == "hotkey" or key_name.endswith("_hotkey")) and isinstance(val, str) and val.strip():
                label = key_name.replace("_hotkey", "").replace("_", " ").title()
                title = cls.name if label.lower() == "hotkey" else f"{cls.name}: {label}"
                rows.append(("Knobu", title, val.strip()))
    rows.extend(DESKTOP_SHORTCUTS)
    return rows


class ShortcutGuideWindow(Gtk.Window):
    def __init__(self, application=None):
        super().__init__(application=application, title="Knobu Shortcut Guide")
        self.set_default_size(580, 560)
        self.set_icon_name(APP_ID)
        style.apply()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
        header = Gtk.Box(spacing=10)
        header.append(app_icon(24))
        header.append(Gtk.Label(label="Shortcut Guide", css_classes=["title-3"], hexpand=True, xalign=0))
        box.append(header)

        self.search = Gtk.SearchEntry(placeholder_text="Filter shortcuts...")
        self.search.connect("search-changed", lambda _e: self._populate())
        box.append(self.search)

        self.list_box = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        scroll = Gtk.ScrolledWindow(vexpand=True, child=self.list_box)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box.append(scroll)
        self.set_child(box)

        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", lambda _c, kv, _kc, _st: (self.close(), True)[1] if kv == Gdk.KEY_Escape else False)
        self.add_controller(ctrl)

        self._shortcuts = collect_shortcuts()
        self._populate()

    def _populate(self) -> None:
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)
        q = self.search.get_text().strip().lower()
        for cat, title, chord in self._shortcuts:
            if q and q not in title.lower() and q not in chord.lower() and q not in cat.lower():
                continue
            row = Gtk.Box(spacing=12, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
            lbl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            lbl_box.append(Gtk.Label(label=title, xalign=0, css_classes=["heading"]))
            lbl_box.append(Gtk.Label(label=cat, xalign=0, css_classes=["dim-label", "caption"]))
            row.append(lbl_box)
            try:
                row.append(keycaps(chord))
            except Exception:
                row.append(Gtk.Label(label=keys.pretty(chord), css_classes=["dim-label"]))
            self.list_box.append(row)


class ShortcutGuideApp(ToolApp):
    suffix = "shortcut_guide"

    def do_activate(self):
        ShortcutGuideWindow(application=self).present()


def main() -> int:
    return ShortcutGuideApp().run([])
