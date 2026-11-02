"""One-shot tools started by a shortcut or `knobu <command>`: they use the desktop's own
picker/selector, copy the result and confirm with a notification. No windows."""

from knobu import config, modules


def settings(module_id: str) -> dict:
    return config.module_settings(config.load(), module_id, modules.get(module_id).defaults)
