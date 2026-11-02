"""Shared pieces for Knobu's small tool windows (Color Picker, Text Extractor)."""

from gi.repository import Adw, Gdk, Gio, GObject, Gtk

from knobu import APP_ID, config, modules


class ToolApp(Adw.Application):
    """A separate, non-unique app so a tool never activates the settings window."""

    suffix = ""

    def __init__(self):
        super().__init__(application_id=f"{APP_ID}.{self.suffix}",
                         flags=Gio.ApplicationFlags.NON_UNIQUE)

    def settings(self, module_id: str) -> dict:
        return config.module_settings(config.load(), module_id, modules.get(module_id).defaults)


def copy_text(widget: Gtk.Widget, text: str) -> None:
    widget.get_clipboard().set_content(
        Gdk.ContentProvider.new_for_value(GObject.Value(GObject.TYPE_STRING, text)))


def copy_when_focused(window: Gtk.Window, text_fn, on_copied) -> None:
    """Copy once the window has focus: Wayland only lets focused apps set the clipboard."""
    def on_active(win, _pspec):
        if win.is_active():
            win.disconnect(handler)
            text = text_fn()
            if text:
                copy_text(win, text)
                on_copied(text)
    handler = window.connect("notify::is-active", on_active)
