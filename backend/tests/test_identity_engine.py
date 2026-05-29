"""Golden-file tests for the deterministic name_key canonicalizer (F2.1)."""
import json
from pathlib import Path

import pytest

from backend.coauthorship.identity import name_key

GOLDEN = json.loads(
    (Path(__file__).parent / "fixtures" / "name_key_golden.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: c["input"])
def test_name_key_golden(case):
    assert name_key(case["input"]) == case["name_key"]


def test_name_key_empty():
    assert name_key("") == ""
    assert name_key("   ") == ""


def test_name_key_idempotent():
    # Running name_key on a surface form reconstructed from a key should still
    # produce that key.
    for case in GOLDEN[:10]:
        k = case["name_key"]
        if "_" in k:
            last, first = k.split("_", 1)
            surface = f"{first.title()} {last.title()}" if first else last.title()
            assert name_key(surface) == k


def test_name_key_pure():
    # Same input -> same output, no global state.
    for _ in range(3):
        assert name_key("Dr. John A. Smith Jr.") == "smith_john"


def test_name_key_handles_unicode_without_crashing():
    # Hangul/Han must not raise and must place the family name first.
    assert name_key("김 민준") == "김_민준"  # 김 민준
    assert name_key("李 明") == "李_明"  # 李 明
