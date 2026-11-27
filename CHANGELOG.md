# Changelog

All notable changes to Knobu will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1](https://github.com/Aries-Surya/knobu/compare/v0.5.0...v0.5.1) (2026-11-27)


### Bug Fixes

* **ci:** remove broken preinstalled microsoft apt sources before apt-get update ([fc33844](https://github.com/Aries-Surya/knobu/commit/fc338443342f6fc335b33f3c2027d653ea982a14))
* **ci:** remove broken preinstalled microsoft apt sources before apt-get update ([8b9d3ee](https://github.com/Aries-Surya/knobu/commit/8b9d3ee4e67f67420125da84ac8f0b73ad32a35b))

## [0.5.0](https://github.com/Aries-Surya/knobu/compare/v0.4.0...v0.5.0) (2026-11-26)


### Features

* Complete Knobu PowerToys & DevOps Suite (Milestones 1, 2, 5, 7, 8, 9, 10, 11, 12) ([f4eecfe](https://github.com/Aries-Surya/knobu/commit/f4eecfece45aa33f3decec4eb637232e8ad06835))
* **config:** add JSON backup and restore via CLI and General settings UI ([30d6e2a](https://github.com/Aries-Surya/knobu/commit/30d6e2a9c419271935d6c1bfbe001bde977c27de))
* **devops:** create separate DevOps on Cloud category with local Cron Jobs manager ([74b80b5](https://github.com/Aries-Surya/knobu/commit/74b80b5b29b64040e7e09cd36d7a83e020cf7ff9))
* **devops:** implement Milestone 10 Cloud, Networking & AWS DevOps toolkit ([b23dbd6](https://github.com/Aries-Surya/knobu/commit/b23dbd6b585554a10bbebbc9c298cc79a2873960))
* implement Milestone 11 (Automations) and Milestone 12 (Extended PowerToys) ([ff53f88](https://github.com/Aries-Surya/knobu/commit/ff53f8804ce201d227523b3d8aba8d183fe1f63f))
* implement Milestone 2 (Sound Suite), Milestone 5 (Window Manager), and Milestone 7 (System Monitor) ([cb6a286](https://github.com/Aries-Surya/knobu/commit/cb6a2866d3f05ea1afa8ee534f7bf9baeaa66d3b))
* **powertools:** add Milestone 8 Port Manager, Cleaning Mode, Cleaner & Uninstaller, and FFmpeg Media Tools ([98a4f9a](https://github.com/Aries-Surya/knobu/commit/98a4f9ab3a5ee937a9b2bd9dec2958e4c07a9a1c))
* **powertools:** implement Milestone 9 EnvVars, Hosts Editor, Screen Ruler, File Locksmith, Image Resizer, and Find My Mouse ([720c4f3](https://github.com/Aries-Surya/knobu/commit/720c4f3424b4957cb91a1e0ef434985e127cbad8))
* **powertools:** support APT, Snap, Flatpak, Brew, Pipx, NPM, and Cargo in Package Uninstaller ([f3a5ed9](https://github.com/Aries-Surya/knobu/commit/f3a5ed98087b962791400e28c65597a9d64ef9d5))
* **tray:** add Milestone 1 Top Notification Tray with live Private/Public IP, AWS Profile switcher & Notification HUD ([3681425](https://github.com/Aries-Surya/knobu/commit/3681425ec12fc4cdf6b215f8f5f82f21e28dc48f))
* **tray:** inline IP refresh-and-copy actions without separate bottom refresh row ([d95d015](https://github.com/Aries-Surya/knobu/commit/d95d01592b4d009074ec9c52388e41ac7b510298))
* **tray:** separate copy and refresh IP actions and add VPN IP/service detection ([e5a9a7d](https://github.com/Aries-Surya/knobu/commit/e5a9a7d34767e8d3393a52c1a41b7e164b7f116d))


### Bug Fixes

* **ci:** handle headless runners in UI page tests and fix mock patch import ([1392d79](https://github.com/Aries-Surya/knobu/commit/1392d7997553ceb5cac4b9fd0cab44224a582d3e))
* **ci:** install python3-gi-cairo in CI and Build-Depends ([9e57b11](https://github.com/Aries-Surya/knobu/commit/9e57b1105adf3aa86770a27a7ba719fce58a6499))
* resolve circular imports, missing osd.show, zoomit capture_screen callback, and python3-gi-cairo dep ([0c74996](https://github.com/Aries-Surya/knobu/commit/0c74996a87d293fbe29caf3fca7864d655bd8c96))
* **tray:** return GLib.Variant tuple in DBusMenu GetLayout without recursive unpack ([aa4db7a](https://github.com/Aries-Surya/knobu/commit/aa4db7a3d305dd924e1093dafff33f532126334f))
* **tray:** stabilize dbusmenu IDs, fix circular import, and keep tray alive across config reloads ([d833a3a](https://github.com/Aries-Surya/knobu/commit/d833a3a3250c34475cc1d76fd4da760e1f920ed5))
* **tray:** use symbolic icons without emojis and auto-refresh on menu open ([a3f2c13](https://github.com/Aries-Surya/knobu/commit/a3f2c13ba9916b1d730852dc4abca224b46a2cbe))
* **ui:** remove unescaped ampersand in Public IP subtitle ([68c5fd7](https://github.com/Aries-Surya/knobu/commit/68c5fd798f05cd00121aaddaa57ff3bb4421df89))
* **windows:** use valid focus-windows-symbolic icon for Window Manager ([902cc9f](https://github.com/Aries-Surya/knobu/commit/902cc9f3d6c7c9086bc9494cd35a34802d0d6538))


### Documentation

* add comprehensive end-to-end user manual ([7a25f90](https://github.com/Aries-Surya/knobu/commit/7a25f90a67c155a71b227c565ac07328bdd75881))
* sync ROADMAP, README, CHANGELOG, and man pages with all completed milestones ([aeba61f](https://github.com/Aries-Surya/knobu/commit/aeba61f6e73a9efbdf95397667f468f159a5de23))

## [0.5.0] (2026-11-26)

### Features

* **sound:** implement Per-App Volume Mixer, up to 150% volume boost, Super+Shift+A global mic mute, and Super+Shift+O output device switcher
* **windows:** implement Always on Top (`Super+Ctrl+T`), FancyZones grid layouts (`2col`, `3col`, `2x2`, `priority`, `left_main`), layout overlay (`knobu fancyzones`), and keyboard zone snapping
* **sysmon:** real-time hardware resource monitoring (CPU, RAM, network, thermal, battery) and high-load/low-battery health alerts
* **devops:** dedicated DevOps on Cloud category with local Cron Jobs manager, CIDR subnet calculator, DNS lookup, SSL certificate inspector, active AWS Caller Identity readout, and Docker containers status
* **automation:** rule-based automation engine ("When [Trigger] -> If [Condition] -> Then [Action]") with Wi-Fi/battery/schedule triggers and execution history logging
* **powertoys:** extended PowerToys suite with ZoomIt screen annotation overlay, interactive Shortcut Guide (`Super+Shift+?`), Quick Accent picker, Workspaces Launcher, Light Switch auto-theme, and Advanced Paste transforms in Clipboard History
* **config:** add JSON configuration backup and restore via CLI (`knobu backup` / `knobu restore`) and Settings UI

### Bug Fixes

* **ci:** handle headless test environments gracefully in UI page tests when no display server is available
* **tray:** replace emojis with standard symbolic icons and add auto-refresh on menu opening
* **windows:** replace missing `focus-windows` icon with valid standard `focus-windows-symbolic` icon

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
- **Top Bar Status Tray, IP/AWS Readout & Mac-Style Notifications (`src/knobu/system/tray.py`, `src/knobu/modules/notifications/`, `src/knobu/ui/hud.py`)**:
  - Native `org.kde.StatusNotifierItem` + `com.canonical.dbusmenu` tray icon compatible with Ubuntu GNOME AppIndicator and KDE Plasma 6.
  - Live tray dropdown displaying current Wi-Fi/Ethernet/VPN connection, **Private IP**, **Public IP** (1-click copy + refresh), **Active AWS CLI profile** quick-switcher, Master Bypass toggle, Awake presets, Do Not Disturb, and Quick Tool launchers.
  - Passive D-Bus `BecomeMonitor` listener capturing desktop notifications into a Mac-style Notification Center drawer (`knobu notifications`) and optional floating Dynamic Island HUD capsule.
- **Power Tools & System Maintenance (`src/knobu/modules/powertools/`, `src/knobu/ui/cleaning.py`)**:
  - **Port Manager**: Inspect active listening TCP/UDP ports via `ss -tulpn` with search filtering and 1-click process termination (plus `knobu ports` CLI).
  - **Hardware Cleaning Mode (`Super+Alt+K` / `knobu cleaning-mode`)**: Fullscreen overlay that grabs physical keyboards, mice, and touchpads via `evdev` for safe wiping, featuring an auto-unlock countdown timer and 2-second `Esc` hold exit.
  - **System Cleaner & Package Uninstaller**: Safe cleanup of user caches (`~/.cache`), thumbnail caches, crash dumps (`/var/crash`), and APT package archives (`apt-get clean`), plus searchable multi-source package uninstallation across APT, Snap, Flatpak, Brew, Pipx, NPM, and Cargo.
  - **Media Tools (`ffmpeg`)**: Video compression (H.264/AAC MP4), palette-optimized Video-to-GIF conversion, batch image format conversion (`webp`, `png`, `jpg`, `avif`, `bmp`), and batch image resize presets.
  - **Environment Variables Manager**: Manage `~/.config/environment.d/90-knobu.conf` with live `systemctl --user set-environment` sync, enable/disable toggles, and read-only session inspector.
  - **Hosts File Editor**: Visual `/etc/hosts` rule manager with IP/domain validation, enable/disable toggles, automatic backup, and `pkexec` save.
  - **Screen Ruler & File Locksmith**: On-screen pixel measurement tool (`Super+Shift+M` / `knobu screen-ruler`) with clipboard copy, and `/proc/*/fd` open-handle inspector with 1-click process termination.
  - **Mouse Pointer Locator (`Super+Alt+F` / Shake)**: Find My Mouse spotlight overlay (`knobu find-mouse`) with rapid mouse-shake detection and GNOME `locate-pointer` sync.

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
