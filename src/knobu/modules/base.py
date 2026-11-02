"""Base class for Knobu modules.

A module is one feature (like a single PowerToy). The daemon runs each enabled module
in its own thread and stops it by setting the event passed to run().
"""

import logging
import threading


class Module:
    id: str = ""
    name: str = ""
    description: str = ""
    icon: str = "application-x-addon-symbolic"
    defaults: dict = {"enabled": True}

    def __init__(self, settings: dict):
        self.settings = settings
        self.log = logging.getLogger(f"knobu.{self.id}")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_guarded, name=self.id, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def run(self, stop: threading.Event) -> None:
        """Do the module's work until `stop` is set. Must check it at least every second."""
        raise NotImplementedError

    def _run_guarded(self) -> None:
        try:
            self.run(self._stop)
        except Exception:
            self.log.exception("module crashed")
