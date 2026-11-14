"""Command Bar module package for Knobu.

PowerToys Run for Linux: instant floating launcher (Alt+Space) with app searching,
safe calculation, shell command runner, web search, path opening, and hardware-level
exclusive grab with OS shortcut override.
"""

from __future__ import annotations

import logging
import threading

from knobu.modules.base import Module
from knobu.modules.commandbar.os_shortcuts import (
    check_conflicts,
    override_os_shortcuts,
    restore_os_shortcuts,
)
from knobu.modules.commandbar.providers import (
    AppProvider,
    CalculatorProvider,
    ConverterProvider,
    EmojiProvider,
    PathProvider,
    SearchEngine,
    SearchResult,
    ShellProvider,
    SystemProvider,
    WebProvider,
    WindowProvider,
)
from knobu.system import hotkeys, keys, launch

log = logging.getLogger("knobu.commandbar")

__all__ = [
    "CommandBarModule",
    "SearchEngine",
    "SearchResult",
    "AppProvider",
    "CalculatorProvider",
    "ConverterProvider",
    "EmojiProvider",
    "PathProvider",
    "ShellProvider",
    "SystemProvider",
    "WebProvider",
    "WindowProvider",
    "check_conflicts",
    "override_os_shortcuts",
    "restore_os_shortcuts",
]


class CommandBarModule(Module):
    id = "commandbar"
    name = "Command Bar"
    description = "PowerToys Run for Linux: fast app launcher, calculator, and command bar."
    icon = "system-search-symbolic"
    defaults = {
        "enabled": True,
        "hotkey": "alt+space",
        "exclusive": True,
        "override_os_shortcut": True,
        "max_results": 8,
        "enable_apps": True,
        "enable_calc": True,
        "enable_shell": True,
        "enable_web": True,
        "enable_paths": True,
        "enable_system": True,
        "enable_converter": True,
        "enable_emoji": True,
        "enable_windows": True,
    }

    def run(self, stop: threading.Event) -> None:
        # Override desktop environment shortcut if configured
        if self.settings.get("override_os_shortcut", True):
            try:
                override_os_shortcuts()
            except Exception as e:
                self.log.warning("Could not override OS shortcut: %s", e)

        bindings = []
        try:
            chord = keys.parse(self.settings.get("hotkey", "alt+space"))
            exclusive = bool(self.settings.get("exclusive", True))
            binding = hotkeys.service().register(
                chord,
                lambda: launch.knobu("command-bar"),
                exclusive=exclusive,
            )
            bindings.append(binding)
            self.log.info(
                "Registered shortcut %s for Command Bar (exclusive=%s)",
                keys.pretty(self.settings.get("hotkey", "alt+space")),
                exclusive,
            )
        except ValueError as err:
            self.log.error("Invalid hotkey: %s", err)

        try:
            stop.wait()
        finally:
            for b in bindings:
                hotkeys.service().unregister(b)
