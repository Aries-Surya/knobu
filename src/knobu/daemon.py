"""The background process that runs enabled modules.

SIGHUP reloads the config (the settings app sends it via `systemctl --user reload`);
SIGTERM/SIGINT stop it cleanly.
"""

import logging
import signal
import threading

from knobu import config
from knobu.modules import MODULES, Module

log = logging.getLogger("knobu")


class Daemon:
    def __init__(self):
        self.running: list[Module] = []
        self._wake = threading.Event()
        self._reload = False
        self._quit = False

    def start_modules(self) -> None:
        data = config.load()
        bypass_all = bool(data.get("general", {}).get("bypass", False))
        from knobu.system import hotkeys
        hotkeys.service().set_bypass(bypass_all)
        if bypass_all:
            log.info("Bypass Mode is ACTIVE: hardware grabs suspended (tray remains active)")

        existing = {m.id: m for m in self.running}
        for cls in MODULES:
            if bypass_all and cls.id != "notifications":
                continue
            settings = config.module_settings(data, cls.id, cls.defaults)
            if settings["enabled"] and not settings.get("bypass", False):
                if cls.id in existing:
                    existing[cls.id].update_settings(settings)
                    continue
                module = cls(settings)
                module.start()
                self.running.append(module)
        log.info("running modules: %s", ", ".join(m.id for m in self.running) or "none")

    def stop_modules(self, reloading: bool = False) -> None:
        kept: list[Module] = []
        data = config.load() if reloading else {}
        for module in self.running:
            if reloading and module.id == "notifications":
                s = config.module_settings(data, module.id, module.defaults)
                if s["enabled"] and not s.get("bypass", False):
                    kept.append(module)
                    continue
            module.stop()
        self.running = kept
        from knobu.system import hotkeys
        hotkeys.service().set_keyboard_processor(None)

    def run(self) -> None:
        signal.signal(signal.SIGHUP, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)
        self.start_modules()
        from knobu.modules import cloud_backup
        while not self._quit:
            if not self._wake.wait(1):  # timeout keeps signal handling responsive
                cloud_backup.maybe_periodic_sync()
                continue
            self._wake.clear()
            if self._reload and not self._quit:
                self._reload = False
                log.info("reloading config")
                self.stop_modules(reloading=True)
                self.start_modules()
        self.stop_modules()
        log.info("stopped")

    def _on_signal(self, signum, _frame) -> None:
        if signum == signal.SIGHUP:
            self._reload = True
        else:
            self._quit = True
        self._wake.set()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    Daemon().run()
