<div align="center">

# Knobu

**Windows has PowerToys. Ubuntu has Knobu.**

Touchpad volume gestures, key remapping, a colour picker, on-screen text copying and
"keep awake", all in one native GTK4 app. Works on Wayland and X11.

[![Latest release](https://img.shields.io/github/v/release/Saad-1719/knobu?color=E95420)](https://github.com/Saad-1719/knobu/releases/latest)
[![License: GPL-3.0](https://img.shields.io/github/license/Saad-1719/knobu)](LICENSE)
[![Kubuntu: supported](https://img.shields.io/badge/Kubuntu-supported-1d99f3)](#supported-desktops)
[![Ubuntu: beta](https://img.shields.io/badge/Ubuntu-beta-E95420)](#supported-desktops)

[Website](https://knobu.saaadi.dev) · [Download](https://github.com/Saad-1719/knobu/releases/latest) · [PowerToys → Knobu](https://knobu.saaadi.dev/powertoys-alternative-linux) · [Report a bug](https://github.com/Saad-1719/knobu/issues)

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
| 🖐️ **Touchpad Gestures** | Slide three fingers to change the volume, tap to mute or play/pause |
| ⌨️ **Keyboard Manager** | Remap keys and shortcuts (CapsLock → Ctrl, Super+E → terminal) in every app |
| ☕ **Awake** | Keep the computer awake for a while, without touching power settings |
| 🎨 **Color Picker** | Super+Shift+C, click any pixel, and its HEX/RGB/HSL is copied |
| 📝 **Text Extractor** | Super+Shift+T, drag over any text on screen, and it's copied (OCR) |

Each tool is a *module* you can turn on or off in the Knobu settings app.

> If Knobu saves you a trip back to Windows, a ⭐ helps other people find it.

## Supported desktops

| Desktop | Status | Notes |
|---|---|---|
| Kubuntu (KDE Plasma 6) | ✅ Supported | All features, including the volume pop-up and Color Picker magnifier |
| Ubuntu (GNOME) | 🧪 Beta | No volume pop-up or magnifier; use 4-finger gestures, since GNOME uses 3-finger swipes |
| Xubuntu, Lubuntu, Ubuntu MATE | 🔜 Planned | Start at login and the screen tools still need work |

Found a problem on your desktop? Please open an issue and mention your flavour and version.

## Modules

### Touchpad Gestures

| Gesture | Action |
|---|---|
| 3-finger slide up / down | Volume up / down, smoothly, as far as you slide |
| 3-finger quick tap | Mute / unmute |
| 4-finger quick tap | Play / pause music and videos |

- Works on Wayland and X11, alongside your desktop's own gestures.
- Each tap can be set to mute, play/pause, next track, previous track, or nothing.
- Media control works with any player that supports MPRIS: Spotify, browsers, VLC,
  Rhythmbox, Elisa and more. The player that's currently playing gets the command.
- Follows your desktop's maximum volume: 150% when KDE's "Raise maximum volume" or
  GNOME's "Over-amplification" is on, 100% otherwise. You can also set your own limit.
- Speed, direction and slide finger count (3 or 4) are configurable.
- Shows your desktop's volume pop-up (KDE Plasma today, more desktops planned).

> **Tip:** Linux turns a 3-finger tap into a middle-click, which pastes text in some
> apps. If that gets in the way, move mute to the 4-finger tap.

### Keyboard Manager

Remap keys and shortcuts on every keyboard, in every app, on Wayland and X11.

- **Key → key** changes the key everywhere, even inside shortcuts. For example,
  CapsLock → Ctrl gives you a real Ctrl key.
- **Shortcut → shortcut** changes only that combination, e.g. Super+E → Ctrl+Alt+T.
- Record remaps by pressing the keys: no key names to look up.
- Nothing is intercepted while you have no remaps. New keyboards are picked up when
  you plug them in.

Needs a one-time permission to create a virtual keyboard (see [Requirements](#requirements)).

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
                                                   |-- Keyboard Manager  (grabs keyboards, re-sends via uinput)
                                                   |-- Awake             (logind + ScreenSaver inhibitors)
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

## License

Knobu is free software, licensed under the [GNU GPL v3.0 or later](LICENSE).
