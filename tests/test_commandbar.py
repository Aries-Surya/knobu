import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from knobu.modules.commandbar import (
    AppProvider,
    CalculatorProvider,
    CommandBarModule,
    PathProvider,
    SearchEngine,
    ShellProvider,
    SystemProvider,
    WebProvider,
    check_conflicts,
    override_os_shortcuts,
    restore_os_shortcuts,
)
from knobu.modules.commandbar.providers import AppEntry, SafeCalculator


class TestCommandBar(unittest.TestCase):
    def test_module_defaults(self):
        self.assertEqual(CommandBarModule.id, "commandbar")
        self.assertEqual(CommandBarModule.name, "Command Bar")
        self.assertTrue(CommandBarModule.defaults["enabled"])
        self.assertEqual(CommandBarModule.defaults["hotkey"], "alt+space")
        self.assertTrue(CommandBarModule.defaults["exclusive"])
        self.assertTrue(CommandBarModule.defaults["override_os_shortcut"])
        self.assertEqual(CommandBarModule.defaults["max_results"], 8)

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
        })
        res = engine.search("5 * 5", limit=5)
        self.assertTrue(any(r.category == "Calculator" for r in res))

    @patch("subprocess.run")
    def test_os_shortcut_conflict_check(self, mock_run):
        mock_run.return_value = MagicMock(stdout="['<Alt>space']")
        conflicts = check_conflicts()
        self.assertIsInstance(conflicts, list)


if __name__ == "__main__":
    unittest.main()
