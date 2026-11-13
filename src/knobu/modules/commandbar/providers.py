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

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        q = query.strip()
        results: list[SearchResult] = []

        # 1. Shell commands have highest priority when prefix '>' is used
        if self.settings.get("enable_shell", True) and (q.startswith(">") or q.startswith("term:")):
            return self.shell.search(q)[:limit]

        # 2. Path provider triggers on path prefixes
        if self.settings.get("enable_paths", True) and (q.startswith("~/") or q.startswith("/") or q.startswith("./")):
            return self.paths.search(q)[:limit]

        # 3. Direct URL or web search
        if self.settings.get("enable_web", True):
            web_res = self.web.search(q)
            if web_res:
                results.extend(web_res)

        # 4. Safe calculation
        if self.settings.get("enable_calc", True):
            calc_res = self.calc.search(q)
            if calc_res:
                results.extend(calc_res)

        # 5. System commands & actions
        if self.settings.get("enable_system", True):
            results.extend(self.system.search(q))

        # 6. Desktop applications
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
