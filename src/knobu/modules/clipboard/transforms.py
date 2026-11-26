"""Clipboard text transforms for Advanced Paste in Knobu."""

from __future__ import annotations

import base64
import json
import re
from urllib.parse import unquote

TRANSFORMS: list[tuple[str, str]] = [
    ("json_pretty", "Format JSON"),
    ("plain", "Strip Formatting / Plain"),
    ("base64_encode", "Base64 Encode"),
    ("base64_decode", "Base64 Decode"),
    ("url_decode", "URL Decode"),
    ("snake_case", "snake_case"),
    ("camel_case", "camelCase"),
    ("upper", "UPPERCASE"),
    ("lower", "lowercase"),
]


def _words(text: str) -> list[str]:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text.strip())
    return [w for w in re.split(r"[^a-zA-Z0-9]+", s) if w]


def transform_text(text: str, mode: str) -> tuple[bool, str]:
    """Apply a named Advanced Paste transform to text. Returns (ok, result_or_error)."""
    if mode == "json_pretty":
        try:
            obj = json.loads(text)
            return True, json.dumps(obj, indent=2, ensure_ascii=False)
        except Exception as err:
            return False, f"Invalid JSON: {err}"

    if mode == "plain":
        cleaned = re.sub(r"<[^>]+>", "", text)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        return True, "\n".join(ln.strip() for ln in cleaned.splitlines()).strip()

    if mode == "base64_encode":
        return True, base64.b64encode(text.encode("utf-8")).decode("ascii")

    if mode == "base64_decode":
        try:
            raw = base64.b64decode(text.strip(), validate=True)
            return True, raw.decode("utf-8")
        except Exception as err:
            return False, f"Invalid Base64: {err}"

    if mode == "url_decode":
        return True, unquote(text)

    if mode == "snake_case":
        words = _words(text)
        return True, "_".join(w.lower() for w in words) if words else text

    if mode == "camel_case":
        words = _words(text)
        if not words:
            return True, text
        return True, words[0].lower() + "".join(w.capitalize() for w in words[1:])

    if mode == "upper":
        return True, text.upper()

    if mode == "lower":
        return True, text.lower()

    return False, f"Unknown transform: {mode}"
