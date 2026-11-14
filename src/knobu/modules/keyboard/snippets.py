"""Text snippets expansion engine for Knobu Keyboard Manager.

Monitors typing buffer and expands triggers (e.g., ;email -> me@example.com)
with dynamic date/time variables.
"""

from __future__ import annotations

import datetime
from evdev import ecodes as e

from knobu.system import clipboard

CHAR_TO_KEY: dict[str, tuple[int, bool]] = {
    "a": (e.KEY_A, False), "b": (e.KEY_B, False), "c": (e.KEY_C, False),
    "d": (e.KEY_D, False), "e": (e.KEY_E, False), "f": (e.KEY_F, False),
    "g": (e.KEY_G, False), "h": (e.KEY_H, False), "i": (e.KEY_I, False),
    "j": (e.KEY_J, False), "k": (e.KEY_K, False), "l": (e.KEY_L, False),
    "m": (e.KEY_M, False), "n": (e.KEY_N, False), "o": (e.KEY_O, False),
    "p": (e.KEY_P, False), "q": (e.KEY_Q, False), "r": (e.KEY_R, False),
    "s": (e.KEY_S, False), "t": (e.KEY_T, False), "u": (e.KEY_U, False),
    "v": (e.KEY_V, False), "w": (e.KEY_W, False), "x": (e.KEY_X, False),
    "y": (e.KEY_Y, False), "z": (e.KEY_Z, False),
    "A": (e.KEY_A, True), "B": (e.KEY_B, True), "C": (e.KEY_C, True),
    "D": (e.KEY_D, True), "E": (e.KEY_E, True), "F": (e.KEY_F, True),
    "G": (e.KEY_G, True), "H": (e.KEY_H, True), "I": (e.KEY_I, True),
    "J": (e.KEY_J, True), "K": (e.KEY_K, True), "L": (e.KEY_L, True),
    "M": (e.KEY_M, True), "N": (e.KEY_N, True), "O": (e.KEY_O, True),
    "P": (e.KEY_P, True), "Q": (e.KEY_Q, True), "R": (e.KEY_R, True),
    "S": (e.KEY_S, True), "T": (e.KEY_T, True), "U": (e.KEY_U, True),
    "V": (e.KEY_V, True), "W": (e.KEY_W, True), "X": (e.KEY_X, True),
    "Y": (e.KEY_Y, True), "Z": (e.KEY_Z, True),
    "0": (e.KEY_0, False), "1": (e.KEY_1, False), "2": (e.KEY_2, False),
    "3": (e.KEY_3, False), "4": (e.KEY_4, False), "5": (e.KEY_5, False),
    "6": (e.KEY_6, False), "7": (e.KEY_7, False), "8": (e.KEY_8, False),
    "9": (e.KEY_9, False),
    " ": (e.KEY_SPACE, False), "\n": (e.KEY_ENTER, False), "\t": (e.KEY_TAB, False),
    "-": (e.KEY_MINUS, False), "_": (e.KEY_MINUS, True),
    "=": (e.KEY_EQUAL, False), "+": (e.KEY_EQUAL, True),
    ";": (e.KEY_SEMICOLON, False), ":": (e.KEY_SEMICOLON, True),
    "'": (e.KEY_APOSTROPHE, False), "\"": (e.KEY_APOSTROPHE, True),
    ",": (e.KEY_COMMA, False), "<": (e.KEY_COMMA, True),
    ".": (e.KEY_DOT, False), ">": (e.KEY_DOT, True),
    "/": (e.KEY_SLASH, False), "?": (e.KEY_SLASH, True),
    "[": (e.KEY_LEFTBRACE, False), "{": (e.KEY_LEFTBRACE, True),
    "]": (e.KEY_RIGHTBRACE, False), "}": (e.KEY_RIGHTBRACE, True),
    "\\": (e.KEY_BACKSLASH, False), "|": (e.KEY_BACKSLASH, True),
    "`": (e.KEY_GRAVE, False), "~": (e.KEY_GRAVE, True),
    "!": (e.KEY_1, True), "@": (e.KEY_2, True), "#": (e.KEY_3, True),
    "$": (e.KEY_4, True), "%": (e.KEY_5, True), "^": (e.KEY_6, True),
    "&": (e.KEY_7, True), "*": (e.KEY_8, True), "(": (e.KEY_9, True),
    ")": (e.KEY_0, True),
}

# Reverse lookup: (key_code, shift_active) -> char
KEY_TO_CHAR: dict[tuple[int, bool], str] = {
    (code, shift): ch for ch, (code, shift) in CHAR_TO_KEY.items()
}


def parse_snippet(text: str) -> tuple[str, str]:
    """Parses ';email -> me@example.com' into trigger and replacement."""
    trigger, sep, expansion = text.partition("->")
    if not sep or not trigger.strip() or not expansion.strip():
        raise ValueError(f"snippet must look like 'trigger -> replacement': {text!r}")
    return trigger.strip(), expansion.strip()


def expand_variables(template: str, now: datetime.datetime | None = None) -> str:
    """Replaces dynamic variables like {date}, {time}, {datetime}."""
    t = now or datetime.datetime.now()
    return (
        template.replace("{date}", t.strftime("%Y-%m-%d"))
        .replace("{time}", t.strftime("%H:%M:%S"))
        .replace("{datetime}", t.strftime("%Y-%m-%d %H:%M:%S"))
        .replace("{year}", t.strftime("%Y"))
        .replace("{month}", t.strftime("%m"))
        .replace("{day}", t.strftime("%d"))
    )


class TextExpander:
    """Maintains a keystroke buffer and expands snippet triggers."""

    def __init__(self, snippets: list[str] | dict[str, str] | None = None):
        self.snippets: dict[str, str] = {}
        if isinstance(snippets, dict):
            self.snippets = dict(snippets)
        elif snippets:
            for item in snippets:
                try:
                    trig, exp = parse_snippet(item)
                    self.snippets[trig] = exp
                except ValueError:
                    pass

        self._buffer: list[str] = []
        self._max_buffer = 40

    def process(
        self,
        code: int,
        value: int,
        shift_held: bool,
        now: datetime.datetime | None = None,
    ) -> tuple[bool, list[tuple[int, int]]]:
        """Processes key event.

        Returns: (suppress_original_key: bool, events_to_emit: list[(code, value)])
        """
        if not self.snippets or value != 1:  # Only track on press
            return False, []

        # Handle backspace
        if code == e.KEY_BACKSPACE:
            if self._buffer:
                self._buffer.pop()
            return False, []

        # Reset on cursor movement, enter, escape, tab
        if code in (
            e.KEY_ENTER, e.KEY_KPENTER, e.KEY_ESC, e.KEY_TAB,
            e.KEY_LEFT, e.KEY_RIGHT, e.KEY_UP, e.KEY_DOWN,
            e.KEY_HOME, e.KEY_END, e.KEY_PAGEUP, e.KEY_PAGEDOWN,
        ):
            self._buffer.clear()
            return False, []

        ch = KEY_TO_CHAR.get((code, shift_held))
        if not ch:
            return False, []

        self._buffer.append(ch)
        if len(self._buffer) > self._max_buffer:
            self._buffer.pop(0)

        buf_str = "".join(self._buffer)

        # Check for matching trigger
        matched_trigger = None
        for trig in self.snippets:
            if buf_str.endswith(trig):
                matched_trigger = trig
                break

        if not matched_trigger:
            return False, []

        # Found trigger: suppress the last keypress and emit expansion
        expansion = expand_variables(self.snippets[matched_trigger], now)
        self._buffer.clear()

        # Erase the trigger: (len - 1) backspaces needed if last key was suppressed,
        # but to guarantee clean deletion on screen, we erase the trigger characters that were typed.
        # Since the current key event is suppressed (suppress=True), only len(trigger)-1 characters
        # are currently on screen!
        backspace_count = len(matched_trigger) - 1
        out: list[tuple[int, int]] = []

        for _ in range(backspace_count):
            out.append((e.KEY_BACKSPACE, 1))
            out.append((e.KEY_BACKSPACE, 0))

        # Check if expansion contains characters outside standard keycode map
        has_unicode = any(c not in CHAR_TO_KEY for c in expansion)
        if has_unicode:
            # Clipboard paste for unicode/emojis
            clipboard.set_clipboard(expansion)
            out.append((e.KEY_LEFTCTRL, 1))
            out.append((e.KEY_V, 1))
            out.append((e.KEY_V, 0))
            out.append((e.KEY_LEFTCTRL, 0))
        else:
            # Emit keycodes directly
            for c in expansion:
                key_code, needs_shift = CHAR_TO_KEY[c]
                if needs_shift:
                    out.append((e.KEY_LEFTSHIFT, 1))
                out.append((key_code, 1))
                out.append((key_code, 0))
                if needs_shift:
                    out.append((e.KEY_LEFTSHIFT, 0))

        return True, out
