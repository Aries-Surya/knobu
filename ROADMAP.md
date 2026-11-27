# Knobu Development Roadmap

Knobu is evolving into the definitive Linux desktop companion, bringing together the capabilities of **Microsoft PowerToys** and macOS's **Vorssaint** (`vorssaint-utils`) under a native GTK4/Libadwaita interface.

---

## Milestone 1: Top Bar HUD, Notifications & Status Tray 🔔 ✅

*Inspired by Vorssaint Dynamic Island & Menu Bar Status Controller*

- [X] **Top Bar Status Tray & Configuration Dropdown**:
  - Native `org.kde.StatusNotifierItem` + `com.canonical.dbusmenu` provider over `Gio.DBus` (works on Ubuntu GNOME AppIndicator and KDE Plasma tray with zero extra dependencies).
  - **Live Network & Cloud Status in Tray**: Displays active connection name (Wi-Fi SSID / Ethernet / VPN), **Private IP**, **Public IP** (1-click copy + auto-refresh), and currently active **AWS CLI profile + region** with a quick-switch submenu.
  - Opens a live configuration dropdown with service status, Master Bypass toggle, Awake presets, Cleaning Mode trigger, direct launchers (Command Bar, Clipboard, Screen Ruler, Always on Top, Power Tools), recent notifications, and Open Settings / Reload.
- [X] **Mac-Style Notification HUD & Dynamic Island**:
  - Non-intrusive D-Bus eavesdropping on `org.freedesktop.Notifications` to capture incoming desktop notifications.
  - Compact floating top-bar notification capsule + expandable **Notification Drawer** (`knobu notifications`) with timestamps, app icon, Do Not Disturb toggle, and "Clear All".
- [X] **CI/CD Pipeline**: Automated Debian package build (`.deb`), automated testing, and GitHub release deployment.

---

## Milestone 2: Per-App Volume Mixer & Sound Suite 🔄 ✅

*Inspired by Vorssaint Sound Mixer & PowerToys Video Conference Mute*

- [X] **Per-App Volume Mixer**:
  - Independent volume sliders for each active application stream via PipeWire (`wpctl`).
  - Audio boost past 100% (up to 150%) per application.
  - Quick mute per app (`knobu streams` + Sound Suite UI).
- [X] **Global Microphone Mute**:
  - Global shortcut (`Super+Shift+A`) to toggle default input source mute (`knobu mic-mute`).
  - Visual OSD and live mic status.
- [X] **Output Device Switcher**:
  - Hotkey (`Super+Shift+O`) and CLI (`knobu audio-switch`) to cycle output devices.
  - Auto-lower speaker volume on headphone disconnect to protect hearing.
- [X] **Music App Blocker**:
  - Configurable setting to prevent unintended media player launches on Bluetooth reconnect.

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

## Milestone 5: Window Management — FancyZones & Always on Top 🪟 ✅

*Inspired by Vorssaint WindowLayout, PowerToys FancyZones & PowerToys Always on Top*

- [X] **Unified Desktop Window Bridge**:
  - KWin D-Bus (`qdbus`) for KDE Plasma and `wmctrl` / EWMH backend for X11/XWayland (`knobu always-on-top`, `knobu snap`).
- [X] **Always on Top (`Super+Ctrl+T`)**:
  - Pin or unpin the active window above all other windows (`toggle,above`) from a global `evdev` shortcut with excluded-apps list and OSD feedback.
- [X] **Custom Zone Grids (FancyZones)**:
  - 2-column, 3-column, 2x2 grid, priority-grid, and left-main layouts with configurable zone padding/gaps.
  - Interactive visual Layout Editor overlay (`Super+Shift+Grave`, `knobu fancyzones`).
- [X] **Zone Snapping**:
  - Snap active windows into defined zones via keyboard shortcuts (`Super+Ctrl+Left/Right`) or clicking zones in the overlay.
- [X] **Window Maximize**:
  - Maximize window (`Super+Ctrl+Up`) to fill active screen area cleanly without fullscreen displacement.

---

## Milestone 6: Keyboard & Mouse Utilities ⌨️🖱️ ✅

*Inspired by Vorssaint Keyboard & Mouse Tools*

- [X] **Text Snippets Expansion**:
  - Evdev abbreviation engine expanding triggers (e.g., `;email` -> full email address) with dynamic date/time variables (`{date}`, `{time}`, `{datetime}`, `{year}`, `{month}`, `{day}`).
- [X] **Quit & Close Protection**:
  - Require hold (0.5s) or double-press for `Ctrl+Q` or `Ctrl+W` in designated apps to prevent accidental loss of work.
- [X] **Hardware Debounce Filter**:
  - Software debouncing for worn mouse switches (double-click filtering) and mechanical key chatter.
- [X] **Smooth & Independent Scrolling**:
  - Per-device scroll direction inversion (invert mouse wheel independently of touchpad).
  - Smooth scroll acceleration and speed multiplier adjustments.

---

## Milestone 7: System Monitor & Hardware Alerts 📊 ✅

*Inspired by Vorssaint System Monitor & Menu Bar Readouts*

- [X] **Hardware Resource Monitoring**:
  - Real-time CPU usage (overall & per-core), memory pressure, network bandwidth, battery state, and thermal sensors (`knobu sysmon` + System Monitor UI).
- [X] **Top Bar Metrics**:
  - Optional compact RAM metric readout directly in the top notification tray header.
- [X] **Health Alerts**:
  - Configurable notifications for sustained CPU load (>90%), memory pressure (>95%), and low battery (<15%) with alert cooldown.

---

## Milestone 8: Everyday Power Tools & System Maintenance 🛠️ ✅

*Inspired by Vorssaint Cleaner, Port Manager & Media Tools*

- [X] **Port Manager**:
  - Inspect listening TCP/UDP ports (`ss -tulpn`) with 1-click process termination.
- [X] **Cleaning Mode**:
  - Fullscreen lock overlay that disables all keyboard and mouse inputs to allow wiping hardware safely.
- [X] **Cleaner & Uninstaller**:
  - Safe cleanup of user caches (`~/.cache`), crash dumps, and package manager residue (`apt clean`).
- [X] **Media Tools**:
  - Quick local video compression, GIF creation, and batch image format conversion via `ffmpeg`.

---

## Milestone 9: Developer PowerToys & Pointer Utilities 🎯 ✅

*Inspired by Microsoft PowerToys Environment Variables, Mouse Utilities, Hosts File Editor, Screen Ruler & File Locksmith*

- [X] **Environment Variables Manager**:
  - Visual editor for user environment variables persisted via XDG/systemd (`~/.config/environment.d/90-knobu.conf`) and synced live into active Wayland/X11 sessions (`systemctl --user set-environment` / `dbus-update-activation-environment`).
  - Toggleable variable profiles, live read-only view of inherited System variables, and `PATH` segment helpers.
- [X] **Mouse Highlighter & Find My Mouse**:
  - **Find My Mouse (`Super+Alt+F` / Shake)**: Shake mouse or trigger spotlight overlay (`knobu find-mouse`) plus synced GNOME `locate-pointer` Ctrl locator ring.
- [X] **Hosts File Editor**:
  - Safe visual `/etc/hosts` editor to add, filter, and toggle domain/IP entries on or off, saving via `pkexec` with automatic backup.
- [X] **Screen Ruler & File Locksmith**:
  - **Screen Ruler (`Super+Shift+M`)**: Capture silent screenshot (`capture.py`) and measure pixel distances, spacing guides, and bounding boxes with copy-to-clipboard.
  - **File Locksmith**: Inspect processes holding open file descriptors on any chosen file or directory (`/proc/*/fd`) with 1-click process termination.
  - **Image Resizer**: Batch scale presets (`Small`, `Medium`, `Large`, `50%`) integrated into Media Tools.

---

## Milestone 10: Cloud, Networking & AWS DevOps Toolkit ☁️🌐 ✅

*Tailored for Cloud & DevOps Engineers (AWS CLI, Network Diagnostics, Docker & Kubernetes Contexts)*

- [X] **Network & IP Inspector**:
  - Live detection of active Wi-Fi SSID / Ethernet / VPN (`nmcli` + `ip -j`), Private IPv4/IPv6, Gateway, and cached Public IP (with tray readout, auto-refresh on menu open, and discrete 1-click copy).
- [X] **In-App Networking Diagnostics**:
  - **DNS Lookup**: Query `A`, `AAAA`, `CNAME`, `MX`, `TXT`, `NS` records via `dig` (and socket fallback) with custom resolver selector.
  - **SSL/TLS Certificate Inspector**: Check expiry countdown days, issuer, and SANs for any `host:port` via native SSL/socket inspection.
  - **TCP Port Ping & HTTP Timing**: Check `host:port` reachability latency, HTTP status code and latency probes, and pure-Python CIDR subnet calculator (`netmask`, `broadcast`, `usable hosts`).
- [X] **AWS CLI Configuration & Active Profile Manager**:
  - Parse `~/.aws/config` & `~/.aws/credentials` (masked secrets), display the **currently active `AWS_PROFILE` & region**, and inspect SSO/role configuration.
  - **1-Click Profile Switcher** (Settings UI + Tray Menu): updates `AWS_PROFILE` & `AWS_DEFAULT_REGION` via `~/.config/environment.d/90-knobu.conf` + `systemctl --user set-environment`.
  - **Live Identity & SSO**: Verify credentials via `aws sts get-caller-identity` (Account ID & ARN) directly in UI and via `knobu aws-whoami`.
- [X] **Container & Infra Context Quick View**:
  - View/switch active `kubectl` context (`kubectl config current-context`) and view running `docker ps` containers with CLI inspection (`knobu containers`).

---

## Milestone 11: Rule-Based Automation Engine (Mac Shortcuts Style) ⚡ ✅

*Inspired by macOS Shortcuts, Automator & AppleScript Triggers ("When X happens -> Do Y")*

- [X] **Trigger Listeners (Daemon-Integrated)**:
  - Network/Wi-Fi SSID change, Power/Battery threshold, and Cron/Time schedules (`knobu automations`, `knobu run-automation`).
- [X] **Conditional Actions**:
  - Chain actions: switch theme (light/dark), toggle Awake, toggle Master Bypass (gaming), run shell script, or send notification.
- [X] **Automation Builder UI**:
  - Visual "When [Trigger] -> If [Condition] -> Then [Action]" rule editor with enable/disable switches, execution history log, and "Run Now" test button (`knobu automations`).

---

## Milestone 12: Extended Microsoft PowerToys for Linux 🧩 ✅

*Remaining high-value PowerToys utilities adapted cleanly for Wayland & X11*

- [X] **Advanced Paste (Clipboard Transforms)**:
  - Format JSON, strip formatting, Base64 encode/decode, URL decode, and convert casing (`snake_case` / `camelCase` / `UPPER`) directly inside `Super+V` Clipboard History.
- [X] **Light Switch (Auto Dark/Light Theme)**:
  - Switch GNOME (`color-scheme`) / KDE (`plasma-apply-colorscheme`) theme automatically by schedule or sunrise/sunset (`knobu theme`).
- [X] **Shortcut Guide (`Super+Shift+?`)**:
  - Interactive cheat-sheet overlay listing all configured Knobu and desktop shortcuts (`knobu shortcut-guide`).
- [X] **Workspaces Launcher**:
  - Save named app + layout groups ("Dev Ops", "Review") and launch them together in one click (`knobu workspace`).
- [X] **ZoomIt & Quick Accent**:
  - Screen freeze-zoom & pen/arrow/box annotation overlay (`knobu zoomit`), plus Quick Accent character picker (`knobu quick-accent`).

---

## Milestone 13: Cloud Sync, System Tools & Wayland Window Bridge 🚀 (In Progress)

*Architecture restructuring, enterprise cloud backup, native Wayland window controls, and static docs portal*

- [ ] **Architecture Reorganization**:
  - **DevOps on Cloud**: Relocate Port Manager (`knobu ports`) and Hosts File Editor (`/etc/hosts`) into DevOps on Cloud.
  - **Cloud Integrations**: Add active AWS CLI profile switcher and Kubernetes context switcher (`kubectl config use-context`) directly in UI and CLI.
  - **System Tools (New Category)**: Separate System Tools from Power Tools, housing System Cleaner (`~/.cache`, crash dumps, apt), Package Uninstaller, Environment Variables Manager, and File Locksmith.
  - **Universal Bypass Mode**: Add per-feature bypass switches across every module in UI and config for seamless OS troubleshooting.
- [ ] **Native Wayland Window Management & Pointer Fixes**:
  - **Wayland Window Bridge**: Bundle native GNOME Shell Extension (`knobu-window-bridge@knobu.org`) providing D-Bus controls for Always on Top (`Super+Ctrl+T`), FancyZones window snapping, and clean window maximizing under native Wayland.
  - **Find My Mouse Spotlight Fix**: Replace static screenshot center circles with live dynamic cursor coordinates and native GNOME `locate-pointer` ripple rings.
- [ ] **Automation Engine Expansion & Recommendations**:
  - Expand triggers (Wi-Fi connect/disconnect, VPN, battery thresholds, process launch/exit, screen locks, schedules).
  - Expand conditions (Wi-Fi SSID lists, battery ranges, power sources, running processes, time windows).
  - Predefined Recommendation Templates (DevOps Workday, Gaming Passthrough, Low Battery Saver, Secure Screen Lock).
- [ ] **GitHub Gist Cloud Backup & Synchronization**:
  - Authenticated GitHub Gist cloud backup supporting personal access tokens (PAT).
  - Automated background sync on configuration changes or periodic schedules, plus manual 1-click push/pull sync.
- [ ] **Static Documentation Website (GitHub Pages)**:
  - Complete, self-contained, responsive static documentation site in `docs-site/` ready for self-hosted GitHub Pages deployment.
- [ ] **Comprehensive Issue & Bug Tracking**:
  - Maintain centralized bug tracking in `BUGS.md` with root causes, affected environments, and verification criteria.
