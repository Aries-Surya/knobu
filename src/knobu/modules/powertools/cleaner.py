"""Safe system cache cleaner and apt package uninstaller."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess

_PKG_RE = re.compile(r"^[a-z0-9][a-z0-9+.\-:]+$")


@dataclass(frozen=True)
class CleanupTarget:
    id: str
    name: str
    description: str
    size_bytes: int
    requires_admin: bool = False


@dataclass(frozen=True)
class PackageInfo:
    name: str
    size_kb: int
    summary: str


def format_bytes(n: int) -> str:
    value = float(max(0, n))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"


def dir_size(path: Path) -> int:
    """Safely sum file sizes under `path`, skipping symlinks and unreadable entries."""
    if not path.exists():
        return 0
    if path.is_file() and not path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    stack = [path]
    while stack:
        curr = stack.pop()
        try:
            with os.scandir(curr) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _clear_directory_contents(root: Path, exclude: set[str] = frozenset()) -> tuple[int, int]:
    """Delete files/subdirs inside `root`, returning (freed_bytes, skipped_count)."""
    if not root.is_dir():
        return 0, 0
    freed = 0
    skipped = 0
    try:
        entries = list(os.scandir(root))
    except OSError:
        return 0, 1

    for entry in entries:
        if entry.name in exclude:
            continue
        p = Path(entry.path)
        size = dir_size(p)
        try:
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(p)
            else:
                p.unlink()
            freed += size
        except OSError:
            skipped += 1
    return freed, skipped


def _apt_archives_size(apt_dir: Path = Path("/var/cache/apt/archives")) -> int:
    if not apt_dir.is_dir():
        return 0
    total = 0
    try:
        for entry in os.scandir(apt_dir):
            if entry.name.endswith(".deb") and entry.is_file(follow_symlinks=False):
                try:
                    total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def scan_cleanup_targets(
    home: Path | None = None,
    var_crash: Path = Path("/var/crash"),
    apt_archives: Path = Path("/var/cache/apt/archives"),
) -> list[CleanupTarget]:
    """Measure reclaimable space across safe user and system cleanup targets."""
    base = home or Path.home()
    cache_dir = base / ".cache"
    thumbs_dir = cache_dir / "thumbnails"
    user_crash = base / ".local" / "share" / "systemd" / "coredump"

    # Compute app cache excluding thumbnails so the user can clean thumbnails independently.
    thumbs_size = dir_size(thumbs_dir)
    app_cache_size = max(0, dir_size(cache_dir) - thumbs_size)
    crash_size = dir_size(var_crash) + dir_size(user_crash)
    apt_size = _apt_archives_size(apt_archives)

    return [
        CleanupTarget(
            "thumbnails",
            "Thumbnail Cache",
            "Cached image/video previews (~/.cache/thumbnails)",
            thumbs_size,
            requires_admin=False,
        ),
        CleanupTarget(
            "user_cache",
            "User Application Cache",
            "Temporary application caches in ~/.cache",
            app_cache_size,
            requires_admin=False,
        ),
        CleanupTarget(
            "crash_dumps",
            "Crash Reports and Core Dumps",
            "Crash logs in /var/crash and systemd coredumps",
            crash_size,
            requires_admin=var_crash.exists() and any(var_crash.iterdir()) if var_crash.is_dir() else False,
        ),
        CleanupTarget(
            "apt_cache",
            "APT Package Cache",
            "Downloaded .deb installers in /var/cache/apt/archives",
            apt_size,
            requires_admin=True,
        ),
    ]


def clean_target(
    target_id: str,
    home: Path | None = None,
    var_crash: Path = Path("/var/crash"),
) -> tuple[bool, str, int]:
    """Execute cleanup for one target_id. Returns (ok, message, freed_bytes)."""
    base = home or Path.home()
    cache_dir = base / ".cache"

    if target_id == "thumbnails":
        freed, skipped = _clear_directory_contents(cache_dir / "thumbnails")
        return True, f"Freed {format_bytes(freed)} from thumbnail cache.", freed

    if target_id == "user_cache":
        # Keep active runtime/mesa/thumbnails if desired; skip thumbnails so each button matches its scope.
        freed, skipped = _clear_directory_contents(cache_dir, exclude={"thumbnails"})
        note = f" ({skipped} locked items skipped)" if skipped else ""
        return True, f"Freed {format_bytes(freed)} from application cache{note}.", freed

    if target_id == "crash_dumps":
        freed_user, _ = _clear_directory_contents(base / ".local" / "share" / "systemd" / "coredump")
        var_size = dir_size(var_crash)
        if var_size > 0:
            if not shutil.which("pkexec"):
                return False, "pkexec not found to clear /var/crash.", freed_user
            r = subprocess.run(
                ["pkexec", "sh", "-c", "rm -f /var/crash/*.crash /var/crash/*.upload /var/crash/*.uploaded"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if r.returncode != 0:
                return False, r.stderr.strip() or "Failed clearing /var/crash.", freed_user
        total = freed_user + var_size
        return True, f"Cleared {format_bytes(total)} of crash reports.", total

    if target_id == "apt_cache":
        before = _apt_archives_size()
        if not shutil.which("pkexec"):
            return False, "pkexec not found to run apt-get clean.", 0
        r = subprocess.run(
            ["pkexec", "apt-get", "clean"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if r.returncode != 0:
            return False, r.stderr.strip() or "apt-get clean failed.", 0
        after = _apt_archives_size()
        freed = max(0, before - after)
        return True, f"Cleaned APT cache ({format_bytes(freed)} freed).", freed

    return False, f"Unknown cleanup target: {target_id}", 0


def list_installed_packages(query: str = "", limit: int = 80) -> list[PackageInfo]:
    """List manually installed APT packages, optionally filtered by substring."""
    try:
        manual = subprocess.run(
            ["apt-mark", "showmanual"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        manual_set = {line.strip() for line in manual.stdout.splitlines() if line.strip()} if manual.returncode == 0 else set()
        dpkg = subprocess.run(
            ["dpkg-query", "-W", "-f=${Package}\t${Installed-Size}\t${binary:Summary}\n"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if dpkg.returncode != 0:
            return []
    except (OSError, subprocess.TimeoutExpired):
        return []

    q = query.strip().lower()
    packages: list[PackageInfo] = []
    for line in dpkg.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        if manual_set and name not in manual_set:
            continue
        summary = parts[2].strip() if len(parts) > 2 else ""
        if q and q not in name.lower() and q not in summary.lower():
            continue
        try:
            size_kb = int(parts[1])
        except ValueError:
            size_kb = 0
        packages.append(PackageInfo(name, size_kb, summary))

    packages.sort(key=lambda p: (-p.size_kb, p.name))
    return packages[:limit]


def uninstall_package(package: str) -> tuple[bool, str]:
    """Uninstall an APT package via pkexec."""
    if not _PKG_RE.fullmatch(package):
        return False, f"Invalid package name: {package}"
    if not shutil.which("pkexec"):
        return False, "pkexec not found."
    try:
        r = subprocess.run(
            ["pkexec", "apt-get", "remove", "-y", package],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if r.returncode == 0:
            return True, f"Uninstalled {package}."
        return False, r.stderr.strip() or f"Failed to uninstall {package}."
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)
