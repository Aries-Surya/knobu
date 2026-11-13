"""Command Bar (PowerToys Run for Linux) floating launcher window for Knobu.

Search apps, calculate, run shell commands, navigate paths, and perform system actions.
"""

from __future__ import annotations

import logging
from gi.repository import Adw, Gdk, GLib, Gtk

from knobu import APP_ID, config
from knobu.modules.commandbar.providers import SearchEngine, SearchResult
from knobu.ui import style
from knobu.ui.tools import ToolApp
from knobu.ui.widgets import app_icon

log = logging.getLogger("knobu.ui.commandbar")

BAR_CSS = """
.knobu-bar-window {
  background-color: #1e1e22;
  color: #f0f0f4;
  border: 1px solid #36363d;
  border-radius: 12px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6);
}

.knobu-bar-entry {
  font-size: 1.15em;
  padding: 10px 14px;
  border-radius: 8px;
  background-color: #26262b;
  border: 1px solid #3c3c45;
  color: #ffffff;
}

.knobu-bar-entry:focus-within {
  border-color: @accent_color;
  box-shadow: 0 0 0 1px @accent_color;
}

.knobu-bar-row {
  padding: 8px 12px;
  border-radius: 8px;
  background-color: transparent;
  border: 1px solid transparent;
  margin-bottom: 4px;
  transition: all 120ms ease;
}

.knobu-bar-row:hover {
  background-color: #2b2b32;
  border-color: #3e3e48;
}

.knobu-bar-row.selected {
  background-color: #32323c;
  border-color: @accent_color;
}

.knobu-bar-title {
  font-size: 1.05em;
  font-weight: 600;
  color: #ffffff;
}

.knobu-bar-subtitle {
  font-size: 0.85em;
  color: #92929e;
}

.knobu-bar-badge {
  font-size: 0.72em;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
  background-color: #2d2d35;
  color: #a4a4b2;
  border: 1px solid #3e3e4a;
}

scrollbar {
  background: transparent;
  border: none;
}

scrollbar slider {
  min-width: 6px;
  min-height: 24px;
  border-radius: 4px;
  background-color: #3e3e48;
}
"""


class CommandBarWindow(Gtk.Window):
    def __init__(self, application=None):
        super().__init__(application=application, title="Knobu Command Bar")
        self.set_default_size(680, -1)
        self.set_modal(False)
        self.set_icon_name(APP_ID)

        # Load settings
        raw_cfg = config.load()
        cb_settings = raw_cfg.get("commandbar", {})
        self.engine = SearchEngine(cb_settings)
        self.max_results = int(cb_settings.get("max_results", 8))

        self.current_results: list[SearchResult] = []
        self.selected_index: int = 0
        self.row_widgets: list[Gtk.Widget] = []

        self._setup_style()
        self._build_ui()

        # Auto-dismiss on blur
        self._activated = False
        self.connect("notify::is-active", self._on_is_active_changed)

        # Initial default query
        self._on_search_changed()

    def _on_is_active_changed(self, _obj, _param) -> None:
        if self.is_active():
            self._activated = True
        elif self._activated:
            self.close()

    def _setup_style(self) -> None:
        style.apply()
        provider = Gtk.CssProvider()
        provider.load_from_string(BAR_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10,
        )

    def _build_ui(self) -> None:
        self.set_css_classes(["knobu-bar-window"])

        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=12,
            margin_bottom=12,
            margin_start=14,
            margin_end=14,
        )

        # Search bar row with brand logo
        entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        entry_box.append(app_icon(28))

        self.entry = Gtk.SearchEntry(
            placeholder_text="Type to search apps, calculate, or run commands (e.g. > top, 25*4, ~/...)",
            hexpand=True,
            css_classes=["knobu-bar-entry"],
        )
        self.entry.connect("search-changed", lambda _e: self._on_search_changed())
        entry_box.append(self.entry)
        main_box.append(entry_box)

        # Results container
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.set_max_content_height(420)
        scroll.set_propagate_natural_height(True)
        scroll.set_child(self.list_box)
        main_box.append(scroll)

        self.set_child(main_box)

        # Keyboard controller for Up / Down / Enter / Escape
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        elif keyval in (Gdk.KEY_Down, Gdk.KEY_Tab):
            self._move_selection(1)
            return True
        elif keyval in (Gdk.KEY_Up, Gdk.KEY_ISO_Left_Tab):
            self._move_selection(-1)
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._activate_selected()
            return True
        return False

    def _on_search_changed(self) -> None:
        query = self.entry.get_text()
        self.current_results = self.engine.search(query, limit=self.max_results)
        self.selected_index = 0
        self._render_results()

    def _render_results(self) -> None:
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        self.row_widgets.clear()

        if not self.current_results:
            empty = Gtk.Label(
                label="No matching apps, commands, or calculations found",
                css_classes=["dim-label"],
                margin_top=24,
                margin_bottom=24,
            )
            self.list_box.append(empty)
            return

        for idx, item in enumerate(self.current_results):
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=12,
                css_classes=["knobu-bar-row"] + (["selected"] if idx == self.selected_index else []),
            )

            # Icon
            icon = Gtk.Image.new_from_icon_name(item.icon_name)
            icon.set_pixel_size(32)
            icon.set_valign(Gtk.Align.CENTER)
            row.append(icon)

            # Text container
            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            title_lbl = Gtk.Label(label=item.title, xalign=0, css_classes=["knobu-bar-title"])
            sub_lbl = Gtk.Label(label=item.subtitle, xalign=0, css_classes=["knobu-bar-subtitle"])
            sub_lbl.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            text_box.append(title_lbl)
            text_box.append(sub_lbl)
            row.append(text_box)

            # Category badge
            badge = Gtk.Label(label=item.category, css_classes=["knobu-bar-badge"], valign=Gtk.Align.CENTER)
            row.append(badge)

            # Click gesture
            click = Gtk.GestureClick()
            click.connect("released", lambda _c, _n, _x, _y, i=idx: self._on_row_clicked(i))
            row.add_controller(click)

            self.list_box.append(row)
            self.row_widgets.append(row)

    def _move_selection(self, delta: int) -> None:
        if not self.current_results:
            return
        new_idx = (self.selected_index + delta) % len(self.current_results)
        if new_idx != self.selected_index:
            if self.selected_index < len(self.row_widgets):
                self.row_widgets[self.selected_index].remove_css_class("selected")
            self.selected_index = new_idx
            if self.selected_index < len(self.row_widgets):
                self.row_widgets[self.selected_index].add_css_class("selected")

    def _activate_selected(self) -> None:
        if 0 <= self.selected_index < len(self.current_results):
            action = self.current_results[self.selected_index].action
            self._activated = False
            self.close()
            try:
                action()
            except Exception as e:
                log.error("Failed to execute action: %s", e)

    def _on_row_clicked(self, index: int) -> None:
        self.selected_index = index
        self._activate_selected()


class CommandBarApp(ToolApp):
    suffix = "commandbar"

    def do_activate(self):
        win = CommandBarWindow(application=self)
        win.present()


def main() -> int:
    return CommandBarApp().run([])
