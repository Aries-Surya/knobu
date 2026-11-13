"""Clipboard Manager module package for Knobu.

Searchable clipboard history, copied image support, paste plain text, tracking URL cleaner,
and persistent SQLite storage.
"""

from __future__ import annotations

import logging
import threading
import time

from knobu.modules.base import Module
from knobu.modules.clipboard.storage import (
    Clip,
    ClipboardStorage,
    TRACKING_PARAMS,
    clean_url,
    get_clipboard,
    get_clipboard_image,
    get_clipboard_types,
    is_sensitive_clipboard,
    set_clipboard,
    set_clipboard_image,
    simulate_paste,
)
from knobu.system import hotkeys, keys, launch

log = logging.getLogger("knobu.clipboard")

__all__ = [
    "ClipboardModule",
    "ClipboardStorage",
    "Clip",
    "TRACKING_PARAMS",
    "clean_url",
    "get_clipboard",
    "get_clipboard_image",
    "get_clipboard_types",
    "is_sensitive_clipboard",
    "set_clipboard",
    "set_clipboard_image",
    "simulate_paste",
]


class ClipboardModule(Module):
    id = "clipboard"
    name = "Clipboard History"
    description = "Searchable clipboard history, images, paste plain text, and tracking URL cleaner."
    icon = "edit-paste-symbolic"
    defaults = {
        "enabled": True,
        "hotkey": "super+v",
        "plain_hotkey": "",
        "clean_urls": True,
        "strip_whitespace": True,
        "ignore_passwords": True,
        "store_text": True,
        "store_images": True,
        "direct_paste": True,
        "max_items": 50,
    }

    def __init__(self, settings: dict):
        super().__init__(settings)
        self.storage = ClipboardStorage()

    def run(self, stop: threading.Event) -> None:
        bindings = []
        # Register Super+V strictly for Clipboard History
        try:
            chord = keys.parse(self.settings.get("hotkey", "super+v"))
            b1 = hotkeys.service().register(chord, lambda: launch.knobu("clipboard"))
            bindings.append(b1)
            self.log.info("Registered shortcut %s for Clipboard History", keys.pretty(self.settings.get("hotkey", "super+v")))
        except ValueError as err:
            self.log.error("Invalid hotkey: %s", err)

        # Register optional Paste Plain hotkey only if explicitly configured
        plain_key = self.settings.get("plain_hotkey", "")
        if plain_key:
            try:
                plain_chord = keys.parse(plain_key)
                b2 = hotkeys.service().register(plain_chord, lambda: launch.knobu("paste-plain"))
                bindings.append(b2)
                self.log.info("Registered shortcut %s for Paste Plain", keys.pretty(plain_key))
            except ValueError as err:
                self.log.error("Invalid plain hotkey: %s", err)

        # Passive capture on Ctrl+C / Ctrl+X without continuous polling
        def on_copy():
            time.sleep(0.08)
            types = get_clipboard_types()
            if self.settings.get("ignore_passwords", True) and is_sensitive_clipboard(types):
                return

            max_items = self.settings.get("max_items", 50)

            # Store images if enabled and an image was copied
            if self.settings.get("store_images", True):
                img_bytes = get_clipboard_image()
                if img_bytes:
                    self.storage.add_image_clip(img_bytes, max_items=max_items)
                    return

            # Store text if enabled
            if self.settings.get("store_text", True):
                current = get_clipboard()
                if current:
                    if self.settings.get("strip_whitespace", True):
                        current = current.strip()
                    if self.settings.get("clean_urls", True) and (current.startswith("http://") or current.startswith("https://")):
                        cleaned = clean_url(current)
                        if cleaned != current:
                            set_clipboard(cleaned)
                            current = cleaned
                    self.storage.add_clip(current, "text", max_items=max_items)

        try:
            ctrl_c = keys.parse("ctrl+c")
            ctrl_x = keys.parse("ctrl+x")
            bindings.append(hotkeys.service().register(ctrl_c, on_copy))
            bindings.append(hotkeys.service().register(ctrl_x, on_copy))
        except Exception:
            pass

        try:
            stop.wait()
        finally:
            for b in bindings:
                hotkeys.service().unregister(b)
