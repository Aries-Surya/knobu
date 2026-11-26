"""Listening TCP/UDP port inspection via `ss` and safe process termination."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import shutil
import signal
import subprocess

_USERS_RE = re.compile(r'\("([^"]+)",pid=(\d+)')


@dataclass(frozen=True)
class PortEntry:
    proto: str
    address: str
    port: int
    process: str
    pid: int | None


def _split_addr_port(endpoint: str) -> tuple[str, int | None]:
    idx = endpoint.rfind(":")
    if idx == -1:
        return endpoint, None
    addr = endpoint[:idx]
    if addr.startswith("[") and addr.endswith("]"):
        addr = addr[1:-1]
    try:
        return addr, int(endpoint[idx + 1:])
    except ValueError:
        return endpoint, None


def parse_ss_output(text: str) -> list[PortEntry]:
    """Parse `ss -tulpnH` output into sorted unique PortEntry items."""
    entries: list[PortEntry] = []
    seen: set[tuple[str, str, int, int | None]] = set()

    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].lower() == "netid":
            continue
        proto = parts[0].lower()
        local = parts[4]
        addr, port = _split_addr_port(local)
        if port is None:
            continue

        proc_col = " ".join(parts[6:]) if len(parts) > 6 else ""
        matches = _USERS_RE.findall(proc_col)
        if matches:
            for name, pid_str in matches:
                pid = int(pid_str)
                key = (proto, addr, port, pid)
                if key not in seen:
                    seen.add(key)
                    entries.append(PortEntry(proto, addr, port, name, pid))
        else:
            key = (proto, addr, port, None)
            if key not in seen:
                seen.add(key)
                entries.append(PortEntry(proto, addr, port, "system", None))

    entries.sort(key=lambda e: (e.port, e.proto, e.process))
    return entries


def list_listening_ports() -> list[PortEntry]:
    """Return active listening TCP and UDP ports on this host."""
    try:
        r = subprocess.run(
            ["ss", "-tulpnH"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode != 0:
            return []
        return parse_ss_output(r.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return []


def kill_process(pid: int, force: bool = False) -> tuple[bool, str]:
    """Terminate a process by PID; escalates via pkexec only when needed."""
    if pid <= 1:
        return False, "Refusing to terminate system PID."
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
        return True, f"Sent {sig.name} to PID {pid}."
    except ProcessLookupError:
        return True, f"PID {pid} has already exited."
    except PermissionError:
        if not shutil.which("pkexec"):
            return False, f"Permission denied terminating PID {pid}."
        try:
            r = subprocess.run(
                ["pkexec", "kill", f"-{int(sig)}", str(pid)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if r.returncode == 0:
                return True, f"Terminated PID {pid} as administrator."
            return False, (r.stderr.strip() or f"Failed to terminate PID {pid}.")
        except (OSError, subprocess.TimeoutExpired) as err:
            return False, str(err)
