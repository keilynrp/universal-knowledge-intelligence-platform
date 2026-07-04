"""
ORCID public API resolver.
Searches researchers by name via the *expanded-search* endpoint, which — unlike
the plain ``/search/`` endpoint — returns the researcher's name and institution
inline. That name is essential: without it every ORCID candidate's
``canonical_label`` falls back to the bare ORCID id, which scores ~0 on the name
signal and drags even an exact ORCID-hint match down to ~0.65.
Only meaningful for entity_type in (person, general). No auth required.
"""
import logging
from typing import List

import httpx

from backend.authority.base import AuthorityCandidate, BaseAuthorityResolver

logger = logging.getLogger(__name__)

_ORCID_EXPANDED_SEARCH = "https://pub.orcid.org/v3.0/expanded-search/"
_PERSON_TYPES = {"person", "general"}


def _parse_expanded_results(data: dict) -> List[AuthorityCandidate]:
    """Build candidates from an ORCID expanded-search JSON payload.

    Pure/parsing-only so it can be unit-tested without network. Prefers the
    ``credit-name`` display form, then ``given family``; institution names go
    into the description so the affiliation signal has something to match.
    """
    candidates: List[AuthorityCandidate] = []
    for result in data.get("expanded-result") or []:
        if not isinstance(result, dict):
            continue
        orcid_id = (result.get("orcid-id") or "").strip()
        if not orcid_id:
            continue
        given = (result.get("given-names") or "").strip()
        family = (result.get("family-names") or "").strip()
        credit = (result.get("credit-name") or "").strip()
        label = credit or f"{given} {family}".strip() or orcid_id
        institutions = [
            i.strip() for i in (result.get("institution-name") or []) if isinstance(i, str) and i.strip()
        ]
        description = (
            f"Researcher (ORCID) — {', '.join(institutions)}"
            if institutions
            else "Researcher identifier (ORCID)"
        )
        candidates.append(AuthorityCandidate(
            authority_source="orcid",
            authority_id=orcid_id,
            canonical_label=label,
            description=description,
            uri=f"https://orcid.org/{orcid_id}",
        ))
    return candidates


class OrcidResolver(BaseAuthorityResolver):
    source_name = "orcid"

    def resolve(self, value: str, entity_type: str) -> List[AuthorityCandidate]:
        if entity_type not in _PERSON_TYPES:
            return []
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    _ORCID_EXPANDED_SEARCH,
                    params={"q": value, "rows": 5},
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
            return _parse_expanded_results(data)
        except Exception as exc:
            logger.warning("OrcidResolver failed for '%s': %s", value, exc)
            return []
