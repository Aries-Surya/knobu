# Changelog

All notable changes to Knobu will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Command Bar (PowerToys Run for Linux) (`src/knobu/modules/commandbar/`)**:
  - Instant floating launcher palette summoned via `Alt+Space`, auto-dismissing on focus loss or `Escape`.
  - Application search: scans `.desktop` files across system, user, Flatpak, and Snap directories with fuzzy matching and detached launching.
  - Safe Calculator: AST-based mathematical evaluator supporting arithmetic, powers, percentages, functions (`sqrt`, `abs`, `round`, `sin`, `cos`, `tan`, `log`), and constants (`pi`, `e`) with copy-to-clipboard on Enter.
  - Shell / Terminal command execution: prefix `>` runs commands directly in system terminal.
  - Filesystem path navigation: typing `~/` or `/` navigates folders and opens files in default file manager.
  - Web & quick search: direct URL opening and `? <query>` web searches in default browser.
  - System commands: quick shortcuts for lock screen, sleep/suspend, restart, shutdown, and Knobu module launchers.
  - Zero-conflict `Alt+Space` handling: kernel-level exclusive `evdev` grabbing and automatic OS-level shortcut override for GNOME and KDE window manager shortcuts.
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
