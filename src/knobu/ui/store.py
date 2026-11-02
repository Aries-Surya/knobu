"""Settings shared by all pages: saves to the config file and tells the daemon to reload."""

from gi.repository import GLib

from knobu import config, modules, service


class SettingsStore:
    RELOAD_DELAY_MS = 400  # batch rapid changes (e.g. spin buttons) into one reload

    def __init__(self):
        self.data = config.load()
        self._reload_source = 0
        self.listeners = []  # callables(module_id, key, value), e.g. sidebar status dots

    def get(self, module_id: str, key: str):
        defaults = modules.get(module_id).defaults
        return config.module_settings(self.data, module_id, defaults)[key]

    def set(self, module_id: str, key: str, value) -> None:
        if self.get(module_id, key) == value:
            return
        self.data.setdefault(module_id, {})[key] = value
        config.save(self.data)
        for listener in self.listeners:
            listener(module_id, key, value)
        if self._reload_source:
            GLib.source_remove(self._reload_source)
        self._reload_source = GLib.timeout_add(self.RELOAD_DELAY_MS, self._reload)

    def _reload(self) -> bool:
        self._reload_source = 0
        service.reload()
        return GLib.SOURCE_REMOVE
