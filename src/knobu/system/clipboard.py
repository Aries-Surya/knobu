"""Clipboard system utilities for Knobu.

Re-exports core clipboard storage, URL cleaner, and paste simulation
from knobu.modules.clipboard.
"""

from knobu.modules.clipboard.storage import (
    Clip,
    ClipboardStorage,
    TRACKING_PARAMS,
    clean_url,
    get_clipboard,
    set_clipboard,
    simulate_paste,
)

__all__ = [
    "Clip",
    "ClipboardStorage",
    "TRACKING_PARAMS",
    "clean_url",
    "get_clipboard",
    "set_clipboard",
    "simulate_paste",
]
