"""Text Extractor: the desktop's own area selector, Tesseract OCR, copy and confirm."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from gi.repository import GLib

from knobu.system import clipboard, notify, portal
from knobu.tools import settings

ICON = "insert-text-symbolic"
INSTALL_TESSERACT = "sudo apt install tesseract-ocr"

# Knobu's own Spectacle settings: capture as soon as the mouse is released, with no
# toolbar, saving or clipboard actions afterwards. Kept apart from the user's settings.
SPECTACLE_RC = """\
[General]
autoSaveImage=false
clipboardGroup=PostScreenshotDoNothing

[GuiConfig]
useReleaseToCapture=true
showCaptureInstructions=true
showMagnifier=ShowMagnifierNever
"""


def is_kde() -> bool:
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "")


def spectacle_config_home() -> str:
    """A config dir mirroring the user's (theme, fonts, ...) with Knobu's spectaclerc."""
    real = Path(GLib.get_user_config_dir())
    home = Path(GLib.get_user_cache_dir()) / "knobu" / "spectacle-config"
    home.mkdir(parents=True, exist_ok=True)
    for entry in real.iterdir():
        link = home / entry.name
        if not entry.name.startswith("spectacle") and not link.exists() and not link.is_symlink():
            link.symlink_to(entry)
    (home / "spectaclerc").write_text(SPECTACLE_RC)
    return str(home)


def select_area(callback) -> None:
    """callback(path to a PNG of the selected area, or None if cancelled)."""
    if is_kde() and shutil.which("spectacle"):
        fd, path = tempfile.mkstemp(prefix="knobu-", suffix=".png")
        os.close(fd)
        os.unlink(path)  # spectacle creates it; still missing means cancelled
        env = {**os.environ, "XDG_CONFIG_HOME": spectacle_config_home()}
        subprocess.run(["spectacle", "--background", "--region", "--nonotify", "--output", path],
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        callback(path if os.path.exists(path) else None)
    else:
        portal.screenshot(lambda uri: callback(unquote(urlparse(uri).path) if uri else None))


def ocr(image_path: str, language: str) -> tuple[str, str]:
    """Returns (text, error)."""
    r = subprocess.run(["tesseract", image_path, "stdout", "-l", language],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        lines = r.stderr.strip().splitlines()
        return "", lines[-1] if lines else "Text recognition failed"
    return r.stdout.strip(), ""


def main() -> int:
    if not shutil.which("tesseract"):
        notify.notify("Text Extractor needs text recognition",
                      f"Install it in a terminal with: {INSTALL_TESSERACT}", icon=ICON,
                      timeout_ms=15000)
        return 1

    language = settings("textextractor")["language"]
    loop = GLib.MainLoop()
    hint = notify.notify("Text Extractor", "Drag over the text you want to copy.",
                         icon=ICON, timeout_ms=10000)

    def on_selected(path):
        if path is None:
            notify.close(hint)
        else:
            text, error = ocr(path, language)
            if path.startswith(tempfile.gettempdir()):
                os.unlink(path)
            if error:
                notify.notify("Couldn't read the text", error, icon=ICON, replaces=hint)
            elif not text:
                notify.notify("No text found", "Try selecting a larger or sharper area.",
                              icon=ICON, replaces=hint)
            elif clipboard.copy(text):
                preview = text if len(text) <= 120 else text[:117] + "…"
                notify.notify("Text copied", preview, icon=ICON, replaces=hint)
            else:
                notify.notify("Couldn't copy the text",
                              f"Install the clipboard tool with: {clipboard.INSTALL_HINT}",
                              icon=ICON, replaces=hint, timeout_ms=10000)
        loop.quit()

    GLib.idle_add(lambda: select_area(on_selected) and False)
    loop.run()
    return 0
