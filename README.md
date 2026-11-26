<div align="center">

# Knobu

**Windows has PowerToys. Ubuntu has Knobu.**

Touchpad volume gestures, key remapping, a colour picker, on-screen text copying and
"keep awake", all in one native GTK4 app. Works on Wayland and X11.

[![Latest release](https://img.shields.io/github/v/release/Aries-Surya/knobu?color=E95420)](https://github.com/Aries-Surya/knobu/releases/latest)
[![License: GPL-3.0](https://img.shields.io/github/license/Aries-Surya/knobu)](LICENSE)
[![Kubuntu: supported](https://img.shields.io/badge/Kubuntu-supported-1d99f3)](#supported-desktops)
[![Ubuntu: beta](https://img.shields.io/badge/Ubuntu-beta-E95420)](#supported-desktops)

[Download](https://github.com/Aries-Surya/knobu/releases/latest) · [User Manual](docs/USER_MANUAL.md) · [Report a bug](https://github.com/Aries-Surya/knobu/issues)

<img src="docs/demo.gif" alt="Knobu demo: three-finger volume slide, CapsLock to Ctrl remap, colour picker, text extractor and Awake" width="800">

</div>

## Quick install

On Ubuntu or Kubuntu 24.04 or newer:

```bash
# Download and install the latest release package
wget https://github.com/Aries-Surya/knobu/releases/latest/download/knobu_all.deb -O /tmp/knobu_latest.deb || \
wget $(curl -s https://api.github.com/repos/Aries-Surya/knobu/releases/latest | grep "browser_download_url.*deb" | cut -d '"' -f 4) -O /tmp/knobu_latest.deb
sudo apt install /tmp/knobu_latest.deb
sudo usermod -aG input $USER   # then log out and back in
```

Open **Knobu** from the app menu and turn on the background service. Details are in
[Install](#install), [Updating](#updating), and [Requirements](#requirements).

## What you get

| Tool | What it does |
|---|---|
| 🔍 **Command Bar** | Alt+Space floating launcher (PowerToys Run for Linux): search apps, calculate math, run shell commands, paths & web |
| 🔔 **Top Tray & Notifications** | System tray dropdown showing Wi-Fi/VPN, Private & Public IP (copy), active AWS CLI profile switcher, and Mac-style Notification Center |
| 📋 **Clipboard History** | Super+V floating manager: persistent SQLite history, copied images, live thumbnails, search, pinning, URL sanitization, and Advanced Paste transforms |
| 🪟 **Window Manager (FancyZones)** | Super+Ctrl+T Always on Top, Super+Shift+` FancyZones layout overlay, and keyboard zone snapping |
| 🔊 **Sound Suite** | Per-app volume mixer, up to 150% audio boost, Super+Shift+A mic mute, and Super+Shift+O output device cycling |
| 📊 **System Monitor** | Live CPU (per-core), memory, network, thermal readings, and high-load/low-battery health alerts |
| ☁️ **DevOps & Cloud** | CIDR subnet calculator, DNS lookup, SSL expiry checker, AWS Caller Identity, Docker containers, and Cron jobs |
| ⚡ **Automations Engine** | Rule-based automation engine ("When [Trigger] -> If [Condition] -> Then [Action]") with execution history |
| 🧩 **Extended PowerToys** | ZoomIt (`knobu zoomit`), Shortcut Guide (`Super+Shift+?`), Quick Accent (`knobu quick-accent`), Workspaces Launcher, and Light Switch |
| 🖐️ **Touchpad Gestures** | Slide three fingers to change the volume, tap to mute or play/pause |
| ⌨️ **Keyboard Manager** | Remap keys and shortcuts (CapsLock → Ctrl, Super+E → terminal) in every app |
| ☕ **Awake** | Keep the computer awake for a while, without touching power settings |
| 🛠️ **Power Tools** | Port Manager (`ss -tulpn`), Hardware Cleaning Mode (`Super+Alt+K`), System Cleaner & Uninstaller, and FFmpeg Media Tools |
| 🎨 **Color Picker** | Super+Shift+C, click any pixel, and its HEX/RGB/HSL is copied |
| 📝 **Text Extractor** | Super+Shift+T, drag over any text on screen, and it's copied (OCR) |

Each tool is a *module* you can turn on or off in the Knobu settings app.

> If Knobu saves you a trip back to Windows, a ⭐ helps other people find it.

## Supported desktops

| Desktop | Status | Notes |
|---|---|---|
| Kubuntu (KDE Plasma 6) | ✅ Supported | All features, including the volume pop-up and Color Picker magnifier |
| Ubuntu (GNOME) | ✅ Supported | Native on-screen volume indicator and 4-finger gestures (avoids GNOME 3-finger workspace conflict) |
| Xubuntu, Lubuntu, Ubuntu MATE | 🔜 Planned | Start at login and the screen tools still need work |

Found a problem on your desktop? Please open an issue and mention your flavour and version.

## Modules

### Command Bar (PowerToys Run for Linux)

Press **Alt+Space** to open an instant, floating search and quick-command bar (pressing **Alt+Space** again toggles it closed):

- **Installed Applications**: Fast fuzzy search across all system and user desktop entries (`.desktop`), Flatpaks, and Snaps.
- **Safe Calculator**: Evaluates math expressions instantly (e.g. `(15 * 4) / 2`, `sqrt(144)`, `20% of 150`, `pi`). Press Enter to copy the answer to your clipboard.
- **Unit & Currency Converter**: Convert lengths, masses, storage, times, speeds, volumes, temperatures, and 35+ global currencies (e.g., `100 USD in EUR`, `50 miles in km`, `100 C in F`, `16 GB in MB`, `$100 in INR`).
- **Emoji Search & Picker**: Prefix with `:` to search and copy emojis directly (e.g., `:fire`, `:rocket`, `:check`, `:tada`, `:coffee`).
- **Open Windows & Tab Switcher**: Switch to open application windows and browser tabs, prefixed with `<` (e.g., `< code`, `< browser`, `< cliq`) or surfaced directly in search.
- **Terminal & Shell Runner**: Run commands directly in your terminal by prefixing with `>` (e.g., `> htop`, `> ping 8.8.8.8`).
- **Files & Path Navigation**: Type `~/` or `/` to search and navigate file paths, pressing Enter opens them in your default file manager.
- **Web & URLs**: Open URLs directly or prefix with `? <query>` to search the web in your default browser.
- **System Actions**: Quick commands to lock screen, sleep/suspend, reboot, shutdown, or open any Knobu tool.
- **Zero-Conflict Alt+Space**: Features hardware-level exclusive `evdev` grabbing, toggle-to-close dismiss, and automatic desktop environment shortcut overriding (safely frees `Alt+Space` in GNOME window menu and KDE KRunner).

### Clipboard History

Press **Super+V** (`Windows+V`) to summon a clean, searchable floating clipboard palette:

- **Rich Content Support**: Stores and previews text and copied graphics (screenshots, PNG, JPEG) with instant dimension tags and live thumbnail rendering.
- **Privacy & Sanitization**: Automatically strips marketing and tracking parameters (`utm_*`, `fbclid`, `gclid`, etc.) and trims trailing whitespaces on copy.
- **Password Manager Protection**: Automatically detects and ignores sensitive secrets copied from KeePassXC, 1Password, or password managers with KDE/GNOME privacy flags.
- **Hardware-Level Exclusive Grab**: Swallows `Super+V` at the evdev hardware layer so underlying applications never receive stray keystrokes or premature paste events.
- **Persistent Local SQLite**: Stored safely in `~/.local/share/knobu/clipboard.db` with unpinned clip capacity bounds (10–500 clips).
- **Settings Dashboard**: Configure history limit, allowed types (text/images), privacy filters, keyboard shortcuts, view storage metrics, or clear history in one click.

### Touchpad Gestures

Precision multi-finger touchpad gestures with full 4-directional customization and zero OS conflict:

| Gesture | Default Action | Supported Actions |
|---|---|---|
| **3-finger swipe up** | Volume Slide (smooth continuous) | Volume Slide, Volume Up (+5%), Overview, Desktop, Workspace Up, App Switch, Command Bar, None |
| **3-finger swipe down** | Volume Slide (smooth continuous) | Volume Slide, Volume Down (-5%), Overview, Desktop, Workspace Down, App Switch, None |
| **3-finger swipe left** | Previous Track (media) | Previous Track, Workspace Left, Previous App, None |
| **3-finger swipe right** | Next Track (media) | Next Track, Workspace Right, Next App, None |
| **4-finger swipe up** | Overview / Task View (`Super`) | Overview, Volume Slide, Volume Up, Workspace Up, Desktop, None |
| **4-finger swipe down** | Show Desktop (`Super+D`) | Show Desktop, Volume Slide, Volume Down, Overview, None |
| **4-finger swipe left** | Switch Workspace Left | Switch Workspace Left, Previous Track, Previous App, None |
| **4-finger swipe right** | Switch Workspace Right | Switch Workspace Right, Next Track, Next App, None |
| **3-finger quick tap** | Mute / Unmute | Mute, Play/Pause, Next, Previous, Overview, Desktop, Command Bar, None |
| **4-finger quick tap** | Play / Pause media | Play/Pause, Mute, Next, Previous, Overview, Desktop, Command Bar, None |

- **Zero-Conflict OS Grab (`grab_gestures`)**: Claims touchpad exclusively during 3-finger and 4-finger gestures, preventing GNOME from double-triggering native workspace switching or overview. Ungrabs instantly on finger lift so normal 1-finger cursor and 2-finger scroll remain 100% native.
- **Native On-Screen Volume Slider**: Volume adjustments trigger the desktop's native on-screen volume bubble without intrusive notification pop-ups.
- **Works on Wayland and X11**: Independent of libinput desktop gesture bindings.
- **Configurable Audio Limit & Speed**: Speed (percent per cm), inversion, and max volume (system, 100%, 125%, 150%) are fully adjustable.
- **Gaming & Passthrough Mode**: Easily bypass all gestures via `knobu bypass on` or in the Settings UI.

### Keyboard Manager

Remap keys and shortcuts on every keyboard, in every app, on Wayland and X11.

- **Key → key** changes the key everywhere, even inside shortcuts. For example,
  CapsLock → Ctrl gives you a real Ctrl key.
- **Shortcut → shortcut** changes only that combination, e.g. Super+E → Ctrl+Alt+T.
- **Text Snippets Expansion**: Auto-expand abbreviations like `;email` into full text or dynamic date/time variables (`{date}`, `{time}`, `{datetime}`).
- **Quit & Close Protection**: Prevents accidental loss of work by requiring hold (0.5s) or double-press for `Ctrl+Q` and `Ctrl+W`.
- **Key Chatter Filter**: Software debouncing for worn mechanical switches to eliminate repeated characters.
- Record remaps by pressing the keys: no key names to look up.
- Nothing is intercepted while you have no remaps or active keyboard tools. New keyboards are picked up when you plug them in.

Needs a one-time permission to create a virtual keyboard (see [Requirements](#requirements)).

### Mouse Utilities

Configure mouse behavior independently of touchpad desktop settings:

- **Independent Wheel Inversion**: Reverse mouse wheel direction without altering the touchpad scrolling direction.
- **Smooth Scrolling & Speed Multiplier**: Adjust wheel scroll speed multiplier (0.25x to 5.0x).
- **Hardware Debounce Filter**: Suppress accidental double-clicks caused by worn mouse microswitches.
- **Find My Mouse (`Super+Alt+F` / Shake)**: Syncs GNOME `Ctrl` pointer-locator ring and launches a fullscreen spotlight overlay on rapid mouse shake or shortcut.

### Power Tools & System Maintenance

Everyday developer and maintenance utilities built into Knobu:

- **Port Manager**: Inspect listening TCP/UDP ports (`ss -tulpn`), filter by port or process name, and terminate stuck processes in one click.
- **Hardware Cleaning Mode (`Super+Alt+K`)**: Fullscreen dark overlay that exclusively locks keyboards, mice, and touchpads via `evdev` so you can wipe hardware safely; hold `Esc` for 2 seconds or wait for the countdown timer to unlock.
- **Screen Ruler (`Super+Shift+M`)**: Measure pixel dimensions (`W × H px`) and diagonal spacing across monitors and copy results to clipboard.
- **System Cleaner & Uninstaller**: Measure and clean `~/.cache`, thumbnail previews, crash dumps, and APT cache (`apt-get clean`), plus search and remove installed packages across **APT, Snap, Flatpak, Brew, Pipx, NPM, and Cargo**.
- **Environment Variables Manager**: Manage `~/.config/environment.d/90-knobu.conf` with live `systemctl --user set-environment` syncing and read-only session inspector.
- **Hosts File Editor**: Add, enable/disable, and save `/etc/hosts` entries safely with automatic backup.
- **File Locksmith**: Inspect processes holding open `/proc/*/fd` handles on any file and terminate locks in one click.
- **Media Tools (`ffmpeg`)**: Local H.264/AAC MP4 compression, two-pass Lanczos GIF conversion, batch image format conversion (`webp`, `png`, `jpg`, `avif`, `bmp`), and batch image resizing presets.

### Awake

Keep the computer awake without changing your power settings: until you turn it
off, or for a set time. Optionally keeps the screen on too.

```bash
knobu awake on      # until you turn it off
knobu awake 1h30m   # for a while
knobu awake off
```

### Color Picker

Press **Super+Shift+C** and click any pixel: the colour is copied (HEX, RGB or HSL),
and a small window shows it in all three formats with your recent colours. Picking uses
your desktop's own colour picker; on KDE a small magnifier follows the cursor so you
can see exactly which pixel you're on, like PowerToys on Windows.

### Text Extractor

Press **Super+Shift+T** and drag over the text on screen: it's copied as soon as you
let go, and a window shows the text so you can check or edit it. No screenshot tool
or menus appear: the screen looks unchanged until you drag. Uses Tesseract OCR;
install more languages with `sudo apt install tesseract-ocr-<lang>`.

Both shortcuts can be changed in the settings app. They're also in the app menu:
right-click Knobu's icon.

## Requirements

- Ubuntu 24.04 or newer, on a [supported desktop](#supported-desktops)
- Your user in the `input` group, so Knobu can read the touchpad and keyboards:

  ```bash
  sudo usermod -aG input $USER
  ```

  Then log out and back in.

- For **Keyboard Manager**: permission to create a virtual keyboard. Ubuntu keeps this
  root-only, so install the rule in [`data/70-knobu-uinput.rules`](data/70-knobu-uinput.rules):

  ```bash
  sudo cp data/70-knobu-uinput.rules /etc/udev/rules.d/
  sudo udevadm control --reload && sudo udevadm trigger --name-match=uinput
  ```

- For **Text Extractor**: Tesseract OCR:

  ```bash
  sudo apt install tesseract-ocr
  ```


- GTK 4 and libadwaita for the settings app (preinstalled on Ubuntu; on other flavours):

  ```bash
  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
  ```

## Install

Download the latest `.deb` from the [Releases page](https://github.com/Aries-Surya/knobu/releases/latest) and install it with apt, which pulls in
the dependencies:

```bash
sudo apt install ./knobu_*_all.deb
```

Then open **Knobu** from the app menu and turn on the background service on the General
page. Each user turns it on for themselves; nothing starts automatically after install.

The package also installs a udev rule that lets members of the `input` group create
virtual keyboards, which Keyboard Manager needs. You still need to be in that group
(see [Requirements](#requirements)).

## Updating

When a new version is published to GitHub Releases, you can update without losing any configuration or clipboard history:

### Option A: One-line Terminal Upgrade (Recommended)
```bash
# Fetch and install the latest release .deb
wget $(curl -s https://api.github.com/repos/Aries-Surya/knobu/releases/latest | grep "browser_download_url.*deb" | cut -d '"' -f 4) -O /tmp/knobu_latest.deb
sudo apt install --reinstall /tmp/knobu_latest.deb

# Restart your user service
systemctl --user restart knobu.service

# Verify installed version
knobu --version
```

### Option B: Using GitHub CLI
```bash
gh release download --repo Aries-Surya/knobu --pattern "*.deb" --dir /tmp --clobber
sudo apt install --reinstall /tmp/knobu_*_all.deb
systemctl --user restart knobu.service
knobu --version
```

### Option C: Web Browser
1. Download the latest `.deb` asset from [GitHub Releases](https://github.com/Aries-Surya/knobu/releases/latest).
2. Open terminal in your download directory and run:
   ```bash
   sudo apt install --reinstall ./knobu_*_all.deb
   systemctl --user restart knobu.service
   ```

*(Your settings in `~/.config/knobu/` and clipboard history in `~/.local/share/knobu/` are automatically preserved during upgrades.)*

### Building the package

```bash
sudo apt install debhelper dh-python pybuild-plugin-pyproject python3-all \
    python3-setuptools python3-evdev devscripts lintian
dpkg-buildpackage -us -uc -b
```

The `.deb` is written to the parent folder.

## Running from source

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .
.venv/bin/knobu
```

`--system-site-packages` lets the virtual environment use the system's GTK bindings.

### Commands

| Command | What it does |
|---|---|
| `knobu` | Open the settings app |
| `knobu enable` | Start the background service now and at every login |
| `knobu disable` | Stop the background service and remove it from login |
| `knobu status` | Show whether the background service is running |
| `knobu awake on\|off\|30m` | Keep the computer awake |
| `knobu pick-color` | Pick a colour from the screen |
| `knobu extract-text` | Copy text from an area of the screen |
| `knobu command-bar` (or `run`) | Open the floating Command Bar launcher |
| `knobu clipboard` | Open the Clipboard History palette |
| `knobu paste-plain` | Paste current clipboard text stripped of formatting |
| `knobu cleaning-mode` | Lock keyboard, mouse, and touchpad inputs for safe hardware cleaning |
| `knobu screen-ruler` | Measure pixel distances and bounding boxes on screen |
| `knobu find-mouse` | Spotlight cursor location on screen |
| `knobu notifications` | Open the Mac-style Notification Center drawer |
| `knobu ports` | Print listening TCP/UDP ports and PIDs in the terminal |
| `knobu bypass on\|off\|toggle` | Temporarily bypass all hardware grabs and customizations (gaming / passthrough mode) |
| `knobu restore-os-shortcuts` | Restore default OS shortcuts overridden by Knobu (GNOME / KDE) |
| `knobu backup [path]` | Export all configurations to a JSON backup file |
| `knobu restore <path>` | Restore configurations from a JSON backup file |
| `knobu mic-mute` | Toggle global default microphone mute |
| `knobu audio-switch` | Cycle default audio output device (speakers / headphones) |
| `knobu streams` | List active application audio playback streams and volumes |
| `knobu always-on-top` | Pin or unpin the active window above all other windows |
| `knobu fancyzones` | Open interactive FancyZones layout grid overlay |
| `knobu snap <zone>` | Snap the active window to a FancyZones zone index (0, 1, 2...) |
| `knobu sysmon` | Output live CPU, memory, thermal, and network metrics |
| `knobu cidr <subnet>` | Calculate IPv4/IPv6 CIDR network range and usable hosts |
| `knobu dns <domain>` | Query DNS records (`A`, `AAAA`, `CNAME`, `MX`, `TXT`) |
| `knobu ssl-check <host:port>` | Inspect SSL/TLS certificate expiry, issuer, and SANs |
| `knobu aws-whoami` | Display active AWS caller identity (Account ID, ARN, UserId) |
| `knobu containers` | List Docker containers status and exposed ports |
| `knobu cron` | Show local cron service status and list user cron jobs |
| `knobu cron-add "<expr>" "<cmd>"` | Add a new user cron job with syntax validation |
| `knobu automations` | List configured rule-based automations |
| `knobu run-automation <id>` | Manually run an automation rule |
| `knobu shortcut-guide` | Open the interactive Shortcut Guide overlay |
| `knobu zoomit` | Freeze screen for zoom and pen/arrow/box annotation |
| `knobu quick-accent` | Open the Quick Accent character picker popup |
| `knobu theme [dark\|light\|toggle]` | Switch or inspect desktop light/dark theme |
| `knobu workspace [name]` | Launch a saved workspace app group |
| `knobu daemon` | Run the background service in the terminal (useful for debugging) |

Settings live in `~/.config/knobu/config.toml`. Service logs:

```bash
journalctl --user -u knobu -f
```

## How it works

```
knobu (settings app, GTK4)  --writes-->  ~/.config/knobu/config.toml
           |                                       |
           +-- systemctl --user reload knobu --> knobu daemon (systemd user service)
                                                   |-- Touchpad Gestures (reads the touchpad via evdev)
                                                   |-- Keyboard Manager  (remaps, snippets, quit protection, chatter filter)
                                                   |-- Mouse Utilities   (independent wheel invert, scroll multiplier, click debounce)
                                                   |-- Awake             (logind + ScreenSaver inhibitors)
                                                   |-- Clipboard History (Super+V palette, image & text SQLite store)
                                                   |-- Command Bar       (Alt+Space launcher, apps, calc, shell, emoji, converter)
                                                   '-- Color Picker, Text Extractor
                                                         (global shortcuts -> knobu pick-color / extract-text)
```

- `src/knobu/modules/`: one module per tool, registered in `modules/__init__.py`.
- `src/knobu/system/`: desktop-neutral helpers: audio (`wpctl`/`pactl`), media players
  (MPRIS), global shortcuts, key names, xdg-desktop-portal, notifications, permissions.
- `src/knobu/ui/`: the settings app (`app.py`, one page per module in `pages.py`) and the
  tool windows: `colorpicker.py` with its KWin-driven `magnifier.py`, and
  `textextractor.py` with its quiet `selection.py`.

## Development

```bash
.venv/bin/python -m unittest discover -s tests
```

### Adding a module

1. Create `src/knobu/modules/<name>/` with a `Module` subclass (`id`, `name`,
   `description`, `icon`, `defaults`, and a `run(stop)` loop).
2. Add it to `MODULES` in `src/knobu/modules/__init__.py`.
3. Add a settings page for it to `PAGES` in `src/knobu/ui/pages.py`.

## Roadmap

- Full support for Xubuntu, Lubuntu and Ubuntu MATE (start at login, screen capture on X11)
- Volume pop-up on GNOME, Xfce, LXQt, MATE and Budgie
- Tray icon for quick toggles (Awake, Keyboard Manager)
- Caps Lock / Num Lock LEDs while Keyboard Manager is remapping
- More gestures (brightness, edge slides)
- Flatpak/Snap
- More modules, PowerToys-style (ideas welcome!)

## AI Usage Disclosure

Generative AI tools were used during the development of Knobu to assist with software engineering tasks, including code generation, implementation, debugging, and documentation.

AI-generated contributions were reviewed, tested, and integrated as part of the development process. The project is maintained as open-source software under the GNU GPL v3.0 or later license.

The use of AI tools does not change the project's licensing terms.

## License & Attribution

Knobu is free software, licensed under the [GNU GPL v3.0 or later](LICENSE).

- **Original Author**: [saad-1719](https://github.com/Saad-1719/knobu) (Copyright © 2026)
- **Fork Maintainer**: [Surya Prakash](https://github.com/Aries-Surya/knobu) (Copyright © 2026)
