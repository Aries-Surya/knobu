# Changelog

All notable changes to Knobu will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
