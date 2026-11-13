"""Clipboard storage, URL sanitization, image handling, and paste simulation for Knobu."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sqlite3
import struct
import subprocess
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from evdev import UInput
from evdev import ecodes as e

log = logging.getLogger("knobu.clipboard")

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid", "mc_eid", "si", "igshid",
    "srsltid", "yclid", "zanpid", "ref_src",
}

PASSWORD_HINT_TYPES = {
    "x-kde-passwordmanagerhint",
    "application/x-keepassxc-metadata",
    "text/x-password",
    "application/x-secret",
}


def clean_url(url: str) -> str:
    """Strip known tracking parameters from HTTP/HTTPS URLs."""
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return url
    try:
        parsed = urllib.parse.urlsplit(url)
        if not parsed.query:
            return url
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        cleaned_pairs = [
            (k, v) for k, v in query_pairs
            if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
        ]
        new_query = urllib.parse.urlencode(cleaned_pairs)
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
        )
    except Exception:
        return url


def parse_image_dimensions(data: bytes) -> tuple[int, int] | None:
    """Extract width and height from PNG or JPEG headers without loading libraries."""
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        try:
            return struct.unpack(">II", data[16:24])
        except Exception:
            pass
    return None


@dataclass
class Clip:
    id: int
    kind: str  # 'text' or 'image'
    content: str
    preview: str
    timestamp: float
    pinned: bool = False

    @property
    def formatted_time(self) -> str:
        return time.strftime("%-I:%M %p", time.localtime(self.timestamp))


class ClipboardStorage:
    def __init__(self, db_path: Path | None = None, images_dir: Path | None = None):
        data_dir = Path.home() / ".local" / "share" / "knobu"
        if db_path is None:
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "clipboard.db"
        if images_dir is None:
            images_dir = data_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.images_dir = images_dir
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    preview TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    pinned INTEGER DEFAULT 0
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clips_ts ON clips(timestamp DESC)")

    def add_clip(self, content: str, kind: str = "text", max_items: int = 50) -> Clip | None:
        content = content.strip() if kind == "text" else content
        if not content:
            return None

        preview = content.replace("\n", " ")[:120] if kind == "text" else content
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, content FROM clips WHERE kind = ? ORDER BY timestamp DESC LIMIT 1", (kind,))
            last = cur.fetchone()
            if last and last[1] == content:
                cur.execute("UPDATE clips SET timestamp = ? WHERE id = ?", (now, last[0]))
                conn.commit()
                return Clip(last[0], kind, content, preview, now, False)

            cur.execute(
                "INSERT INTO clips (kind, content, preview, timestamp, pinned) VALUES (?, ?, ?, ?, 0)",
                (kind, content, preview, now),
            )
            clip_id = cur.lastrowid
            self._trim(conn, max_items)
            conn.commit()
            return Clip(clip_id, kind, content, preview, now, False)

    def add_image_clip(self, image_bytes: bytes, max_items: int = 50) -> Clip | None:
        if not image_bytes:
            return None

        img_hash = hashlib.sha256(image_bytes).hexdigest()[:16]
        file_path = self.images_dir / f"clip_{img_hash}.png"
        if not file_path.exists():
            file_path.write_bytes(image_bytes)

        dims = parse_image_dimensions(image_bytes)
        preview = f"Image ({dims[0]}×{dims[1]})" if dims else "Image (PNG)"
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, content FROM clips WHERE kind = 'image' ORDER BY timestamp DESC LIMIT 1")
            last = cur.fetchone()
            if last and last[1] == str(file_path):
                cur.execute("UPDATE clips SET timestamp = ? WHERE id = ?", (now, last[0]))
                conn.commit()
                return Clip(last[0], "image", str(file_path), preview, now, False)

            cur.execute(
                "INSERT INTO clips (kind, content, preview, timestamp, pinned) VALUES ('image', ?, ?, ?, 0)",
                (str(file_path), preview, now),
            )
            clip_id = cur.lastrowid
            self._trim(conn, max_items)
            conn.commit()
            return Clip(clip_id, "image", str(file_path), preview, now, False)

    def _trim(self, conn: sqlite3.Connection, max_items: int) -> None:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, kind, content FROM clips WHERE pinned = 0 AND id NOT IN (
                SELECT id FROM clips ORDER BY timestamp DESC LIMIT ?
            )
            """,
            (max_items,),
        )
        to_delete = cur.fetchall()
        for cid, kind, content in to_delete:
            if kind == "image":
                try:
                    p = Path(content)
                    if p.exists() and p.is_file():
                        p.unlink()
                except OSError:
                    pass
            cur.execute("DELETE FROM clips WHERE id = ?", (cid,))

    def get_clips(self, search: str = "") -> list[Clip]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            if search.strip():
                term = f"%{search.strip()}%"
                cur.execute(
                    """
                    SELECT id, kind, content, preview, timestamp, pinned
                    FROM clips
                    WHERE content LIKE ? OR preview LIKE ?
                    ORDER BY pinned DESC, timestamp DESC
                    """,
                    (term, term),
                )
            else:
                cur.execute(
                    """
                    SELECT id, kind, content, preview, timestamp, pinned
                    FROM clips
                    ORDER BY pinned DESC, timestamp DESC
                    """
                )
            rows = cur.fetchall()
            return [Clip(r[0], r[1], r[2], r[3], r[4], bool(r[5])) for r in rows]

    def delete_clip(self, clip_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT kind, content FROM clips WHERE id = ?", (clip_id,))
            row = cur.fetchone()
            if row and row[0] == "image":
                try:
                    p = Path(row[1])
                    if p.exists() and p.is_file():
                        p.unlink()
                except OSError:
                    pass
            cur.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
            conn.commit()

    def toggle_pin(self, clip_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT pinned FROM clips WHERE id = ?", (clip_id,))
            row = cur.fetchone()
            if not row:
                return False
            new_pinned = 0 if row[0] else 1
            cur.execute("UPDATE clips SET pinned = ? WHERE id = ?", (new_pinned, clip_id))
            conn.commit()
            return bool(new_pinned)

    def clear_all(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT content FROM clips WHERE pinned = 0 AND kind = 'image'")
            for row in cur.fetchall():
                try:
                    p = Path(row[0])
                    if p.exists() and p.is_file():
                        p.unlink()
                except OSError:
                    pass
            cur.execute("DELETE FROM clips WHERE pinned = 0")
            conn.commit()

    def get_stats(self) -> dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), COALESCE(SUM(pinned), 0) FROM clips")
            row = cur.fetchone()
            total = row[0] or 0
            pinned = row[1] or 0
            cur.execute("SELECT COUNT(*) FROM clips WHERE kind = 'image'")
            images = cur.fetchone()[0] or 0
            return {"total": total, "pinned": pinned, "images": images}


def get_clipboard_types() -> list[str]:
    """Return available clipboard mime types on Wayland or X11."""
    if os.environ.get("WAYLAND_DISPLAY"):
        try:
            res = subprocess.run(["wl-paste", "--list-types"], capture_output=True, text=True, timeout=0.5)
            return [t.strip() for t in res.stdout.splitlines() if t.strip()]
        except Exception:
            pass
    try:
        res = subprocess.run(["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                             capture_output=True, text=True, timeout=0.5)
        return [t.strip() for t in res.stdout.splitlines() if t.strip()]
    except Exception:
        return []


def is_sensitive_clipboard(types: list[str]) -> bool:
    """Detect if clipboard content originates from a password manager or secret vault."""
    lower_types = {t.lower() for t in types}
    return bool(lower_types & PASSWORD_HINT_TYPES)


def get_clipboard() -> str:
    """Read current clipboard text using wl-paste or xclip."""
    if os.environ.get("WAYLAND_DISPLAY"):
        try:
            return subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                timeout=0.5,
            ).stdout
        except Exception:
            pass
    try:
        return subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True,
            text=True,
            timeout=0.5,
        ).stdout
    except Exception:
        return ""


def get_clipboard_image() -> bytes | None:
    """Read current clipboard image bytes if an image mime type is available."""
    types = get_clipboard_types()
    img_types = [t for t in types if t.startswith("image/")]
    if not img_types:
        return None

    target_type = "image/png" if "image/png" in img_types else img_types[0]

    if os.environ.get("WAYLAND_DISPLAY"):
        try:
            res = subprocess.run(["wl-paste", "--type", target_type], capture_output=True, timeout=1.0)
            if res.returncode == 0 and res.stdout:
                return res.stdout
        except Exception:
            pass
    try:
        res = subprocess.run(["xclip", "-selection", "clipboard", "-t", target_type, "-o"],
                             capture_output=True, timeout=1.0)
        if res.returncode == 0 and res.stdout:
            return res.stdout
    except Exception:
        pass
    return None


def set_clipboard(text: str) -> bool:
    """Set clipboard text using wl-copy or xclip."""
    if os.environ.get("WAYLAND_DISPLAY"):
        try:
            p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE, text=True)
            p.communicate(input=text)
            return p.returncode == 0
        except Exception:
            pass
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True)
        p.communicate(input=text)
        return p.returncode == 0
    except Exception:
        return False


def set_clipboard_image(image_path: str) -> bool:
    """Set clipboard content to an image file using wl-copy or xclip."""
    p = Path(image_path)
    if not p.exists() or not p.is_file():
        return False

    if os.environ.get("WAYLAND_DISPLAY"):
        try:
            with open(p, "rb") as f:
                res = subprocess.run(["wl-copy", "--type", "image/png"], stdin=f, timeout=1.0)
                return res.returncode == 0
        except Exception:
            pass
    try:
        res = subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-i", str(p)], timeout=1.0)
        return res.returncode == 0
    except Exception:
        return False


def simulate_paste() -> None:
    """Simulate Ctrl+V keystroke using evdev UInput."""
    time.sleep(0.12)  # Give time for the previously focused window to regain focus
    try:
        with UInput({e.EV_KEY: [e.KEY_LEFTCTRL, e.KEY_V]}, name="knobu-paste") as ui:
            ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)
            ui.write(e.EV_KEY, e.KEY_V, 1)
            ui.syn()
            time.sleep(0.02)
            ui.write(e.EV_KEY, e.KEY_V, 0)
            ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)
            ui.syn()
    except Exception:
        log.exception("Failed to simulate paste keystroke via UInput")
