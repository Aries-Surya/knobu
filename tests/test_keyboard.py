import unittest

from evdev import ecodes as e

from knobu.modules.keyboard.remapper import DISARM_KEY, Remapper, parse_remap
from knobu.system import keys


def remapper(*pairs):
    return Remapper([(keys.parse(a), keys.parse(b)) for a, b in pairs])


class KeyTests(unittest.TestCase):
    def test_parse_and_format(self):
        chord = keys.parse("Control+Alt+T")
        self.assertEqual(chord.mods, {"ctrl", "alt"})
        self.assertEqual(chord.key, e.KEY_T)
        self.assertEqual(str(chord), "ctrl+alt+t")
        self.assertEqual(keys.pretty("shift+super+c"), "Super+Shift+C")
        self.assertEqual(keys.pretty("ctrl+alt+t"), "Ctrl+Alt+T")
        self.assertEqual(keys.pretty("capslock"), "CapsLock")

    def test_aliases(self):
        self.assertEqual(keys.parse("escape").key, e.KEY_ESC)
        self.assertEqual(keys.parse("win+e").mods, {"super"})

    def test_bad_input(self):
        for text in ["", "notakey", "t+ctrl", "ctrl+"]:
            with self.assertRaises(ValueError, msg=text):
                keys.parse(text)

    def test_parse_remap(self):
        self.assertEqual(parse_remap("capslock -> esc"), ("capslock", "esc"))
        with self.assertRaises(ValueError):
            parse_remap("capslock")


class RemapperTests(unittest.TestCase):
    def test_unmapped_keys_pass_through(self):
        r = remapper(("capslock", "esc"))
        self.assertEqual(r.handle(e.KEY_A, 1), [(e.KEY_A, 1)])
        self.assertEqual(r.handle(e.KEY_A, 2), [(e.KEY_A, 2)])
        self.assertEqual(r.handle(e.KEY_A, 0), [(e.KEY_A, 0)])

    def test_simple_key_swap(self):
        r = remapper(("capslock", "esc"))
        self.assertEqual(r.handle(e.KEY_CAPSLOCK, 1), [(e.KEY_ESC, 1)])
        self.assertEqual(r.handle(e.KEY_CAPSLOCK, 0), [(e.KEY_ESC, 0)])

    def test_key_remapped_to_modifier_works_in_shortcuts(self):
        r = remapper(("capslock", "ctrl"))
        self.assertEqual(r.handle(e.KEY_CAPSLOCK, 1), [(e.KEY_LEFTCTRL, 1)])
        self.assertEqual(r.handle(e.KEY_C, 1), [(e.KEY_C, 1)])  # Ctrl+C reaches the app

    def test_shortcut_to_shortcut(self):
        r = remapper(("ctrl+alt+t", "super+enter"))
        r.handle(e.KEY_LEFTCTRL, 1)
        r.handle(e.KEY_LEFTALT, 1)
        out = r.handle(e.KEY_T, 1)
        self.assertEqual(out, [
            (e.KEY_LEFTCTRL, 0), (e.KEY_LEFTALT, 0),   # lift held modifiers
            (e.KEY_LEFTMETA, 1), (e.KEY_ENTER, 1), (e.KEY_ENTER, 0), (e.KEY_LEFTMETA, 0),
            (e.KEY_LEFTCTRL, 1), (e.KEY_LEFTALT, 1),   # restore them
        ])
        self.assertEqual(r.handle(e.KEY_T, 0), [])     # the release is swallowed

    def test_shortcut_needs_exact_modifiers(self):
        r = remapper(("ctrl+t", "f5"))
        r.handle(e.KEY_LEFTCTRL, 1)
        r.handle(e.KEY_LEFTSHIFT, 1)
        self.assertEqual(r.handle(e.KEY_T, 1), [(e.KEY_T, 1)])

    def test_right_modifier_matches(self):
        r = remapper(("ctrl+t", "f5"))
        r.handle(e.KEY_RIGHTCTRL, 1)
        self.assertIn((e.KEY_F5, 1), r.handle(e.KEY_T, 1))

    def test_autorepeat_repeats_target(self):
        r = remapper(("ctrl+j", "down"))
        r.handle(e.KEY_LEFTCTRL, 1)
        r.handle(e.KEY_J, 1)
        self.assertIn((e.KEY_DOWN, 1), r.handle(e.KEY_J, 2))

    def test_super_shortcut_does_not_open_launcher(self):
        r = remapper(("super+e", "ctrl+alt+t"))
        r.handle(e.KEY_LEFTMETA, 1)
        out = r.handle(e.KEY_E, 1)
        self.assertEqual(out[:3], [(DISARM_KEY, 1), (DISARM_KEY, 0), (e.KEY_LEFTMETA, 0)])
        r.handle(e.KEY_E, 0)
        # Releasing Super afterwards is disarmed too, since Super was re-pressed.
        self.assertEqual(r.handle(e.KEY_LEFTMETA, 0),
                         [(DISARM_KEY, 1), (DISARM_KEY, 0), (e.KEY_LEFTMETA, 0)])

    def test_plain_super_tap_still_opens_launcher(self):
        r = remapper(("super+e", "ctrl+alt+t"))
        self.assertEqual(r.handle(e.KEY_LEFTMETA, 1), [(e.KEY_LEFTMETA, 1)])
        self.assertEqual(r.handle(e.KEY_LEFTMETA, 0), [(e.KEY_LEFTMETA, 0)])


if __name__ == "__main__":
    unittest.main()
