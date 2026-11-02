"""Global keyboard shortcuts that work on Wayland and X11 on every desktop.

Reads all keyboards directly (without grabbing them), so the desktop still sees the
keys too. When Keyboard Manager is remapping, the physical keyboards are grabbed and
this listener sees the remapped keys through Knobu's virtual keyboard instead.
"""

import logging
import select
import threading
import time

import evdev
from evdev import ecodes as e

from knobu.system import keyboards
from knobu.system.keys import MOD_OF_CODE, Chord, held_mods

log = logging.getLogger("knobu.hotkeys")
RESCAN_SECONDS = 3


class HotkeyService:
    def __init__(self):
        self._lock = threading.Lock()
        self._bindings: dict[int, tuple[Chord, callable]] = {}
        self._next_id = 0
        self._thread: threading.Thread | None = None

    def register(self, chord: Chord, callback) -> int:
        with self._lock:
            self._next_id += 1
            self._bindings[self._next_id] = (chord, callback)
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="hotkeys", daemon=True)
                self._thread.start()
            return self._next_id

    def unregister(self, binding_id: int) -> None:
        with self._lock:
            self._bindings.pop(binding_id, None)

    def _fire(self, code: int, pressed: set[int]) -> None:
        mods = held_mods(pressed)
        with self._lock:
            matches = [cb for chord, cb in self._bindings.values()
                       if chord.key == code and chord.mods == mods]
        for cb in matches:
            threading.Thread(target=cb, daemon=True).start()

    def _run(self) -> None:
        devices: dict[int, evdev.InputDevice] = {}  # fd -> device
        pressed: set[int] = set()
        last_scan = 0.0
        while True:
            if time.monotonic() - last_scan > RESCAN_SECONDS:
                last_scan = time.monotonic()
                known = {d.path for d in devices.values()}
                for dev in keyboards.open_keyboards(skip=known):
                    devices[dev.fd] = dev
            if not devices:
                time.sleep(1)
                continue
            ready, _, _ = select.select(list(devices), [], [], 1.0)
            for fd in ready:
                dev = devices[fd]
                try:
                    events = list(dev.read())
                except OSError:  # unplugged
                    devices.pop(fd).close()
                    pressed.clear()
                    continue
                for ev in events:
                    if ev.type != e.EV_KEY:
                        continue
                    if ev.value == 1:
                        if ev.code not in MOD_OF_CODE:
                            self._fire(ev.code, pressed)
                        pressed.add(ev.code)
                    elif ev.value == 0:
                        pressed.discard(ev.code)


_service: HotkeyService | None = None


def service() -> HotkeyService:
    global _service
    if _service is None:
        _service = HotkeyService()
    return _service
