"""Finding mouse input devices."""

from __future__ import annotations

import evdev
from evdev import ecodes as e

VIRTUAL_MOUSE_NAME = "Knobu virtual mouse"


def is_mouse(dev: evdev.InputDevice) -> bool:
    """Returns True if the device is a pointing device with relative coordinates and buttons, excluding touchpads."""
    caps = dev.capabilities()
    if e.EV_REL not in caps or e.EV_KEY not in caps:
        return False

    rel_codes = set(caps.get(e.EV_REL, []))
    keys = set(caps.get(e.EV_KEY, []))

    # Must have pointer axes (REL_X and REL_Y)
    if not (e.REL_X in rel_codes and e.REL_Y in rel_codes):
        return False

    # Must have mouse buttons (left or generic mouse)
    if not (e.BTN_LEFT in keys or e.BTN_MOUSE in keys):
        return False

    # Exclude touchpads (touchpads have their own module)
    name_lower = dev.name.lower()
    if "touchpad" in name_lower or "trackpad" in name_lower:
        return False

    return True


def open_mice(skip: set[str] = frozenset(), include_virtual: bool = False) -> list[evdev.InputDevice]:
    """Open every mouse whose path isn't in `skip`."""
    found = []
    for path in evdev.list_devices():
        if path in skip:
            continue
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue

        if not include_virtual and ("virtual" in dev.name.lower() or dev.name == VIRTUAL_MOUSE_NAME):
            dev.close()
            continue

        if is_mouse(dev):
            found.append(dev)
        else:
            dev.close()
    return found
