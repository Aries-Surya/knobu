# Knobu User Manual

Knobu brings PowerToys and macOS-style utilities to Linux desktop environments (Ubuntu GNOME and Kubuntu KDE Plasma) under a native GTK4/Libadwaita interface.

This manual explains how to configure, launch, and operate every module, tool, and shortcut.

---

## Table of Contents

1. [Initial Setup & Requirements](#1-initial-setup--requirements)
2. [Command Bar (PowerToys Run)](#2-command-bar-powertoys-run)
3. [Clipboard History & Advanced Paste](#3-clipboard-history--advanced-paste)
4. [Window Manager (FancyZones & Always on Top)](#4-window-manager-fancyzones--always-on-top)
5. [Sound Suite & Per-App Volume Mixer](#5-sound-suite--per-app-volume-mixer)
6. [Top Bar HUD & Notifications](#6-top-bar-hud--notifications)
7. [Touchpad Gestures](#7-touchpad-gestures)
8. [Keyboard Manager](#8-keyboard-manager)
9. [Mouse Utilities](#9-mouse-utilities)
10. [DevOps & Cloud Toolkit](#10-devops--cloud-toolkit)
11. [Rule-Based Automations Engine](#11-rule-based-automations-engine)
12. [Extended PowerTools (ZoomIt, Ruler, Cleaner, Hosts, Ports)](#12-extended-powertools)
13. [Awake, Color Picker & Text Extractor](#13-awake-color-picker--text-extractor)
14. [Backup & Restore](#14-backup--restore)
15. [CLI Reference & Troubleshooting](#15-cli-reference--troubleshooting)

---

## 1. Initial Setup & Requirements

### Hardware Input Permissions
Knobu reads hardware touchpads and keyboards directly via `/dev/input/` and `evdev` to provide kernel-level shortcuts without desktop conflicts.

Add your user account to the `input` group:
```bash
sudo usermod -aG input $USER
```
*Note: Log out and log back in for group membership to take effect.*

### Virtual Keyboard Creation (uinput)
For keystroke remapping and auto-paste, create a virtual `uinput` device rule:
```bash
sudo cp /usr/share/knobu/data/70-knobu-uinput.rules /etc/udev/rules.d/ 2>/dev/null || sudo cp data/70-knobu-uinput.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger --name-match=uinput
```

### Background Service
Start the user daemon at login:
```bash
knobu enable
knobu status
```

---

## 2. Command Bar (PowerToys Run)

Summon the centered omnibar with **`Alt+Space`**. Pressing **`Alt+Space`** again or pressing **`Escape`** closes it.

### Query Syntax
- **Application Search**: Type any app name (`firefox`, `code`, `terminal`). Press `Enter` to launch.
- **Calculator**: Type mathematical expressions directly:
  - `(15 * 4) / 2`
  - `sqrt(144) + 12`
  - `20% of 150`
  - `sin(pi / 2)`
  - Press `Enter` to copy the result to clipboard.
- **Unit & Currency Converter**:
  - `100 USD in EUR` or `$50 in INR`
  - `50 miles in km`
  - `100 C in F`
  - `16 GB in MB`
- **Shell Runner**: Prefix with `>` to run terminal commands:
  - `> htop`
  - `> ping 8.8.8.8`
- **Path Explorer**: Type `~/` or `/` to explore directories and open files.
- **Emoji Picker**: Prefix with `:`:
  - `:fire`, `:rocket`, `:check`, `:coffee`
- **Window Switcher**: Prefix with `<`:
  - `< visual studio code` switches active focus to that window.
- **Web Search**: Prefix with `? <query>` or enter full URLs (`https://...`).

---

## 3. Clipboard History & Advanced Paste

Summon the clipboard palette with **`Super+V`**.

### Features
1. **Search & Pinning**: Filter past clips in the search bar. Click the star icon to pin clips permanently so capacity sweeps do not evict them.
2. **Image Clips**: Captured screenshots and copied image buffers render live thumbnail dimensions directly in the list.
3. **Tracking URL Cleaner**: Strips tracking query parameters (`utm_*`, `fbclid`, `gclid`, `si`, etc.) automatically when URLs are copied.
4. **Password Security**: Bypasses clipboard capture when copying passwords from password managers (KeePassXC, 1Password, Bitwarden).
5. **Advanced Paste Transforms**:
   - Right-click any clip in `Super+V` or use the CLI:
   - **Format JSON**: Beautifies raw unformatted JSON strings.
   - **Plain Text (`Super+Shift+V`)**: Strips RTF, styles, and HTML tags.
   - **Case Transforms**: Converts selection to `UPPERCASE`, `lowercase`, `camelCase`, or `snake_case`.
   - **Base64 & URL Decode**: Decodes encoded payloads directly into the paste buffer.

---

## 4. Window Manager (FancyZones & Always on Top)

### Always on Top (`Super+Alt+T`)
- Press **`Super+Alt+T`** or run `knobu always-on-top`.
- Pins the current focused window on top of all other windows.
- Press again to unpin. Configurable excluded applications prevent full-screen games or video players from pinning unintentionally.

### FancyZones (`Super+Shift+Grave`)
- Open the visual layout selector overlay with **`Super+Shift+~`** (or `knobu fancyzones`).
- Choose a grid template:
  - `2col`: Two equal side-by-side columns.
  - `3col`: Three equal vertical columns.
  - `2x2`: 4-quadrant grid.
  - `priority`: Wide center work area with narrow flanking toolbars.
  - `left_main`: Large left primary workspace with two stacked right panes.
- **Keyboard Snapping**:
  - Press **`Super+Alt+Left`** / **`Super+Alt+Right`** or run `knobu snap <zone-index>` to snap the active window into the target zone.
  - Press **`Super+Alt+Up`** to maximize the window to active screen boundaries without full-screen desktop displacement.

---

## 5. Sound Suite & Per-App Volume Mixer

Manage audio output, streams, and inputs directly from the desktop.

### Controls & CLI
- **Per-App Volume Mixer**:
  - Open `knobu` -> **Sound Suite** or run `knobu streams`.
  - Adjust sliders per app stream via PipeWire/WirePlumber.
  - Boost volume up to **150%** for quiet video calls or media.
- **Global Mic Mute (`Super+Shift+A`)**:
  - Press **`Super+Shift+A`** or run `knobu mic-mute`.
  - Mutes or unmutes the default microphone source instantly with visual OSD feedback.
- **Audio Output Switcher (`Super+Shift+O`)**:
  - Press **`Super+Shift+O`** or run `knobu audio-switch`.
  - Cycles audio playback between headphones, external monitors, and built-in speakers.

---

## 6. Top Bar HUD & Notifications

Knobu integrates with system trays via the FreeDesktop StatusNotifierItem standard.

### Tray Menu Status
- **Network Readout**: Displays active Wi-Fi SSID, Ethernet interface, or VPN name.
- **IP Display & 1-Click Copy**: Shows local private IP (`192.168.x.x`) and public WAN IP (`203.0.113.x`). Clicking either copies the address directly to your clipboard.
- **AWS Profile Switcher**: Shows the current active AWS profile and region. Click any profile to switch profiles instantly.
- **Notification Center (`knobu notifications`)**:
  - Mac-style drawer capturing desktop notifications.
  - Filter notifications, toggle Do Not Disturb, or clear logs with one click.

---

## 7. Touchpad Gestures

Zero-conflict precision gesture tracking on Wayland and X11:

| Gesture | Default Action | Optional Configurations |
|---|---|---|
| **3-finger swipe up** | Continuous volume slide up | Volume Slide, Volume Up, Workspace Up, Overview |
| **3-finger swipe down** | Continuous volume slide down | Volume Slide, Volume Down, Workspace Down |
| **3-finger swipe left/right**| Previous / Next audio track | App Switch, Workspace Left/Right |
| **3-finger tap** | Mute / Unmute audio | Play/Pause, Command Bar |
| **4-finger swipe up** | Task Overview (`Super`) | Volume Slide, Workspace Up |
| **4-finger swipe down** | Show Desktop (`Super+D`) | Overview, Minimize All |
| **4-finger tap** | Play / Pause media | Mute, Command Bar |

To temporarily disable gestures while gaming, run `knobu bypass on`.

---

## 8. Keyboard Manager

Remap keys, protect unsaved work, and expand snippets system-wide.

1. **Key Remapping**: Remap physical keys (e.g. `Caps Lock` -> `Ctrl`).
2. **Shortcut Remapping**: Map key combos (e.g. `Super+E` -> `Ctrl+Alt+T`).
3. **Text Snippets Expansion**:
   - Type dynamic abbreviations (e.g. `;email` -> `your.name@example.com`).
   - Dynamic templates supported: `{date}`, `{time}`, `{datetime}`, `{year}`, `{month}`, `{day}`.
4. **Quit & Close Protection**:
   - Requires holding `Ctrl+Q` or `Ctrl+W` for 0.5s or double-pressing in selected apps to prevent accidental window closure.
5. **Key Chatter Filter**:
   - Filters out mechanical keyboard switch bounce within a configurable millisecond window.

---

## 9. Mouse Utilities

- **Independent Wheel Inversion**: Invert mouse scroll direction without affecting touchpad scrolling.
- **Scroll Multiplier**: Speed up or slow down wheel scroll stepping (0.25x to 5.0x).
- **Click Debouncing**: Suppress double-click glitches from failing mouse microswitches.
- **Find My Mouse (`Super+Alt+F` / Mouse Shake)**:
  - Shaking the cursor rapidly or pressing **`Super+Alt+F`** dims the display and draws a bright spotlight around the cursor.

---

## 10. DevOps & Cloud Toolkit

Access cloud, network, and container diagnostics from the Settings app or terminal:

### Commands
- **Subnet Calculator**:
  ```bash
  knobu cidr 192.168.1.0/24
  ```
  Outputs netmask, broadcast address, and total usable hosts.
- **DNS Record Lookup**:
  ```bash
  knobu dns github.com
  ```
  Resolves `A`, `AAAA`, `CNAME`, `MX`, and `TXT` records.
- **SSL Certificate Expiry Checker**:
  ```bash
  knobu ssl-check github.com:443
  ```
  Displays days remaining until expiration, issuing CA, and Subject Alternative Names.
- **AWS Identity Inspector**:
  ```bash
  knobu aws-whoami
  ```
  Runs STS caller identity verification and displays Account ID, ARN, and UserId.
- **Docker Containers**:
  ```bash
  knobu containers
  ```
  Lists active container names, images, status, and port bindings.
- **Cron Jobs Manager**:
  ```bash
  knobu cron
  knobu cron-add "0 2 * * *" "/usr/local/bin/backup.sh"
  ```
  Displays local cron daemon status, user cron jobs, and adds validated cron entries.

---

## 11. Rule-Based Automations Engine

Automate desktop workflows with "When [Trigger] -> If [Condition] -> Then [Action]" triggers.

### Triggers
- **Network**: Wi-Fi SSID connects/disconnects (e.g. entering "Office-5G").
- **Power**: Battery falls below threshold or AC adapter connects/disconnects.
- **Schedule**: Specific time of day or cron intervals.

### Actions
- Toggle Light/Dark system theme.
- Toggle Awake mode.
- Toggle Master Bypass (gaming mode).
- Launch a saved Workspace app group.
- Execute shell scripts or send custom notifications.

### CLI
```bash
knobu automations          # List all configured rules
knobu run-automation <id>  # Test-run a rule manually
```

---

## 12. Extended PowerTools

- **ZoomIt (`knobu zoomit`)**: Freezes the screen for instant magnification, arrow drawings, boxes, and freehand pen markup. Press `Escape` to dismiss.
- **Shortcut Guide (`Super+Shift+?` / `knobu shortcut-guide`)**: Fullscreen visual HUD listing active desktop shortcuts, window controls, and Knobu hotkeys.
- **Quick Accent (`knobu quick-accent`)**: Hold a letter key or run `knobu quick-accent` to open a quick character selection palette for accented glyphs (`é`, `è`, `ê`, `ñ`, `ü`).
- **Screen Ruler (`Super+Shift+M` / `knobu screen-ruler`)**: Click and drag to measure pixel dimensions and spacing across screens.
- **Hardware Cleaning Mode (`Super+Alt+K` / `knobu cleaning-mode`)**: Locks keyboard, touchpad, and mouse inputs so you can wipe hardware down safely. Hold `Escape` for 2 seconds to unlock.
- **Port Manager (`knobu ports`)**: Lists all listening TCP and UDP ports and active process IDs.
- **Hosts File Editor**: Visual editor for `/etc/hosts` with toggle switches, search, and automatic timestamped backups.
- **File Locksmith**: Inspects `/proc/*/fd` to see which applications are locking a file or directory, with 1-click termination.

---

## 13. Awake, Color Picker & Text Extractor

### Awake
Prevents sleep and screen locking without altering power profiles:
```bash
knobu awake on      # Indefinite
knobu awake 1h30m   # 1 hour 30 minutes
knobu awake off     # Revert to normal
```

### Color Picker (`Super+Shift+C`)
- Click any pixel on screen.
- Automatically copies the color to clipboard and displays HEX, RGB, and HSL values.

### Text Extractor (`Super+Shift+T`)
- Click and drag a selection rectangle over any unselectable text or image on screen.
- Runs local Tesseract OCR and places the extracted text onto your clipboard.

---

## 14. Backup & Restore

Knobu stores settings in `~/.config/knobu/config.toml`. You can export and migrate settings as JSON:

### Exporting Settings
```bash
knobu backup ~/knobu-settings.json
```

### Restoring Settings
```bash
knobu restore ~/knobu-settings.json
systemctl --user restart knobu.service
```

Settings can also be backed up and restored directly in the **General** tab of the settings UI.

---

## 15. CLI Reference & Troubleshooting

### CLI Summary
```text
knobu [command]

Core Commands:
  settings             Open GTK4 settings dashboard
  status               Check user service status
  enable / disable     Toggle service autostart at login
  bypass [on|off]      Toggle gaming passthrough mode
  backup / restore     JSON configuration export/import

Window & Sound:
  always-on-top        Pin/unpin active window
  fancyzones           Open zone editor overlay
  snap <index>         Snap window to zone
  mic-mute             Toggle microphone mute
  audio-switch         Cycle audio output sink
  streams              List active audio streams

Cloud & DevOps:
  cidr <subnet>        Subnet network calculations
  dns <domain>         Query DNS records
  ssl-check <host:port>Check SSL certificate validity
  aws-whoami           Verify AWS STS credentials
  containers           List Docker containers
  cron / cron-add      Manage cron schedules

Utilities:
  command-bar / run    Summon Alt+Space search bar
  clipboard            Summon Super+V clipboard
  pick-color           Color picker magnifier
  extract-text         OCR screen text extractor
  zoomit               Screen zoom and annotation
  shortcut-guide       Show shortcut cheat sheet
  quick-accent         Open accent character picker
  theme [dark|light]   Switch desktop appearance
```

### Troubleshooting
- **Input group error**: Ensure your user is in the `input` group (`groups $USER`). If recently added, reboot or log out.
- **Service logs**: Check daemon background logs with:
  ```bash
  journalctl --user -u knobu -f
  ```
- **Restore desktop shortcuts**: If `Alt+Space` or other desktop defaults need restoration, run:
  ```bash
  knobu restore-os-shortcuts
  ```
