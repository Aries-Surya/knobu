"""SQLite notification history store for Knobu's Mac-style Notification Center."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import threading
import time

DEFAULT_DB_PATH = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "knobu" / "notifications.db"
MAX_NOTIFICATIONS = 100


@dataclass(frozen=True)
class NotificationRecord:
    id: int
    app_name: str
    summary: str
    body: str
    icon: str
    timestamp: float


class NotificationHistory:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=5)

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    body TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.commit()

    def add(self, app_name: str, summary: str, body: str = "", icon: str = "",
            ts: float | None = None) -> NotificationRecord:
        now = time.time() if ts is None else ts
        with self._lock, closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO notifications (app_name, summary, body, icon, timestamp) VALUES (?, ?, ?, ?, ?)",
                (app_name, summary, body, icon, now),
            )
            nid = int(cur.lastrowid or 0)
            conn.execute(
                "DELETE FROM notifications WHERE id NOT IN (SELECT id FROM notifications ORDER BY id DESC LIMIT ?)",
                (MAX_NOTIFICATIONS,),
            )
            conn.commit()
        return NotificationRecord(nid, app_name, summary, body, icon, now)

    def list_recent(self, limit: int = 30) -> list[NotificationRecord]:
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, app_name, summary, body, icon, timestamp FROM notifications ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [NotificationRecord(*r) for r in rows]

    def count(self) -> int:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()
        return int(row[0]) if row else 0

    def clear(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute("DELETE FROM notifications")
            conn.commit()
