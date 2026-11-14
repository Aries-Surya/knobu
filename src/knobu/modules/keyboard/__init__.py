"""Keyboard Manager: remap keys, expand text snippets, protect quits, and debounce keys.

Physical keyboards are grabbed (so the desktop no longer sees them directly) and their
keys are re-sent from a virtual keyboard. Nothing is grabbed while there are no active
keyboard tools, and if anything goes wrong the grab is released so typing keeps working.
"""

from __future__ import annotations

import select
import threading
import time

from knobu.modules.base import Module
from knobu.modules.keyboard.quit_protection import QuitProtector
from knobu.modules.keyboard.remapper import Remapper, parse_remap
from knobu.modules.keyboard.snippets import TextExpander
from knobu.system import keys, permissions
from knobu.system.debounce import DebounceFilter

RESCAN_SECONDS = 3.0


class KeyboardModule(Module):
    id = "keyboard"
    name = "Keyboard Manager"
    description = "Remap keys, expand text snippets, prevent accidental quit, and debounce keys."
    icon = "knobu-keyboard-symbolic"
    defaults = {
        "enabled": True,
        "remaps": [],
        "snippets": [
            ";email -> user@example.com",
            ";date -> {date}",
            ";time -> {time}",
        ],
        "enable_snippets": True,
        "quit_protection": True,
        "quit_protection_mode": "hold",
        "quit_protection_delay": 0.5,
        "key_debounce": False,
        "key_debounce_ms": 30,
    }

    def run(self, stop: threading.Event) -> None:
        remaps = []
        for text in self.settings.get("remaps", []):
            try:
                src, dst = parse_remap(text)
                remaps.append((keys.parse(src), keys.parse(dst)))
            except ValueError as err:
                self.log.warning("skipping remap: %s", err)

        enable_snippets = bool(self.settings.get("enable_snippets", True))
        snippets_list = self.settings.get("snippets", []) if enable_snippets else []
        quit_protection = bool(self.settings.get("quit_protection", True))
        key_debounce = bool(self.settings.get("key_debounce", False))

        has_work = bool(remaps) or bool(snippets_list) or quit_protection or key_debounce
        if not has_work:
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
        expander = TextExpander(snippets_list) if enable_snippets and snippets_list else None
        quit_protector = (
            QuitProtector(
                mode=self.settings.get("quit_protection_mode", "hold"),
                delay=float(self.settings.get("quit_protection_delay", 0.5)),
            )
            if quit_protection
            else None
        )
        debouncer = (
            DebounceFilter(float(self.settings.get("key_debounce_ms", 30)))
            if key_debounce
            else None
        )

        grabbed: dict[int, evdev.InputDevice] = {}
        self.log.info(
            "keyboard utilities active: remaps=%d, snippets=%d, quit_protect=%s, debounce=%s",
            len(remaps),
            len(snippets_list),
            quit_protection,
            key_debounce,
        )

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
                        if ev.type != e.EV_KEY:
                            continue

                        # 1. Debounce check
                        if debouncer and debouncer.should_suppress(ev.code, ev.value):
                            continue

                        # Active modifier state
                        ctrl_held = bool(keys.held_mods(remapper.pressed) & {"ctrl"})
                        shift_held = bool(keys.held_mods(remapper.pressed) & {"shift"})

                        # 2. Quit & Close Protection
                        if quit_protector:
                            suppress, qp_extra = quit_protector.process(ev.code, ev.value, ctrl_held)
                            if suppress:
                                for c, v in qp_extra:
                                    ui.write(e.EV_KEY, c, v)
                                if qp_extra:
                                    ui.syn()
                                continue

                        # 3. Remapper
                        mapped_events = remapper.handle(ev.code, ev.value)

                        # 4. Text Snippets Expansion
                        for code, value in mapped_events:
                            if expander and not ctrl_held:
                                suppress_snip, snip_events = expander.process(code, value, shift_held)
                                if suppress_snip:
                                    for c, v in snip_events:
                                        ui.write(e.EV_KEY, c, v)
                                    if snip_events:
                                        ui.syn()
                                    continue

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
        deadline = time.monotonic() + 5.0
        while dev.active_keys() and time.monotonic() < deadline and not stop.is_set():
            time.sleep(0.05)
        try:
            dev.grab()
        except OSError as err:
            self.log.warning("can't grab %s: %s", dev.name, err)
            dev.close()
            return False
        self.log.info("grabbed keyboard: %s", dev.name)
        return True
