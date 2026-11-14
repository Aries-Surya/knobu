"""Keyboard Manager: remap keys, expand text snippets, protect quits, and debounce keys.

Physical keyboards are grabbed (so the desktop no longer sees them directly) and their
keys are re-sent from a virtual keyboard via the unified hotkeys/input service.
"""

from __future__ import annotations

import threading
import time

from evdev import ecodes as e

from knobu.modules.base import Module
from knobu.modules.keyboard.quit_protection import QuitProtector
from knobu.modules.keyboard.remapper import Remapper, parse_remap
from knobu.modules.keyboard.snippets import TextExpander
from knobu.system import hotkeys, keys, permissions
from knobu.system.debounce import DebounceFilter


class KeyboardProcessor:
    """Handles key events: debounce, quit protection, remapping, and text snippets."""

    def __init__(
        self,
        remaps: list[tuple[keys.Chord, keys.Chord]],
        snippets: list[str] | None = None,
        enable_snippets: bool = True,
        quit_protection: bool = True,
        quit_protection_mode: str = "hold",
        quit_protection_delay: float = 0.5,
        key_debounce: bool = False,
        key_debounce_ms: float = 30.0,
    ):
        self.remapper = Remapper(remaps)
        self.expander = TextExpander(snippets) if enable_snippets and snippets else None
        self.quit_protector = (
            QuitProtector(mode=quit_protection_mode, delay=quit_protection_delay)
            if quit_protection
            else None
        )
        self.debouncer = (
            DebounceFilter(key_debounce_ms) if key_debounce else None
        )

    def process_event(self, ev, mods: frozenset[str], ui) -> bool:
        """Processes key event. Returns True if event was handled/consumed."""
        ctrl_held = "ctrl" in mods
        shift_held = "shift" in mods

        # 1. Quit & Close Protection
        if self.quit_protector:
            suppress, qp_extra = self.quit_protector.process(ev.code, ev.value, ctrl_held)
            if suppress:
                for c, v in qp_extra:
                    ui.write(e.EV_KEY, c, v)
                    ui.syn()
                return True

        # 2. Remapper
        mapped_events = self.remapper.handle(ev.code, ev.value)

        # 3. Text Snippets Expansion
        for code, value in mapped_events:
            if self.expander and not ctrl_held and not ("alt" in mods or "super" in mods):
                suppress_snip, snip_events = self.expander.process(code, value, shift_held)
                if suppress_snip:
                    for c, v in snip_events:
                        ui.write(e.EV_KEY, c, v)
                        ui.syn()
                        time.sleep(0.002)
                    continue

            ui.write(e.EV_KEY, code, value)
            ui.syn()

        return True


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

        processor = KeyboardProcessor(
            remaps=remaps,
            snippets=snippets_list,
            enable_snippets=enable_snippets,
            quit_protection=quit_protection,
            quit_protection_mode=self.settings.get("quit_protection_mode", "hold"),
            quit_protection_delay=float(self.settings.get("quit_protection_delay", 0.5)),
            key_debounce=key_debounce,
            key_debounce_ms=float(self.settings.get("key_debounce_ms", 30)),
        )

        self.log.info(
            "keyboard utilities active: remaps=%d, snippets=%d, quit_protect=%s, debounce=%s",
            len(remaps),
            len(snippets_list),
            quit_protection,
            key_debounce,
        )

        hotkeys.service().set_keyboard_processor(processor)
        try:
            stop.wait()
        finally:
            hotkeys.service().set_keyboard_processor(None)
