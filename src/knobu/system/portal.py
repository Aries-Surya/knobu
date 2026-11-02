"""Calls to xdg-desktop-portal, the desktop-neutral API for screenshots and colour picking.

Portal methods answer asynchronously through a Response signal, so these helpers need a
running GLib main loop (the GTK helper apps have one).
"""

import secrets

from gi.repository import Gio, GLib

BUS_NAME = "org.freedesktop.portal.Desktop"
OBJECT_PATH = "/org/freedesktop/portal/desktop"


def request(interface: str, method: str, options: dict, callback) -> None:
    """Call a portal method; callback(ok: bool, results: dict) runs on the main loop."""
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    token = "knobu_" + secrets.token_hex(6)
    sender = bus.get_unique_name()[1:].replace(".", "_")
    handle = f"{OBJECT_PATH}/request/{sender}/{token}"

    def on_response(_bus, _sender, _path, _iface, _signal, params):
        bus.signal_unsubscribe(sub_id)
        code, results = params.unpack()
        callback(code == 0, results)

    # Subscribe before calling so a fast response can't be missed.
    sub_id = bus.signal_subscribe(BUS_NAME, "org.freedesktop.portal.Request", "Response",
                                  handle, None, Gio.DBusSignalFlags.NONE, on_response)
    opts = {"handle_token": GLib.Variant("s", token), **options}

    def on_called(_bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error as err:
            bus.signal_unsubscribe(sub_id)
            callback(False, {"error": err.message})

    bus.call(BUS_NAME, OBJECT_PATH, f"org.freedesktop.portal.{interface}", method,
             GLib.Variant("(sa{sv})", ("", opts)), None, Gio.DBusCallFlags.NONE, -1, None,
             on_called)


def pick_color(callback) -> None:
    """callback((r, g, b) floats 0..1, or None if cancelled/unsupported)."""
    request("Screenshot", "PickColor", {},
            lambda ok, res: callback(tuple(res["color"]) if ok and "color" in res else None))


def screenshot(callback, interactive: bool = True) -> None:
    """callback(file URI, or None)."""
    request("Screenshot", "Screenshot", {"interactive": GLib.Variant("b", interactive)},
            lambda ok, res: callback(res.get("uri") if ok else None))
