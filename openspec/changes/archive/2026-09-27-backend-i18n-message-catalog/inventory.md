# String inventory — task 1

127 candidates extracted from `backend/` (excluding `tests/`, `alembic/`, `__pycache__`, `openalex_lake/`) with a deliberately over-inclusive heuristic, then **classified by reading each one**. The extractor decides nothing; that is the point. Two earlier heuristic counts disagreed (96 across 17 modules, 71 across 16) and both admitted strings that must not be touched.

## Totals

| category | count | action |
|---|---|---|
| `label` / `operator-message` | 70 | migrate to catalog, EN + ES |
| `email` | 4 | migrate to catalog, EN + ES |
| `analysis-prose` (composed) | 6 | **convert to English**, no key |
| `false-positive` | 47 | leave alone |
| **total** | **127** | |

**37% of the candidates are false positives.** A regex-driven migration would have translated English docstrings and, worse, destroyed working input aliases.

## Three corrections to the plan

**1. "Analysis prose stays English" is not "leave it alone".**

The proposal says composed analysis text is not localised. It is currently **Spanish**, so honouring that decision means *converting these 22 strings to English*, not skipping them. The headline symptom in #209 — `"Concentración temática: Political science"` in an English report — is in this bucket. It is fixed by writing the sentence in English, not by adding a catalog key.

This makes the reported bug considerably cheaper to fix than the catalog work, and it can ship first, independently.

**2. Fourteen Spanish strings must be preserved exactly as they are.**

`services/field_correspondence.py` and `scripts/backfill_canonical_id_entity_type.py` hold Spanish strings that are **input-matching aliases**, not output: they map incoming CSV headers (`"Identificador único"`, `"Tipo de publicación"`, `"institución"`) onto canonical fields so that a user can upload a Spanish spreadsheet.

Translating them, or moving them to a message catalog, would break Spanish CSV imports. They are Spanish on purpose and belong to the data layer, not the presentation layer. Both earlier counts included them.

**3. Only 6 of the 22 "analysis prose" strings are actually analysis prose.**

The case for leaving analysis text in English is that it quotes data which is itself English: `"Concentración temática: Political science"` is incoherent in either language, because `Political science` arrives from OpenAlex and is not ours to translate. A Spanish frame around an English payload reads worse than an English one.

That argument is sound — and on reading the strings, it applies to **6 of the 22**. The other 16 interpolate nothing. They are fixed sentences, indistinguishable from any other operator-facing label:

| | example |
|---|---|
| static (16) | `"Explorar este cluster como posible lente narrativo o línea estratégica."` |
| static (16) | `"Importa y enriquece registros para generar una proyección de impacto."` |
| static (16) | `"Output de impacto atípico"` |
| composed (6) | `f"Concentración temática: {concept}"` |
| composed (6) | `f"{count:,} registros comparten este concepto dentro del portafolio analizado."` |
| composed (6) | `f"{top['name']} lidera la evidencia sobre {topic} con score {top['topic_score']}."` |

The reasoning never covered the 16. They were swept into the bucket **by module**, not by property — every string in `impact_projection.py` was classified together because they live in the same file. The distinction that matters is whether a string embeds English data, and that is a property of the string.

So the 16 static sentences join the catalog like any other label, and only the 6 data-composing ones are converted to English. Decided with the user, 2026-07-31.

Worth noting what did *not* change: `proposal.md` and the `backend-locale-resolution` spec both already scope the exemption to *"prose the system composes from data"* — the property, stated correctly from the start. Only the classification drifted, by reaching for the file a string lives in instead of the test the spec gives. This correction brings the inventory back in line with the spec; it is not a change of policy, and no requirement needs editing.

The split by module:

| module | static → catalog | composed → English |
|---|---|---|
| `services/pattern_discovery.py` | 6 | 4 |
| `services/impact_projection.py` | 10 | 0 |
| `services/researcher_topic_analytics.py` | 0 | 2 |
| **total** | **16** | **6** |

Note `impact_projection.py` contributes nothing to the English conversion: all ten of its strings are static. The module that appeared to justify the whole category turns out not to belong to it at all.

## `label` / `operator-message` → catalog (70)

| module | n | notes |
|---|---|---|
| `services/domain_neutral_labels.py` | 14 | field labels, examples, two destructive-action confirmations |
| `services/agentic_research_chat.py` | 12 | fallback replies and suggested follow-up questions (lines 330–341, 414–427) |
| `enrichment_worker.py` | 11 | remediation hints and failure reasons shown to operators |
| `services/impact_projection.py` | 10 | static recommendations and the methodology sentence — see correction 3 |
| `services/audience_presets.py` | 9 | preset names, descriptions, export CTAs |
| `services/pattern_discovery.py` | 6 | static recommendations — see correction 3 |
| `routers/dashboards.py` | 2 | dashboard title and description |
| `routers/demo.py` | 2 | demo portal description |
| `services/assistant_actions.py` | 2 | action descriptions |
| `services/researcher_topic_analytics.py` | 2 | metric descriptions (lines 521–522) |

## `email` → catalog (4)

`routers/auth_users.py` lines 158–162: password-reset subject and body. Outward-facing — the only strings here that reach someone who is not logged in.

## `analysis-prose` → convert to English (6)

Only strings that interpolate data. See correction 3 for why this is 6 and not 22.

| module | n | notes |
|---|---|---|
| `services/pattern_discovery.py` | 4 | includes `f"Concentración temática: {concept}"`, the exact string reported in #209 |
| `services/researcher_topic_analytics.py` | 2 | lines 276, 278 |

`services/impact_projection.py` is absent: all ten of its strings are static and go to the catalog.

## `false-positive` → leave alone (47)

| kind | n | why |
|---|---|---|
| English docstring with an accented term | 27 | `Cramér's V`, `García → garcia`, `Kölner Phonetik`, `"Müller"`, `"English and Spanish names"` — matched on orthography, not language |
| Input-matching alias | 14 | see correction 2 — `field_correspondence.py` (10), `backfill_canonical_id_entity_type.py` (4) |
| Regex / character class | 5 | Spanish-language intent detection in `agentic_research_chat.py` (128, 132, 136), a multilingual stopword set in `institution_reconciliation.py` (82), an accent-inclusive character class in `semantic_keyword_signal_engine.py` (43) — these parse input, they are never displayed |
| English LLM prompt | 1 | `routers/ingest_helpers.py` (75) — matched on the word "no" appearing twice |

## Noted in passing, not part of this change

`services/agentic_research_chat.py` detects user intent with Spanish-only regexes (`cuant`, `distribución`, `evidencia`, `patrón`). An English-speaking user's question will not match any intent branch. That is an input-side language gap, the mirror image of #209, and it is not fixed by a message catalog.

Filed as **#227**. Before starting it, check whether it belongs *inside* this change rather than beside it: the same module contributes 12 output strings to the catalog here, so fixing intent detection separately risks writing code this change then rewrites.
