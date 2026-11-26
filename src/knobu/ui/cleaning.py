"""Cleaning Mode: fullscreen lock overlay that disables keyboard, mouse, and touchpad inputs."""

from __future__ import annotations

import logging
import select
import threading
import time

import evdev
from evdev import ecodes as e
from gi.repository import Adw, Gdk, GLib, Gtk

from knobu import service
from knobu.modules.powertools import PowerToolsModule
from knobu.modules.touchpad import device as tp_device
from knobu.system import keyboards, mice
from knobu.ui import style
from knobu.ui.tools import ToolApp

log = logging.getLogger("knobu.ui.cleaning")

HOLD_TO_UNLOCK_SEC = 2.0

CLEANING_CSS = """
.knobu-cleaning-window {
  background-color: #09090b;
  color: #f4f4f6;
}
.knobu-cleaning-hint {
  color: #9b9ba8;
  font-size: 1.05em;
}
.knobu-cleaning-timer {
  font-size: 2.2em;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: @accent_color;
}
"""


class InputLocker:
    """Exclusively grabs keyboards, mice, and touchpads until released or Esc held for 2s."""

    def __init__(self, on_unlock, on_esc_progress=None):
        self.on_unlock = on_unlock
        self.on_esc_progress = on_esc_progress
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._devices: list[evdev.InputDevice] = []
        self._was_service_active = False
        self.grabbed_count = 0

    def start(self) -> int:
        self._was_service_active = service.is_active()
        if self._was_service_active:
            service.stop()
            time.sleep(0.15)  # allow daemon to ungrab keyboards/mice cleanly

        candidates: list[evdev.InputDevice] = []
        candidates.extend(keyboards.open_keyboards(include_virtual=False))
        candidates.extend(mice.open_mice(include_virtual=False))
        tp = tp_device.find_touchpad()
        if tp is not None:
            candidates.append(tp)

        for dev in candidates:
            try:
                dev.grab()
                self._devices.append(dev)
            except OSError as err:
                log.debug("could not grab %s: %s", dev.path, err)
                dev.close()

        self.grabbed_count = len(self._devices)
        if self._devices:
            self._thread = threading.Thread(target=self._loop, name="cleaning-locker", daemon=True)
            self._thread.start()
        return self.grabbed_count

    def _loop(self) -> None:
        by_fd = {d.fd: d for d in self._devices}
        esc_since: float | None = None
        unlocked = False

        while not self._stop.is_set() and by_fd:
            ready, _, _ = select.select(list(by_fd.keys()), [], [], 0.05)
            now = time.monotonic()
            for fd in ready:
                dev = by_fd.get(fd)
                if dev is None:
                    continue
                try:
                    for ev in dev.read():
                        if ev.type == e.EV_KEY and ev.code == e.KEY_ESC:
                            if ev.value == 1 and esc_since is None:
                                esc_since = now
                            elif ev.value == 0:
                                esc_since = None
                                if self.on_esc_progress:
                                    GLib.idle_add(self.on_esc_progress, 0.0)
                except OSError:
                    by_fd.pop(fd, None)

            if esc_since is not None and not unlocked:
                ratio = min(1.0, (now - esc_since) / HOLD_TO_UNLOCK_SEC)
                if self.on_esc_progress:
                    GLib.idle_add(self.on_esc_progress, ratio)
                if ratio >= 1.0:
                    unlocked = True
                    GLib.idle_add(self.on_unlock)
                    break

    def release(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        for dev in self._devices:
            try:
                dev.ungrab()
            except OSError:
                pass
            try:
                dev.close()
            except OSError:
                pass
        self._devices.clear()
        if self._was_service_active:
            self._was_service_active = False
            service.start()


class CleaningWindow(Gtk.Window):
    def __init__(self, app: ToolApp, duration_sec: int):
        super().__init__(application=app, title="Knobu Cleaning Mode", decorated=False)
        self.duration_sec = max(10, min(120, int(duration_sec)))
        self.remaining = float(self.duration_sec)
        self._closing = False

        style.apply()
        provider = Gtk.CssProvider()
        provider.load_from_string(CLEANING_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10
        )
        self.set_css_classes(["knobu-cleaning-window"])

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        icon = Gtk.Image.new_from_icon_name("preferences-desktop-display-symbolic")
        icon.set_pixel_size(72)
        box.append(icon)

        title = Gtk.Label(label="Hardware Cleaning Mode", css_classes=["title-1"])
        box.append(title)

        self.timer_lbl = Gtk.Label(label=f"{self.duration_sec}s", css_classes=["knobu-cleaning-timer"])
        box.append(self.timer_lbl)

        self.locker = InputLocker(self.unlock, self._set_esc_progress)
        grabbed = self.locker.start()

        if grabbed > 0:
            desc_text = (
                f"Locked {grabbed} input device(s). Wipe your keyboard, touchpad, and screen safely.\n"
                "Hold Esc for 2 seconds to unlock early, or wait for the countdown."
            )
        else:
            desc_text = (
                "No evdev hardware devices could be locked (check input group permissions).\n"
                "Fullscreen screen-clean guard is active. Press Esc or click Unlock below."
            )
        desc = Gtk.Label(
            label=desc_text,
            justify=Gtk.Justification.CENTER,
            css_classes=["knobu-cleaning-hint"],
        )
        box.append(desc)

        self.esc_bar = Gtk.ProgressBar(fraction=0.0, visible=grabbed > 0)
        self.esc_bar.set_size_request(280, -1)
        box.append(self.esc_bar)

        if grabbed == 0:
            btn = Gtk.Button(label="Unlock Now", halign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
            btn.connect("clicked", lambda _b: self.unlock())
            box.append(btn)
            key_ctrl = Gtk.EventControllerKey()
            key_ctrl.connect("key-pressed", lambda _c, keyval, _kc, _st: self.unlock() or True if keyval == Gdk.KEY_Escape else False)
            self.add_controller(key_ctrl)

        self.set_child(box)
        self.connect("close-request", self._on_close_request)
        self.fullscreen()
        GLib.timeout_add(200, self._tick)

    def _set_esc_progress(self, ratio: float) -> bool:
        self.esc_bar.set_fraction(ratio)
        return GLib.SOURCE_REMOVE

    def _tick(self) -> bool:
        if self._closing:
            return GLib.SOURCE_REMOVE
        self.remaining -= 0.2
        if self.remaining <= 0:
            self.unlock()
            return GLib.SOURCE_REMOVE
        self.timer_lbl.set_label(f"{int(self.remaining) + 1}s")
        return GLib.SOURCE_CONTINUE

    def _on_close_request(self, _win) -> bool:
        self.locker.release()
        return False

    def unlock(self) -> bool:
        if not self._closing:
            self._closing = True
            self.locker.release()
            self.close()
        return GLib.SOURCE_REMOVE


class CleaningApp(ToolApp):
    suffix = "cleaning"

    def do_activate(self):
        settings = self.settings(PowerToolsModule.id)
        win = CleaningWindow(self, int(settings.get("cleaning_duration", 30)))
        win.present()


def main() -> int:
    return CleaningApp().run([])
