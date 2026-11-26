"""File Locksmith: find processes holding open handles on a file or directory via /proc."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class FileLock:
    pid: int
    process: str
    fd: str
    path: str


def _proc_name(pid_dir: Path) -> str:
    try:
        return (pid_dir / "comm").read_text(encoding="utf-8", errors="replace").strip() or pid_dir.name
    except OSError:
        return pid_dir.name


def _matches_target(fd_target: str, resolved_target: str, is_dir: bool) -> bool:
    if fd_target == resolved_target:
        return True
    if is_dir and fd_target.startswith(resolved_target.rstrip("/") + "/"):
        return True
    return False


def find_file_locks(target: Path, proc_root: Path = Path("/proc")) -> list[FileLock]:
    """Scan /proc/*/fd symlinks to identify processes locking `target`."""
    try:
        resolved = str(target.resolve())
    except OSError:
        resolved = str(target)
    is_dir = target.is_dir()

    locks: list[FileLock] = []
    seen_pids: set[int] = set()

    try:
        proc_entries = list(os.scandir(proc_root))
    except OSError:
        return []

    for entry in proc_entries:
        if not entry.name.isdigit() or not entry.is_dir(follow_symlinks=False):
            continue
        pid = int(entry.name)
        pid_dir = Path(entry.path)
        fd_dir = pid_dir / "fd"
        try:
            fds = list(os.scandir(fd_dir))
        except OSError:
            continue

        for fd_entry in fds:
            try:
                link = os.readlink(fd_entry.path)
            except OSError:
                continue
            if _matches_target(link, resolved, is_dir):
                if pid not in seen_pids:
                    seen_pids.add(pid)
                    locks.append(FileLock(pid=pid, process=_proc_name(pid_dir), fd=fd_entry.name, path=link))
                break

    locks.sort(key=lambda lk: (lk.process.lower(), lk.pid))
    return locks
