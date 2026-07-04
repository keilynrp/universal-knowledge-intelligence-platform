"""ORCID expanded-search parsing → candidates carry the researcher NAME.

Regression guard for the bug where candidates' canonical_label was the bare
ORCID id (the plain /search/ endpoint returns no name), scoring ~0 on the name
signal and capping exact ORCID-hint matches at ~0.65.
"""
from __future__ import annotations

from backend.authority.resolvers.orcid import _parse_expanded_results


_SAMPLE = {
    "expanded-result": [
        {
            "orcid-id": "0000-0002-2324-5292",
            "given-names": "Tycho",
            "family-names": "Mevissen",
            "credit-name": "Tycho E. T. Mevissen",
            "institution-name": ["Harvard University"],
        },
        {
            "orcid-id": "0000-0001-0000-0002",
            "given-names": "Grace",
            "family-names": "Hopper",
            "credit-name": None,
            "institution-name": [],
        },
        {"orcid-id": "", "given-names": "No", "family-names": "Id"},  # dropped
    ],
    "num-found": 2,
}


def test_prefers_credit_name_and_carries_orcid():
    cands = _parse_expanded_results(_SAMPLE)
    assert len(cands) == 2  # empty orcid-id row dropped
    c0 = cands[0]
    assert c0.authority_id == "0000-0002-2324-5292"
    assert c0.canonical_label == "Tycho E. T. Mevissen"  # credit-name preferred
    assert c0.uri == "https://orcid.org/0000-0002-2324-5292"
    assert "Harvard University" in c0.description


def test_falls_back_to_given_family_when_no_credit_name():
    cands = _parse_expanded_results(_SAMPLE)
    assert cands[1].canonical_label == "Grace Hopper"


def test_label_never_falls_back_to_orcid_when_name_present():
    # The whole point: a real name must beat the ORCID id as the label.
    cands = _parse_expanded_results(_SAMPLE)
    assert all(c.canonical_label != c.authority_id for c in cands)


def test_empty_payload_is_safe():
    assert _parse_expanded_results({}) == []
    assert _parse_expanded_results({"expanded-result": None}) == []
