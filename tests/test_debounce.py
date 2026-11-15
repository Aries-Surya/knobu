import unittest

from evdev import ecodes as e

from knobu.system.debounce import DebounceFilter


class TestDebounceFilter(unittest.TestCase):
    def test_normal_clicks_allowed(self):
        deb = DebounceFilter(debounce_ms=35)
        # First press at t=1.0
        self.assertFalse(deb.should_suppress(e.BTN_LEFT, 1, now=1.0))
        # Release at t=1.1 (100ms later)
        self.assertFalse(deb.should_suppress(e.BTN_LEFT, 0, now=1.1))
        # Second press at t=1.2 (100ms later)
        self.assertFalse(deb.should_suppress(e.BTN_LEFT, 1, now=1.2))

    def test_switch_bounce_suppressed(self):
        deb = DebounceFilter(debounce_ms=35)
        # Press at t=1.0
        self.assertFalse(deb.should_suppress(e.BTN_LEFT, 1, now=1.0))
        # Release at t=1.05
        self.assertFalse(deb.should_suppress(e.BTN_LEFT, 0, now=1.05))
        # Spurious chatter press at t=1.06 (only 10ms after release!)
        self.assertTrue(deb.should_suppress(e.BTN_LEFT, 1, now=1.06))

    def test_release_bounce_suppressed(self):
        deb = DebounceFilter(debounce_ms=35)
        # Press at t=1.0
        self.assertFalse(deb.should_suppress(e.KEY_A, 1, now=1.0))
        # Spurious release bounce at t=1.005 (5ms after press!)
        self.assertTrue(deb.should_suppress(e.KEY_A, 0, now=1.005))

    def test_autorepeat_never_suppressed(self):
        deb = DebounceFilter(debounce_ms=50)
        self.assertFalse(deb.should_suppress(e.KEY_A, 2, now=1.0))
        self.assertFalse(deb.should_suppress(e.KEY_A, 2, now=1.01))


if __name__ == "__main__":
    unittest.main()
