import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from knobu.modules.commandbar import (
    AppProvider,
    CalculatorProvider,
    CommandBarModule,
    ConverterProvider,
    EmojiProvider,
    PathProvider,
    SearchEngine,
    ShellProvider,
    SystemProvider,
    WebProvider,
    WindowProvider,
    check_conflicts,
    override_os_shortcuts,
    restore_os_shortcuts,
)
from knobu.modules.commandbar.providers import AppEntry, SafeCalculator, UnitConverter


class TestCommandBar(unittest.TestCase):
    def test_module_defaults(self):
        self.assertEqual(CommandBarModule.id, "commandbar")
        self.assertEqual(CommandBarModule.name, "Command Bar")
        self.assertTrue(CommandBarModule.defaults["enabled"])
        self.assertEqual(CommandBarModule.defaults["hotkey"], "alt+space")
        self.assertTrue(CommandBarModule.defaults["exclusive"])
        self.assertTrue(CommandBarModule.defaults["override_os_shortcut"])
        self.assertEqual(CommandBarModule.defaults["max_results"], 8)
        self.assertTrue(CommandBarModule.defaults["enable_converter"])
        self.assertTrue(CommandBarModule.defaults["enable_emoji"])
        self.assertTrue(CommandBarModule.defaults["enable_windows"])

    def test_calculator_basic_arithmetic(self):
        self.assertEqual(SafeCalculator.evaluate("2 + 2"), 4)
        self.assertEqual(SafeCalculator.evaluate("10 - 4"), 6)
        self.assertEqual(SafeCalculator.evaluate("6 * 7"), 42)
        self.assertEqual(SafeCalculator.evaluate("20 / 4"), 5.0)
        self.assertEqual(SafeCalculator.evaluate("2 + 3 * 4"), 14)

    def test_calculator_powers_and_percentages(self):
        self.assertEqual(SafeCalculator.evaluate("2 ^ 3"), 8)
        self.assertEqual(SafeCalculator.evaluate("2 ** 4"), 16)
        self.assertEqual(SafeCalculator.evaluate("20% of 150"), 30.0)
        self.assertEqual(SafeCalculator.evaluate("50% of 200"), 100.0)

    def test_calculator_functions(self):
        self.assertEqual(SafeCalculator.evaluate("sqrt(144)"), 12.0)
        self.assertEqual(SafeCalculator.evaluate("abs(-42)"), 42)
        self.assertEqual(SafeCalculator.evaluate("round(3.14159, 2)"), 3.14)
        self.assertAlmostEqual(SafeCalculator.evaluate("pi"), 3.14159265, places=5)

    def test_calculator_safety(self):
        # Malicious expressions must safely return None without executing
        self.assertIsNone(SafeCalculator.evaluate("__import__('os').system('ls')"))
        self.assertIsNone(SafeCalculator.evaluate("open('/etc/passwd')"))
        self.assertIsNone(SafeCalculator.evaluate("eval('1+1')"))
        self.assertIsNone(SafeCalculator.evaluate("hello world"))
        self.assertIsNone(SafeCalculator.evaluate(""))

    def test_calculator_provider_search(self):
        calc = CalculatorProvider()
        res = calc.search("15 * 4")
        self.assertEqual(len(res), 1)
        self.assertIn("60", res[0].title)
        self.assertEqual(res[0].category, "Calculator")

    def test_shell_provider(self):
        shell = ShellProvider()
        empty = shell.search("regular text")
        self.assertEqual(len(empty), 0)

        results = shell.search("> htop")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, "Command")
        self.assertIn("htop", results[0].title)

    def test_web_provider(self):
        web = WebProvider()
        url_res = web.search("https://github.com")
        self.assertEqual(len(url_res), 1)
        self.assertEqual(url_res[0].category, "Web")

        search_res = web.search("? arch linux")
        self.assertEqual(len(search_res), 1)
        self.assertIn("Google", search_res[0].title)
        self.assertEqual(search_res[0].category, "Web Search")

    def test_path_provider(self):
        paths = PathProvider()
        res = paths.search("~/")
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0].category, "Path")

    def test_system_provider(self):
        sys_prov = SystemProvider()
        res = sys_prov.search("lock")
        self.assertTrue(len(res) > 0)
        self.assertIn("Lock Screen", res[0].title)

    def test_app_provider_custom(self):
        app = AppEntry(Path("/fake/test.desktop"), "Test App", "testapp", "test-icon", "A test", ["test"], False)
        provider = AppProvider()
        provider._apps = [app]
        provider._loaded = True

        matches = provider.search("test")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].title, "Test App")

    def test_search_engine_composite(self):
        engine = SearchEngine({
            "enable_apps": False,
            "enable_calc": True,
            "enable_shell": True,
            "enable_web": True,
            "enable_paths": True,
            "enable_system": True,
            "enable_converter": True,
            "enable_emoji": True,
            "enable_windows": True,
        })
        res = engine.search("5 * 5", limit=5)
        self.assertTrue(any(r.category == "Calculator" for r in res))

        emoji_res = engine.search(":fire", limit=5)
        self.assertTrue(any(r.category == "Emoji" for r in emoji_res))

        conv_res = engine.search("100 USD in EUR", limit=5)
        self.assertTrue(any(r.category == "Converter" for r in conv_res))

    def test_unit_converter_units(self):
        res = UnitConverter.convert("50 miles in km")
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res[0], 80.4672, places=3)
        self.assertIn("km", res[1])

        res_gb = UnitConverter.convert("16 GB in MB")
        self.assertIsNotNone(res_gb)
        self.assertEqual(res_gb[0], 16384.0)

        res_mass = UnitConverter.convert("10 kg to lbs")
        self.assertIsNotNone(res_mass)
        self.assertAlmostEqual(res_mass[0], 22.0462, places=2)

    def test_unit_converter_temperature(self):
        res_f = UnitConverter.convert("100 C in F")
        self.assertIsNotNone(res_f)
        self.assertEqual(res_f[0], 212.0)

        res_c = UnitConverter.convert("32 F to C")
        self.assertIsNotNone(res_c)
        self.assertEqual(res_c[0], 0.0)

    def test_unit_converter_currency(self):
        res_eur = UnitConverter.convert("100 USD in EUR")
        self.assertIsNotNone(res_eur)
        self.assertEqual(res_eur[0], 92.0)

        res_sym = UnitConverter.convert("$100 in EUR")
        self.assertIsNotNone(res_sym)
        self.assertEqual(res_sym[0], 92.0)

    def test_unit_converter_invalid(self):
        self.assertIsNone(UnitConverter.convert("hello in world"))
        self.assertIsNone(UnitConverter.convert("100 apples in oranges"))
        self.assertIsNone(UnitConverter.convert(""))

    def test_emoji_provider(self):
        prov = EmojiProvider()
        res = prov.search(":fire")
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0].category, "Emoji")
        self.assertIn("🔥", res[0].title)

        res_rocket = prov.search(":rocket")
        self.assertTrue(len(res_rocket) > 0)
        self.assertIn("🚀", res_rocket[0].title)

        res_hint = prov.search(":")
        self.assertTrue(len(res_hint) > 0)

        empty = prov.search("normal text")
        self.assertEqual(len(empty), 0)

    def test_window_provider(self):
        prov = WindowProvider()
        res = prov.search("< ")
        self.assertIsInstance(res, list)

    def test_commandbar_toggle_app(self):
        from knobu.ui.commandbar import CommandBarApp
        app = CommandBarApp()
        self.assertIsNone(app.win)

        mock_win = MagicMock()
        mock_win.is_visible.return_value = True
        app.win = mock_win

        # Activating while visible should close the window (Alt+Space toggle off)
        app.do_activate()
        mock_win.close.assert_called_once()
        self.assertIsNone(app.win)

    @patch("subprocess.run")
    def test_os_shortcut_conflict_check(self, mock_run):
        mock_run.return_value = MagicMock(stdout="['<Alt>space']")
        conflicts = check_conflicts()
        self.assertIsInstance(conflicts, list)


if __name__ == "__main__":
    unittest.main()
