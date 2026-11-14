"""Search providers for Knobu Command Bar (PowerToys Run for Linux).

Implements modular, low-latency providers for:
1. Installed Applications (.desktop entries with fuzzy matching)
2. Safe Math & Calculator (AST-based, zero arbitrary execution)
3. Shell / Terminal Command Execution (e.g., > top, > htop)
4. Filesystem Navigation & Path Opening (~/..., /...)
5. Web & Quick Search (URLs, ? query)
6. System Commands & Knobu Actions (Lock, Suspend, Restart, Knobu tools)
"""

from __future__ import annotations

import ast
import configparser
import logging
import math
import operator
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus

log = logging.getLogger("knobu.commandbar.providers")


@dataclass
class SearchResult:
    id: str
    title: str
    subtitle: str
    icon_name: str
    category: str
    action: Callable[[], None]
    score: int = 0


# ==============================================================================
# 1. APPLICATION PROVIDER
# ==============================================================================

class AppEntry:
    def __init__(self, desktop_file: Path, name: str, exec_cmd: str, icon: str, comment: str, keywords: list[str], terminal: bool):
        self.desktop_file = desktop_file
        self.name = name
        self.exec_cmd = exec_cmd
        self.icon = icon or "application-x-executable"
        self.comment = comment
        self.keywords = keywords
        self.terminal = terminal

    def launch(self) -> None:
        """Launch application detached in background."""
        # Strip field codes like %f, %F, %u, %U, %i, %c, %k
        cmd = re.sub(r"%[a-zA-Z]", "", self.exec_cmd).strip()
        args = shlex.split(cmd)
        if not args:
            return

        if self.terminal:
            term = os.environ.get("TERMINAL") or shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal") or shutil.which("ptyxis") or shutil.which("konsole")
            if term:
                args = [term, "-e"] + args

        try:
            # Prefer gio launch if available
            if shutil.which("gio") and self.desktop_file.exists():
                subprocess.Popen(["gio", "launch", str(self.desktop_file)], start_new_session=True)
            else:
                subprocess.Popen(args, start_new_session=True)
        except Exception as err:
            log.error("Failed to launch %s: %s", self.name, err)


class AppProvider:
    SEARCH_DIRS = [
        Path.home() / ".local/share/applications",
        Path.home() / ".local/share/flatpak/exports/share/applications",
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        Path("/var/lib/snapd/desktop/applications"),
    ]

    def __init__(self):
        self._apps: list[AppEntry] = []
        self._loaded = False

    def load_apps(self) -> None:
        seen_names = set()
        apps = []

        for d in self.SEARCH_DIRS:
            if not d.is_dir():
                continue
            for f in d.glob("*.desktop"):
                try:
                    cp = configparser.ConfigParser(interpolation=None)
                    cp.read(f, encoding="utf-8")
                    if not cp.has_section("Desktop Entry"):
                        continue
                    sec = cp["Desktop Entry"]
                    if sec.getboolean("NoDisplay", fallback=False) or sec.getboolean("Hidden", fallback=False):
                        continue
                    if sec.get("Type", "Application") != "Application":
                        continue

                    name = sec.get("Name", "").strip()
                    if not name or name in seen_names:
                        continue

                    exec_cmd = sec.get("Exec", "").strip()
                    if not exec_cmd:
                        continue

                    icon = sec.get("Icon", "").strip()
                    comment = sec.get("Comment", "").strip()
                    raw_keywords = sec.get("Keywords", "")
                    keywords = [k.strip() for k in raw_keywords.split(";") if k.strip()]
                    terminal = sec.getboolean("Terminal", fallback=False)

                    seen_names.add(name)
                    apps.append(AppEntry(f, name, exec_cmd, icon, comment, keywords, terminal))
                except Exception:
                    continue

        self._apps = sorted(apps, key=lambda a: a.name.lower())
        self._loaded = True

    def search(self, query: str) -> list[SearchResult]:
        if not self._loaded:
            self.load_apps()

        q = query.strip().lower()
        if not q:
            # Return top popular/first apps
            return [
                SearchResult(
                    id=f"app:{a.name}",
                    title=a.name,
                    subtitle=a.comment or a.exec_cmd,
                    icon_name=a.icon,
                    category="Application",
                    action=a.launch,
                    score=10,
                )
                for a in self._apps[:8]
            ]

        results = []
        for a in self._apps:
            name_lower = a.name.lower()
            score = 0

            if name_lower == q:
                score = 100
            elif name_lower.startswith(q):
                score = 80
            elif any(w.startswith(q) for w in name_lower.split()):
                score = 70
            elif q in name_lower:
                score = 50
            elif any(q in k.lower() for k in a.keywords):
                score = 40
            elif q in a.exec_cmd.lower():
                score = 30
            elif a.comment and q in a.comment.lower():
                score = 20

            if score > 0:
                results.append(
                    SearchResult(
                        id=f"app:{a.name}",
                        title=a.name,
                        subtitle=a.comment or a.exec_cmd,
                        icon_name=a.icon,
                        category="Application",
                        action=a.launch,
                        score=score,
                    )
                )

        return sorted(results, key=lambda r: r.score, reverse=True)


# ==============================================================================
# 2. SAFE CALCULATOR & MATH PROVIDER
# ==============================================================================

class SafeCalculator:
    """AST-based safe arithmetic & math evaluator without eval()."""

    SAFE_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    SAFE_FUNCTIONS = {
        "sqrt": math.sqrt,
        "abs": abs,
        "round": round,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "log2": math.log2,
        "exp": math.exp,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    SAFE_CONSTANTS = {
        "pi": math.pi,
        "e": math.e,
    }

    @classmethod
    def evaluate(cls, expression: str) -> float | int | None:
        expr = expression.strip()
        # Replace power notation
        expr = expr.replace("^", "**")

        # Handle "X% of Y" -> (X / 100) * Y
        pct_match = re.match(r"^([\d.]+)\s*%\s*of\s*([\d.]+)$", expr, re.IGNORECASE)
        if pct_match:
            try:
                p, val = float(pct_match.group(1)), float(pct_match.group(2))
                return (p / 100.0) * val
            except Exception:
                return None

        # Must contain at least one math operator or known function/digit or constant
        if not re.search(r"[\d+\-*/%()]", expr) and expr.lower() not in cls.SAFE_CONSTANTS:
            return None

        try:
            tree = ast.parse(expr, mode="eval")
            return cls._eval_node(tree.body)
        except Exception:
            return None

    @classmethod
    def _eval_node(cls, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)
            op = cls.SAFE_OPERATORS.get(type(node.op))
            if op:
                return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = cls._eval_node(node.operand)
            op = cls.SAFE_OPERATORS.get(type(node.op))
            if op:
                return op(operand)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id.lower()
            if func_name in cls.SAFE_FUNCTIONS:
                args = [cls._eval_node(arg) for arg in node.args]
                return cls.SAFE_FUNCTIONS[func_name](*args)
        elif isinstance(node, ast.Name):
            name_lower = node.id.lower()
            if name_lower in cls.SAFE_CONSTANTS:
                return cls.SAFE_CONSTANTS[name_lower]
        raise ValueError("Unsupported mathematical node")


class CalculatorProvider:
    def search(self, query: str) -> list[SearchResult]:
        q = query.strip()
        if not q or len(q) < 2:
            return []

        res = SafeCalculator.evaluate(q)
        if res is None:
            return []

        # Format number nicely
        if isinstance(res, float) and res.is_integer():
            formatted = f"{int(res):,}"
            raw_str = str(int(res))
        elif isinstance(res, float):
            formatted = f"{res:,.6g}"
            raw_str = f"{res:.6g}"
        else:
            formatted = f"{res:,}"
            raw_str = str(res)

        def copy_result():
            from knobu.modules.clipboard import set_clipboard
            set_clipboard(raw_str)
            try:
                from knobu.system import notify
                notify.send("Copied to clipboard", f"{raw_str} ({q})")
            except Exception:
                pass

        return [
            SearchResult(
                id=f"calc:{formatted}",
                title=f"= {formatted}",
                subtitle=f"{q} — Press Enter to copy to clipboard",
                icon_name="accessories-calculator-symbolic",
                category="Calculator",
                action=copy_result,
                score=95,
            )
        ]


# ==============================================================================
# 3. SHELL & COMMAND PROVIDER
# ==============================================================================

class ShellProvider:
    def search(self, query: str) -> list[SearchResult]:
        q = query.strip()
        if not q.startswith(">") and not q.startswith("term:"):
            return []

        cmd = q.lstrip(">").lstrip("term:").strip()
        if not cmd:
            return [
                SearchResult(
                    id="shell:hint",
                    title="Run Terminal Command",
                    subtitle="Type a command to run (e.g., > top, > ping 8.8.8.8)",
                    icon_name="utilities-terminal-symbolic",
                    category="Command",
                    action=lambda: None,
                    score=90,
                )
            ]

        def run_terminal():
            term = os.environ.get("TERMINAL") or shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal") or shutil.which("ptyxis") or shutil.which("konsole")
            if term:
                subprocess.Popen([term, "-e", "bash", "-c", f"{cmd}; echo; read -p 'Press Enter to exit...'"], start_new_session=True)
            else:
                subprocess.Popen(["sh", "-c", cmd], start_new_session=True)

        return [
            SearchResult(
                id=f"shell:{cmd}",
                title=f"> {cmd}",
                subtitle="Execute command in terminal emulator",
                icon_name="utilities-terminal-symbolic",
                category="Command",
                action=run_terminal,
                score=100,
            )
        ]


# ==============================================================================
# 4. PATH & FILE SYSTEM PROVIDER
# ==============================================================================

class PathProvider:
    def search(self, query: str) -> list[SearchResult]:
        q = query.strip()
        if not (q.startswith("~/") or q.startswith("/") or q.startswith("./")):
            return []

        expanded = Path(os.path.expanduser(q))
        parent = expanded.parent if not expanded.is_dir() else expanded
        prefix = expanded.name if not expanded.is_dir() else ""

        results = []
        if parent.is_dir():
            try:
                for entry in parent.iterdir():
                    if prefix and not entry.name.lower().startswith(prefix.lower()):
                        continue
                    if entry.name.startswith(".") and not prefix.startswith("."):
                        continue

                    icon = "folder-symbolic" if entry.is_dir() else "text-x-generic-symbolic"
                    action_path = entry

                    results.append(
                        SearchResult(
                            id=f"path:{entry}",
                            title=entry.name,
                            subtitle=str(entry),
                            icon_name=icon,
                            category="Path",
                            action=lambda p=action_path: subprocess.Popen(["xdg-open", str(p)], start_new_session=True),
                            score=85,
                        )
                    )
                    if len(results) >= 8:
                        break
            except Exception:
                pass

        return results


# ==============================================================================
# 5. WEB & URL PROVIDER
# ==============================================================================

class WebProvider:
    def search(self, query: str) -> list[SearchResult]:
        q = query.strip()
        if not q:
            return []

        # Direct URL
        if q.startswith("http://") or q.startswith("https://") or (q.startswith("www.") and "." in q):
            url = q if q.startswith("http") else f"https://{q}"
            return [
                SearchResult(
                    id=f"web:{url}",
                    title=f"Open: {url}",
                    subtitle="Open URL in default web browser",
                    icon_name="web-browser-symbolic",
                    category="Web",
                    action=lambda: subprocess.Popen(["xdg-open", url], start_new_session=True),
                    score=95,
                )
            ]

        # Explicit search query with '?'
        if q.startswith("?"):
            terms = q.lstrip("?").strip()
            if terms:
                url = f"https://www.google.com/search?q={quote_plus(terms)}"
                return [
                    SearchResult(
                        id=f"web_search:{terms}",
                        title=f"Search Google: {terms}",
                        subtitle="Search web in default browser",
                        icon_name="system-search-symbolic",
                        category="Web Search",
                        action=lambda: subprocess.Popen(["xdg-open", url], start_new_session=True),
                        score=90,
                    )
                ]

        return []


# ==============================================================================
# 6. SYSTEM & KNOBU ACTIONS PROVIDER
# ==============================================================================

class SystemProvider:
    ACTIONS = [
        ("knobu:settings", "Knobu Settings", "Open Knobu preferences and module configurations", "preferences-system-symbolic", lambda: subprocess.Popen(["knobu", "settings"], start_new_session=True)),
        ("knobu:clipboard", "Clipboard History", "Open Knobu clipboard manager and history", "edit-paste-symbolic", lambda: subprocess.Popen(["knobu", "clipboard"], start_new_session=True)),
        ("knobu:colorpicker", "Color Picker", "Sample pixel colour from screen (Super+Shift+C)", "knobu-colorpicker-symbolic", lambda: subprocess.Popen(["knobu", "pick-color"], start_new_session=True)),
        ("knobu:textextractor", "Text Extractor", "Capture screen region and copy text via OCR", "knobu-textextractor-symbolic", lambda: subprocess.Popen(["knobu", "extract-text"], start_new_session=True)),
        ("knobu:awake", "Awake (Keep Awake)", "Keep computer awake indefinitely", "knobu-awake-symbolic", lambda: subprocess.Popen(["knobu", "awake", "on"], start_new_session=True)),
        ("sys:lock", "Lock Screen", "Lock the current desktop session", "system-lock-screen-symbolic", lambda: subprocess.Popen(["loginctl", "lock-session"], start_new_session=True)),
        ("sys:sleep", "Sleep / Suspend", "Suspend system to RAM", "system-suspend-symbolic", lambda: subprocess.Popen(["systemctl", "suspend"], start_new_session=True)),
        ("sys:restart", "Restart Computer", "Reboot operating system", "system-reboot-symbolic", lambda: subprocess.Popen(["systemctl", "reboot"], start_new_session=True)),
        ("sys:shutdown", "Shut Down", "Power off computer", "system-shutdown-symbolic", lambda: subprocess.Popen(["systemctl", "poweroff"], start_new_session=True)),
    ]

    def search(self, query: str) -> list[SearchResult]:
        q = query.strip().lower()
        if not q:
            return []

        results = []
        for aid, title, sub, icon, fn in self.ACTIONS:
            score = 0
            if title.lower().startswith(q):
                score = 85
            elif q in title.lower() or q in sub.lower():
                score = 65

            if score > 0:
                results.append(
                    SearchResult(
                        id=aid,
                        title=title,
                        subtitle=sub,
                        icon_name=icon,
                        category="System Action",
                        action=fn,
                        score=score,
                    )
                )

        return results


# ==============================================================================
# 7. UNIT & CURRENCY CONVERTER PROVIDER
# ==============================================================================

class UnitConverter:
    """Zero-dependency unit and currency converter for lengths, masses, data, times, temps, and FX."""

    LENGTH = {
        "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
        "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0, "kilometre": 1000.0, "kilometres": 1000.0,
        "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01, "centimetre": 0.01, "centimetres": 0.01,
        "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001, "millimetre": 0.001, "millimetres": 0.001,
        "um": 1e-6, "micrometer": 1e-6, "micrometers": 1e-6, "micron": 1e-6, "microns": 1e-6,
        "nm": 1e-9, "nanometer": 1e-9, "nanometers": 1e-9,
        "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
        "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
        "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
        "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
        "nmi": 1852.0, "nautical mile": 1852.0, "nautical miles": 1852.0,
    }

    MASS = {
        "g": 1.0, "gram": 1.0, "grams": 1.0,
        "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0, "kilo": 1000.0, "kilos": 1000.0,
        "mg": 0.001, "milligram": 0.001, "milligrams": 0.001,
        "ug": 1e-6, "microgram": 1e-6, "micrograms": 1e-6,
        "lb": 453.59237, "lbs": 453.59237, "pound": 453.59237, "pounds": 453.59237,
        "oz": 28.349523125, "ounce": 28.349523125, "ounces": 28.349523125,
        "t": 1000000.0, "ton": 1000000.0, "tons": 1000000.0, "tonne": 1000000.0, "tonnes": 1000000.0,
        "st": 6350.29318, "stone": 6350.29318, "stones": 6350.29318,
    }

    DATA = {
        "b": 1.0, "byte": 1.0, "bytes": 1.0,
        "bit": 0.125, "bits": 0.125,
        "kb": 1024.0, "kilobyte": 1024.0, "kilobytes": 1024.0, "kib": 1024.0,
        "mb": 1024.0**2, "megabyte": 1024.0**2, "megabytes": 1024.0**2, "mib": 1024.0**2,
        "gb": 1024.0**3, "gigabyte": 1024.0**3, "gigabytes": 1024.0**3, "gib": 1024.0**3,
        "tb": 1024.0**4, "terabyte": 1024.0**4, "terabytes": 1024.0**4, "tib": 1024.0**4,
        "pb": 1024.0**5, "petabyte": 1024.0**5, "petabytes": 1024.0**5,
    }

    TIME = {
        "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0,
        "ms": 0.001, "millisecond": 0.001, "milliseconds": 0.001,
        "min": 60.0, "minute": 60.0, "minutes": 60.0,
        "h": 3600.0, "hr": 3600.0, "hour": 3600.0, "hours": 3600.0,
        "d": 86400.0, "day": 86400.0, "days": 86400.0,
        "w": 604800.0, "wk": 604800.0, "week": 604800.0, "weeks": 604800.0,
        "mo": 2629800.0, "month": 2629800.0, "months": 2629800.0,
        "y": 31557600.0, "yr": 31557600.0, "year": 31557600.0, "years": 31557600.0,
    }

    SPEED = {
        "m/s": 1.0, "mps": 1.0,
        "km/h": 1.0 / 3.6, "kph": 1.0 / 3.6, "kmh": 1.0 / 3.6,
        "mph": 0.44704, "mi/h": 0.44704, "miles per hour": 0.44704,
        "knot": 0.514444, "knots": 0.514444, "kn": 0.514444,
        "fps": 0.3048, "ft/s": 0.3048,
    }

    VOLUME = {
        "l": 1.0, "liter": 1.0, "liters": 1.0, "litre": 1.0, "litres": 1.0,
        "ml": 0.001, "milliliter": 0.001, "milliliters": 0.001, "millilitre": 0.001, "millilitres": 0.001,
        "cl": 0.01, "centiliter": 0.01, "centiliters": 0.01,
        "dl": 0.1, "deciliter": 0.1, "deciliters": 0.1,
        "m3": 1000.0, "cubic meter": 1000.0, "cubic meters": 1000.0,
        "cm3": 0.001, "cc": 0.001,
        "gal": 3.785411784, "gallon": 3.785411784, "gallons": 3.785411784,
        "qt": 0.946352946, "quart": 0.946352946, "quarts": 0.946352946,
        "pt": 0.473176473, "pint": 0.473176473, "pints": 0.473176473,
        "cup": 0.2365882365, "cups": 0.2365882365,
        "tbsp": 0.0147867648, "tablespoon": 0.0147867648, "tablespoons": 0.0147867648,
        "tsp": 0.00492892159, "teaspoon": 0.00492892159, "teaspoons": 0.00492892159,
        "floz": 0.0295735296, "fl oz": 0.0295735296, "fluid ounce": 0.0295735296, "fluid ounces": 0.0295735296,
    }

    AREA = {
        "m2": 1.0, "sqm": 1.0, "square meter": 1.0, "square meters": 1.0,
        "km2": 1000000.0, "sqkm": 1000000.0, "square kilometer": 1000000.0,
        "cm2": 0.0001, "sqcm": 0.0001,
        "ha": 10000.0, "hectare": 10000.0, "hectares": 10000.0,
        "acre": 4046.8564224, "acres": 4046.8564224,
        "sqft": 0.09290304, "square foot": 0.09290304, "square feet": 0.09290304,
        "sqin": 0.00064516, "square inch": 0.00064516, "square inches": 0.00064516,
        "sqmi": 2589988.11, "square mile": 2589988.11, "square miles": 2589988.11,
    }

    CURRENCIES = {
        "usd": 1.0, "eur": 0.92, "gbp": 0.79, "inr": 86.50, "jpy": 154.50,
        "cad": 1.40, "aud": 1.55, "chf": 0.88, "cny": 7.24, "sgd": 1.35,
        "nzd": 1.70, "aed": 3.67, "sar": 3.75, "brl": 5.80, "mxn": 20.30,
        "sek": 10.90, "nok": 11.10, "zar": 18.20, "try": 35.00, "krw": 1400.0,
        "rub": 100.0, "idr": 16200.0, "thb": 34.50, "myr": 4.45, "php": 58.50,
        "vnd": 25400.0, "pln": 4.10, "ils": 3.70, "hkd": 7.78, "twd": 32.50,
        "btc": 0.000011, "eth": 0.00031,
    }

    CURRENCY_SYMBOLS = {
        "$": "usd", "€": "eur", "£": "gbp", "₹": "inr", "¥": "jpy"
    }

    TEMPERATURE_UNITS = {"c", "celsius", "°c", "f", "fahrenheit", "°f", "k", "kelvin"}

    CATEGORIES = [LENGTH, MASS, DATA, TIME, SPEED, VOLUME, AREA]

    PATTERNS = [
        re.compile(
            r"^\s*([$€£₹¥])?\s*([+-]?\d+(?:\.\d+)?)\s*([a-zA-Z°/%$€£₹¥]*(?:\s+[a-zA-Z°/%$€£₹¥]+)?)\s+(?:in|to|=)\s+([a-zA-Z°/%$€£₹¥]+(?:\s+[a-zA-Z°/%$€£₹¥]+)?)\s*$",
            re.IGNORECASE,
        ),
    ]

    @classmethod
    def convert(cls, query: str) -> tuple[float, str, str, str] | None:
        q = query.strip()
        for pat in cls.PATTERNS:
            m = pat.match(q)
            if not m:
                continue
            sym, val_str, u1, u2 = m.groups()
            try:
                val = float(val_str)
            except ValueError:
                continue

            u1_clean = (sym if sym and not u1 else u1).strip().lower()
            u2_clean = u2.strip().lower()

            # Map currency symbols
            u1_clean = cls.CURRENCY_SYMBOLS.get(u1_clean, u1_clean)
            u2_clean = cls.CURRENCY_SYMBOLS.get(u2_clean, u2_clean)

            # 1. Temperature
            if u1_clean in cls.TEMPERATURE_UNITS and u2_clean in cls.TEMPERATURE_UNITS:
                if u1_clean in ("c", "celsius", "°c"):
                    c = val
                elif u1_clean in ("f", "fahrenheit", "°f"):
                    c = (val - 32.0) * 5.0 / 9.0
                elif u1_clean in ("k", "kelvin"):
                    c = val - 273.15
                else:
                    continue

                if u2_clean in ("c", "celsius", "°c"):
                    target_val = c
                    target_unit = "°C"
                elif u2_clean in ("f", "fahrenheit", "°f"):
                    target_val = c * 9.0 / 5.0 + 32.0
                    target_unit = "°F"
                elif u2_clean in ("k", "kelvin"):
                    target_val = c + 273.15
                    target_unit = "K"
                else:
                    continue

                formatted = f"{target_val:,.4g} {target_unit}"
                return target_val, formatted, q, target_unit

            # 2. Currencies
            if u1_clean in cls.CURRENCIES and u2_clean in cls.CURRENCIES:
                val_in_usd = val / cls.CURRENCIES[u1_clean]
                target_val = val_in_usd * cls.CURRENCIES[u2_clean]
                target_unit = u2.strip().upper()
                formatted = f"{target_val:,.2f} {target_unit}"
                return target_val, formatted, q, target_unit

            # 3. Standard unit categories
            for cat in cls.CATEGORIES:
                if u1_clean in cat and u2_clean in cat:
                    base_val = val * cat[u1_clean]
                    target_val = base_val / cat[u2_clean]
                    target_unit = u2.strip()
                    formatted = f"{target_val:,.6g} {target_unit}"
                    return target_val, formatted, q, target_unit

        return None


class ConverterProvider:
    def search(self, query: str) -> list[SearchResult]:
        res = UnitConverter.convert(query)
        if not res:
            return []

        target_val, formatted, original, _unit = res
        raw_str = f"{target_val:.6g}" if isinstance(target_val, float) else str(target_val)

        def copy_result():
            from knobu.modules.clipboard import set_clipboard
            set_clipboard(raw_str)
            try:
                from knobu.system import notify
                notify.send("Copied to clipboard", f"{raw_str} ({original})")
            except Exception:
                pass

        return [
            SearchResult(
                id=f"conv:{formatted}",
                title=f"= {formatted}",
                subtitle=f"{original} — Press Enter to copy to clipboard",
                icon_name="view-refresh-symbolic",
                category="Converter",
                action=copy_result,
                score=96,
            )
        ]


# ==============================================================================
# 8. EMOJI PICKER PROVIDER
# ==============================================================================

EMOJI_LIST: list[tuple[str, str, str, str, list[str]]] = [
    ("😀", "Grinning Face", ":grinning:", "Smileys & Emotion", ["smile", "happy", "grin", "face"]),
    ("😃", "Grinning Face with Big Eyes", ":smiley:", "Smileys & Emotion", ["happy", "joy", "haha"]),
    ("😄", "Grinning Face with Smiling Eyes", ":smile:", "Smileys & Emotion", ["laugh", "glad"]),
    ("😁", "Beaming Face with Smiling Eyes", ":grin:", "Smileys & Emotion", ["cheerful"]),
    ("😆", "Grinning Squinting Face", ":laughing:", "Smileys & Emotion", ["lol", "rofl"]),
    ("😅", "Grinning Face with Sweat", ":sweat_smile:", "Smileys & Emotion", ["nervous", "relief"]),
    ("😂", "Face with Tears of Joy", ":joy:", "Smileys & Emotion", ["cry", "tears", "lol", "funny"]),
    ("🤣", "Rolling on the Floor Laughing", ":rofl:", "Smileys & Emotion", ["rotfl", "funny"]),
    ("😊", "Smiling Face with Smiling Eyes", ":blush:", "Smileys & Emotion", ["shy", "proud"]),
    ("😇", "Smiling Face with Halo", ":innocent:", "Smileys & Emotion", ["angel"]),
    ("🙂", "Slightly Smiling Face", ":slightly_smiling_face:", "Smileys & Emotion", ["ok"]),
    ("🙃", "Upside-Down Face", ":upside_down_face:", "Smileys & Emotion", ["sarcasm", "irony"]),
    ("😉", "Winking Face", ":wink:", "Smileys & Emotion", ["flirt"]),
    ("😍", "Smiling Face with Heart-Eyes", ":heart_eyes:", "Smileys & Emotion", ["love", "crush"]),
    ("🥰", "Smiling Face with Hearts", ":smiling_face_with_3_hearts:", "Smileys & Emotion", ["adore"]),
    ("😘", "Face Blowing a Kiss", ":kissing_heart:", "Smileys & Emotion", ["kiss"]),
    ("😋", "Face Savoring Food", ":yum:", "Smileys & Emotion", ["delicious", "tasty"]),
    ("😜", "Winking Face with Tongue", ":stuck_out_tongue_winking_eye:", "Smileys & Emotion", ["prank", "crazy"]),
    ("🤪", "Zany Face", ":zany_face:", "Smileys & Emotion", ["wild", "goofy"]),
    ("😎", "Smiling Face with Sunglasses", ":sunglasses:", "Smileys & Emotion", ["cool", "chill"]),
    ("🤓", "Nerd Face", ":nerd_face:", "Smileys & Emotion", ["geek", "smart"]),
    ("🧐", "Face with Monocle", ":monocle_face:", "Smileys & Emotion", ["curious", "examining"]),
    ("🥳", "Partying Face", ":partying_face:", "Smileys & Emotion", ["celebrate", "birthday", "party"]),
    ("😏", "Smirking Face", ":smirk:", "Smileys & Emotion", ["smug"]),
    ("😒", "Unamused Face", ":unamused:", "Smileys & Emotion", ["meh", "bored"]),
    ("😞", "Disappointed Face", ":disappointed:", "Smileys & Emotion", ["sad"]),
    ("😔", "Pensive Face", ":pensive:", "Smileys & Emotion", ["thoughtful"]),
    ("🥺", "Pleading Face", ":pleading_face:", "Smileys & Emotion", ["begging", "puppy eyes"]),
    ("😢", "Crying Face", ":cry:", "Smileys & Emotion", ["sad", "tear"]),
    ("😭", "Loudly Crying Face", ":sob:", "Smileys & Emotion", ["wail", "heartbroken"]),
    ("😤", "Face with Steam From Nose", ":triumph:", "Smileys & Emotion", ["frustrated"]),
    ("😠", "Angry Face", ":angry:", "Smileys & Emotion", ["mad", "annoyed"]),
    ("😡", "Pouting Face", ":rage:", "Smileys & Emotion", ["furious"]),
    ("🤬", "Face with Symbols on Mouth", ":cursing_face:", "Smileys & Emotion", ["swearing"]),
    ("🤯", "Exploding Head", ":exploding_head:", "Smileys & Emotion", ["mind blown", "shock"]),
    ("😳", "Flushed Face", ":flushed:", "Smileys & Emotion", ["embarrassed"]),
    ("🥵", "Hot Face", ":hot_face:", "Smileys & Emotion", ["heat", "sweat"]),
    ("🥶", "Cold Face", ":cold_face:", "Smileys & Emotion", ["freezing", "ice"]),
    ("😱", "Face Screaming in Fear", ":scream:", "Smileys & Emotion", ["horror", "munch"]),
    ("😨", "Fearful Face", ":fearful:", "Smileys & Emotion", ["scared"]),
    ("😰", "Anxious Face with Sweat", ":cold_sweat:", "Smileys & Emotion", ["nervous"]),
    ("🤔", "Thinking Face", ":thinking:", "Smileys & Emotion", ["wonder", "hmmm", "ponder"]),
    ("🤫", "Shushing Face", ":shushing_face:", "Smileys & Emotion", ["quiet", "secret"]),
    ("🤭", "Face with Hand Over Mouth", ":hand_over_mouth:", "Smileys & Emotion", ["oops", "giggle"]),
    ("🥱", "Yawning Face", ":yawning_face:", "Smileys & Emotion", ["tired", "sleepy"]),
    ("😴", "Sleeping Face", ":sleeping:", "Smileys & Emotion", ["zzz"]),
    ("🤤", "Drooling Face", ":drooling_face:", "Smileys & Emotion", ["yummy"]),
    ("🤒", "Face with Thermometer", ":face_with_thermometer:", "Smileys & Emotion", ["sick"]),
    ("🤕", "Face with Head-Bandage", ":head_bandage:", "Smileys & Emotion", ["hurt"]),
    ("🤢", "Nauseated Face", ":nauseated_face:", "Smileys & Emotion", ["gross", "disgusted"]),
    ("🤮", "Face Vomiting", ":vomiting_face:", "Smileys & Emotion", ["puke"]),
    ("🤧", "Sneezing Face", ":sneezing_face:", "Smileys & Emotion", ["cold", "allergy"]),
    ("😷", "Face with Medical Mask", ":mask:", "Smileys & Emotion", ["virus", "covid"]),
    ("🤐", "Zipper-Mouth Face", ":zipper_mouth_face:", "Smileys & Emotion", ["silent"]),
    ("🥴", "Woozy Face", ":woozy_face:", "Smileys & Emotion", ["dizzy", "drunk"]),
    ("🤠", "Cowboy Hat Face", ":cowboy_hat_face:", "Smileys & Emotion", ["western"]),
    ("🤡", "Clown Face", ":clown_face:", "Smileys & Emotion", ["circus", "fool"]),
    ("👻", "Ghost", ":ghost:", "Smileys & Emotion", ["spooky", "halloween"]),
    ("💀", "Skull", ":skull:", "Smileys & Emotion", ["dead", "skeleton", "death"]),
    ("☠️", "Skull and Crossbones", ":skull_and_crossbones:", "Smileys & Emotion", ["danger", "pirate"]),
    ("👽", "Alien", ":alien:", "Smileys & Emotion", ["ufo", "extraterrestrial"]),
    ("👾", "Alien Monster", ":space_invader:", "Smileys & Emotion", ["game", "retro"]),
    ("🤖", "Robot", ":robot:", "Smileys & Emotion", ["bot", "ai"]),
    ("💩", "Pile of Poo", ":poop:", "Smileys & Emotion", ["crap"]),
    ("🔥", "Fire", ":fire:", "Nature & Symbols", ["flame", "hot", "lit", "burn"]),
    ("✨", "Sparkles", ":sparkles:", "Nature & Symbols", ["magic", "shine", "clean", "star"]),
    ("🌟", "Glowing Star", ":star2:", "Nature & Symbols", ["sparkle", "night"]),
    ("⭐", "Star", ":star:", "Nature & Symbols", ["favorite", "rate"]),
    ("⚡", "High Voltage", ":zap:", "Nature & Symbols", ["lightning", "electricity", "bolt", "fast"]),
    ("💥", "Collision", ":boom:", "Nature & Symbols", ["explosion", "bang"]),
    ("💯", "Hundred Points", ":100:", "Nature & Symbols", ["perfect", "score", "century"]),
    ("💢", "Anger Symbol", ":anger:", "Nature & Symbols", ["mad"]),
    ("💤", "Zzz", ":zzz:", "Nature & Symbols", ["sleep"]),
    ("🎉", "Party Popper", ":tada:", "Activities", ["congrats", "celebrate", "party"]),
    ("🎊", "Confetti Ball", ":confetti_ball:", "Activities", ["celebrate"]),
    ("🎈", "Balloon", ":balloon:", "Activities", ["celebration", "party"]),
    ("🎁", "Wrapped Gift", ":gift:", "Activities", ["present", "birthday", "christmas"]),
    ("🏆", "Trophy", ":trophy:", "Activities", ["winner", "first", "prize"]),
    ("🥇", "1st Place Medal", ":first_place_medal:", "Activities", ["gold", "winner"]),
    ("🥈", "2nd Place Medal", ":second_place_medal:", "Activities", ["silver"]),
    ("🥉", "3rd Place Medal", ":third_place_medal:", "Activities", ["bronze"]),
    ("⚽", "Soccer Ball", ":soccer:", "Activities", ["football", "sports"]),
    ("🏀", "Basketball", ":basketball:", "Activities", ["sports", "ball"]),
    ("🎮", "Video Game", ":video_game:", "Activities", ["gaming", "controller", "play"]),
    ("🎯", "Direct Hit", ":dart:", "Activities", ["target", "bullseye"]),
    ("🎨", "Artist Palette", ":art:", "Activities", ["draw", "paint", "design"]),
    ("🎭", "Performing Arts", ":performing_arts:", "Activities", ["theater", "drama"]),
    ("🎤", "Microphone", ":microphone:", "Activities", ["sing", "karaoke", "podcast"]),
    ("🎧", "Headphone", ":headphones:", "Activities", ["music", "audio", "listen"]),
    ("🎸", "Guitar", ":guitar:", "Activities", ["instrument", "rock"]),
    ("🎹", "Musical Keyboard", ":musical_keyboard:", "Activities", ["piano"]),
    ("❤️", "Red Heart", ":heart:", "Symbols", ["love", "like"]),
    ("🧡", "Orange Heart", ":orange_heart:", "Symbols", ["love"]),
    ("💛", "Yellow Heart", ":yellow_heart:", "Symbols", ["love"]),
    ("💚", "Green Heart", ":green_heart:", "Symbols", ["love"]),
    ("💙", "Blue Heart", ":blue_heart:", "Symbols", ["love"]),
    ("💜", "Purple Heart", ":purple_heart:", "Symbols", ["love"]),
    ("🖤", "Black Heart", ":black_heart:", "Symbols", ["love", "dark"]),
    ("🤍", "White Heart", ":white_heart:", "Symbols", ["pure"]),
    ("🤎", "Brown Heart", ":brown_heart:", "Symbols", ["love"]),
    ("💔", "Broken Heart", ":broken_heart:", "Symbols", ["heartbreak", "sad"]),
    ("💖", "Sparkling Heart", ":sparkling_heart:", "Symbols", ["love", "shiny"]),
    ("💗", "Growing Heart", ":heartpulse:", "Symbols", ["love"]),
    ("👍", "Thumbs Up", ":thumbsup:", "People & Body", ["approve", "yes", "like", "+1", "good"]),
    ("👎", "Thumbs Down", ":thumbsdown:", "People & Body", ["disapprove", "no", "dislike", "-1", "bad"]),
    ("👏", "Clapping Hands", ":clap:", "People & Body", ["applause", "praise"]),
    ("🙌", "Raising Hands", ":raised_hands:", "People & Body", ["hooray", "celebrate"]),
    ("👐", "Open Hands", ":open_hands:", "People & Body", ["hug"]),
    ("🤝", "Handshake", ":handshake:", "People & Body", ["deal", "agreement", "partnership"]),
    ("🙏", "Folded Hands", ":pray:", "People & Body", ["please", "thank you", "hope"]),
    ("✌️", "Victory Hand", ":v:", "People & Body", ["peace", "two"]),
    ("🤞", "Crossed Fingers", ":crossed_fingers:", "People & Body", ["luck"]),
    ("🤟", "Love-You Gesture", ":love_you_gesture:", "People & Body", ["ily"]),
    ("🤘", "Sign of the Horns", ":metal:", "People & Body", ["rock"]),
    ("👌", "OK Hand", ":ok_hand:", "People & Body", ["perfect", "fine"]),
    ("🤌", "Pinched Fingers", ":pinched_fingers:", "People & Body", ["italian", "chef"]),
    ("👈", "Backhand Index Pointing Left", ":point_left:", "People & Body", ["left"]),
    ("👉", "Backhand Index Pointing Right", ":point_right:", "People & Body", ["right"]),
    ("👆", "Backhand Index Pointing Up", ":point_up_2:", "People & Body", ["up"]),
    ("👇", "Backhand Index Pointing Down", ":point_down:", "People & Body", ["down"]),
    ("👋", "Waving Hand", ":wave:", "People & Body", ["hello", "bye", "greeting"]),
    ("💪", "Flexed Biceps", ":muscle:", "People & Body", ["strong", "workout", "power"]),
    ("👀", "Eyes", ":eyes:", "People & Body", ["look", "see", "watch"]),
    ("🧠", "Brain", ":brain:", "People & Body", ["mind", "smart", "intellect"]),
    ("🚀", "Rocket", ":rocket:", "Travel & Places", ["launch", "ship", "space", "fast"]),
    ("✈️", "Airplane", ":airplane:", "Travel & Places", ["flight", "travel"]),
    ("🚗", "Automobile", ":car:", "Travel & Places", ["vehicle", "drive"]),
    ("🚕", "Taxi", ":taxi:", "Travel & Places", ["cab"]),
    ("🚲", "Bicycle", ":bike:", "Travel & Places", ["cycle", "ride"]),
    ("⛵", "Sailboat", ":sailboat:", "Travel & Places", ["boat", "sea"]),
    ("🏠", "House", ":house:", "Travel & Places", ["home", "building"]),
    ("🌍", "Globe Showing Europe-Africa", ":earth_africa:", "Travel & Places", ["world", "planet"]),
    ("🌎", "Globe Showing Americas", ":earth_americas:", "Travel & Places", ["world", "planet"]),
    ("🌏", "Globe Showing Asia-Australia", ":earth_asia:", "Travel & Places", ["world", "planet"]),
    ("☀️", "Sun", ":sunny:", "Travel & Places", ["weather", "warm"]),
    ("🌙", "Crescent Moon", ":crescent_moon:", "Travel & Places", ["night", "sleep"]),
    ("☁️", "Cloud", ":cloud:", "Travel & Places", ["weather"]),
    ("🌧️", "Cloud with Rain", ":cloud_with_rain:", "Travel & Places", ["rain", "weather"]),
    ("❄️", "Snowflake", ":snowflake:", "Travel & Places", ["cold", "winter"]),
    ("☕", "Hot Beverage", ":coffee:", "Food & Drink", ["tea", "cafe", "espresso"]),
    ("🍵", "Teacup Without Handle", ":tea:", "Food & Drink", ["green tea", "matcha"]),
    ("🍺", "Beer Mug", ":beer:", "Food & Drink", ["drink", "alcohol"]),
    ("🍻", "Clinking Beer Mugs", ":beers:", "Food & Drink", ["cheers"]),
    ("🍷", "Wine Glass", ":wine_glass:", "Food & Drink", ["alcohol"]),
    ("🍕", "Pizza", ":pizza:", "Food & Drink", ["fast food", "cheese"]),
    ("🍔", "Hamburger", ":burger:", "Food & Drink", ["fast food", "cheeseburger"]),
    ("🍟", "French Fries", ":fries:", "Food & Drink", ["chips"]),
    ("🌮", "Taco", ":taco:", "Food & Drink", ["mexican"]),
    ("🍦", "Soft Ice Cream", ":icecream:", "Food & Drink", ["dessert"]),
    ("🍩", "Doughnut", ":doughnut:", "Food & Drink", ["sweet", "donut"]),
    ("🍪", "Cookie", ":cookie:", "Food & Drink", ["biscuit"]),
    ("🍎", "Red Apple", ":apple:", "Food & Drink", ["fruit"]),
    ("🍌", "Banana", ":banana:", "Food & Drink", ["fruit"]),
    ("🥑", "Avocado", ":avocado:", "Food & Drink", ["fruit"]),
    ("💻", "Laptop", ":laptop:", "Objects", ["computer", "pc", "tech"]),
    ("🖥️", "Desktop Computer", ":desktop_computer:", "Objects", ["monitor", "screen"]),
    ("📱", "Mobile Phone", ":iphone:", "Objects", ["smartphone", "cell"]),
    ("⌨️", "Keyboard", ":keyboard:", "Objects", ["type", "input"]),
    ("🖱️", "Computer Mouse", ":computer_mouse:", "Objects", ["click"]),
    ("🖨️", "Printer", ":printer:", "Objects", ["paper"]),
    ("💾", "Floppy Disk", ":floppy_disk:", "Objects", ["save"]),
    ("📁", "File Folder", ":file_folder:", "Objects", ["directory"]),
    ("📂", "Open File Folder", ":open_file_folder:", "Objects", ["files"]),
    ("📄", "Page Facing Up", ":page_facing_up:", "Objects", ["document", "file"]),
    ("📝", "Memo", ":memo:", "Objects", ["note", "pencil", "write"]),
    ("📦", "Package", ":package:", "Objects", ["box", "delivery", "shipping"]),
    ("🔒", "Locked", ":lock:", "Objects", ["secure", "password", "private"]),
    ("🔓", "Unlocked", ":unlock:", "Objects", ["insecure", "open"]),
    ("🔑", "Key", ":key:", "Objects", ["password", "access"]),
    ("💡", "Light Bulb", ":bulb:", "Objects", ["idea", "bright"]),
    ("🔍", "Magnifying Glass Tilted Left", ":mag:", "Objects", ["search", "find"]),
    ("⚙️", "Gear", ":gear:", "Objects", ["settings", "cog", "preferences"]),
    ("🔧", "Wrench", ":wrench:", "Objects", ["tool", "fix", "repair"]),
    ("🔨", "Hammer", ":hammer:", "Objects", ["build", "tool"]),
    ("🛡️", "Shield", ":shield:", "Objects", ["security", "protect"]),
    ("🔔", "Bell", ":bell:", "Objects", ["notification", "ring", "alert"]),
    ("🔕", "Bell with Slash", ":no_bell:", "Objects", ["silent", "mute"]),
    ("🏷️", "Label", ":label:", "Objects", ["tag"]),
    ("📌", "Pushpin", ":pushpin:", "Objects", ["pin", "favorite"]),
    ("📍", "Round Pushpin", ":round_pushpin:", "Objects", ["location", "map"]),
    ("🗑️", "Wastebasket", ":wastebasket:", "Objects", ["trash", "delete", "bin"]),
    ("✅", "Check Mark Button", ":white_check_mark:", "Symbols", ["yes", "done", "ok", "complete", "pass"]),
    ("✔️", "Check Mark", ":heavy_check_mark:", "Symbols", ["check", "yes"]),
    ("❌", "Cross Mark", ":x:", "Symbols", ["no", "cancel", "error", "fail", "wrong"]),
    ("❎", "Cross Mark Button", ":negative_squared_cross_mark:", "Symbols", ["delete"]),
    ("⚠️", "Warning", ":warning:", "Symbols", ["caution", "alert", "danger"]),
    ("⛔", "No Entry", ":no_entry:", "Symbols", ["forbidden", "stop"]),
    ("🚫", "Prohibited", ":prohibited:", "Symbols", ["ban", "no"]),
    ("❓", "Red Question Mark", ":question:", "Symbols", ["help", "confused"]),
    ("❗", "Red Exclamation Mark", ":exclamation:", "Symbols", ["important"]),
    ("ℹ️", "Information", ":information_source:", "Symbols", ["info"]),
    ("🔄", "Counterclockwise Arrows Button", ":arrows_counterclockwise:", "Symbols", ["reload", "sync", "refresh"]),
    ("⏰", "Alarm Clock", ":alarm_clock:", "Symbols", ["time", "wake"]),
    ("⏱️", "Stopwatch", ":stopwatch:", "Symbols", ["timer"]),
    ("⏳", "Hourglass Done", ":hourglass_flowing_sand:", "Symbols", ["waiting", "loading"]),
    ("🔗", "Link", ":link:", "Symbols", ["url", "hyperlink"]),
    ("🔘", "Radio Button", ":radio_button:", "Symbols", ["select"]),
    ("🟢", "Green Circle", ":green_circle:", "Symbols", ["online", "active"]),
    ("🔴", "Red Circle", ":red_circle:", "Symbols", ["offline", "busy"]),
    ("🟡", "Yellow Circle", ":yellow_circle:", "Symbols", ["away", "idle"]),
    ("⚪", "White Circle", ":white_circle:", "Symbols", ["blank"]),
    ("⚫", "Black Circle", ":black_circle:", "Symbols", ["dark"]),
    ("🚩", "Triangular Flag", ":triangular_flag_on_post:", "Symbols", ["report"]),
    ("🏁", "Chequered Flag", ":checkered_flag:", "Symbols", ["finish", "race"]),
]


class EmojiProvider:
    def search(self, query: str) -> list[SearchResult]:
        q = query.strip()
        if not q.startswith(":"):
            return []

        search_term = q.lstrip(":").strip().lower()

        if not search_term:
            # Top popular emojis hint
            results = []
            for char, name, shortcode, cat, _kw in EMOJI_LIST[:8]:
                def make_copy(c=char, n=name, sc=shortcode):
                    return lambda: self._copy_emoji(c, n, sc)
                results.append(
                    SearchResult(
                        id=f"emoji:{shortcode}",
                        title=f"{char}  {shortcode}",
                        subtitle=f"{name} ({cat}) — Press Enter to copy to clipboard",
                        icon_name=char,
                        category="Emoji",
                        action=make_copy(),
                        score=90,
                    )
                )
            return results

        results = []
        for char, name, shortcode, cat, keywords in EMOJI_LIST:
            sc_clean = shortcode.strip(":").lower()
            name_lower = name.lower()
            score = 0

            if sc_clean == search_term or name_lower == search_term:
                score = 100
            elif sc_clean.startswith(search_term):
                score = 90
            elif name_lower.startswith(search_term) or any(w.startswith(search_term) for w in name_lower.split()):
                score = 85
            elif any(k == search_term for k in keywords):
                score = 80
            elif any(k.startswith(search_term) for k in keywords):
                score = 75
            elif search_term in sc_clean or search_term in name_lower:
                score = 65
            elif any(search_term in k for k in keywords):
                score = 55
            elif search_term in cat.lower():
                score = 45

            if score > 0:
                def make_copy(c=char, n=name, sc=shortcode):
                    return lambda: self._copy_emoji(c, n, sc)
                results.append(
                    SearchResult(
                        id=f"emoji:{shortcode}",
                        title=f"{char}  {shortcode}",
                        subtitle=f"{name} ({cat}) — Press Enter to copy to clipboard",
                        icon_name=char,
                        category="Emoji",
                        action=make_copy(),
                        score=score,
                    )
                )

        return sorted(results, key=lambda r: r.score, reverse=True)

    def _copy_emoji(self, char: str, name: str, shortcode: str) -> None:
        from knobu.modules.clipboard import set_clipboard
        set_clipboard(char)
        try:
            from knobu.system import notify
            notify.send("Copied to clipboard", f"{char} {name} ({shortcode})")
        except Exception:
            pass


# ==============================================================================
# 9. OPEN WINDOWS & TAB SWITCHER PROVIDER
# ==============================================================================

class WindowProvider:
    """Lists running desktop application windows and tabs, allowing instant switching."""

    def __init__(self, app_provider: AppProvider | None = None):
        self.app_provider = app_provider or AppProvider()

    def search(self, query: str) -> list[SearchResult]:
        q = query.strip()
        is_explicit = q.startswith("<") or q.startswith("win:") or q.startswith("tab:")
        clean_q = q.lstrip("<").removeprefix("win:").removeprefix("tab:").strip().lower()

        windows = self._get_windows()
        if not windows:
            if is_explicit:
                return [
                    SearchResult(
                        id="win:none",
                        title="No Open Windows Detected",
                        subtitle="No running application windows match the current desktop session",
                        icon_name="window-new-symbolic",
                        category="Open Window",
                        action=lambda: None,
                        score=90,
                    )
                ]
            return []

        if is_explicit and not clean_q:
            results = []
            for wid, title, sub, d_file, icon, xid, exec_cmd, app_name in windows:
                def make_act(x=xid, df=d_file, ec=exec_cmd, an=app_name):
                    return lambda: self._activate_window(x, df, ec, an)
                results.append(
                    SearchResult(
                        id=wid,
                        title=title,
                        subtitle=sub,
                        icon_name=icon,
                        category="Open Window",
                        action=make_act(),
                        score=95,
                    )
                )
            return results

        results = []
        for wid, title, sub, d_file, icon, xid, exec_cmd, app_name in windows:
            title_lower = title.lower()
            score = 0
            base_score = 95 if is_explicit else 88

            if title_lower == clean_q or (app_name and app_name.lower() == clean_q):
                score = base_score + 5
            elif title_lower.startswith(clean_q) or (app_name and app_name.lower().startswith(clean_q)):
                score = base_score + 3
            elif any(w.startswith(clean_q) for w in title_lower.split()) or (app_name and any(w.startswith(clean_q) for w in app_name.lower().split())):
                score = base_score
            elif clean_q in title_lower or (app_name and clean_q in app_name.lower()):
                score = base_score - 5

            if score > 0:
                def make_act(x=xid, df=d_file, ec=exec_cmd, an=app_name):
                    return lambda: self._activate_window(x, df, ec, an)
                results.append(
                    SearchResult(
                        id=wid,
                        title=title,
                        subtitle=sub,
                        icon_name=icon,
                        category="Open Window",
                        action=make_act(),
                        score=score,
                    )
                )

        return sorted(results, key=lambda r: r.score, reverse=True)

    def _get_windows(self) -> list[tuple[str, str, str, Path | None, str, str | None, str | None, str]]:
        """Returns list of (id, title, subtitle, desktop_file, icon_name, xid, exec_cmd, app_name)."""
        windows = []
        seen = set()

        if not self.app_provider._loaded:
            self.app_provider.load_apps()

        # 1. Query wmctrl if available (captures real X11/XWayland window captions and browser tabs)
        if shutil.which("wmctrl"):
            try:
                proc = subprocess.run(
                    ["wmctrl", "-l", "-p", "-x"],
                    capture_output=True,
                    text=True,
                    timeout=1.0,
                )
                if proc.returncode == 0:
                    for line in proc.stdout.splitlines():
                        parts = line.split(maxsplit=4)
                        if len(parts) >= 5:
                            xid, _d, _pid, wm_class, title = parts
                            title = title.strip()
                            if not title or title in ("Desktop", "gnome-shell", "Knobu Command Bar", "Knobu"):
                                continue
                            app_class = wm_class.split(".")[0] if "." in wm_class else wm_class
                            icon = "window-new-symbolic"
                            d_file = None
                            exec_cmd = None
                            app_name = app_class

                            for a in self.app_provider._apps:
                                if app_class.lower() in a.name.lower() or app_class.lower() in a.desktop_file.stem.lower():
                                    icon = a.icon
                                    d_file = a.desktop_file
                                    exec_cmd = a.exec_cmd
                                    app_name = a.name
                                    break

                            wid = f"wmctrl:{xid}"
                            if wid not in seen:
                                seen.add(wid)
                                windows.append((
                                    wid,
                                    title,
                                    f"Window ({app_name}) — Press Enter to switch",
                                    d_file,
                                    icon,
                                    xid,
                                    exec_cmd,
                                    app_name,
                                ))
            except Exception as e:
                log.debug("wmctrl window query error: %s", e)

        # 2. Query systemd user scopes for active application scopes
        try:
            proc = subprocess.run(
                ["systemctl", "--user", "list-units", "--type=scope", "--no-legend", "--plain"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    parts = line.split()
                    if not parts:
                        continue
                    unit = parts[0]
                    unit_clean = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), unit)
                    m = re.match(r"^(?:app-gnome-|app-|snap\.)([a-zA-Z0-9_.-]+?)(?:-[0-9]+)?\.scope$", unit_clean)
                    if m:
                        app_key = m.group(1).lower()
                        if app_key.startswith("org.gnome.settingsdaemon") or app_key.endswith("-notify"):
                            continue
                        for a in self.app_provider._apps:
                            if (app_key in a.name.lower() or
                                app_key in a.desktop_file.stem.lower() or
                                app_key in a.exec_cmd.lower()):
                                wid = f"scope:{a.name}"
                                if wid not in seen and not any(w[7] == a.name for w in windows):
                                    seen.add(wid)
                                    windows.append((
                                        wid,
                                        a.name,
                                        "Running Application — Press Enter to switch",
                                        a.desktop_file,
                                        a.icon,
                                        None,
                                        a.exec_cmd,
                                        a.name,
                                    ))
                                break
        except Exception as e:
            log.debug("systemd scope query error: %s", e)

        return windows

    def _activate_window(self, xid: str | None, desktop_file: Path | None, exec_cmd: str | None, app_name: str | None) -> None:
        """Brings target window or application to focus."""
        # 1. Direct X11 window activation via wmctrl
        if xid and shutil.which("wmctrl"):
            try:
                subprocess.Popen(["wmctrl", "-ia", xid], start_new_session=True)
                return
            except Exception as e:
                log.warning("wmctrl activation failed: %s", e)

        # 2. Activate via desktop manager launcher (gio or gtk-launch)
        if desktop_file and desktop_file.exists() and shutil.which("gio"):
            try:
                subprocess.Popen(["gio", "launch", str(desktop_file)], start_new_session=True)
                return
            except Exception as e:
                log.warning("gio launch failed: %s", e)

        if desktop_file and shutil.which("gtk-launch"):
            try:
                subprocess.Popen(["gtk-launch", desktop_file.stem], start_new_session=True)
                return
            except Exception as e:
                log.warning("gtk-launch failed: %s", e)

        if exec_cmd:
            try:
                cmd = re.sub(r"%[a-zA-Z]", "", exec_cmd).strip()
                args = shlex.split(cmd)
                if args:
                    subprocess.Popen(args, start_new_session=True)
            except Exception as e:
                log.warning("exec failed: %s", e)


# ==============================================================================
# COMPOSITE SEARCH ENGINE
# ==============================================================================

class SearchEngine:
    def __init__(self, settings: dict | None = None):
        self.settings = settings or {}
        self.apps = AppProvider()
        self.calc = CalculatorProvider()
        self.shell = ShellProvider()
        self.paths = PathProvider()
        self.web = WebProvider()
        self.system = SystemProvider()
        self.converter = ConverterProvider()
        self.emoji = EmojiProvider()
        self.windows = WindowProvider(self.apps)

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        q = query.strip()
        results: list[SearchResult] = []

        # 1. Shell commands have highest priority when prefix '>' is used
        if self.settings.get("enable_shell", True) and (q.startswith(">") or q.startswith("term:")):
            return self.shell.search(q)[:limit]

        # 2. Emoji search when prefix ':' is used
        if self.settings.get("enable_emoji", True) and q.startswith(":"):
            return self.emoji.search(q)[:limit]

        # 3. Window & tab switcher when prefix '<' or 'win:' or 'tab:' is used
        if self.settings.get("enable_windows", True) and (q.startswith("<") or q.startswith("win:") or q.startswith("tab:")):
            return self.windows.search(q)[:limit]

        # 4. Path provider triggers on path prefixes
        if self.settings.get("enable_paths", True) and (q.startswith("~/") or q.startswith("/") or q.startswith("./")):
            return self.paths.search(q)[:limit]

        # 5. Direct URL or web search
        if self.settings.get("enable_web", True):
            web_res = self.web.search(q)
            if web_res:
                results.extend(web_res)

        # 6. Unit & currency converter
        if self.settings.get("enable_converter", True):
            conv_res = self.converter.search(q)
            if conv_res:
                results.extend(conv_res)

        # 7. Safe calculation
        if self.settings.get("enable_calc", True):
            calc_res = self.calc.search(q)
            if calc_res:
                results.extend(calc_res)

        # 8. Open windows & active applications in general search
        if self.settings.get("enable_windows", True) and q:
            win_res = self.windows.search(q)
            if win_res:
                results.extend(win_res)

        # 9. System commands & actions
        if self.settings.get("enable_system", True):
            results.extend(self.system.search(q))

        # 10. Desktop applications
        if self.settings.get("enable_apps", True):
            results.extend(self.apps.search(q))

        # Rank and deduplicate
        seen_ids = set()
        deduped = []
        for r in sorted(results, key=lambda x: x.score, reverse=True):
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                deduped.append(r)
            if len(deduped) >= limit:
                break

        return deduped
