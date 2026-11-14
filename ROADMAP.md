# Knobu Development Roadmap

Knobu is evolving into the definitive Linux desktop companion, bringing together the capabilities of **Microsoft PowerToys** and macOS's **Vorssaint** (`vorssaint-utils`) under a native GTK4/Libadwaita interface.

---

## Milestone 1: Top Bar HUD & Status Tray 

*Inspired by Vorssaint Dynamic Island & Menu Bar Status Controller*

- [ ] **Top Bar Dynamic Island**: Floating top-bar capsule that expands for incoming desktop notifications.
- [ ] **D-Bus Notification Monitoring**: Non-intrusive eavesdropping on `org.freedesktop.Notifications`.
- [ ] **Notification Drawer**: Expandable card view of recent notifications with timestamps, open actions, and "Clear All".
- [ ] **Top Bar Status Tray**: Native `org.kde.StatusNotifierItem` provider for GNOME AppIndicator and KDE Plasma tray with dynamic unread and Awake badges.
- [ ] **CI/CD Pipeline**: Automated Debian package build (`.deb`), automated testing, and GitHub release deployment.

---

## Milestone 2: Per-App Volume Mixer & Sound Suite 🔄

*Inspired by Vorssaint Sound Mixer & PowerToys Video Conference Mute*

- [ ] **Per-App Volume Mixer**:
  - Independent volume sliders for each active application stream via PipeWire / PulseAudio (`pactl` JSON / `wpctl`).
  - Audio boost past 100% (up to 150%) per application.
  - Quick mute and output channel routing per app.
- [ ] **Global Microphone Mute**:
  - Global shortcut (e.g., `Super+Shift+M`) to toggle default input source mute.
  - Visual OSD and Top Bar indicator badge showing live mic status.
- [ ] **Output Device Switcher**:
  - Hotkey and tray shortcut to toggle between headphones and speakers.
  - Auto-lower volume on headphone disconnect to protect hearing.
- [ ] **Music App Blocker**:
  - Prevent unintended media player launches upon Bluetooth headphone reconnect.

---

## Milestone 3: Clipboard History, Paste Plain & URL Cleaner ✅

*Inspired by Vorssaint Clipboard & PowerToys Clipboard History*

- [X] **Clipboard History (`Super+V`)**:
  - Background monitor tracking copied text with SQLite persistence (`~/.local/share/knobu/clipboard.db`).
  - Searchable GTK4 floating popup with pinned favorites, preview, delete, and clear.
  - Auto-paste into previous window via `uinput` virtual keystroke.
- [X] **Paste as Plain Text (`Super+Shift+V`)**:
  - Strips rich text formatting, fonts, and HTML tags before pasting clean text.
- [X] **URL Cleaner**:
  - Automatically strips tracking parameters (`utm_*`, `fbclid`, `gclid`, `mc_eid`, `si`, `igshid`) on copy.

---

## Milestone 4: Command Bar (PowerToys Run for Linux) ✅

*Inspired by Vorssaint Command Bar & PowerToys Run*

- [X] **Centered Search Omnibar (`Alt+Space`)**:
  - Fast desktop application launcher scanning `.desktop` files with fuzzy matching.
  - Safe mathematical expression calculator (AST-based arithmetic, powers, percentages, math functions, constants).
  - Direct shell command executor (prefixed with `>`).
  - Filesystem path navigator (typing `~/` or `/` navigates folders and opens files).
  - Web & quick search (direct URLs and `? <query>` web searches in default browser).
  - Quick system commands (Lock, Sleep, Restart, Shutdown, and Knobu module launchers).
  - Zero-conflict `Alt+Space` handling: kernel-level exclusive `evdev` grabbing and automatic OS-level shortcut override for GNOME and KDE window manager shortcuts.
  - Native GTK4/Adwaita Settings Dashboard for provider selection, max results, and manual OS shortcut management.
- [X] Unit and currency converter (e.g., `100 USD in EUR`, `50 miles in km`, `100 C in F`, `16 GB in MB`).
- [X] Emoji search and picker (prefixed with `:`, e.g., `:fire`, `:rocket`, `:check`).
- [X] Open windows switcher and tab finder (prefixed with `<`, e.g., `< code`, `< browser`).
- [X] Instant toggle-to-close behavior: pressing `Alt+Space` while open immediately dismisses the launcher.

---

## Milestone 5: Window Snapping & Layouts (FancyZones) 🪟

*Inspired by Vorssaint WindowLayout & PowerToys FancyZones*

- [ ] **Custom Zone Grids**:
  - 2-column, 3-column, 2x2 grid, and priority-center layout presets.
  - KWin D-Bus integration for KDE Plasma and Mutter/XDG integration for GNOME.
- [ ] **Zone Snapping**:
  - Snap active windows into defined zones using modifier keys + drag or keyboard shortcuts (`Super+Arrow`).
  - Multi-monitor window movement and workspace preservation.
- [ ] **Window Maximize**:
  - Maximize window to fill screen without fullscreen workspace displacement.

---

## Milestone 6: Keyboard & Mouse Utilities ⌨️🖱️

*Inspired by Vorssaint Keyboard & Mouse Tools*

- [ ] **Text Snippets Expansion**:
  - Evdev abbreviation engine expanding triggers (e.g., `;email` -> full email address) with dynamic date/time variables.
- [ ] **Quit & Close Protection**:
  - Require hold (0.5s) or double-press for `Ctrl+Q` or `Ctrl+W` in designated apps to prevent accidental loss of work.
- [ ] **Hardware Debounce Filter**:
  - Software debouncing for worn mouse switches (double-click filtering) and key chatter.
- [ ] **Smooth & Independent Scrolling**:
  - Per-device scroll direction inversion (invert mouse wheel independently of touchpad).
  - Smooth scroll acceleration curve adjustments.

---

## Milestone 7: System Monitor & Hardware Alerts 📊

*Inspired by Vorssaint System Monitor & Menu Bar Readouts*

- [ ] **Hardware Resource Monitoring**:
  - Real-time CPU usage (per-core), memory pressure, GPU load, network bandwidth, and thermal sensors.
- [ ] **Top Bar Metrics**:
  - Optional compact CPU, RAM, or network speed readouts directly in the top panel or tray.
- [ ] **Health Alerts**:
  - Configurable notifications for sustained CPU load (>90%), memory pressure (>95%), and low battery (<15%).

---

## Milestone 8: Everyday Power Tools & System Maintenance 🛠️

*Inspired by Vorssaint Cleaner, Port Manager & Media Tools*

- [ ] **Port Manager**:
  - Inspect listening TCP/UDP ports (`ss -tulpn`) with 1-click process termination.
- [ ] **Cleaning Mode**:
  - Fullscreen lock overlay that disables all keyboard and mouse inputs to allow wiping hardware safely.
- [ ] **Cleaner & Uninstaller**:
  - Safe cleanup of user caches (`~/.cache`), crash dumps, and package manager residue (`apt clean`).
- [ ] **Media Tools**:
  - Quick local video compression, GIF creation, and batch image format conversion via `ffmpeg`.
