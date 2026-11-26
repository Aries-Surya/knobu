# Changelog

All notable changes to Knobu will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0](https://github.com/Aries-Surya/knobu/compare/v0.3.0...v0.4.0) (2026-11-15)


### Features

* **input:** add master and per-module bypass for hardware grabs and OS customizations ([46e9549](https://github.com/Aries-Surya/knobu/commit/46e9549309747904058c1a2dc8574f1b5297bc07))
* **input:** add Text Snippets, Quit Protection, Hardware Debounce, and Mouse Utilities ([d23757c](https://github.com/Aries-Surya/knobu/commit/d23757cf81827f70043da43b5dde7933b94c803f))
* **input:** Precision Touchpad Gestures, Mouse Utilities, Keyboard Manager & Master Bypass ([08d4639](https://github.com/Aries-Surya/knobu/commit/08d4639ce797d1330b670e32410cac6f46308453))
* **osd:** trigger native OS volume slider directly and suppress notification banners ([3c3b7c0](https://github.com/Aries-Surya/knobu/commit/3c3b7c0763df74f0a3cde5a92ec896a87a289d89))
* **touchpad:** add bypass toggle and full GNOME desktop volume OSD support ([e23cc57](https://github.com/Aries-Surya/knobu/commit/e23cc5723d04e4e053d1acc204e9bda8c15e4faf))
* **touchpad:** Windows-style 3 and 4-finger swipes with exclusive grab to eliminate GNOME double-trigger ([8dbc4a6](https://github.com/Aries-Surya/knobu/commit/8dbc4a6db8931422f0ee64bb6a588761432653eb))


### Bug Fixes

* **input:** unify keyboard grabbing with hotkeys and fix notification/timing ([a4a2685](https://github.com/Aries-Surya/knobu/commit/a4a268583c2f75c48a4899a9b8dcd1f77e0226a2))
* **ui:** escape pango ampersands, import cairo for drawing areas, and support search kwargs ([3906357](https://github.com/Aries-Surya/knobu/commit/39063577da04e9e5b40f8c2d152f90d7cebea1da))
* **ui:** resolve KeyError in module_summary for dashboard card rendering ([f6df0f4](https://github.com/Aries-Surya/knobu/commit/f6df0f47e5dcfd54054d97e55e73ea5828c0d06d))


### Documentation

* document Windows Precision touchpad gestures and bypass system in README and CHANGELOG ([5f7cd5e](https://github.com/Aries-Surya/knobu/commit/5f7cd5edb59e45d4662df04332a1be089a9e4e56))

## [0.3.0](https://github.com/Aries-Surya/knobu/compare/v0.2.0...v0.3.0) (2026-11-14)


### Features

* **commandbar:** add Command Bar (PowerToys Run for Linux) with Alt+Space exclusive grab and OS override ([d60867a](https://github.com/Aries-Surya/knobu/commit/d60867a76dd735149051120db6a5df25e224c208))
* **commandbar:** add PowerToys Run Command Bar for Linux with converter, emoji, window switcher, and toggle ([9a4720b](https://github.com/Aries-Surya/knobu/commit/9a4720b5ed0bc1e6b262a98ba64d0354b33068a7))
* **commandbar:** add unit converter, emoji picker, window switcher, and toggle-to-close ([ac1fd7b](https://github.com/Aries-Surya/knobu/commit/ac1fd7b825fb2e0e9f78393d23fb224285081cb0))


### Documentation

* add release download and upgrade runbook to README and CICD documentation ([49f0286](https://github.com/Aries-Surya/knobu/commit/49f0286e2d144eb503b14c880777a329a7a97595))
* document Clipboard History module in README and Debian man/control files ([45b900c](https://github.com/Aries-Surya/knobu/commit/45b900c10e80d4a46be1f20d23548c0cf1358274))
* **legal:** preserve original author copyright attribution under GPL-3.0 ([db1324c](https://github.com/Aries-Surya/knobu/commit/db1324c966e3e1b9854ae135291deb4bfa8020a0))

## [0.2.0](https://github.com/Aries-Surya/knobu/compare/v0.1.0...v0.2.0) (2026-11-13)


### Features

* **ci:** robust Debian packaging, automated Release Please pipeline, and workflow documentation ([7563081](https://github.com/Aries-Surya/knobu/commit/7563081e75606bc72e6d8bd7ad88e27d59b58d8c))
* **clipboard:** add clipboard history module, copied image support, settings dashboard, and CI/CD release pipeline ([531a47e](https://github.com/Aries-Surya/knobu/commit/531a47e12bde110f550591554b46e26218c536cb))
* **clipboard:** add exclusive shortcut grab to swallow Super+V pass-through ([828ef2e](https://github.com/Aries-Surya/knobu/commit/828ef2eb8792e1369e600907e94711339b3e61fa))


### Bug Fixes

* **ci:** rename job to 'Lint, Test, & Build' to match branch protection check ([51d2d6c](https://github.com/Aries-Surya/knobu/commit/51d2d6c887c34932ca8741cf4311f03439bffd00))
* **ci:** stage deb packages in workspace dist/ directory for upload-artifact ([6f7ea85](https://github.com/Aries-Surya/knobu/commit/6f7ea85e889e0156a56270fa028fd59c1373574a))
* **hotkeys:** query live device active_keys directly to eliminate ghost modifier paste ([4497466](https://github.com/Aries-Surya/knobu/commit/44974663d0ebbd39a5527d2244cd93aa81e1fea6))
* **ui:** escape markup entities in preferences group and format unassigned hotkeys ([55b9e65](https://github.com/Aries-Surya/knobu/commit/55b9e650373dd7f7e677b17ce84f405733b24259))


### Documentation

* add newline to CICD documentation ([2acd1e7](https://github.com/Aries-Surya/knobu/commit/2acd1e78c15503e4f6d14b5795ffea2f746cdacc))
* **ci:** document complete CI/CD release workflow and add archify diagram ([d20b828](https://github.com/Aries-Surya/knobu/commit/d20b828ec186a00c33df4bcaf7a24f46fc1a0813))

## [Unreleased]

### Added
- **Power Tools & System Maintenance (`src/knobu/modules/powertools/`, `src/knobu/ui/cleaning.py`)**:
  - **Port Manager**: Inspect active listening TCP/UDP ports via `ss -tulpn` with search filtering and 1-click process termination (plus `knobu ports` CLI).
  - **Hardware Cleaning Mode (`Super+Alt+K` / `knobu cleaning-mode`)**: Fullscreen overlay that grabs physical keyboards, mice, and touchpads via `evdev` for safe wiping, featuring an auto-unlock countdown timer and 2-second `Esc` hold exit.
  - **System Cleaner & Package Uninstaller**: Safe cleanup of user caches (`~/.cache`), thumbnail caches, crash dumps (`/var/crash`), and APT package archives (`apt-get clean`), plus searchable manual package uninstallation.
  - **Media Tools (`ffmpeg`)**: Video compression (H.264/AAC MP4), palette-optimized Video-to-GIF conversion, and batch image format conversion (`webp`, `png`, `jpg`, `avif`, `bmp`).

### Added
- **Touchpad Gestures Upgrade (`src/knobu/modules/touchpad/`)**:
  - **Windows Precision Multi-Directional Swipes**: Independent actions for all 4 swipe directions across both 3-finger and 4-finger gestures (8 distinct directional swipe actions plus 3 and 4-finger taps).
  - Supported actions: Smooth Volume Slide, Discrete Volume Step Up/Down (+/-5%), Media Play/Pause, Next Track, Previous Track, Mute/Unmute, Overview/Task View (`Super`), Show Desktop (`Super+D`), Workspace Left/Right/Up/Down, Application Switch (`Alt+Tab`, `Alt+Shift+Tab`), and Knobu Command Bar (`Alt+Space`).
  - **Zero-Conflict OS Grab (`grab_gestures`)**: Claims touchpad hardware dynamically during 3 and 4-finger gestures to prevent GNOME from double-triggering native workspace switching or overview. Ungrabs instantly on finger lift.
  - **Native On-Screen Volume Slider**: Volume adjustments trigger the desktop's native on-screen volume bubble without intrusive notification pop-ups.
- **Global & Module Bypass System (`src/knobu/cli.py`, `src/knobu/daemon.py`)**:
  - Master bypass command `knobu bypass on|off|toggle|status` and Settings UI switch to suspend all hardware grabs and customizations (ideal for gaming and virtual machines).
  - Per-module bypass toggles for Touchpad, Keyboard, and Mouse utilities.
  - Restore OS shortcuts utility `knobu restore-os-shortcuts` for restoring overridden desktop environment shortcuts.
- **Keyboard Manager Utilities (`src/knobu/modules/keyboard/`)**:
  - **Text Snippets Expansion**: Low-latency evdev abbreviation expander replacing triggers (e.g. `;email`, `;date`, `;time`) with full text or dynamic date/time variables (`{date}`, `{time}`, `{datetime}`, `{year}`, `{month}`, `{day}`).
  - **Quit & Close Protection**: Prevents accidental loss of work from `Ctrl+Q` and `Ctrl+W` by requiring hold (0.5s) or double-press confirmation with desktop notifications.
  - **Key Chatter Filter**: Software debouncing for mechanical keyboard switches to filter contact bounce.
- **Mouse Utilities Module (`src/knobu/modules/mouse/`)**:
  - **Independent Wheel Inversion**: Reverse mouse wheel scroll direction without altering touchpad gestures or desktop touchpad settings.
  - **Scroll Speed Multiplier**: Adjust mouse wheel speed multiplier (0.25x to 5.0x).
  - **Hardware Debounce Filter**: Suppress accidental double-clicks caused by worn mouse microswitches within configurable threshold (10ms to 150ms).
  - Dedicated GTK4/Adwaita Mouse Utilities preferences page.
- **Command Bar (PowerToys Run for Linux) (`src/knobu/modules/commandbar/`)**:
  - Instant floating launcher palette summoned via `Alt+Space`, auto-dismissing on focus loss, `Escape`, or pressing `Alt+Space` again to toggle closed.
  - Application search: scans `.desktop` files across system, user, Flatpak, and Snap directories with fuzzy matching and detached launching.
  - Safe Calculator: AST-based mathematical evaluator supporting arithmetic, powers, percentages, functions (`sqrt`, `abs`, `round`, `sin`, `cos`, `tan`, `log`), and constants (`pi`, `e`) with copy-to-clipboard on Enter.
  - Unit & Currency Converter: instant conversion for length, mass, storage, time, speed, volume, temperature, and 35+ currencies (`100 USD in EUR`, `50 miles in km`, `100 C in F`, `16 GB in MB`, `$100 in INR`).
  - Emoji search & picker: prefix with `:` to search and copy emojis directly (e.g., `:fire`, `:rocket`, `:check`).
  - Open windows & tab switcher: prefix with `<` or search open windows/browser tabs to switch focus instantly.
  - Shell / Terminal command execution: prefix `>` runs commands directly in system terminal.
  - Filesystem path navigation: typing `~/` or `/` navigates folders and opens files in default file manager.
  - Web & quick search: direct URL opening and `? <query>` web searches in default browser.
  - System commands: quick shortcuts for lock screen, sleep/suspend, restart, shutdown, and Knobu module launchers.
  - Zero-conflict `Alt+Space` handling: kernel-level exclusive `evdev` grabbing, toggle-to-close dismiss, and automatic OS-level shortcut override for GNOME and KDE window manager shortcuts.
  - Native GTK4/Adwaita Settings Dashboard for provider selection, max results, and manual OS shortcut management.
- **Clipboard History & Manager Module (`src/knobu/modules/clipboard/`)**:
  - Full modular package architecture for clipboard history management and persistent SQLite storage (`~/.local/share/knobu/clipboard.db`).
  - Searchable floating palette summoned with `Super+V` (`Windows+V`), auto-dismissing on click outside or `Escape`.
  - Copied image clip support: automatically captures copied screenshots and PNG graphics (`~/.local/share/knobu/images/`), renders live thumbnails with dimensions in the popup, and restores images on paste.
  - URL tracking parameter sanitizer: automatically strips `utm_*`, `fbclid`, `gclid`, etc., on copy.
  - Passive event-driven capture on `Ctrl+C` and `Ctrl+X` with zero continuous clipboard polling.
  - Trailing whitespace trimmer and password manager secret detection (`x-kde-passwordManagerHint`, KeepassXC).
  - Native GTK4/Adwaita Settings Dashboard for configuring history capacity (10–500 clips), allowed content types, sanitization options, shortcuts, live storage stats, and one-click database cleanup.
  - Official Knobu brand identity with application icon and solid dark theme (no glassy/translucent effects).
  - 12-hour AM/PM time formatting across all time displays.
- **Automated Semantic Release & Packaging Pipeline**:
  - Single-file consolidated GitHub Actions workflow (`.github/workflows/ci.yml`) integrating test suite validation, Google Release Please version bumping, and production Debian package (`.deb`) publishing to GitHub Releases.
  - Release Please configuration (`release-please-config.json` and `.release-please-manifest.json`).
  - Code ownership definition (`.github/CODEOWNERS`).
  - Comprehensive Open Source community standards (`ROADMAP.md`, `CONTRIBUTING.md`, `SECURITY.md`).

## [0.1.0] - 2026-11-03

### Added
- **Touchpad Gestures**: Slide three fingers to smoothly control volume; taps for mute and MPRIS media playback.
- **Keyboard Manager**: Intercept and remap keys and keyboard shortcuts globally via `evdev` and `uinput`.
- **Awake**: Sleep inhibitor keeping system and display awake indefinitely or for set durations (`30m`, `1h30m`).
- **Color Picker**: Global shortcut (`Super+Shift+C`) to sample pixel colors in HEX, RGB, or HSL with KWin magnifier integration.
- **Text Extractor**: Global shortcut (`Alt+Shift+C`) to select a screen area and extract text via Tesseract OCR.
- **Settings App**: Native GTK4 and Libadwaita preferences dashboard.
- **System Service**: Background `systemd --user` service with SIGHUP configuration reload.
