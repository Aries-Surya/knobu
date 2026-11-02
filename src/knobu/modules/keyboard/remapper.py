"""Key and shortcut remapping logic, independent of evdev devices so it can be tested.

Feed it each physical key event; it returns the key events to send from the virtual
keyboard instead.
"""

from evdev import ecodes as e

from knobu.system.keys import MOD_OF_CODE, MODIFIERS, Chord, held_mods

# Desktops open their launcher when Super is pressed and released on its own. Tapping an
# unused key in between tells them Super was part of a shortcut.
SUPER_KEYS = set(MODIFIERS["super"])
DISARM_KEY = e.KEY_F24


def parse_remap(text: str) -> tuple[str, str]:
    src, sep, dst = text.partition("->")
    if not sep or not src.strip() or not dst.strip():
        raise ValueError(f"remap must look like 'from -> to': {text!r}")
    return src.strip(), dst.strip()


class Remapper:
    def __init__(self, remaps: list[tuple[Chord, Chord]]):
        # A plain key -> plain key remap swaps the key everywhere, even inside shortcuts
        # (so CapsLock -> Ctrl works as a real Ctrl). Anything with modifiers is a shortcut.
        self.simple = {s.key: d.key for s, d in remaps if not s.mods and not d.mods}
        self.chords = [(s, d) for s, d in remaps if s.mods or d.mods]
        self.pressed: set[int] = set()        # keys held on the virtual keyboard
        self.consumed: dict[int, Chord] = {}  # physical key -> shortcut it triggered
        self._super_used = False              # a shortcut fired while Super was held

    def handle(self, code: int, value: int) -> list[tuple[int, int]]:
        """value: 1 press, 0 release, 2 autorepeat. Returns (code, value) to emit."""
        if code in self.consumed:
            if value == 0:
                del self.consumed[code]
                return []
            return self._tap(self.consumed[code]) if value == 2 else []

        mapped = self.simple.get(code, code)
        if value == 1 and mapped not in MOD_OF_CODE:
            mods = held_mods(self.pressed)
            for src, dst in self.chords:
                if src.key == mapped and src.mods == mods:
                    self.consumed[code] = dst
                    return self._tap(dst)

        out = []
        if value == 1:
            self.pressed.add(mapped)
        elif value == 0:
            self.pressed.discard(mapped)
            if mapped in SUPER_KEYS and self._super_used:
                out += [(DISARM_KEY, 1), (DISARM_KEY, 0)]
                self._super_used = False
        return out + [(mapped, value)]

    def _tap(self, dst: Chord) -> list[tuple[int, int]]:
        """Press and release `dst`, temporarily lifting held modifiers it doesn't use."""
        held = sorted(c for c in self.pressed if c in MOD_OF_CODE)
        lift = [c for c in held if MOD_OF_CODE[c] not in dst.mods]
        add = [MODIFIERS[m][0] for m in sorted(dst.mods) if m not in held_mods(self.pressed)]
        out = []
        if any(c in SUPER_KEYS for c in lift):
            out += [(DISARM_KEY, 1), (DISARM_KEY, 0)]
        if any(c in SUPER_KEYS for c in held):
            self._super_used = True
        out += [(c, 0) for c in lift]
        out += [(c, 1) for c in add]
        out += [(dst.key, 1), (dst.key, 0)]
        out += [(c, 0) for c in reversed(add)]
        out += [(c, 1) for c in lift]
        return out
