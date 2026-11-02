"""Key names and shortcuts ("Ctrl+Alt+T") as used in the config, the UI and the daemon.

Keys are stored as lowercase evdev names without the KEY_ prefix ("capslock", "esc",
"t"), joined with "+" after any modifiers ("ctrl+alt+t"). Modifiers match either the
left or right key.
"""

from dataclasses import dataclass

from evdev import ecodes as e

MODIFIERS = {
    "ctrl": (e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL),
    "alt": (e.KEY_LEFTALT, e.KEY_RIGHTALT),
    "shift": (e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT),
    "super": (e.KEY_LEFTMETA, e.KEY_RIGHTMETA),
}
MOD_OF_CODE = {code: name for name, codes in MODIFIERS.items() for code in codes}
MOD_ORDER = ["super", "ctrl", "alt", "shift"]

ALIASES = {
    "control": "ctrl", "win": "super", "meta": "super", "cmd": "super",
    "escape": "esc", "return": "enter", "del": "delete", "ins": "insert",
    "caps": "capslock", "pgup": "pageup", "pgdn": "pagedown", "altgr": "rightalt",
}
PRETTY = {
    "esc": "Esc", "capslock": "CapsLock", "pageup": "PageUp", "pagedown": "PageDown",
    "leftctrl": "Left Ctrl", "rightctrl": "Right Ctrl", "leftalt": "Left Alt",
    "rightalt": "AltGr", "leftshift": "Left Shift", "rightshift": "Right Shift",
    "leftmeta": "Left Super", "rightmeta": "Right Super", "sysrq": "PrintScreen",
    "backspace": "Backspace", "numlock": "NumLock", "scrolllock": "ScrollLock",
}


@dataclass(frozen=True)
class Chord:
    mods: frozenset[str]
    key: int

    def __str__(self) -> str:
        return "+".join([*(m for m in MOD_ORDER if m in self.mods), key_name(self.key)])


def key_name(code: int) -> str:
    name = e.KEY.get(code) or e.BTN.get(code) or f"KEY_{code}"
    if isinstance(name, list):  # some codes have several names; the first is canonical
        name = name[0]
    return name.removeprefix("KEY_").lower()


def key_code(name: str) -> int:
    name = ALIASES.get(name, name)
    if name in MODIFIERS:
        return MODIFIERS[name][0]
    code = e.ecodes.get("KEY_" + name.upper())
    if code is None:
        raise ValueError(f"unknown key: {name!r}")
    return code


def parse(text: str) -> Chord:
    parts = [p.strip().lower() for p in text.split("+")]
    if not all(parts):
        raise ValueError(f"incomplete shortcut: {text!r}")
    mods = []
    for p in parts[:-1]:
        p = ALIASES.get(p, p)
        if p not in MODIFIERS:
            raise ValueError(f"not a modifier: {p!r}")
        mods.append(p)
    return Chord(frozenset(mods), key_code(parts[-1]))


def held_mods(pressed: set[int]) -> frozenset[str]:
    return frozenset(MOD_OF_CODE[c] for c in pressed if c in MOD_OF_CODE)


def pretty(text: str) -> str:
    """'ctrl+alt+t' -> 'Ctrl+Alt+T' for display."""
    try:
        chord = parse(text)
    except ValueError:
        return text
    names = [m.capitalize() for m in MOD_ORDER if m in chord.mods]
    key = key_name(chord.key)
    names.append(PRETTY.get(key, key.upper() if len(key) == 1 else key.capitalize()))
    return "+".join(names)
