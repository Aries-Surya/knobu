# Contributing to Knobu

Thank you for your interest in contributing to Knobu! Knobu is an open-source productivity suite for Linux built with Python, GTK4, Libadwaita, and systemd.

## Getting Started

### Prerequisites

On Ubuntu or Debian-based distributions:

```bash
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-evdev \
    debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools
```

### Local Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/Aries-Surya/knobu.git
   cd knobu
   ```

2. Install in editable development mode:
   ```bash
   pip install --user --break-system-packages -e .
   ```

3. Test running the application:
   ```bash
   knobu          # Launches the settings application
   knobu status   # Checks background service status
   ```

## Running Tests

Knobu includes a comprehensive test suite. Run tests using `unittest`:

```bash
python3 -m unittest discover -s tests -t .
```

## Adding a New Module

Each tool in Knobu is a modular component:

1. **Create the module file** in `src/knobu/modules/<name>.py` (or directory `src/knobu/modules/<name>/__init__.py`) subclassing `knobu.modules.base.Module`:
   ```python
   from knobu.modules.base import Module

   class MyToolModule(Module):
       id = "mytool"
       name = "My Tool"
       description = "Does something awesome on Linux"
       icon = "preferences-other-symbolic"
       defaults = {"enabled": True}

       def run(self, stop):
           while not stop.is_set():
               # Do background work
               stop.wait(1)
   ```
2. **Register the module** in `src/knobu/modules/__init__.py` under `MODULES`.
3. **Add its settings page** in `src/knobu/ui/pages.py` under `PAGES`.
4. **Add unit tests** in `tests/test_<name>.py`.

## Building the Debian Package

Knobu builds standard Debian (`.deb`) packages:

```bash
dpkg-buildpackage -us -uc -b
```

The resulting `.deb` package will be written to the parent directory (`../knobu_*.deb`). You can test installation with:

```bash
sudo apt install ../knobu_*_all.deb
```

## Submitting Pull Requests

1. Create a descriptive feature branch (`git checkout -b feature/my-new-tool`).
2. Ensure all tests pass (`python3 -m unittest discover -s tests -t .`).
3. Commit with clear, conventional messages.
4. Open a Pull Request on GitHub describing the motivation and changes.

