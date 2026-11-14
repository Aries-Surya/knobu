"""Registry of Knobu modules. Add new modules to MODULES to make them appear
in the daemon and the settings app."""

from knobu.modules.awake import AwakeModule
from knobu.modules.base import Module
from knobu.modules.clipboard import ClipboardModule
from knobu.modules.commandbar import CommandBarModule
from knobu.modules.hotkey_tools import ColorPickerModule, TextExtractorModule
from knobu.modules.keyboard import KeyboardModule
from knobu.modules.touchpad import TouchpadModule

MODULES: list[type[Module]] = [
    TouchpadModule, KeyboardModule, AwakeModule, ClipboardModule, CommandBarModule, ColorPickerModule, TextExtractorModule,
]


def get(module_id: str) -> type[Module]:
    for m in MODULES:
        if m.id == module_id:
            return m
    raise KeyError(module_id)
