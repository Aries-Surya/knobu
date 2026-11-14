"""Finding keyboard input devices."""

import evdev
from evdev import ecodes as e

VIRTUAL_KEYBOARD_NAME = "Knobu virtual keyboard"


def is_keyboard(dev: evdev.InputDevice) -> bool:
    keys = set(dev.capabilities().get(e.EV_KEY, []))
    return {e.KEY_A, e.KEY_Z, e.KEY_SPACE, e.KEY_ENTER} <= keys


def open_keyboards(skip: set[str] = frozenset(), include_virtual: bool = True) -> list:
    """Open every keyboard whose path isn't in `skip`."""
    found = []
    for path in evdev.list_devices():
        if path in skip:
            continue
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        name_lower = dev.name.lower()
        is_virt = dev.name == VIRTUAL_KEYBOARD_NAME or "virtual" in name_lower or "helper" in name_lower
        if is_keyboard(dev) and (include_virtual or not is_virt):
            found.append(dev)
        else:
            dev.close()
    return found
