"""Local cron daemon status and user crontab list/add/toggle/remove helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess

SPECIAL_SCHEDULES = {"@reboot", "@yearly", "@annually", "@monthly", "@weekly", "@daily", "@midnight", "@hourly"}
CRON_LINE_RE = re.compile(r"^(@\w+|\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+(.+)$")


@dataclass
class CronJob:
    schedule: str
    command: str
    comment: str = ""
    enabled: bool = True
    raw_line: str = ""


def is_valid_schedule(schedule: str) -> bool:
    s = schedule.strip()
    if s.lower() in SPECIAL_SCHEDULES:
        return True
    parts = s.split()
    return len(parts) == 5


def cron_service_status() -> tuple[bool, str]:
    """Check whether local cron/crond daemon is running."""
    if shutil.which("systemctl"):
        for unit in ("cron", "crond"):
            r = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=2, check=False)
            state = r.stdout.strip()
            if state == "active":
                return True, f"{unit}.service active"
    if shutil.which("pgrep"):
        r = subprocess.run(["pgrep", "-x", "cron"], capture_output=True, text=True, timeout=2, check=False)
        if r.returncode == 0:
            return True, "cron process running"
    return False, "cron service inactive"


def parse_crontab(text: str) -> list[CronJob]:
    """Parse crontab text into CronJob entries, preserving preceding comments."""
    jobs: list[CronJob] = []
    pending_comment = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            pending_comment = ""
            continue
        if line.startswith("#DISABLED# "):
            inner = line[len("#DISABLED# "):].strip()
            m = CRON_LINE_RE.match(inner)
            if m:
                jobs.append(CronJob(
                    schedule=m.group(1),
                    command=m.group(2).strip(),
                    comment=pending_comment,
                    enabled=False,
                    raw_line=raw,
                ))
                pending_comment = ""
                continue
        if line.startswith("#"):
            pending_comment = line.lstrip("# ").strip()
            continue
        if "=" in line and not line.startswith("@") and not CRON_LINE_RE.match(line):
            pending_comment = ""
            continue
        m = CRON_LINE_RE.match(line)
        if m:
            jobs.append(CronJob(
                schedule=m.group(1),
                command=m.group(2).strip(),
                comment=pending_comment,
                enabled=True,
                raw_line=raw,
            ))
            pending_comment = ""
    return jobs


def read_raw_crontab() -> str:
    if not shutil.which("crontab"):
        return ""
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=3, check=False)
    return r.stdout if r.returncode == 0 else ""


def write_raw_crontab(text: str) -> tuple[bool, str]:
    if not shutil.which("crontab"):
        return False, "crontab command not found"
    content = text.rstrip("\n") + "\n" if text.strip() else ""
    r = subprocess.run(["crontab", "-"], input=content, capture_output=True, text=True, timeout=3, check=False)
    if r.returncode == 0:
        return True, "Crontab updated"
    return False, r.stderr.strip() or "Failed to update crontab"


def list_cron_jobs() -> list[CronJob]:
    return parse_crontab(read_raw_crontab())


def add_cron_job(schedule: str, command: str, comment: str = "") -> tuple[bool, str]:
    sched = schedule.strip()
    cmd = command.strip()
    if not is_valid_schedule(sched):
        return False, "Invalid schedule (use 5 fields like '0 12 * * *' or '@daily')"
    if not cmd:
        return False, "Command cannot be empty"
    raw = read_raw_crontab().rstrip("\n")
    lines = raw.splitlines() if raw else []
    if comment.strip():
        lines.append(f"# {comment.strip()}")
    lines.append(f"{sched} {cmd}")
    return write_raw_crontab("\n".join(lines))


def toggle_cron_job(index: int) -> tuple[bool, str]:
    raw = read_raw_crontab()
    jobs = parse_crontab(raw)
    if not (0 <= index < len(jobs)):
        return False, "Cron job not found"
    target = jobs[index]
    lines = raw.splitlines()
    for i, ln in enumerate(lines):
        if ln == target.raw_line:
            if target.enabled:
                lines[i] = f"#DISABLED# {ln.strip()}"
            else:
                lines[i] = ln.strip()[len("#DISABLED# "):].strip()
            return write_raw_crontab("\n".join(lines))
    return False, "Matching crontab line not found"


def remove_cron_job(index: int) -> tuple[bool, str]:
    raw = read_raw_crontab()
    jobs = parse_crontab(raw)
    if not (0 <= index < len(jobs)):
        return False, "Cron job not found"
    target = jobs[index]
    lines = raw.splitlines()
    for i, ln in enumerate(lines):
        if ln == target.raw_line:
            lines.pop(i)
            return write_raw_crontab("\n".join(lines))
    return False, "Matching crontab line not found"
