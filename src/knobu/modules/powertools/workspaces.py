"""Workspaces Launcher: save and launch named groups of apps/commands in one click."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import subprocess

from knobu import config


@dataclass
class WorkspaceGroup:
    name: str
    commands: list[str]


def workspaces_path() -> Path:
    return config.config_path().parent / "workspaces.json"


def load_workspaces(path: Path | None = None) -> list[WorkspaceGroup]:
    p = path or workspaces_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [
            WorkspaceGroup(name=str(item["name"]), commands=[str(c) for c in item.get("commands", []) if str(c).strip()])
            for item in raw
            if isinstance(item, dict) and item.get("name")
        ]
    except (FileNotFoundError, ValueError, KeyError):
        return []


def save_workspaces(groups: list[WorkspaceGroup], path: Path | None = None) -> None:
    p = path or workspaces_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = [{"name": g.name, "commands": g.commands} for g in groups]
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def launch_workspace(name: str, path: Path | None = None) -> tuple[bool, str]:
    """Launch all commands in the named workspace group detached in the background."""
    groups = load_workspaces(path)
    target = next((g for g in groups if g.name.lower() == name.strip().lower()), None)
    if not target:
        return False, f"Workspace '{name}' not found"
    if not target.commands:
        return False, f"Workspace '{target.name}' has no commands"

    launched = 0
    errors = []
    for cmd in target.commands:
        try:
            args = shlex.split(cmd)
            if not args:
                continue
            subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            launched += 1
        except Exception as err:
            errors.append(f"{cmd}: {err}")

    if errors and launched == 0:
        return False, "; ".join(errors)
    msg = f"Launched {launched} app(s) for '{target.name}'"
    if errors:
        msg += f" ({len(errors)} failed)"
    return True, msg
