"""Text normalization helpers for imported records."""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any


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

    The goal is intentionally narrow: make imported labels readable in UKIP by
    decoding HTML entities, removing inline markup, and dropping common footnote
    markers such as ``<sup>*</sup>`` without changing the natural wording.
    """

    text = unicodedata.normalize("NFC", str(value))
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
