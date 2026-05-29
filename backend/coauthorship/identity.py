"""Author identity engine — deterministic, pure-Python.

Public API:
- name_key(surface_form: str) -> str
"""
from __future__ import annotations

import re
import unicodedata

_STRIP_PARTS = {
    "dr", "dr.", "prof", "prof.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.",
    "phd", "ph.d", "md", "m.d", "jr", "jr.", "sr", "sr.", "iii", "iv", "ii",
}
_PARTICLES = {
    "van", "der", "den", "de", "du", "la", "del", "da", "dos",
    "el", "al", "von", "di",
}


def _strip_diacritics(s: str) -> str:
    # Decompose, drop combining marks, then RE-COMPOSE (NFC). The final NFC is
    # essential for Hangul: NFD splits syllables (e.g. 김) into conjoining jamo
    # which would otherwise defeat East-Asian surname detection. Latin letters
    # are unaffected (José -> Jose either way).
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
    )
    return unicodedata.normalize("NFC", stripped)


def _tokenize(surface: str) -> list[str]:
    return [t for t in re.split(r"\s+", surface.strip()) if t]


def _alpha_lower(tok: str) -> str:
    return "".join(ch for ch in tok if ch.isalpha() or ch == "-").lower()


def _is_cjk_char(ch: str) -> bool:
    """True for Han ideographs (CJK Unified + Ext-A + Compatibility) and
    Hangul syllables — scripts that order the family name first."""
    return (
        "㐀" <= ch <= "鿿"   # CJK Unified Ideographs (+ Ext-A)
        or "豈" <= ch <= "﫿"  # CJK Compatibility Ideographs
        or "가" <= ch <= "힣"  # Hangul syllables
    )


def _is_cjk_token(tok: str) -> bool:
    letters = [c for c in tok if c.isalpha()]
    return bool(letters) and all(_is_cjk_char(c) for c in letters)


def name_key(surface_form: str) -> str:
    """Canonical fingerprint. Deterministic. Empty input -> empty string."""
    if not surface_form or not surface_form.strip():
        return ""

    s = _strip_diacritics(surface_form)
    inverted = "," in s
    if inverted:
        left, right = s.split(",", 1)
        toks_last = _tokenize(left)
        toks_first = _tokenize(right)
        # "John Smith, PhD" / "John Smith, Jr." are NOT "Last, First" — the
        # comma only fences off a suffix/title. If the right side is empty
        # once suffixes are stripped, reparse the left side as a normal name.
        right_meaningful = [
            t for t in toks_first if t.rstrip(".").lower() not in _STRIP_PARTS
        ]
        if not right_meaningful and len(toks_last) > 1:
            inverted = False
            s = left

    if not inverted:
        toks = _tokenize(s)
        toks = [t for t in toks if t.rstrip(".").lower() not in _STRIP_PARTS]
        if not toks:
            return ""
        if len(toks) >= 2 and all(_is_cjk_token(t) for t in toks):
            # East-Asian order: family name first. "李 明" -> last=李, first=明.
            toks_last = [toks[0]]
            toks_first = toks[1:]
        else:
            toks_last = [toks[-1]]
            toks_first = toks[:-1]
            while toks_first and toks_first[-1].lower().rstrip(".") in _PARTICLES:
                toks_last.insert(0, toks_first.pop())

    toks_last = [t for t in toks_last if t.rstrip(".").lower() not in _STRIP_PARTS]
    toks_first = [t for t in toks_first if t.rstrip(".").lower() not in _STRIP_PARTS]

    if not toks_last:
        return ""

    last = "".join(_alpha_lower(t) for t in toks_last) or toks_last[0].lower()

    first = ""
    for t in toks_first:
        cleaned = _alpha_lower(t).rstrip(".")
        if len(cleaned) >= 2:
            first = cleaned
            break
    if not first and toks_first:
        cleaned = _alpha_lower(toks_first[0])
        first = cleaned[:1] if cleaned else ""

    return f"{last}_{first}"
