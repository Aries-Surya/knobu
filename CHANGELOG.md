# Changelog

All notable changes to Knobu will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-13

### Added
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
