"""Reading and writing ~/.config/knobu/config.toml.

The file has one table per module, e.g. [touchpad]. Missing keys fall back to the
module's defaults, so the file only needs the values a user actually changed.
"""

import json
import os
import tomllib
from pathlib import Path


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "knobu" / "config.toml"


def load(path: Path | None = None) -> dict:
    path = path or config_path()
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def save(data: dict, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(dumps(data))
    tmp.replace(path)  # atomic, so the daemon never reads a half-written file


def module_settings(data: dict, module_id: str, defaults: dict) -> dict:
    return {**defaults, **data.get(module_id, {})}


def dumps(data: dict) -> str:
    """Minimal TOML writer for our flat module tables of scalars and lists (stdlib can
    only read TOML)."""
    lines = ["# Knobu settings. Edit here or in the Knobu app.", ""]
    for table, values in data.items():
        lines.append(f"[{table}]")
        lines.extend(f"{key} = {_value(v)}" for key, v in values.items())
        lines.append("")
    return "\n".join(lines)


def _value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)  # JSON string escapes are valid TOML basic strings
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    raise TypeError(f"unsupported config value: {v!r}")
