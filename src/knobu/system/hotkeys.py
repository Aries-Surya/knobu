"""Global keyboard shortcuts that work on Wayland and X11 on every desktop.

Reads keyboards directly. Supports exclusive grab mode so registered hotkeys
(like Super+V) can be swallowed without leaking through to active applications.
"""

import logging
import select
import threading
import time

import evdev
from evdev import ecodes as e

from knobu.system import keyboards, permissions
from knobu.system.keys import MOD_OF_CODE, Chord, held_mods

log = logging.getLogger("knobu.hotkeys")
RESCAN_SECONDS = 3
KEY_CODES = list(range(1, 0x100)) + list(range(0x160, 0x2c0))


class HotkeyService:
    def __init__(self):
        self._lock = threading.Lock()
        self._bindings: dict[int, tuple[Chord, callable, bool]] = {}
        self._next_id = 0
        self._thread: threading.Thread | None = None

    def register(self, chord: Chord, callback, exclusive: bool = False) -> int:
        with self._lock:
            self._next_id += 1
            self._bindings[self._next_id] = (chord, callback, exclusive)
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="hotkeys", daemon=True)
                self._thread.start()
            return self._next_id

    def unregister(self, binding_id: int) -> None:
        with self._lock:
            self._bindings.pop(binding_id, None)

    def _get_live_modifiers(self, devices: dict[int, evdev.InputDevice], current_dev: evdev.InputDevice) -> frozenset[str]:
        """Query live hardware key state directly to prevent stale modifier leakage."""
        active_codes: set[int] = set()
        try:
            active_codes.update(current_dev.active_keys())
        except (OSError, ValueError):
            pass
        for dev in list(devices.values()):
            if dev.fd != current_dev.fd:
                try:
                    active_codes.update(dev.active_keys())
                except (OSError, ValueError):
                    pass
        return held_mods(active_codes)

    def _fire(self, code: int, mods: frozenset[str]) -> bool:
        with self._lock:
            matches = [(cb, excl) for chord, cb, excl in self._bindings.values()
                       if chord.key == code and chord.mods == mods]
        for cb, _ in matches:
            threading.Thread(target=cb, daemon=True).start()
        return any(excl for _, excl in matches)

    def _run(self) -> None:
        devices: dict[int, evdev.InputDevice] = {}  # fd -> device
        grabbed: set[int] = set()
        consumed: set[int] = set()
        ui: evdev.UInput | None = None
        last_scan = 0.0

        try:
            while True:
                with self._lock:
                    exclusive_needed = any(excl for _, _, excl in self._bindings.values()) and permissions.can_write_uinput()

                if exclusive_needed and ui is None:
                    try:
                        ui = evdev.UInput({e.EV_KEY: KEY_CODES}, name=keyboards.VIRTUAL_KEYBOARD_NAME)
                    except Exception as err:
                        log.warning("can't create UInput for exclusive hotkeys: %s", err)
                        ui = None

                if time.monotonic() - last_scan > RESCAN_SECONDS:
                    last_scan = time.monotonic()
                    known = {d.path for d in devices.values()}
                    for dev in keyboards.open_keyboards(skip=known, include_virtual=not exclusive_needed):
                        devices[dev.fd] = dev
                        if exclusive_needed and ui is not None:
                            try:
                                dev.grab()
                                grabbed.add(dev.fd)
                            except OSError:
                                pass

                if not devices:
                    time.sleep(1)
                    continue

                ready, _, _ = select.select(list(devices), [], [], 1.0)
                for fd in ready:
                    dev = devices.get(fd)
                    if not dev:
                        continue
                    try:
                        events = list(dev.read())
                    except OSError:  # unplugged
                        devices.pop(fd, None)
                        grabbed.discard(fd)
                        continue

                    for ev in events:
                        is_grabbed = fd in grabbed and ui is not None
                        if ev.type != e.EV_KEY:
                            if is_grabbed:
                                ui.write(ev.type, ev.code, ev.value)
                                ui.syn()
                            continue

                        if ev.code in consumed:
                            if ev.value == 0:
                                consumed.discard(ev.code)
                            continue

                        if ev.value == 1 and ev.code not in MOD_OF_CODE:
                            mods = self._get_live_modifiers(devices, dev)
                            swallowed = self._fire(ev.code, mods)
                            if swallowed and is_grabbed:
                                consumed.add(ev.code)
                                if "super" in mods:
                                    ui.write(e.EV_KEY, e.KEY_F24, 1)
                                    ui.syn()
                                    ui.write(e.EV_KEY, e.KEY_F24, 0)
                                    ui.syn()
                                continue

                        if is_grabbed:
                            ui.write(e.EV_KEY, ev.code, ev.value)
                            ui.syn()
        finally:
            for fd, dev in list(devices.items()):
                if fd in grabbed:
                    try:
                        dev.ungrab()
                    except OSError:
                        pass
                dev.close()
            if ui is not None:
                ui.close()


_service: HotkeyService | None = None


def service() -> HotkeyService:
    global _service
    if _service is None:
        _service = HotkeyService()
    return _service
