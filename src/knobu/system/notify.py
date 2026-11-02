"""Desktop notifications over the freedesktop Notifications D-Bus API (every flavour)."""

from gi.repository import Gio, GLib

from knobu import APP_ID

_BUS = "org.freedesktop.Notifications"
_PATH = "/org/freedesktop/Notifications"


def _call(method: str, args: GLib.Variant):
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        return bus.call_sync(_BUS, _PATH, _BUS, method, args, None,
                             Gio.DBusCallFlags.NONE, 3000, None)
    except GLib.Error:
        return None


def notify(summary: str, body: str = "", icon: str = "", image: str = "",
           replaces: int = 0, timeout_ms: int = 5000) -> int:
    """Show (or replace) a notification; returns its id for replacing/closing later."""
    hints = {"desktop-entry": GLib.Variant("s", APP_ID)}
    if image:
        hints["image-path"] = GLib.Variant("s", image)
    reply = _call("Notify", GLib.Variant("(susssasa{sv}i)", (
        "Knobu", replaces, icon, summary, body, [], hints, timeout_ms)))
    return reply.unpack()[0] if reply else 0


def close(notification_id: int) -> None:
    if notification_id:
        _call("CloseNotification", GLib.Variant("(u)", (notification_id,)))
