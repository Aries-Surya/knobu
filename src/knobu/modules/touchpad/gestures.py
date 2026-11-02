"""Multi-finger drag and tap recognition, independent of evdev so it can be tested.

Feed it one frame per touchpad report: the current finger count and the Y position of
each tracked contact. It calls back into a listener when gestures start, move and end.
"""

from dataclasses import dataclass
from typing import Protocol


class GestureListener(Protocol):
    def on_drag_start(self) -> None: ...
    def on_drag(self, travel_mm: float) -> None: ...  # signed, up = positive
    def on_drag_end(self) -> None: ...
    def on_tap(self, fingers: int) -> None: ...


@dataclass
class GestureConfig:
    drag_fingers: int = 3
    min_tap_fingers: int = 3  # fewer fingers are left to the desktop (click, right-click)
    drag_deadzone_mm: float = 3.0
    tap_max_ms: int = 250
    tap_max_move_mm: float = 2.0


class GestureRecognizer:
    def __init__(self, cfg: GestureConfig, units_per_mm: float, listener: GestureListener):
        self.cfg = cfg
        self.upm = units_per_mm
        self.listener = listener
        self._prev_ys: dict[int, int] = {}
        self._reset()

    def _reset(self) -> None:
        self._active = False        # any finger down since the last full lift
        self._max_fingers = 0       # most fingers down at once in this touch
        self._max_since = None      # when that finger count was reached
        self._moved = 0.0           # total movement with tap-sized finger counts (units)
        self._travel = 0.0          # signed vertical travel toward a drag (units, up = +)
        self._dragging = False

    def frame(self, fingers: int, ys: dict[int, int], now: float) -> None:
        # Average per-contact delta over contacts present in both frames, so fingers
        # landing or lifting at slightly different moments don't cause jumps.
        common = ys.keys() & self._prev_ys.keys()
        dy = sum(self._prev_ys[s] - ys[s] for s in common) / len(common) if common else 0.0
        self._prev_ys = dict(ys)

        if fingers:
            self._active = True
        if fingers > self._max_fingers:
            self._max_fingers = fingers
            self._max_since = now
        if fingers >= self.cfg.min_tap_fingers:
            self._moved += abs(dy)

        # Only drag while exactly the drag finger count is down and was never exceeded,
        # so e.g. a 4-finger tap never turns into a 3-finger volume drag.
        if fingers == self.cfg.drag_fingers and self._max_fingers == self.cfg.drag_fingers:
            self._travel += dy
            self._update_drag()

        if fingers == 0 and self._active:
            self._finish(now)

    def _update_drag(self) -> None:
        if not self._dragging:
            if abs(self._travel) < self.cfg.drag_deadzone_mm * self.upm:
                return
            self._dragging = True
            self._travel = 0.0  # measure from here so the value doesn't jump
            self.listener.on_drag_start()
        self.listener.on_drag(self._travel / self.upm)

    def _finish(self, now: float) -> None:
        if self._dragging:
            self.listener.on_drag_end()
        elif (self._max_fingers >= self.cfg.min_tap_fingers
              and (now - self._max_since) * 1000 <= self.cfg.tap_max_ms
              and self._moved <= self.cfg.tap_max_move_mm * self.upm):
            self.listener.on_tap(self._max_fingers)
        self._reset()
