"""Safe system cache cleaner and apt package uninstaller."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

_PKG_RE = re.compile(r"^[a-zA-Z0-9@][a-zA-Z0-9+._:/@-]*$")


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
    source: str
    version: str = ""
    size_kb: int = 0
    summary: str = ""


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


def _run_cmd(cmd: list[str], timeout: int = 5) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _list_apt() -> list[PackageInfo]:
    if not shutil.which("dpkg-query"):
        return []
    manual_out = _run_cmd(["apt-mark", "showmanual"]) or ""
    manual_set = {ln.strip() for ln in manual_out.splitlines() if ln.strip()}
    dpkg_out = _run_cmd(["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Installed-Size}\t${binary:Summary}\n"])
    if not dpkg_out:
        return []
    items: list[PackageInfo] = []
    for line in dpkg_out.splitlines():
        parts = line.split("\t", 3)
        if len(parts) < 3:
            continue
        name, ver, size_s = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if manual_set and name not in manual_set:
            continue
        summary = parts[3].strip() if len(parts) > 3 else ""
        items.append(PackageInfo(name, "apt", ver, int(size_s) if size_s.isdigit() else 0, summary))
    return items


def _list_snap() -> list[PackageInfo]:
    if not shutil.which("snap"):
        return []
    out = _run_cmd(["snap", "list"])
    if not out:
        return []
    items: list[PackageInfo] = []
    for line in out.splitlines()[1:]:
        cols = line.split()
        if len(cols) >= 6:
            name, ver, _rev, track, pub, notes = cols[0], cols[1], cols[2], cols[3], cols[4], " ".join(cols[5:])
            items.append(PackageInfo(name, "snap", ver, 0, f"{pub} ({track}) {notes}".strip()))
    return items


def _list_flatpak() -> list[PackageInfo]:
    if not shutil.which("flatpak"):
        return []
    out = _run_cmd(["flatpak", "list", "--app", "--columns=application,name,version"])
    if not out:
        return []
    items: list[PackageInfo] = []
    for line in out.splitlines():
        cols = line.split("\t")
        if cols and cols[0].strip():
            app_id = cols[0].strip()
            title = cols[1].strip() if len(cols) > 1 else ""
            ver = cols[2].strip() if len(cols) > 2 else ""
            items.append(PackageInfo(app_id, "flatpak", ver, 0, title))
    return items


def _list_brew() -> list[PackageInfo]:
    if not shutil.which("brew"):
        return []
    out = _run_cmd(["brew", "list", "--versions"], timeout=10)
    if not out:
        return []
    items: list[PackageInfo] = []
    for line in out.splitlines():
        cols = line.split()
        if cols:
            items.append(PackageInfo(cols[0], "brew", " ".join(cols[1:]), 0, "Homebrew formula/cask"))
    return items


def _list_pipx() -> list[PackageInfo]:
    if not shutil.which("pipx"):
        return []
    out = _run_cmd(["pipx", "list", "--short"])
    if not out:
        return []
    items: list[PackageInfo] = []
    for line in out.splitlines():
        cols = line.split()
        if cols:
            items.append(PackageInfo(cols[0], "pipx", cols[1] if len(cols) > 1 else "", 0, "Python CLI tool (pipx)"))
    return items


def _list_npm() -> list[PackageInfo]:
    if not shutil.which("npm"):
        return []
    out = _run_cmd(["npm", "list", "-g", "--depth=0", "--json"], timeout=8)
    if not out:
        return []
    try:
        deps = json.loads(out).get("dependencies", {})
    except ValueError:
        return []
    return [
        PackageInfo(name, "npm", str(info.get("version", "")), 0, "Global Node.js package")
        for name, info in deps.items() if isinstance(info, dict)
    ]


def _list_cargo() -> list[PackageInfo]:
    if not shutil.which("cargo"):
        return []
    out = _run_cmd(["cargo", "install", "--list"])
    if not out:
        return []
    items: list[PackageInfo] = []
    for line in out.splitlines():
        if not line.startswith(" ") and line.endswith(":"):
            cols = line[:-1].split()
            if cols:
                items.append(PackageInfo(cols[0], "cargo", cols[1].lstrip("v") if len(cols) > 1 else "", 0, "Rust crate binary"))
    return items


_PACKAGE_SOURCES = {
    "apt": ("dpkg-query", _list_apt, ["pkexec", "apt-get", "remove", "-y"]),
    "snap": ("snap", _list_snap, ["pkexec", "snap", "remove"]),
    "flatpak": ("flatpak", _list_flatpak, ["flatpak", "uninstall", "-y"]),
    "brew": ("brew", _list_brew, ["brew", "uninstall"]),
    "pipx": ("pipx", _list_pipx, ["pipx", "uninstall"]),
    "npm": ("npm", _list_npm, ["npm", "uninstall", "-g"]),
    "cargo": ("cargo", _list_cargo, ["cargo", "uninstall"]),
}


def available_package_sources() -> list[str]:
    """Return all supported Linux package managers detected on this system."""
    return [src for src, (binary, _, _) in _PACKAGE_SOURCES.items() if shutil.which(binary)]


def list_installed_packages(query: str = "", source: str = "all", limit: int = 80) -> list[PackageInfo]:
    """List installed packages across all detected Linux sources, filtered by query/source."""
    q = query.strip().lower()
    src_filter = source.strip().lower()
    packages: list[PackageInfo] = []

    for src, (_, lister, _) in _PACKAGE_SOURCES.items():
        if src_filter != "all" and src != src_filter:
            continue
        for pkg in lister():
            if q and q not in pkg.name.lower() and q not in pkg.summary.lower() and q not in pkg.source:
                continue
            packages.append(pkg)

    packages.sort(key=lambda p: (0 if p.source != "apt" else 1, -p.size_kb, p.name))
    return packages[:limit]


def uninstall_package(package: str, source: str = "apt") -> tuple[bool, str]:
    """Uninstall a package from the specified Linux package manager."""
    if not _PKG_RE.fullmatch(package) or ".." in package:
        return False, f"Invalid package name: {package}"
    spec = _PACKAGE_SOURCES.get(source.lower())
    if not spec:
        return False, f"Unsupported package source: {source}"
    cmd_prefix = spec[2]
    if not shutil.which(cmd_prefix[0]):
        return False, f"{cmd_prefix[0]} not found."
    try:
        r = subprocess.run(
            [*cmd_prefix, package],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if r.returncode == 0:
            return True, f"Uninstalled {package} ({source})."
        return False, r.stderr.strip() or f"Failed to uninstall {package}."
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)
