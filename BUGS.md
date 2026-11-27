# Knobu Bug Tracker & Issue Log

This document tracks identified bugs, root causes, system environments affected, workarounds, and resolved fixes across Knobu releases.

---

## Active & Recently Resolved Bugs

### BUG-001: Window Management EWMH Failure on Native Wayland
- **Severity**: High
- **Category**: Window Manager / Wayland
- **Symptoms**:
  - When triggering **Always on Top** (`Super+Ctrl+T`), **FancyZones Snapping** (`knobu snap`), or **Window Maximize** (`Super+Ctrl+Up`), user receives:
    `Active window does not expose EWMH handle (native Wayland app)`.
- **Root Cause**:
  - `wmctrl` and `xdotool` rely on X11 / XWayland root window properties (`_NET_WM_STATE_ABOVE`, `_NET_ACTIVE_WINDOW`). Native Wayland applications (Firefox Wayland, Alacritty, GNOME apps) do not expose X11 window IDs or EWMH handles to client applications for security reasons.
- **Affected Environments**:
  - Ubuntu 24.04+ (GNOME Shell Wayland session).
- **Fix / Remediation**:
  - Bundle `knobu-window-bridge@knobu.org` GNOME Shell extension providing privileged Mutter window manipulation over session D-Bus (`ToggleAlwaysOnTop`, `SnapWindow`, `MaximizeWindow`).
  - Fall back to KDE Plasma KWin D-Bus (`org.kde.KWin.toggleKeepAbove`) on KDE, and `wmctrl` on X11/XWayland.
- **Status**: Scheduled in Current Sprint (Milestone 13).

---

### BUG-002: Find My Mouse Highlights Screen Center Instead of Pointer
- **Severity**: Medium
- **Category**: Pointer Utilities / Mouse
- **Symptoms**:
  - Pressing `Super+Alt+F` or triggering Find My Mouse takes a screen snapshot and draws a spotlight circle fixed at the dead center `(w/2, h/2)` of the monitor rather than highlighting the actual cursor coordinates.
- **Root Cause**:
  - `FindMyMouseOverlay` in `src/knobu/ui/pointer_fx.py` initialized default coordinates to `(w / 2, h / 2)` before any motion event occurred. On Wayland, background applications cannot query global cursor coordinates without a privileged portal or active motion events inside a mapped window.
- **Affected Environments**:
  - All desktop environments (Wayland and X11).
- **Fix / Remediation**:
  - Trigger GNOME interface `locate-pointer` ripple rings via `uinput` virtual `KEY_LEFTCTRL` pulse.
  - Dynamically query Mutter pointer coordinates via D-Bus bridge and track real-time cursor motion on overlay activation.
- **Status**: Scheduled in Current Sprint (Milestone 13).

---

### BUG-003: Headless CI Runner Test Failures (GTK/Adwaita Display Segfault)
- **Severity**: High
- **Category**: CI/CD & Testing
- **Symptoms**:
  - Pipeline test job failed with `FAILED (errors=13)` and segfault (`exit -11`) during `override_dh_auto_test` in GitHub Actions.
- **Root Cause**:
  - Tests calling `Adw.init()` without a display server (`DISPLAY`, `WAYLAND_DISPLAY`, and `XDG_RUNTIME_DIR` unset) crashed inside GTK's icon theme initialization (`gtk_icon_theme_get_for_display: assertion 'GDK_IS_DISPLAY (display)' failed`).
  - Python 3.14 strict import namespace prevented `unittest.mock.patch` attribute resolution when only `unittest` was imported.
- **Affected Environments**:
  - GitHub Actions `ubuntu-24.04` and headless build servers.
- **Fix / Remediation**:
  - Added display detection (`Gdk.Display.get_default() is None`) to skip graphical UI window instantiation in headless CI runners.
  - Corrected `from unittest.mock import patch` in `tests/test_config.py`.
- **Status**: Resolved (Commit `1392d79`).

---

### BUG-004: Missing `cairo` Module in Headless Test Environment
- **Severity**: High
- **Category**: Packaging & CI
- **Symptoms**:
  - CI test runner threw `ModuleNotFoundError: No module named 'cairo'` when loading `knobu.ui.pointer_fx`, `fancyzones`, and `ruler`.
- **Root Cause**:
  - `python3-gi-cairo` was missing from `.github/workflows/ci.yml` `apt-get install` commands and Debian `Build-Depends`.
- **Affected Environments**:
  - Clean Ubuntu installations without pre-installed Cairo bindings.
- **Fix / Remediation**:
  - Added `python3-gi-cairo` and `python3-gi` to `Build-Depends` in `debian/control` and CI dependency steps in `.github/workflows/ci.yml`.
- **Status**: Resolved (Commit `9e57b11`).

---

### BUG-005: Microsoft APT Repository 403 Forbidden on CI Runners
- **Severity**: High
- **Category**: CI/CD Environment
- **Symptoms**:
  - `sudo apt-get update` failed with `403 Forbidden` on `https://packages.microsoft.com/ubuntu/24.04/prod noble InRelease` on GitHub Actions runner image.
- **Root Cause**:
  - Ubuntu 24.04 GitHub runner image pre-installed broken Microsoft package lists that failed signature verification.
- **Affected Environments**:
  - GitHub Actions `ubuntu-24.04` runner instances.
- **Fix / Remediation**:
  - Purged `/etc/apt/sources.list.d/microsoft-prod.list*` prior to executing `apt-get update` in CI workflows.
- **Status**: Resolved (Commit `8b9d3ee`).

---

### BUG-006: Circular Import between UI Tools and Modules
- **Severity**: Medium
- **Category**: Code Architecture
- **Symptoms**:
  - `ImportError: cannot import name 'ToolApp' from partially initialized module 'knobu.ui.tools'`.
- **Root Cause**:
  - Mutual circular imports between `src/knobu/ui/tools.py`, `src/knobu/modules/__init__.py`, and `src/knobu/ui/pointer_fx.py`.
- **Affected Environments**:
  - All environments importing `knobu.ui.tools`.
- **Fix / Remediation**:
  - Decoupled `ToolApp` base class and used deferred imports inside tool activate callbacks.
- **Status**: Resolved (Commit `0c74996`).

---

### BUG-007: Window Manager Missing Symbolic Icon in Dashboards
- **Severity**: Low
- **Category**: UI / Theming
- **Symptoms**:
  - Window Manager module showed a broken/missing icon placeholder on GNOME and KDE desktops.
- **Root Cause**:
  - Configured icon `focus-windows` was not a standard FreeDesktop icon name.
- **Affected Environments**:
  - Systems using Adwaita or standard icon themes.
- **Fix / Remediation**:
  - Updated icon name to standard `focus-windows-symbolic`.
- **Status**: Resolved (Commit `902cc9f`).
