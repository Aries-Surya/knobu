"""Quit & Close Protection engine for Knobu Keyboard Manager.

Prevents accidental closing of windows and applications by requiring a hold
or double-press for Ctrl+Q and Ctrl+W.
"""

from __future__ import annotations

import time
from typing import Callable

from evdev import ecodes as e

from knobu.system import notify


class QuitProtector:
    """Filters Ctrl+Q and Ctrl+W to protect against accidental quits."""

    KEY_NAMES = {
        e.KEY_Q: "Ctrl+Q",
        e.KEY_W: "Ctrl+W",
    }

    def __init__(
        self,
        mode: str = "hold",
        delay: float = 0.5,
        protected: tuple[int, ...] = (e.KEY_Q, e.KEY_W),
        notifier: Callable[[str, str], None] | None = None,
    ):
        self.mode = mode
        self.delay = delay
        self.protected = set(protected)
        self.notify = notifier or self._default_notify

        self._holding: dict[int, float] = {}       # code -> press_time
        self._fired: set[int] = set()              # code that held past threshold
        self._last_press: dict[int, float] = {}    # code -> last_press_time (for double-press)
        self._suppressed_press: set[int] = set()

    def process(
        self,
        code: int,
        value: int,
        ctrl_held: bool,
        now: float | None = None,
    ) -> tuple[bool, list[tuple[int, int]]]:
        """Processes key events for Ctrl+Q / Ctrl+W.

        Returns: (suppress_original_event: bool, extra_events_to_emit: list[(code, value)])
        """
        if code not in self.protected or not ctrl_held:
            return False, []

        t = time.monotonic() if now is None else now
        shortcut_name = self.KEY_NAMES.get(code, "shortcut")

        if self.mode == "double_press":
            if value == 1:
                last = self._last_press.get(code, 0.0)
                if (t - last) <= self.delay:
                    # Second press within window: pass through!
                    self._last_press.pop(code, None)
                    self._suppressed_press.discard(code)
                    return False, []
                else:
                    # First press: intercept and suppress
                    self._last_press[code] = t
                    self._suppressed_press.add(code)
                    self.notify("Accidental Close Prevented", f"Press {shortcut_name} again to close")
                    return True, []
            elif value == 0:
                if code in self._suppressed_press:
                    self._suppressed_press.discard(code)
                    return True, []
                return False, []
            return False, []

        # Default mode: "hold"
        if value == 1:
            self._holding[code] = t
            self.notify("Accidental Close Prevented", f"Hold {shortcut_name} to close")
            return True, []

        if value == 2:
            # Autorepeat while held down
            if code in self._holding and code not in self._fired:
                if (t - self._holding[code]) >= self.delay:
                    # Successfully held past delay!
                    self._fired.add(code)
                    return True, [(code, 1)]
            return True, []

        if value == 0:
            press_t = self._holding.pop(code, None)
            if code in self._fired:
                self._fired.discard(code)
                return False, []  # Pass through normal release
            if press_t is not None:
                # Released before hold threshold: suppress!
                return True, []

        return False, []

    def _default_notify(self, title: str, body: str) -> None:
        try:
            notify.send(title, body)
        except Exception:
            pass
