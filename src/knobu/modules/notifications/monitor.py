"""D-Bus Notification eavesdropper using org.freedesktop.DBus.Monitoring.BecomeMonitor."""

from __future__ import annotations

import logging
from gi.repository import Gio, GLib

log = logging.getLogger("knobu.notifications.monitor")

NOTIFY_RULE = "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"


class NotificationMonitor:
    """Listens passively to desktop notifications on a private session D-Bus connection."""

    def __init__(self, on_notify):
        self.on_notify = on_notify
        self._conn: Gio.DBusConnection | None = None
        self._filter_id: int = 0

    def start(self) -> bool:
        try:
            addr = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
            conn = Gio.DBusConnection.new_for_address_sync(
                addr,
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None,
                None,
            )
            self._filter_id = conn.add_filter(self._on_message)
            conn.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus.Monitoring",
                "BecomeMonitor",
                GLib.Variant("(asu)", ([NOTIFY_RULE], 0)),
                None,
                Gio.DBusCallFlags.NONE,
                2000,
                None,
            )
            self._conn = conn
            log.info("listening for desktop notifications via D-Bus BecomeMonitor")
            return True
        except Exception as err:
            log.warning("notification monitor unavailable: %s", err)
            self.stop()
            return False

    def _on_message(self, _conn, message: Gio.DBusMessage, incoming: bool):
        if (
            incoming
            and message.get_message_type() == Gio.DBusMessageType.METHOD_CALL
            and message.get_interface() == "org.freedesktop.Notifications"
            and message.get_member() == "Notify"
        ):
            body_var = message.get_body()
            if body_var is not None:
                try:
                    app_name, _replaces, icon, summary, body, _actions, hints, _timeout = body_var.unpack()
                    # Skip our own silent/copy feedback notifications to prevent loops
                    if hints and hints.get("x-knobu-internal"):
                        return None
                    if summary or body:
                        self.on_notify(str(app_name or "System"), str(summary), str(body), str(icon or ""))
                except Exception as err:
                    log.debug("failed parsing Notify message: %s", err)
        return None  # BecomeMonitor forbids replying; filter must consume/ignore safely

    def stop(self) -> None:
        conn = self._conn
        self._conn = None
        if conn:
            if self._filter_id:
                try:
                    conn.remove_filter(self._filter_id)
                except Exception:
                    pass
                self._filter_id = 0
            try:
                conn.close_sync(None)
            except Exception:
                pass
