"""Silent full-desktop screenshots, with no screenshot UI shown."""

import os
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import unquote, urlparse

from gi.repository import Gdk, GdkPixbuf, GLib

from knobu.system import portal


def is_kde() -> bool:
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "")


def capture_screen(callback) -> None:
    """callback(GdkPixbuf.Pixbuf of the whole desktop, or None) on the main loop."""
    if is_kde() and shutil.which("spectacle"):
        fd, path = tempfile.mkstemp(prefix="knobu-", suffix=".png")
        os.close(fd)
        os.unlink(path)  # spectacle creates it; a missing file means it failed

        def run():
            # A throwaway config dir keeps the user's own Spectacle settings untouched
            # (otherwise it records our temp file as the last save location).
            with tempfile.TemporaryDirectory(prefix="knobu-spectacle-") as config_home:
                subprocess.run(["spectacle", "--background", "--fullscreen", "--nonotify",
                                "--output", path],
                               env={**os.environ, "XDG_CONFIG_HOME": config_home},
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


def desktop_layout() -> tuple[list, int, int, int]:
    """(monitors with geometries, left, top, total logical width) of the whole desktop."""
    monitors = list(Gdk.Display.get_default().get_monitors())
    geometries = [m.get_geometry() for m in monitors]
    left = min(g.x for g in geometries)
    top = min(g.y for g in geometries)
    width = max(g.x + g.width for g in geometries) - left
    return list(zip(monitors, geometries)), left, top, width


class Pixels:
    """Fast pixel reads from a screenshot."""

    def __init__(self, pixbuf: GdkPixbuf.Pixbuf):
        self.data = pixbuf.read_pixel_bytes().get_data()
        self.rowstride = pixbuf.get_rowstride()
        self.channels = pixbuf.get_n_channels()
        self.width = pixbuf.get_width()
        self.height = pixbuf.get_height()

    def get(self, x: int, y: int) -> tuple[int, int, int] | None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None
        offset = y * self.rowstride + x * self.channels
        return tuple(self.data[offset:offset + 3])
