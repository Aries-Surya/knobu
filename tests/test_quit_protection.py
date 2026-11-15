import unittest

from evdev import ecodes as e

from knobu.modules.keyboard.quit_protection import QuitProtector


class TestQuitProtection(unittest.TestCase):
    def test_non_protected_key_passes_through(self):
        qp = QuitProtector()
        suppress, events = qp.process(e.KEY_A, 1, ctrl_held=True)
        self.assertFalse(suppress)
        self.assertEqual(events, [])

    def test_hold_mode_suppresses_quick_tap(self):
        notifications = []
        qp = QuitProtector(mode="hold", delay=0.5, notifier=lambda t, b: notifications.append((t, b)))

        # Press Ctrl+Q at t=1.0
        suppress, events = qp.process(e.KEY_Q, 1, ctrl_held=True, now=1.0)
        self.assertTrue(suppress)  # Suppressed!
        self.assertEqual(len(notifications), 1)

        # Release at t=1.1 (quick tap, only 100ms)
        suppress, events = qp.process(e.KEY_Q, 0, ctrl_held=True, now=1.1)
        self.assertTrue(suppress)  # Release also suppressed! Target app never quits.

    def test_hold_mode_triggers_on_sustained_hold(self):
        qp = QuitProtector(mode="hold", delay=0.5, notifier=lambda t, b: None)

        # Press at t=1.0
        qp.process(e.KEY_Q, 1, ctrl_held=True, now=1.0)

        # Autorepeat at t=1.6 (held for 600ms >= 500ms delay)
        suppress, events = qp.process(e.KEY_Q, 2, ctrl_held=True, now=1.6)
        self.assertTrue(suppress)
        self.assertIn((e.KEY_Q, 1), events)

        # Normal release afterwards passes through
        suppress, events = qp.process(e.KEY_Q, 0, ctrl_held=True, now=1.7)
        self.assertFalse(suppress)

    def test_double_press_mode(self):
        notifications = []
        qp = QuitProtector(mode="double_press", delay=0.4, notifier=lambda t, b: notifications.append((t, b)))

        # First press at t=1.0
        suppress, events = qp.process(e.KEY_W, 1, ctrl_held=True, now=1.0)
        self.assertTrue(suppress)  # Intercepted!
        self.assertEqual(len(notifications), 1)

        # First release at t=1.1
        suppress, events = qp.process(e.KEY_W, 0, ctrl_held=True, now=1.1)
        self.assertTrue(suppress)

        # Second press at t=1.2 (within 400ms window!)
        suppress, events = qp.process(e.KEY_W, 1, ctrl_held=True, now=1.2)
        self.assertFalse(suppress)  # Allowed through!


if __name__ == "__main__":
    unittest.main()
