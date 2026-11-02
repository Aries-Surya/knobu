"""Keyboard Manager: remap keys and shortcuts on every keyboard, on Wayland and X11.

Physical keyboards are grabbed (so the desktop no longer sees them directly) and their
keys are re-sent, remapped, from a virtual keyboard. Nothing is grabbed while there are
no remaps, and if anything goes wrong the grab is released so typing keeps working.
"""

import select
import threading
import time

from knobu.modules.base import Module
from knobu.modules.keyboard.remapper import Remapper, parse_remap
from knobu.system import keys, permissions

RESCAN_SECONDS = 3


class KeyboardModule(Module):
    id = "keyboard"
    name = "Keyboard Manager"
    description = "Remap keys and shortcuts on every keyboard, in every app."
    icon = "knobu-keyboard-symbolic"
    defaults = {"enabled": True, "remaps": []}

    def run(self, stop: threading.Event) -> None:
        remaps = []
        for text in self.settings["remaps"]:
            try:
                src, dst = parse_remap(text)
                remaps.append((keys.parse(src), keys.parse(dst)))
            except ValueError as err:
                self.log.warning("skipping remap: %s", err)
        if not remaps:
            return
        if not permissions.can_write_uinput():
            self.log.error("can't open /dev/uinput; see the Keyboard Manager page for the fix")
            return

        import evdev
        from evdev import ecodes as e

        from knobu.system import keyboards

        codes = list(range(1, 0x100)) + list(range(0x160, 0x2c0))  # keys, not buttons
        ui = evdev.UInput({e.EV_KEY: codes}, name=keyboards.VIRTUAL_KEYBOARD_NAME)
        remapper = Remapper(remaps)
        grabbed: dict[int, evdev.InputDevice] = {}
        self.log.info("remapping: %s", ", ".join(self.settings["remaps"]))
        try:
            last_scan = 0.0
            while not stop.is_set():
                if time.monotonic() - last_scan > RESCAN_SECONDS:
                    last_scan = time.monotonic()
                    known = {d.path for d in grabbed.values()}
                    for dev in keyboards.open_keyboards(skip=known, include_virtual=False):
                        if self._grab(dev, stop):
                            grabbed[dev.fd] = dev
                if not grabbed:
                    stop.wait(1)
                    continue
                ready, _, _ = select.select(list(grabbed), [], [], 0.5)
                for fd in ready:
                    dev = grabbed[fd]
                    try:
                        events = list(dev.read())
                    except OSError:  # unplugged
                        grabbed.pop(fd).close()
                        continue
                    for ev in events:
                        if ev.type == e.EV_KEY:
                            for code, value in remapper.handle(ev.code, ev.value):
                                ui.write(e.EV_KEY, code, value)
                                ui.syn()
        finally:
            for dev in grabbed.values():
                try:
                    dev.ungrab()
                except OSError:
                    pass
                dev.close()
            ui.close()

    def _grab(self, dev, stop: threading.Event) -> bool:
        # Grabbing while a key is held would leave it stuck down for the desktop,
        # e.g. the Enter used to start Knobu from a terminal.
        deadline = time.monotonic() + 5
        while dev.active_keys() and time.monotonic() < deadline and not stop.is_set():
            time.sleep(0.05)
        try:
            dev.grab()
        except OSError as err:
            self.log.warning("can't grab %s: %s", dev.name, err)
            dev.close()
            return False
        self.log.info("remapping keyboard: %s", dev.name)
        return True
