"""Awake: keep the computer (and optionally the screen) awake, forever or for a while.

System sleep is blocked with a logind inhibitor, which every Ubuntu flavour honours.
Screen blanking is blocked through org.freedesktop.ScreenSaver, which GNOME, KDE, Xfce
and others implement; holding it also stops idle suspend on GNOME.
"""

import subprocess
import threading
import time

from knobu.modules.base import Module

REASON = "Knobu Awake is keeping this computer awake"


class AwakeModule(Module):
    id = "awake"
    name = "Awake"
    description = "Keep your computer awake without changing power settings."
    icon = "knobu-awake-symbolic"
    defaults = {
        "enabled": False,      # the on/off toggle itself
        "mode": "indefinite",  # or "timed"
        "minutes": 60,
        "until": 0.0,          # epoch seconds when a timed session ends
        "keep_screen_on": True,
    }

    def run(self, stop: threading.Event) -> None:
        s = self.settings
        timed = s["mode"] == "timed"
        if timed and time.time() >= s["until"]:
            return
        sleep_lock = subprocess.Popen(
            ["systemd-inhibit", "--what=sleep", "--who=Knobu", f"--why={REASON}",
             "--mode=block", "sleep", "infinity"])
        screen_cookie = self._inhibit_screen() if s["keep_screen_on"] else None
        self.log.info("keeping awake%s%s", " (screen on)" if screen_cookie is not None else "",
                      time.strftime(" until %-I:%M %p", time.localtime(s["until"])) if timed else "")
        try:
            while not stop.is_set():
                if timed and time.time() >= s["until"]:
                    self.log.info("timer ended")
                    break
                stop.wait(1)
        finally:
            sleep_lock.terminate()
            if screen_cookie is not None:
                self._screensaver("UnInhibit", "(u)", (screen_cookie,))

    def _inhibit_screen(self) -> int | None:
        reply = self._screensaver("Inhibit", "(ss)", ("Knobu", REASON))
        return reply[0] if reply else None

    def _screensaver(self, method: str, signature: str, args: tuple):
        # Uses Gio's shared session-bus connection: the inhibition lasts as long as that
        # connection (i.e. this daemon) does, or until UnInhibit.
        from gi.repository import Gio, GLib
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION)
            reply = bus.call_sync("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver",
                                  "org.freedesktop.ScreenSaver", method,
                                  GLib.Variant(signature, args), None,
                                  Gio.DBusCallFlags.NONE, 3000, None)
            return reply.unpack() if reply else ()
        except GLib.Error as err:
            self.log.warning("screen inhibit %s failed: %s", method, err.message)
            return None
