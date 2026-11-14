"""Multi-finger drag, swipe and tap recognition, independent of evdev so it can be tested.

Feed it one frame per touchpad report: the current finger count and the X/Y positions of
each tracked contact. It calls back into a listener when gestures start, move and end.
"""

from dataclasses import dataclass
import math
from typing import Protocol


class GestureListener(Protocol):
    def on_drag_start(self, fingers: int = 3) -> None: ...
    def on_drag(self, fingers: int = 3, travel_mm: float = 0.0) -> None: ...  # signed, up = positive
    def on_drag_end(self, fingers: int = 3) -> None: ...
    def on_swipe(self, fingers: int, direction: str) -> None: ...  # "up", "down", "left", "right"
    def on_tap(self, fingers: int) -> None: ...


@dataclass
class GestureConfig:
    drag_fingers: int | set[int] = 3
    min_tap_fingers: int = 3  # fewer fingers are left to the desktop (click, right-click)
    drag_deadzone_mm: float = 3.0
    swipe_threshold_mm: float = 12.0
    tap_max_ms: int = 250
    tap_max_move_mm: float = 2.0


class GestureRecognizer:
    def __init__(self, cfg: GestureConfig, units_per_mm: float | tuple[float, float], listener: GestureListener):
        self.cfg = cfg
        if isinstance(units_per_mm, (int, float)):
            self.upm_x = float(units_per_mm)
            self.upm_y = float(units_per_mm)
        else:
            self.upm_x = float(units_per_mm[0])
            self.upm_y = float(units_per_mm[1])
        self.upm = self.upm_y  # alias for backward compatibility
        self.listener = listener
        self._prev_xs: dict[int, int] = {}
        self._prev_ys: dict[int, int] = {}
        self._reset()

    def _reset(self) -> None:
        self._active = False        # any finger down since last full lift
        self._max_fingers = 0       # most fingers down at once in this touch
        self._max_since = None      # when that finger count was reached
        self._moved = 0.0           # total movement in units
        self._travel_x_mm = 0.0     # signed horizontal travel in mm (right = +)
        self._travel_y_mm = 0.0     # signed vertical travel in mm (up = +)
        self._dragging = False
        self._swipe_triggered = False

    def _is_drag_enabled(self, fingers: int) -> bool:
        if isinstance(self.cfg.drag_fingers, set):
            return fingers in self.cfg.drag_fingers
        return fingers == self.cfg.drag_fingers

    def frame(self, fingers: int, *args) -> None:
        if len(args) == 2:
            xs: dict[int, int] = {}
            ys: dict[int, int] = args[0]
            now: float = args[1]
        elif len(args) >= 3:
            xs = args[0]
            ys = args[1]
            now = args[2]
        else:
            return

        common_y = ys.keys() & self._prev_ys.keys()
        dy = sum(self._prev_ys[s] - ys[s] for s in common_y) / len(common_y) if common_y else 0.0
        self._prev_ys = dict(ys)

        common_x = xs.keys() & self._prev_xs.keys()
        dx = sum(xs[s] - self._prev_xs[s] for s in common_x) / len(common_x) if common_x else 0.0
        self._prev_xs = dict(xs)

        dx_mm = dx / self.upm_x if self.upm_x else 0.0
        dy_mm = dy / self.upm_y if self.upm_y else 0.0

        if fingers:
            self._active = True
        if fingers > self._max_fingers:
            self._max_fingers = fingers
            self._max_since = now
        if fingers >= self.cfg.min_tap_fingers:
            self._moved += math.hypot(abs(dx), abs(dy))

        # Accumulate movement if finger count is active and valid
        if fingers >= self.cfg.min_tap_fingers:
            self._travel_x_mm += dx_mm
            self._travel_y_mm += dy_mm

            # Check continuous drag (e.g. volume slide)
            if self._is_drag_enabled(fingers) and self._max_fingers == fingers:
                self._update_drag(fingers)

            # Check discrete swipe
            if not self._dragging and not self._swipe_triggered:
                self._check_swipe(fingers)

        if fingers == 0 and self._active:
            self._finish(now)

    def _update_drag(self, fingers: int) -> None:
        if not self._dragging:
            if abs(self._travel_y_mm) < self.cfg.drag_deadzone_mm:
                return
            self._dragging = True
            self._travel_y_mm = 0.0  # measure from here so value does not jump
            self._call_on_drag_start(fingers)
        self._call_on_drag(fingers, self._travel_y_mm)

    def _check_swipe(self, fingers: int) -> None:
        dist_x = abs(self._travel_x_mm)
        dist_y = abs(self._travel_y_mm)

        if dist_x >= self.cfg.swipe_threshold_mm and dist_x > dist_y:
            direction = "right" if self._travel_x_mm > 0 else "left"
            self._swipe_triggered = True
            self._call_on_swipe(fingers, direction)
        elif dist_y >= self.cfg.swipe_threshold_mm and dist_y > dist_x and not self._is_drag_enabled(fingers):
            direction = "up" if self._travel_y_mm > 0 else "down"
            self._swipe_triggered = True
            self._call_on_swipe(fingers, direction)

    def _call_on_drag_start(self, fingers: int) -> None:
        fn = getattr(self.listener, "on_drag_start", None)
        if fn:
            try:
                fn(fingers)
            except TypeError:
                fn()

    def _call_on_drag(self, fingers: int, travel_mm: float) -> None:
        fn = getattr(self.listener, "on_drag", None)
        if fn:
            try:
                fn(fingers, travel_mm)
            except TypeError:
                fn(travel_mm)

    def _call_on_drag_end(self, fingers: int) -> None:
        fn = getattr(self.listener, "on_drag_end", None)
        if fn:
            try:
                fn(fingers)
            except TypeError:
                fn()

    def _call_on_swipe(self, fingers: int, direction: str) -> None:
        fn = getattr(self.listener, "on_swipe", None)
        if fn:
            try:
                fn(fingers, direction)
            except TypeError:
                fn(direction)

    def _call_on_tap(self, fingers: int) -> None:
        fn = getattr(self.listener, "on_tap", None)
        if fn:
            fn(fingers)

    def _finish(self, now: float) -> None:
        if self._dragging:
            self._call_on_drag_end(self._max_fingers)
        elif (
            not self._swipe_triggered
            and self._max_fingers >= self.cfg.min_tap_fingers
            and (now - self._max_since) * 1000 <= self.cfg.tap_max_ms
            and self._moved <= self.cfg.tap_max_move_mm * self.upm_y
        ):
            self._call_on_tap(self._max_fingers)
        self._reset()
