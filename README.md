# Knobu

**PowerToys-style utilities for Ubuntu.**

Fully supported on **Kubuntu (KDE Plasma 6)**. **Ubuntu (GNOME)** support is in beta.
Xubuntu, Lubuntu and Ubuntu MATE are coming soon.

Knobu adds small, switchable power tools to your desktop. Each tool is a *module* you
can turn on or off in the Knobu settings app.

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
- `.deb` package and a PPA; Flatpak/Snap
- More modules, PowerToys-style (ideas welcome!)

## License

Knobu is free software, licensed under the [GNU GPL v3.0 or later](LICENSE).
