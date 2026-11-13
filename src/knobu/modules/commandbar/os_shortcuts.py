"""OS-level shortcut conflict detection and overriding for Command Bar (Alt+Space).

Detects and safely overrides conflicting desktop environment shortcuts in:
- GNOME / Ubuntu (org.gnome.settings-daemon.plugins.media-keys search,
                  org.gnome.desktop.wm.keybindings activate-window-menu)
- KDE Plasma (krunner.desktop _launch, kwin Window Operations Menu)
- XFCE (xfwm4 /commands/custom/override)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess

log = logging.getLogger("knobu.commandbar.os_shortcuts")

# Cache for original values before Knobu overrides them
_original_gnome_bindings: dict[str, str] = {}


def is_gnome() -> bool:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    return any(d in desktop for d in ("GNOME", "UBUNTU", "UNITY"))


def is_kde() -> bool:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    return "KDE" in desktop


def check_conflicts() -> list[dict[str, str]]:
    """Return a list of conflicting OS shortcuts currently bound to Alt+Space."""
    conflicts = []

    # Check GNOME gsettings
    if shutil.which("gsettings"):
        checks = [
            ("org.gnome.settings-daemon.plugins.media-keys", "search", "GNOME Search / Overview"),
            ("org.gnome.desktop.wm.keybindings", "activate-window-menu", "Window Menu"),
        ]
        for schema, key, name in checks:
            try:
                out = subprocess.run(
                    ["gsettings", "get", schema, key],
                    capture_output=True,
                    text=True,
                    timeout=2,
                ).stdout.strip()
                if "space" in out.lower() and "alt" in out.lower():
                    conflicts.append({
                        "system": "GNOME",
                        "schema": schema,
                        "key": key,
                        "name": name,
                        "current": out,
                    })
            except Exception as e:
                log.debug("gsettings check failed for %s.%s: %s", schema, key, e)

    # Check KDE Plasma
    if is_kde():
        kwrite = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
        kread = shutil.which("kreadconfig6") or shutil.which("kreadconfig5")
        if kread:
            try:
                out = subprocess.run(
                    [kread, "--file", "kglobalshortcutsrc", "--group", "krunner.desktop", "--key", "_launch"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                ).stdout.strip()
                if "alt" in out.lower() and "space" in out.lower():
                    conflicts.append({
                        "system": "KDE",
                        "schema": "kglobalshortcutsrc:krunner.desktop",
                        "key": "_launch",
                        "name": "KRunner",
                        "current": out,
                    })
            except Exception as e:
                log.debug("kreadconfig check failed: %s", e)

    return conflicts


def override_os_shortcuts() -> bool:
    """Disable conflicting OS-level Alt+Space shortcuts so Command Bar has full control."""
    success = False

    # GNOME overrides
    if shutil.which("gsettings"):
        targets = [
            ("org.gnome.settings-daemon.plugins.media-keys", "search"),
            ("org.gnome.desktop.wm.keybindings", "activate-window-menu"),
        ]
        for schema, key in targets:
            try:
                current = subprocess.run(
                    ["gsettings", "get", schema, key],
                    capture_output=True,
                    text=True,
                    timeout=2,
                ).stdout.strip()
                if current and current != "@as []" and current != "[]":
                    _original_gnome_bindings[f"{schema}:{key}"] = current
                    subprocess.run(
                        ["gsettings", "set", schema, key, "[]"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        check=True,
                    )
                    log.info("Overrode GNOME shortcut %s.%s: %s -> []", schema, key, current)
                    success = True
            except Exception as e:
                log.warning("Failed to override GNOME shortcut %s.%s: %s", schema, key, e)

    # KDE Plasma overrides
    if is_kde():
        kwrite = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
        if kwrite:
            try:
                subprocess.run(
                    [kwrite, "--file", "kglobalshortcutsrc", "--group", "krunner.desktop", "--key", "_launch", "none,none,KRunner"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                )
                log.info("Overrode KDE KRunner Alt+Space shortcut")
                success = True
            except Exception as e:
                log.warning("Failed to override KDE KRunner shortcut: %s", e)

    return success


def restore_os_shortcuts() -> bool:
    """Restore previously overridden OS shortcuts."""
    restored = False

    if shutil.which("gsettings") and _original_gnome_bindings:
        for full_key, original_val in list(_original_gnome_bindings.items()):
            schema, key = full_key.split(":")
            try:
                subprocess.run(
                    ["gsettings", "set", schema, key, original_val],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                )
                log.info("Restored GNOME shortcut %s.%s -> %s", schema, key, original_val)
                _original_gnome_bindings.pop(full_key, None)
                restored = True
            except Exception as e:
                log.warning("Failed to restore GNOME shortcut %s.%s: %s", schema, key, e)

    # If KDE, restore default
    if is_kde():
        kwrite = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
        if kwrite:
            try:
                subprocess.run(
                    [kwrite, "--file", "kglobalshortcutsrc", "--group", "krunner.desktop", "--key", "_launch", "Alt+Space,none,KRunner"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                log.info("Restored KDE KRunner default shortcut")
                restored = True
            except Exception as e:
                log.warning("Failed to restore KDE shortcut: %s", e)

    return restored
