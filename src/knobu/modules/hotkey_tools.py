"""Modules that open a Knobu tool from a global shortcut."""

import threading

from knobu.modules.base import Module
from knobu.system import hotkeys, keys, launch


class HotkeyToolModule(Module):
    command = ""  # `knobu <command>` opens the tool

    def run(self, stop: threading.Event) -> None:
        try:
            chord = keys.parse(self.settings["hotkey"])
        except ValueError as err:
            self.log.error("bad shortcut: %s", err)
            return
        binding = hotkeys.service().register(chord, lambda: launch.knobu(self.command))
        self.log.info("shortcut %s", keys.pretty(self.settings["hotkey"]))
        try:
            stop.wait()
        finally:
            hotkeys.service().unregister(binding)


class ColorPickerModule(HotkeyToolModule):
    id = "colorpicker"
    name = "Color Picker"
    description = "Pick a colour from anywhere on screen and copy it."
    icon = "knobu-colorpicker-symbolic"
    command = "pick-color"
    defaults = {"enabled": True, "hotkey": "super+shift+c", "format": "hex"}


class TextExtractorModule(HotkeyToolModule):
    id = "textextractor"
    name = "Text Extractor"
    description = "Select any area of the screen and copy the text in it."
    icon = "knobu-textextractor-symbolic"
    command = "extract-text"
    defaults = {"enabled": True, "hotkey": "super+shift+t", "language": "eng"}
