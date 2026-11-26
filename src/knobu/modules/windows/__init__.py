"""Window Management module (Milestone 5): FancyZones & Always on Top."""

from __future__ import annotations

import threading

from knobu.modules.base import Module
from knobu.modules.windows.zones import (
    ZONE_PRESETS,
    ZoneRect,
    compute_zones,
    maximize_active_window,
    snap_active_window,
    toggle_always_on_top,
)
from knobu.system import hotkeys, keys, launch, notify, osd

__all__ = [
    "WindowModule",
    "ZONE_PRESETS",
    "ZoneRect",
    "compute_zones",
    "toggle_always_on_top",
    "snap_active_window",
    "maximize_active_window",
]


class WindowModule(Module):
    id = "windows"
    name = "Window Manager"
    description = "Always on Top pinning, FancyZones grid snapping, and clean window maximize."
    icon = "preferences-system-windows-symbolic"
    defaults = {
        "enabled": True,
        "always_on_top_hotkey": "super+ctrl+t",
        "fancyzones_hotkey": "super+shift+grave",
        "snap_left_hotkey": "super+ctrl+left",
        "snap_right_hotkey": "super+ctrl+right",
        "maximize_hotkey": "super+ctrl+up",
        "zone_preset": "2col",
        "zone_gap": 8,
        "excluded_apps": [],
    }

    def run(self, stop: threading.Event) -> None:
        bindings = []
        preset = str(self.settings.get("zone_preset", "2col"))
        gap = int(self.settings.get("zone_gap", 8))
        excluded = list(self.settings.get("excluded_apps", []))

        actions = [
            ("always_on_top_hotkey", lambda: self._on_top(excluded)),
            ("fancyzones_hotkey", lambda: launch.knobu("fancyzones")),
            ("snap_left_hotkey", lambda: self._snap(0, preset, gap)),
            ("snap_right_hotkey", lambda: self._snap(1, preset, gap)),
            ("maximize_hotkey", self._maximize),
        ]
        for key, fn in actions:
            raw = str(self.settings.get(key, "")).strip()
            if not raw:
                continue
            try:
                chord = keys.parse(raw)
                bindings.append(hotkeys.service().register(chord, fn))
                self.log.info("registered %s for %s", keys.pretty(raw), key)
            except ValueError as err:
                self.log.error("bad window hotkey %s: %s", key, err)

        try:
            stop.wait()
        finally:
            for b in bindings:
                hotkeys.service().unregister(b)

    def _on_top(self, excluded: list[str]) -> None:
        ok, msg = toggle_always_on_top(excluded)
        osd.show("view-pin-symbolic", msg) if ok else notify.notify("Always on Top", msg, timeout_ms=2000)

    def _snap(self, idx: int, preset: str, gap: int) -> None:
        ok, msg = snap_active_window(idx, preset, gap)
        if not ok:
            notify.notify("FancyZones", msg, timeout_ms=2000)

    def _maximize(self) -> None:
        ok, msg = maximize_active_window()
        if not ok:
            notify.notify("Window Manager", msg, timeout_ms=2000)
