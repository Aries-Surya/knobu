"""Color Picker: the desktop's own picker, then copy the colour and confirm."""

import colorsys
import struct
import zlib
from pathlib import Path

from gi.repository import GLib

from knobu.system import clipboard, notify, portal
from knobu.tools import settings

ICON = "color-select-symbolic"


def formats(r: int, g: int, b: int) -> dict[str, str]:
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return {
        "hex": f"#{r:02X}{g:02X}{b:02X}",
        "rgb": f"rgb({r}, {g}, {b})",
        "hsl": f"hsl({round(h * 360)}, {round(s * 100)}%, {round(l * 100)}%)",
    }


def swatch_png(r: int, g: int, b: int, size: int = 64) -> str:
    """Write a solid-colour PNG for the notification image; returns its path."""
    row = b"\x00" + bytes((r, g, b)) * size
    data = zlib.compress(row * size)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload)))

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", data) + chunk(b"IEND", b""))
    path = Path(GLib.get_user_cache_dir()) / "knobu" / "swatch.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return str(path)


def main() -> int:
    fmt = settings("colorpicker")["format"]
    loop = GLib.MainLoop()
    hint = notify.notify("Color Picker", "Click anywhere on the screen to copy its colour.",
                         icon=ICON, timeout_ms=10000)

    def on_picked(rgb):
        if rgb is None:
            notify.close(hint)
        else:
            r, g, b = (round(c * 255) for c in rgb)
            values = formats(r, g, b)
            chosen = values.get(fmt, values["hex"])
            others = "   ".join(v for k, v in values.items() if k != fmt)
            if clipboard.copy(chosen):
                notify.notify(f"Copied {chosen}", others, icon=ICON, image=swatch_png(r, g, b),
                              replaces=hint)
            else:
                notify.notify(f"Picked {chosen}", "Couldn't copy it: install the clipboard "
                              f"tool with: {clipboard.INSTALL_HINT}", icon=ICON,
                              image=swatch_png(r, g, b), replaces=hint, timeout_ms=10000)
        loop.quit()

    portal.pick_color(on_picked)
    loop.run()
    return 0
