import unittest
from unittest.mock import patch

from knobu.modules.touchpad.gestures import GestureConfig, GestureRecognizer

UPM = 12  # units per mm, like a typical Synaptics touchpad


class Recorder:
    def __init__(self):
        self.events = []

    def on_drag_start(self):
        self.events.append("start")

    def on_drag(self, travel_mm):
        self.events.append(round(travel_mm, 1))

    def on_drag_end(self):
        self.events.append("end")

    def on_tap(self, fingers):
        self.events.append(f"tap{fingers}")

    def on_swipe(self, fingers, direction):
        self.events.append(f"swipe{fingers}_{direction}")


def make(fingers=3):
    rec = Recorder()
    return GestureRecognizer(GestureConfig(drag_fingers=fingers), UPM, rec), rec


def touch(g, n, y, t):
    g.frame(n, {i: y for i in range(n)}, t)


class GestureTests(unittest.TestCase):
    def test_quick_tap(self):
        g, rec = make()
        touch(g, 3, 300, 0.00)
        touch(g, 3, 300, 0.10)
        g.frame(0, {}, 0.12)
        self.assertEqual(rec.events, ["tap3"])

    def test_slow_press_is_not_a_tap(self):
        g, rec = make()
        touch(g, 3, 300, 0.0)
        touch(g, 3, 300, 0.5)
        g.frame(0, {}, 0.5)
        self.assertEqual(rec.events, [])

    def test_drag_up_reports_positive_travel_after_deadzone(self):
        g, rec = make()
        touch(g, 3, 300, 0.0)
        touch(g, 3, 300 - 4 * UPM, 0.05)   # 4 mm up: crosses the 3 mm deadzone
        touch(g, 3, 300 - 14 * UPM, 0.10)  # another 10 mm up
        g.frame(0, {}, 0.2)
        self.assertEqual(rec.events, ["start", 0.0, 10.0, "end"])

    def test_drag_down_is_negative(self):
        g, rec = make()
        touch(g, 3, 300, 0.0)
        touch(g, 3, 300 + 4 * UPM, 0.05)
        touch(g, 3, 300 + 9 * UPM, 0.10)
        g.frame(0, {}, 0.2)
        self.assertEqual(rec.events, ["start", 0.0, -5.0, "end"])

    def test_two_finger_scroll_is_ignored(self):
        g, rec = make()
        touch(g, 2, 300, 0.0)
        touch(g, 2, 100, 0.1)
        g.frame(0, {}, 0.12)
        self.assertEqual(rec.events, [])

    def test_four_finger_tap_landing_via_three(self):
        g, rec = make(fingers=3)
        touch(g, 3, 300, 0.00)
        touch(g, 4, 300, 0.05)
        g.frame(0, {}, 0.10)
        self.assertEqual(rec.events, ["tap4"])

    def test_two_finger_tap_is_left_to_the_desktop(self):
        g, rec = make()
        touch(g, 2, 300, 0.00)
        g.frame(0, {}, 0.08)
        self.assertEqual(rec.events, [])

    def test_four_finger_movement_never_starts_three_finger_drag(self):
        g, rec = make(fingers=3)
        touch(g, 4, 300, 0.00)
        touch(g, 3, 300 - 10 * UPM, 0.05)  # one finger lifts while moving
        g.frame(0, {}, 0.10)
        self.assertEqual(rec.events, [])

    def test_four_finger_drag_when_configured(self):
        g, rec = make(fingers=4)
        touch(g, 4, 300, 0.0)
        touch(g, 4, 300 - 4 * UPM, 0.05)
        touch(g, 4, 300 - 9 * UPM, 0.10)
        g.frame(0, {}, 0.2)
        self.assertEqual(rec.events, ["start", 0.0, 5.0, "end"])

    def test_fingers_landing_one_by_one_still_tap(self):
        g, rec = make()
        touch(g, 1, 300, 0.00)
        touch(g, 2, 300, 0.02)
        touch(g, 3, 300, 0.04)
        g.frame(0, {}, 0.15)
        self.assertEqual(rec.events, ["tap3"])

    def test_new_contact_does_not_cause_jump(self):
        g, rec = make()
        g.frame(2, {0: 300, 1: 300}, 0.0)
        g.frame(3, {0: 300, 1: 300, 2: 100}, 0.02)  # third finger lands far away
        g.frame(0, {}, 0.1)
        self.assertEqual(rec.events, ["tap3"])

    def test_touchpad_bypass(self):
        import threading
        from knobu.modules.touchpad import TouchpadModule
        m = TouchpadModule({"enabled": True, "bypass": True})
        stop = threading.Event()
        m.run(stop)

    def test_volume_osd_detect(self):
        from knobu.system.osd import VolumeOsd
        osd = VolumeOsd(True)
        self.assertTrue(osd.available)

    def test_three_finger_swipe_horizontal(self):
        rec = Recorder()
        g = GestureRecognizer(GestureConfig(drag_fingers=set()), UPM, rec)
        # Swipe right: X increases by 15mm
        g.frame(3, {0: 100, 1: 100, 2: 100}, {0: 300, 1: 300, 2: 300}, 0.0)
        g.frame(3, {0: 100 + 15 * UPM, 1: 100 + 15 * UPM, 2: 100 + 15 * UPM}, {0: 300, 1: 300, 2: 300}, 0.1)
        g.frame(0, {}, {}, 0.2)
        self.assertEqual(rec.events, ["swipe3_right"])

        rec.events.clear()
        # Swipe left: X decreases by 15mm
        g.frame(3, {0: 300, 1: 300, 2: 300}, {0: 300, 1: 300, 2: 300}, 0.0)
        g.frame(3, {0: 300 - 15 * UPM, 1: 300 - 15 * UPM, 2: 300 - 15 * UPM}, {0: 300, 1: 300, 2: 300}, 0.1)
        g.frame(0, {}, {}, 0.2)
        self.assertEqual(rec.events, ["swipe3_left"])

    def test_four_finger_swipe_directions(self):
        rec = Recorder()
        g = GestureRecognizer(GestureConfig(drag_fingers=set()), UPM, rec)
        # 4-finger Swipe Up: Y decreases by 15mm
        g.frame(4, {i: 200 for i in range(4)}, {i: 300 for i in range(4)}, 0.0)
        g.frame(4, {i: 200 for i in range(4)}, {i: 300 - 15 * UPM for i in range(4)}, 0.1)
        g.frame(0, {}, {}, 0.2)
        self.assertEqual(rec.events, ["swipe4_up"])

        rec.events.clear()
        # 4-finger Swipe Down: Y increases by 15mm
        g.frame(4, {i: 200 for i in range(4)}, {i: 300 for i in range(4)}, 0.0)
        g.frame(4, {i: 200 for i in range(4)}, {i: 300 + 15 * UPM for i in range(4)}, 0.1)
        g.frame(0, {}, {}, 0.2)
        self.assertEqual(rec.events, ["swipe4_down"])

    @patch("knobu.modules.touchpad.native_volume_up", return_value=False)
    @patch("knobu.modules.touchpad.native_volume_down", return_value=False)
    @patch("knobu.modules.touchpad.native_mute_toggle", return_value=False)
    def test_gesture_actions_dispatch(self, _m_mute, _m_down, _m_up):
        from unittest.mock import MagicMock
        from knobu.modules.touchpad import GestureActions
        mock_audio = MagicMock()
        mock_audio.get.return_value = (50, False)
        mock_osd = MagicMock()
        actions = GestureActions({
            "swipe3_up": "volume_up",
            "swipe3_down": "volume_down",
            "swipe3_left": "previous_track",
            "swipe3_right": "next_track",
            "swipe4_up": "overview",
            "tap3_action": "mute",
        }, mock_audio, mock_osd)

        actions.on_swipe(3, "up")
        mock_audio.set_volume.assert_called_with(55)

        actions.on_swipe(3, "down")
        mock_audio.set_volume.assert_called_with(45)

        actions.on_tap(3)
        mock_audio.set_mute.assert_called()



if __name__ == "__main__":
    unittest.main()
