"""Safe visual editor and parser for /etc/hosts."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from pathlib import Path
import re
import shutil
import subprocess

HOSTS_PATH = Path("/etc/hosts")
BACKUP_PATH = Path.home() / ".local" / "share" / "knobu" / "hosts.bak"
_HOST_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


@dataclass
class HostEntry:
    ip: str
    hosts: list[str]
    comment: str = ""
    enabled: bool = True


def validate_host_entry(ip: str, hosts: list[str]) -> str | None:
    """Return None if IP and hostnames are valid, else a descriptive error string."""
    try:
        ipaddress.ip_address(ip.strip())
    except ValueError:
        return f"Invalid IP address: {ip!r}"
    clean_hosts = [h.strip() for h in hosts if h.strip()]
    if not clean_hosts:
        return "At least one hostname is required."
    for h in clean_hosts:
        if not _HOST_RE.fullmatch(h):
            return f"Invalid hostname: {h!r}"
    return None


def _try_parse_mapping(body: str) -> tuple[str, list[str], str] | None:
    comment = ""
    if "#" in body:
        body, comment = body.split("#", 1)
        comment = comment.strip()
    tokens = body.split()
    if len(tokens) < 2:
        return None
    if validate_host_entry(tokens[0], tokens[1:]) is not None:
        return None
    return tokens[0], tokens[1:], comment


def parse_hosts(text: str) -> tuple[list[HostEntry], list[str]]:
    """Split /etc/hosts into managed HostEntry rows and preserved header/other comment lines."""
    entries: list[HostEntry] = []
    preserved: list[str] = []

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            parsed = _try_parse_mapping(stripped[1:].strip())
            if parsed:
                ip, hosts, comment = parsed
                entries.append(HostEntry(ip=ip, hosts=hosts, comment=comment, enabled=False))
            else:
                preserved.append(raw)
            continue

        parsed = _try_parse_mapping(stripped)
        if parsed:
            ip, hosts, comment = parsed
            entries.append(HostEntry(ip=ip, hosts=hosts, comment=comment, enabled=True))
        else:
            preserved.append(raw)

    return entries, preserved


def render_hosts(entries: list[HostEntry], preserved: list[str] = ()) -> str:
    lines = list(preserved)
    if lines and lines[-1].strip():
        lines.append("")
    for e in entries:
        if validate_host_entry(e.ip, e.hosts) is not None:
            continue
        prefix = "" if e.enabled else "# "
        comment = f"  # {e.comment}" if e.comment else ""
        lines.append(f"{prefix}{e.ip}\t{' '.join(e.hosts)}{comment}")
    return "\n".join(lines) + "\n"


def load_hosts(path: Path = HOSTS_PATH) -> tuple[list[HostEntry], list[str]]:
    if not path.is_file():
        return [], []
    return parse_hosts(path.read_text(encoding="utf-8", errors="replace"))


def save_hosts(
    entries: list[HostEntry],
    preserved: list[str] = (),
    path: Path = HOSTS_PATH,
    backup_path: Path = BACKUP_PATH,
) -> tuple[bool, str]:
    """Backup current hosts file and write updated entries (uses pkexec when root-owned)."""
    for e in entries:
        err = validate_host_entry(e.ip, e.hosts)
        if err:
            return False, err

    rendered = render_hosts(entries, preserved)
    if path.is_file():
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        except OSError:
            pass

    try:
        path.write_text(rendered, encoding="utf-8")
        return True, f"Saved {len(entries)} entry/entries to {path}."
    except PermissionError:
        if not shutil.which("pkexec"):
            return False, f"Permission denied writing {path} (pkexec not found)."
        try:
            r = subprocess.run(
                ["pkexec", "tee", str(path)],
                input=rendered,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if r.returncode == 0:
                return True, f"Saved {len(entries)} entry/entries to {path}."
            return False, r.stderr.strip() or f"Failed writing {path}."
        except (OSError, subprocess.TimeoutExpired) as err:
            return False, str(err)
