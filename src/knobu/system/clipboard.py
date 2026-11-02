"""Copying text to the clipboard from a background process, without a window.

Wayland only lets focused windows set the clipboard, so this goes through tools that
work around that: wl-copy (wl-clipboard) on Wayland, xclip on X11, or KDE's Klipper.
"""

import os
import shutil
import subprocess

from gi.repository import Gio, GLib


def copy(text: str) -> bool:
    """Returns False if no clipboard tool was available."""
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        return _pipe(["wl-copy"], text)
    if os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY") and shutil.which("xclip"):
        return _pipe(["xclip", "-selection", "clipboard"], text)
    return _klipper(text)


def _pipe(cmd: list[str], text: str) -> bool:
    # Both tools fork into the background to keep serving the clipboard, so their
    # output must not be captured or this would wait for them forever.
    r = subprocess.run(cmd, input=text.encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)
    return r.returncode == 0


def _klipper(text: str) -> bool:
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        bus.call_sync("org.kde.klipper", "/klipper", "org.kde.klipper.klipper",
                      "setClipboardContents", GLib.Variant("(s)", (text,)), None,
                      Gio.DBusCallFlags.NONE, 3000, None)
        return True
    except GLib.Error:
        return False


INSTALL_HINT = "sudo apt install wl-clipboard"
