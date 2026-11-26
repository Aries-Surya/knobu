"""Mouse Utilities: independent wheel inversion, smooth scroll adjustments, and hardware debounce.

Intersects physical mice via evdev and re-emits through a virtual mouse.
Nothing is grabbed if no custom mouse features are enabled.
"""

from __future__ import annotations

import select
import threading
import time

import evdev
from evdev import ecodes as e

from knobu.modules.base import Module
from knobu.system import hotkeys, keys, launch, mice, permissions
from knobu.system.debounce import DebounceFilter
from knobu.ui.pointer_fx import ShakeDetector, sync_gnome_locate_pointer

RESCAN_SECONDS = 3.0


class MouseProcessor:
    """Processes mouse events, applying inversion, scroll multiplier, and debounce."""

    def __init__(
        self,
        invert_wheel: bool = False,
        invert_hwheel: bool = False,
        scroll_multiplier: float = 1.0,
        debouncer: DebounceFilter | None = None,
    ):
        self.invert_wheel = invert_wheel
        self.invert_hwheel = invert_hwheel
        self.scroll_multiplier = scroll_multiplier
        self.debouncer = debouncer

    def process_event(self, ev: evdev.InputEvent) -> list[tuple[int, int, int]]:
        """Returns list of (type, code, value) to emit."""
        if ev.type == e.EV_REL:
            if ev.code in (e.REL_WHEEL, getattr(e, "REL_WHEEL_HI_RES", -1)):
                val = -ev.value if self.invert_wheel else ev.value
                if self.scroll_multiplier != 1.0:
                    scaled = int(round(val * self.scroll_multiplier))
                    val = scaled if scaled != 0 else (1 if val > 0 else -1)
                return [(ev.type, ev.code, val)]

            if ev.code in (e.REL_HWHEEL, getattr(e, "REL_HWHEEL_HI_RES", -1)):
                val = -ev.value if self.invert_hwheel else ev.value
                return [(ev.type, ev.code, val)]

            return [(ev.type, ev.code, ev.value)]

        if ev.type == e.EV_KEY:
            if self.debouncer and ev.code in (e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE):
                if self.debouncer.should_suppress(ev.code, ev.value):
                    return []  # Suppress bounce
            return [(ev.type, ev.code, ev.value)]

        if ev.type == e.EV_SYN:
            return [(ev.type, ev.code, ev.value)]

        return [(ev.type, ev.code, ev.value)]


class MouseModule(Module):
    id = "mouse"
    name = "Mouse Utilities"
    description = "Independent wheel inversion, smooth scroll adjustments, and hardware debounce."
    icon = "input-mouse-symbolic"
    defaults = {
        "enabled": True,
        "bypass": False,
        "invert_wheel": False,
        "invert_hwheel": False,
        "scroll_multiplier": 1.0,
        "mouse_debounce": False,
        "mouse_debounce_ms": 40,
        "find_my_mouse": False,
        "find_my_mouse_hotkey": "super+alt+f",
        "mouse_shake_trigger": True,
    }

    def run(self, stop: threading.Event) -> None:
        if bool(self.settings.get("bypass", False)):
            sync_gnome_locate_pointer(False)
            self.log.info("mouse utilities bypassed by user")
            return

        find_my_mouse = bool(self.settings.get("find_my_mouse", False))
        sync_gnome_locate_pointer(find_my_mouse)

        invert_wheel = bool(self.settings.get("invert_wheel", False))
        invert_hwheel = bool(self.settings.get("invert_hwheel", False))
        scroll_multiplier = float(self.settings.get("scroll_multiplier", 1.0))
        mouse_debounce = bool(self.settings.get("mouse_debounce", False))
        debounce_ms = float(self.settings.get("mouse_debounce_ms", 40))
        shake_enabled = find_my_mouse and bool(self.settings.get("mouse_shake_trigger", True))

        binding = None
        if find_my_mouse:
            raw_hk = str(self.settings.get("find_my_mouse_hotkey", "")).strip()
            if raw_hk:
                try:
                    binding = hotkeys.service().register(keys.parse(raw_hk), lambda: launch.knobu("find-mouse"))
                except ValueError as err:
                    self.log.warning("bad find_my_mouse_hotkey %s: %s", raw_hk, err)

        has_work = invert_wheel or invert_hwheel or (scroll_multiplier != 1.0) or mouse_debounce or shake_enabled
        if not has_work:
            try:
                stop.wait()
            finally:
                if binding:
                    hotkeys.service().unregister(binding)
            return

        if not permissions.can_write_uinput():
            self.log.error("can't open /dev/uinput for virtual mouse")
            return

        debouncer = DebounceFilter(debounce_ms) if mouse_debounce else None
        shake = ShakeDetector() if shake_enabled else None
        processor = MouseProcessor(
            invert_wheel=invert_wheel,
            invert_hwheel=invert_hwheel,
            scroll_multiplier=scroll_multiplier,
            debouncer=debouncer,
        )

        caps = {
            e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL],
            e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE, e.BTN_SIDE, e.BTN_EXTRA],
        }
        ui = evdev.UInput(caps, name=mice.VIRTUAL_MOUSE_NAME)
        grabbed: dict[int, evdev.InputDevice] = {}
        self.log.info("mouse utilities active (invert_wheel=%s, multiplier=%.2f, debounce=%s)",
                      invert_wheel, scroll_multiplier, mouse_debounce)

        try:
            last_scan = 0.0
            while not stop.is_set():
                if time.monotonic() - last_scan > RESCAN_SECONDS:
                    last_scan = time.monotonic()
                    known = {d.path for d in grabbed.values()}
                    for dev in mice.open_mice(skip=known, include_virtual=False):
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
                    except OSError:
                        grabbed.pop(fd).close()
                        continue

                    for ev in events:
                        if shake and ev.type == e.EV_REL and ev.code == e.REL_X:
                            if shake.feed(ev.value):
                                launch.knobu("find-mouse")
                        emitted = processor.process_event(ev)
                        for ev_type, ev_code, ev_val in emitted:
                            ui.write(ev_type, ev_code, ev_val)
                        if emitted:
                            ui.syn()
        finally:
            if binding:
                hotkeys.service().unregister(binding)
            for dev in grabbed.values():
                try:
                    dev.ungrab()
                except OSError:
                    pass
                dev.close()
            ui.close()

    def _grab(self, dev: evdev.InputDevice, stop: threading.Event) -> bool:
        deadline = time.monotonic() + 3.0
        while dev.active_keys() and time.monotonic() < deadline and not stop.is_set():
            time.sleep(0.05)
        try:
            dev.grab()
        except OSError as err:
            self.log.warning("can't grab mouse %s: %s", dev.name, err)
            dev.close()
            return False
        self.log.info("grabbed mouse: %s", dev.name)
        return True
