"""Text normalization helpers for imported records."""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

import ftfy


_BLOCK_TAG_RE = re.compile(r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)
_BREAK_TAG_RE = re.compile(r"<\s*(br|/p|/div|/li)\b[^>]*>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_FOOTNOTE_SUP_RE = re.compile(
    r"<\s*(sup|sub)\b[^>]*>\s*(?:\*+|†+|‡+|§+|\[\d+\]|\d{1,3})\s*<\s*/\s*\1\s*>",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_import_text(value: str) -> str:
    """Normalize text imported from provider HTML before storing it.

    Pipeline:
    1. Fix mojibake / encoding errors (ftfy)
    2. Unicode NFC normalization
    3. Decode HTML entities
    4. Strip inline HTML and footnote markers
    5. Collapse whitespace
    """

    text = ftfy.fix_text(str(value))
    text = unicodedata.normalize("NFC", text)
    for _ in range(2):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped

    text = _BLOCK_TAG_RE.sub(" ", text)
    text = _FOOTNOTE_SUP_RE.sub("", text)
    text = _BREAK_TAG_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_import_value(value: Any) -> Any:
    """Recursively normalize imported string values while preserving shape."""

    if isinstance(value, str):
        return normalize_import_text(value)
    if isinstance(value, list):
        return [normalize_import_value(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_import_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_import_value(item) for key, item in value.items()}
    return value
