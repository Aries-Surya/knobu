"""Text Extractor: select a screen area, read its text with Tesseract OCR, copy it."""

import os
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import unquote, urlparse

from gi.repository import Adw, GLib, Gtk

from knobu.system import portal
from knobu.ui.tools import ToolApp, copy_text, copy_when_focused

INSTALL_TESSERACT = "sudo apt install tesseract-ocr"


def is_kde() -> bool:
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "")


def ocr(image_path: str, language: str) -> tuple[str, str]:
    """Returns (text, error)."""
    r = subprocess.run(["tesseract", image_path, "stdout", "-l", language],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return "", r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "OCR failed"
    return r.stdout.strip(), ""


class TextExtractorApp(ToolApp):
    suffix = "TextExtractor"

    def do_activate(self):
        self.prefs = self.settings("textextractor")
        if not shutil.which("tesseract"):
            self.show_message("Text recognition isn't installed",
                              "Run this in a terminal, then try again:", INSTALL_TESSERACT)
            return
        self.hold()
        self.capture()

    def capture(self):
        # Spectacle gives KDE users a proper region selector; elsewhere the portal shows
        # the desktop's own screenshot UI (GNOME's lets you select an area).
        if is_kde() and shutil.which("spectacle"):
            fd, path = tempfile.mkstemp(prefix="knobu-", suffix=".png")
            os.close(fd)
            os.unlink(path)  # spectacle writes it; an existing empty file means "cancelled"

            def run():
                subprocess.run(["spectacle", "--background", "--region", "--nonotify",
                                "--output", path], check=False)
                GLib.idle_add(self.on_captured, path if os.path.exists(path) else None, True)
            threading.Thread(target=run, daemon=True).start()
        else:
            portal.screenshot(lambda uri: self.on_captured(
                unquote(urlparse(uri).path) if uri else None, False))

    def on_captured(self, path: str | None, temporary: bool):
        if path is None:
            self.release()
            return

        def run():
            text, error = ocr(path, self.prefs["language"])
            if temporary:
                os.unlink(path)
            GLib.idle_add(self.on_text, text, error)
        threading.Thread(target=run, daemon=True).start()

    def on_text(self, text: str, error: str):
        self.release()
        if error:
            self.show_message("Couldn't read the text", error)
        elif not text:
            self.show_message("No text found", "Try selecting a larger or sharper area.")
        else:
            self.show_text(text)

    def window(self, title: str, content: Gtk.Widget, width=480, height=-1) -> Adw.ApplicationWindow:
        win = Adw.ApplicationWindow(application=self, title=title, default_width=width,
                                    default_height=height)
        view = Adw.ToolbarView(content=content)
        view.add_top_bar(Adw.HeaderBar())
        win.set_content(view)
        return win

    def show_text(self, text: str):
        toasts = Adw.ToastOverlay()
        buffer = Gtk.TextBuffer(text=text)
        textview = Gtk.TextView(buffer=buffer, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                top_margin=12, bottom_margin=12, left_margin=12, right_margin=12)
        copy = Gtk.Button(label="Copy", css_classes=["suggested-action", "pill"],
                          halign=Gtk.Align.CENTER, margin_top=12, margin_bottom=12)

        def current() -> str:
            return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

        copy.connect("clicked", lambda _b: (copy_text(win, current()),
                                            toasts.add_toast(Adw.Toast(title="Copied"))))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(Gtk.ScrolledWindow(child=textview, vexpand=True))
        box.append(copy)
        toasts.set_child(box)
        win = self.window("Text Extractor", toasts, 520, 360)
        copy_when_focused(win, current, lambda _t: toasts.add_toast(Adw.Toast(title="Text copied")))
        win.present()

    def show_message(self, title: str, description: str, command: str = ""):
        status = Adw.StatusPage(icon_name="insert-text-symbolic", title=title,
                                description=description)
        if command:
            label = Gtk.Label(label=command, selectable=True, css_classes=["monospace", "card"],
                              margin_top=6)
            label.set_margin_start(12)
            label.set_margin_end(12)
            status.set_child(label)
        self.window("Text Extractor", status, 440).present()


def main() -> int:
    return TextExtractorApp().run([])
