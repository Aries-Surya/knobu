"""Clipboard History popup window for Knobu.

Searchable palette for selecting and automatically pasting previous clipboard clips
(text and copied images).
"""

from __future__ import annotations

import threading
from pathlib import Path
from gi.repository import Adw, Gdk, GLib, Gtk

from knobu import APP_ID
from knobu.modules.clipboard import (
    ClipboardStorage,
    clean_url,
    get_clipboard,
    get_clipboard_image,
    set_clipboard,
    set_clipboard_image,
    simulate_paste,
)
from knobu.ui import style
from knobu.ui.tools import ToolApp
from knobu.ui.widgets import app_icon

CLIP_CSS = """
.knobu-clip-window {
  background-color: #1e1e22;
  color: #f0f0f4;
  border: 1px solid #333338;
  border-radius: 10px;
}

.knobu-clip-card {
  padding: 8px 12px;
  border-radius: 6px;
  background-color: #27272b;
  border: 1px solid #38383f;
  margin-bottom: 6px;
}

.knobu-clip-card:hover, .knobu-clip-card:focus-within {
  background-color: #323238;
  border-color: @accent_color;
}

.knobu-clip-preview {
  font-size: 0.9em;
  color: #f0f0f4;
}

.knobu-clip-time {
  font-size: 0.75em;
  font-family: monospace;
  color: #888892;
}

.knobu-clip-image {
  border-radius: 4px;
  background-color: #18181b;
  margin-bottom: 4px;
}

.knobu-clip-btn {
  padding: 4px;
  min-width: 24px;
  min-height: 24px;
  border-radius: 4px;
  background-color: transparent;
  color: #b0b0ba;
}

.knobu-clip-btn:hover {
  background-color: #383842;
  color: #ffffff;
}
"""


class ClipboardWindow(Gtk.Window):
    def __init__(self, application=None, storage: ClipboardStorage | None = None):
        super().__init__(application=application, title="Clipboard History")
        self.set_default_size(440, 520)
        self.set_modal(False)
        self.set_icon_name(APP_ID)
        self.storage = storage or ClipboardStorage()

        # Capture latest clipboard clip on open (image or text)
        img_bytes = get_clipboard_image()
        if img_bytes:
            self.storage.add_image_clip(img_bytes)
        else:
            latest = get_clipboard()
            if latest:
                cleaned = clean_url(latest)
                if cleaned != latest:
                    set_clipboard(cleaned)
                    latest = cleaned
                self.storage.add_clip(latest)

        self._setup_style()
        self._build_ui()
        self._refresh_list()

        # Dismiss automatically when user clicks anywhere outside or window loses focus
        self._activated = False
        self.connect("notify::is-active", self._on_is_active_changed)

    def _on_is_active_changed(self, _obj, _param) -> None:
        if self.is_active():
            self._activated = True
        elif self._activated:
            self.close()

    def _setup_style(self) -> None:
        style.apply()
        provider = Gtk.CssProvider()
        provider.load_from_string(CLIP_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10,
        )

    def _build_ui(self) -> None:
        self.set_css_classes(["knobu-clip-window"])

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=14,
                      margin_bottom=14, margin_start=14, margin_end=14)

        # Brand header with official Knobu logo and Clear All button
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.append(app_icon(22))
        header.append(Gtk.Label(label="Clipboard History", css_classes=["heading"]))

        spacer = Gtk.Box(hexpand=True)
        header.append(spacer)

        clear_btn = Gtk.Button(icon_name="edit-clear-all-symbolic", tooltip_text="Clear unpinned clips",
                               css_classes=["flat", "knobu-clip-btn"])
        clear_btn.connect("clicked", lambda _b: self._on_clear_all())
        header.append(clear_btn)
        box.append(header)

        # Search bar
        self.search = Gtk.SearchEntry(placeholder_text="Search clipboard...", hexpand=True)
        self.search.connect("search-changed", lambda _e: self._refresh_list())
        box.append(self.search)

        # Scrollable list of clips
        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.list_box)
        box.append(scroll)

        self.set_child(box)

        # Escape key controller with capture phase so it dismisses from anywhere
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _refresh_list(self) -> None:
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        clips = self.storage.get_clips(search=self.search.get_text())
        if not clips:
            empty = Gtk.Label(label="No clipboard history found", css_classes=["dim-label"],
                              margin_top=30, margin_bottom=30)
            self.list_box.append(empty)
            return

        for clip in clips:
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                           css_classes=["knobu-clip-card"])

            # Left column: Content and Time (Click only this text/image area to paste)
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
            col.set_cursor_from_name("pointer")

            if clip.kind == "image" and Path(clip.content).exists():
                picture = Gtk.Picture.new_for_filename(clip.content)
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
                picture.set_can_shrink(True)
                picture.set_size_request(-1, 90)
                picture.set_css_classes(["knobu-clip-image"])
                col.append(picture)

                meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                meta_box.append(Gtk.Label(label=clip.preview, css_classes=["knobu-clip-time"]))
                meta_box.append(Gtk.Label(label="•", css_classes=["knobu-clip-time"]))
                meta_box.append(Gtk.Label(label=clip.formatted_time, css_classes=["knobu-clip-time"]))
                col.append(meta_box)
            else:
                txt = Gtk.Label(label=clip.preview, xalign=0, ellipsize=3, max_width_chars=40,
                                wrap=True, lines=2, css_classes=["knobu-clip-preview"])
                time_lbl = Gtk.Label(label=clip.formatted_time, xalign=0, css_classes=["knobu-clip-time"])
                col.append(txt)
                col.append(time_lbl)

            click = Gtk.GestureClick()
            click.set_button(Gdk.BUTTON_PRIMARY)
            click.connect("pressed", lambda _g, _n, _x, _y, c=clip: self._paste_clip(c))
            col.add_controller(click)
            card.append(col)

            # Pin button
            pin_btn = Gtk.Button(
                icon_name="view-pin-symbolic",
                tooltip_text="Unpin" if clip.pinned else "Pin clip",
                css_classes=["knobu-clip-btn", "flat"] if not clip.pinned else ["knobu-clip-btn", "suggested-action"],
                valign=Gtk.Align.CENTER,
            )
            pin_btn.connect("clicked", lambda _b, cid=clip.id: self._on_toggle_pin(cid))
            card.append(pin_btn)

            # Delete button
            del_btn = Gtk.Button(
                icon_name="edit-delete-symbolic",
                tooltip_text="Delete clip",
                css_classes=["knobu-clip-btn", "flat"],
                valign=Gtk.Align.CENTER,
            )
            del_btn.connect("clicked", lambda _b, cid=clip.id: self._on_delete_clip(cid))
            card.append(del_btn)

            self.list_box.append(card)

    def _paste_clip(self, clip) -> None:
        self._activated = False
        self.close()
        # Set clipboard content and simulate Ctrl+V into target application in background
        if clip.kind == "image":
            set_clipboard_image(clip.content)
        else:
            set_clipboard(clip.content)
        threading.Thread(target=simulate_paste, daemon=True).start()

    def _on_toggle_pin(self, clip_id: int) -> None:
        self.storage.toggle_pin(clip_id)
        self._refresh_list()

    def _on_delete_clip(self, clip_id: int) -> None:
        self.storage.delete_clip(clip_id)
        self._refresh_list()

    def _on_clear_all(self) -> None:
        self.storage.clear_all()
        self._refresh_list()


class ClipboardApp(ToolApp):
    suffix = "clipboard"

    def do_activate(self):
        win = ClipboardWindow(application=self)
        win.present()


def main() -> int:
    return ClipboardApp().run([])
