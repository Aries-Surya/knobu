"""Top Bar Tray, Network/AWS quick switcher & Mac-style Notification HUD module."""

from __future__ import annotations

import threading

from gi.repository import GLib

from knobu.modules.base import Module
from knobu.modules.notifications.monitor import NotificationMonitor
from knobu.modules.notifications.store import NotificationHistory
from knobu.system import launch
from knobu.system.tray import StatusTray

__all__ = ["NotificationsModule", "NotificationHistory", "NotificationMonitor", "StatusTray"]


class NotificationsModule(Module):
    id = "notifications"
    name = "Top Bar & Notifications"
    description = "Top notification tray with Private/Public IP, AWS profile switcher, and Mac-style alerts."
    icon = "preferences-system-notifications-symbolic"
    defaults = {
        "enabled": True,
        "bypass": False,
        "show_tray": True,
        "show_hud": False,
        "dnd": False,
        "show_public_ip": True,
        "custom_ringtone": "",
    }

    def __init__(self, settings: dict):
        super().__init__(settings)
        self._tray: StatusTray | None = None

    def update_settings(self, settings: dict) -> None:
        self.settings = settings
        if self._tray:
            self._tray.show_public_ip = bool(settings.get("show_public_ip", True))
            GLib.idle_add(self._tray._emit_layout_if_changed)

    def run(self, stop: threading.Event) -> None:
        history = NotificationHistory()
        tray = StatusTray(history=history, show_public_ip=bool(self.settings.get("show_public_ip", True)))
        self._tray = tray
        loop = GLib.MainLoop()

        def on_notify(app_name: str, summary: str, body: str, icon: str) -> None:
            rec = history.add(app_name, summary, body, icon)
            GLib.idle_add(tray._emit_layout_if_changed)
            if not bool(self.settings.get("dnd", False)):
                ringtone = str(self.settings.get("custom_ringtone", "")).strip()
                if ringtone:
                    from knobu.modules.system_prefs import preview_sound
                    preview_sound(ringtone)
                if bool(self.settings.get("show_hud", False)):
                    launch.knobu("notifications", "--toast", str(rec.id))

        monitor = NotificationMonitor(on_notify)
        if bool(self.settings.get("show_tray", True)):
            tray.start()
        # Start BecomeMonitor once GLib.MainLoop is spinning so private bus auth doesn't stall
        GLib.idle_add(lambda: (monitor.start(), False)[1])

        def watch_stop() -> None:
            stop.wait()
            GLib.idle_add(lambda: (loop.quit(), False)[1])

        threading.Thread(target=watch_stop, daemon=True).start()
        try:
            loop.run()
        finally:
            self._tray = None
            monitor.stop()
            tray.stop()
