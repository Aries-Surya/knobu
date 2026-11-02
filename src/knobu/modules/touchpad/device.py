"""Finding the touchpad and turning its raw evdev events into gesture frames.

The device is read without grabbing it, so the desktop keeps receiving the same events
and normal pointer movement, scrolling and desktop gestures keep working.
"""

import time

import evdev
from evdev import ecodes as e

from knobu.modules.touchpad.gestures import GestureRecognizer

FINGER_TOOLS = {
    e.BTN_TOOL_FINGER: 1, e.BTN_TOOL_DOUBLETAP: 2, e.BTN_TOOL_TRIPLETAP: 3,
    e.BTN_TOOL_QUADTAP: 4, e.BTN_TOOL_QUINTTAP: 5,
}


def find_touchpad(path: str = "") -> evdev.InputDevice | None:
    if path:
        return evdev.InputDevice(path)
    for p in evdev.list_devices():
        dev = evdev.InputDevice(p)
        abs_codes = [code for code, _ in dev.capabilities().get(e.EV_ABS, [])]
        if "touchpad" in dev.name.lower() and e.ABS_MT_POSITION_Y in abs_codes:
            return dev
        dev.close()
    return None


def units_per_mm(dev: evdev.InputDevice) -> float:
    return dev.absinfo(e.ABS_MT_POSITION_Y).resolution or 12


class FrameTracker:
    """Accumulates multitouch slot state and emits a frame on each SYN_REPORT."""

    def __init__(self, recognizer: GestureRecognizer):
        self.recognizer = recognizer
        self.slot = 0
        self.ys: dict[int, int] = {}
        self.fingers = 0

    def feed(self, ev: evdev.InputEvent) -> None:
        if ev.type == e.EV_ABS:
            if ev.code == e.ABS_MT_SLOT:
                self.slot = ev.value
            elif ev.code == e.ABS_MT_TRACKING_ID and ev.value == -1:
                self.ys.pop(self.slot, None)
            elif ev.code == e.ABS_MT_POSITION_Y:
                self.ys[self.slot] = ev.value
        elif ev.type == e.EV_KEY and ev.code in FINGER_TOOLS:
            if ev.value:
                self.fingers = FINGER_TOOLS[ev.code]
            elif self.fingers == FINGER_TOOLS[ev.code]:
                self.fingers = 0
        elif ev.type == e.EV_SYN and ev.code == e.SYN_REPORT:
            self.recognizer.frame(self.fingers, self.ys, time.monotonic())
