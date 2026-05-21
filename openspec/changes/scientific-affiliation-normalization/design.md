## Context

OpenAlex works expose institutional affiliation data in `authorships`:

```json
{
  "authorships": [
    {
      "author_position": "first",
      "author": {
        "id": "https://openalex.org/A123",
        "display_name": "Ada Lovelace",
        "orcid": "https://orcid.org/0000-0001-..."
      },
      "institutions": [
        {
          "id": "https://openalex.org/I123",
          "display_name": "University of Tests",
          "ror": "https://ror.org/03yrm5c26",
          "country_code": "US",
          "type": "education"
        }
      ]
    }
  ]
}
```

UKIP currently extracts authors and ORCIDs but does not preserve the full institutional relationship in a first-class normalized shape. The existing `EnrichedRecord.affiliations: list[str]` is insufficient for ROR and institutional authority work because it cannot answer which author belongs to which institution or which identifier backs the institution.

## Goals / Non-Goals

**Goals:**
- Preserve institution names, ROR IDs, OpenAlex institution IDs, country codes, and types.
- Preserve author-to-institution relationships.
- Deduplicate canonical institutions per publication.
- Keep old connectors compatible by making new fields optional.
- Persist structured affiliation data in `attributes_json`.
- Provide test fixtures that protect this mapping contract.

**Non-Goals:**
- Calling the ROR API in this change.
- Full institution authority resolution UI.
- Retrofitting all historical rows immediately.
- Changing RawEntity relational schema in the first pass.
- Replacing `raw_response` storage.

## Decisions

### D1: Extend `EnrichedRecord` with structured optional fields

**Decision:** Add optional structured fields:

- `author_affiliations`: per-author affiliation entries
- `canonical_affiliations`: deduplicated institution entries

**Rationale:** `affiliations: list[str]` remains useful for backwards compatibility and simple geographic fallback, but ROR requires structured identifiers.

### D2: Use attributes_json for persistence first

**Decision:** Persist structured affiliation fields under `attributes_json` rather than adding new SQL columns immediately.

**Rationale:** The project already uses `attributes_json` for scientific metadata. This keeps the migration small and avoids overfitting before the authority/ROR workflow is fully designed.

### D3: Canonical affiliations deduplicate by strongest identifier

**Decision:** Deduplicate institutions by this key order:

1. ROR ID
2. OpenAlex institution ID
3. normalized display name + country code

**Rationale:** ROR is the strongest cross-system identifier. OpenAlex ID is still useful when ROR is absent. Text fallback is necessary for providers without institution IDs.

### D4: Preserve author position and author IDs when available

**Decision:** Author-affiliation records should include author name, ORCID, OpenAlex author ID, author position, raw author order, and linked institution keys.

**Rationale:** Stakeholder analysis often needs first/corresponding/last author affiliation and institution collaboration structure.

## Proposed Data Shape

```python
class CanonicalAffiliation(BaseModel):
    name: str
    ror: str | None = None
    openalex_id: str | None = None
    country_code: str | None = None
    type: str | None = None
    lineage: list[str] = []

class AuthorAffiliation(BaseModel):
    author_name: str
    author_orcid: str | None = None
    author_openalex_id: str | None = None
    author_position: str | None = None
    author_order: int | None = None
    institutions: list[CanonicalAffiliation]
```

Persisted `attributes_json` should include:

```json
{
  "authors": "Ada Lovelace, Grace Hopper",
  "affiliation": "University of Tests, US; Open Science Lab, GB",
  "affiliations": ["University of Tests, US", "Open Science Lab, GB"],
  "canonical_affiliations": [
    {
      "name": "University of Tests",
      "ror": "https://ror.org/03yrm5c26",
      "openalex_id": "https://openalex.org/I123",
      "country_code": "US",
      "type": "education"
    }
  ],
  "author_affiliations": [
    {
      "author_name": "Ada Lovelace",
      "author_orcid": "0000-0001-...",
      "author_openalex_id": "https://openalex.org/A123",
      "author_position": "first",
      "author_order": 1,
      "institutions": [
        {
          "name": "University of Tests",
          "ror": "https://ror.org/03yrm5c26",
          "openalex_id": "https://openalex.org/I123",
          "country_code": "US",
          "type": "education"
        }
      ]
    }
  ]
}
```

## Risks / Trade-offs

- **Risk: attributes_json grows large.** Mitigation: Store only normalized institution metadata, not the full authorship raw tree.
- **Risk: connectors differ in affiliation richness.** Mitigation: Make fields optional; text-only providers can populate only `affiliations`.
- **Risk: duplicate institutions with slightly different names.** Mitigation: Deduplicate by ROR/OpenAlex IDs before text normalization.
- **Risk: downstream analytics still use old text fields.** Mitigation: Update geographic extraction to prefer structured country codes but keep text fallback.

## Rollout Plan

1. Extend schemas with structured affiliation models.
2. Update OpenAlex parser.
3. Update ingestion helper to persist structured fields.
4. Update geographic extraction to prefer `canonical_affiliations[].country_code`.
5. Add tests for OpenAlex parse and ingestion persistence.
6. Add docs/codemap note for scientific affiliation contract.
