import datetime
import unittest

from evdev import ecodes as e

from knobu.modules.keyboard.snippets import TextExpander, expand_variables, parse_snippet


class TestSnippets(unittest.TestCase):
    def test_parse_snippet(self):
        trig, rep = parse_snippet(";email -> user@test.com")
        self.assertEqual(trig, ";email")
        self.assertEqual(rep, "user@test.com")

        with self.assertRaises(ValueError):
            parse_snippet("invalid_format")

    def test_expand_variables(self):
        fixed_time = datetime.datetime(2026, 11, 14, 15, 30, 45)
        res = expand_variables("Today is {date} at {time}", now=fixed_time)
        self.assertEqual(res, "Today is 2026-11-14 at 15:30:45")

        year_res = expand_variables("{year}-{month}-{day}", now=fixed_time)
        self.assertEqual(year_res, "2026-11-14")

    def test_snippet_expansion_trigger(self):
        expander = TextExpander([";hi -> Hello World"])

        # Type ';' (KEY_SEMICOLON, shift=False)
        suppress, events = expander.process(e.KEY_SEMICOLON, 1, False)
        self.assertFalse(suppress)
        self.assertEqual(events, [])

        # Type 'h' (KEY_H, shift=False)
        suppress, events = expander.process(e.KEY_H, 1, False)
        self.assertFalse(suppress)
        self.assertEqual(events, [])

        # Type 'i' (KEY_I, shift=False) -> trigger ';hi' matches!
        suppress, events = expander.process(e.KEY_I, 1, False)
        self.assertTrue(suppress)
        self.assertTrue(len(events) > 0)

        # First events must be backspaces to erase the previously typed chars (';h')
        backspaces = [ev for ev in events if ev == (e.KEY_BACKSPACE, 1)]
        self.assertEqual(len(backspaces), 2)  # len(';hi') - 1 = 2

    def test_backspace_cancels_partial_trigger(self):
        expander = TextExpander([";hi -> Hello"])

        expander.process(e.KEY_SEMICOLON, 1, False)
        expander.process(e.KEY_X, 1, False)
        # Erase 'x'
        expander.process(e.KEY_BACKSPACE, 1, False)
        # Type 'h' and 'i'
        expander.process(e.KEY_H, 1, False)
        suppress, events = expander.process(e.KEY_I, 1, False)
        self.assertTrue(suppress)


if __name__ == "__main__":
    unittest.main()
