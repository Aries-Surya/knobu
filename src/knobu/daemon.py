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
        for cls in MODULES:
            settings = config.module_settings(data, cls.id, cls.defaults)
            if settings["enabled"]:
                module = cls(settings)
                module.start()
                self.running.append(module)
        log.info("running modules: %s", ", ".join(m.id for m in self.running) or "none")

    def stop_modules(self) -> None:
        for module in self.running:
            module.stop()
        self.running.clear()

    def run(self) -> None:
        signal.signal(signal.SIGHUP, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)
        self.start_modules()
        while not self._quit:
            if not self._wake.wait(1):  # timeout keeps signal handling responsive
                continue
            self._wake.clear()
            if self._reload and not self._quit:
                self._reload = False
                log.info("reloading config")
                self.stop_modules()
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
