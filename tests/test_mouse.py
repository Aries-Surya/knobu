import unittest
from unittest.mock import MagicMock

from evdev import InputEvent
from evdev import ecodes as e

from knobu.modules.mouse import MouseModule, MouseProcessor
from knobu.system.debounce import DebounceFilter


class TestMouse(unittest.TestCase):
    def test_module_defaults(self):
        self.assertEqual(MouseModule.id, "mouse")
        self.assertEqual(MouseModule.name, "Mouse Utilities")
        self.assertTrue(MouseModule.defaults["enabled"])
        self.assertFalse(MouseModule.defaults["invert_wheel"])
        self.assertEqual(MouseModule.defaults["scroll_multiplier"], 1.0)
        self.assertFalse(MouseModule.defaults["mouse_debounce"])
        self.assertEqual(MouseModule.defaults["mouse_debounce_ms"], 40)

    def test_wheel_inversion(self):
        proc = MouseProcessor(invert_wheel=True, scroll_multiplier=1.0)
        # Normal scroll down (+1) becomes -1
        ev = InputEvent(1, 0, e.EV_REL, e.REL_WHEEL, 1)
        res = proc.process_event(ev)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0], (e.EV_REL, e.REL_WHEEL, -1))

        # Normal scroll up (-1) becomes +1
        ev_up = InputEvent(1, 0, e.EV_REL, e.REL_WHEEL, -1)
        res_up = proc.process_event(ev_up)
        self.assertEqual(res_up[0], (e.EV_REL, e.REL_WHEEL, 1))

    def test_scroll_multiplier(self):
        proc = MouseProcessor(invert_wheel=False, scroll_multiplier=2.5)
        ev = InputEvent(1, 0, e.EV_REL, e.REL_WHEEL, 2)
        res = proc.process_event(ev)
        self.assertEqual(res[0], (e.EV_REL, e.REL_WHEEL, 5))

    def test_mouse_button_debounce(self):
        deb = DebounceFilter(debounce_ms=40)
        proc = MouseProcessor(debouncer=deb)

        # Press at t=1.0
        ev_down = InputEvent(1, 0, e.EV_KEY, e.BTN_LEFT, 1)
        res1 = proc.process_event(ev_down)
        self.assertEqual(len(res1), 1)

        # Release at t=1.05
        ev_up = InputEvent(1, 50000, e.EV_KEY, e.BTN_LEFT, 0)
        proc.debouncer._last_release[e.BTN_LEFT] = 1.05

        # Spurious double click at t=1.06 (only 10ms after release)
        deb.should_suppress = MagicMock(return_value=True)
        res_bounce = proc.process_event(ev_down)
        self.assertEqual(len(res_bounce), 0)  # Suppressed!

    def test_pointer_movement_passes_through(self):
        proc = MouseProcessor(invert_wheel=True, scroll_multiplier=2.0)
        ev_x = InputEvent(1, 0, e.EV_REL, e.REL_X, 15)
        res_x = proc.process_event(ev_x)
        self.assertEqual(res_x[0], (e.EV_REL, e.REL_X, 15))


if __name__ == "__main__":
    unittest.main()
