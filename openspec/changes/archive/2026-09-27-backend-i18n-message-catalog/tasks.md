## 1. Inventory

- [x] 1.1 Enumerate every candidate user-facing string literal in `backend/` (excluding `tests/`, `alembic/`), recording file, line and text — 127 candidates, extractor kept at `extract_candidates.js`
- [x] 1.2 Classify each candidate by hand as `label`, `operator-message`, `email`, `analysis-prose`, or `false-positive` — see `inventory.md`
- [x] 1.3 Commit the classified inventory to the change directory as the migration's worklist, with per-category counts
- [x] 1.4 Confirm with the product owner that everything classified `analysis-prose` is staying English, since that is the boundary the whole scope rests on — **answered 2026-07-31: only 6 of the 22 stay English.** The other 16 interpolate nothing and are localised like any other label

Three findings from 1.2 change the plan; all are recorded in `inventory.md`:

- **`analysis-prose` means convert to English, not skip.** Those strings are Spanish today, so honouring "analysis stays English" is work, not an exemption. The exact string reported in #209 is one of them, which makes the headline bug fixable independently of the catalog — see phase 1b.
- **14 Spanish strings must be preserved verbatim.** `field_correspondence.py` and `backfill_canonical_id_entity_type.py` hold input-matching aliases that let users upload Spanish spreadsheets. Migrating them would break Spanish CSV imports. Both earlier counts included them.
- **The `analysis-prose` boundary was drawn by module, not by property.** Asking 1.4 forced a reading of all 22 strings, and only 6 embed English data — the condition the "stays English" argument actually rests on. The other 16 are fixed sentences that were classified together merely for sharing a file. They move to the catalog (phase 6), and phase 1b shrinks accordingly.

## 1b. Fix the reported symptom first

Independent of the catalog, and shippable on its own.

Scope is the **6 data-composing strings only** (see inventory correction 3). The 16 static
sentences that used to sit in this phase are catalog work and moved to phase 6 — converting
them to English here would be writing text this change then replaces.

- [x] 1b.1 Failing test written first — `test_report_language_hidden_patterns.py`, 6 tests, one per
      composed string, RED 6/6 before the conversions. **Scoped to the composed strings, not the
      section.** The task as written ("no Spanish appears in the section") is a phase-6 assertion:
      the static sentences in the same modules are still Spanish by design until 6.1–6.2, so that
      test would be red for reasons this phase does not own. It belongs at 6.9 and is noted there.
- [x] 1b.2 Converted the 4 composed `services/pattern_discovery.py` strings, every interpolation
      argument preserved: semantic cluster label (175), impact-outlier evidence (215), provider-gap
      evidence (266), collaboration-bridge evidence (338).
- [x] 1b.3 Converted `services/researcher_topic_analytics.py` 276 and 278 (both branches of the
      headline conditional).
- [x] 1b.4 Rendered the real section and read it. **The headline symptom is gone** —
      `Concentración temática: knowledge graph` now reads `Thematic concentration: knowledge graph`.

Two things the reading showed that the tests did not:

- **1b makes the mixing more visible before phase 6 removes it.** A single table row now reads
  `Output de impacto atípico | Graph Learning for Research Intelligence clearly exceeds the
  portfolio citation baseline (420 citations). | Usarlo como ancla del brief…` — Spanish label,
  English evidence, Spanish action. That is the correct intermediate state and it is defensible
  (the sentence quoting English data is the one that had to change first), but it is worse-looking
  than before and should not surprise anyone reviewing a report between 1b and phase 6.
- **`collect_hidden_patterns` caps at `limit=6`, so `collaboration_bridge` never reaches the
  report** with this fixture — six higher-scoring patterns crowd it out. Its string was still
  converted, and the test exercises it at `limit=12`. Worth confirming in phase 6 whether that cap
  is intended, since a pattern type that can never render is a separate question from language.

`services/impact_projection.py` is deliberately absent: all ten of its strings are static, so it contributes nothing here and appears in phase 6 instead.

## 2. Catalog projection

- [x] 2.1 `scripts/generate-i18n-projection.mjs` emits one JSON file per language. Parsed with the **TypeScript compiler's AST**, not a regex: the catalog holds apostrophes (`Cramér's V`), arrows (`Análisis completo →`) and interpolation braces (`{platform}`), and a regex over quoted strings gets those subtly wrong — a defect nobody notices until a reader does. Spot-checked all four forms survive.
- [x] 2.2 Committed as `backend/i18n/catalog.en.json` and `catalog.es.json` — **3402 keys each**, matching the source exactly. `backend/i18n/__init__.py` exposes `CATALOG_DIR`, `LANGUAGES`, `DEFAULT_LANGUAGE` only; lookup arrives in phase 3.
- [x] 2.3 Determinism is enforced **inside the generator** rather than by a test. `--check` renders twice and compares before comparing to the committed file, so every CI run proves it. A pytest that shells out to Node would skip wherever Node is absent, and a gate that silently skips is a gate that cannot fail — see 4.3.
- [x] 2.4 CI gate `i18n-projection-drift` in `.github/workflows/lint.yml`, blocking. Given its own job rather than folded into `frontend-lint-repo`, which is `continue-on-error: true` and would have made the gate advisory without saying so.

Mutation-checked, since a gate that passes when written has proven nothing:

| mutation | pytest | `--check` |
|---|---|---|
| keys unsorted | fails `test_keys_are_sorted` | exit 1 |
| one key dropped | fails `test_every_key_in_the_source_survives_the_projection` | exit 1 |
| unmodified | 7 passed | exit 0 |

`test_i18n_catalog_projection.py` counts keys **off `translations.ts` directly**, not off the generator's output — a generator that drops keys and a test reading only that generator's output would agree with each other and both be wrong.

## 3. Catalog module

- [x] 3.1 Tests written first, RED on a missing module — `test_i18n_translate.py`, 22 tests. Exercised against an **injected** fixture catalog: the backend's own `report.`/`email.`/`validation.` keys do not exist yet (they arrive in phases 6–7), and asserting on frontend keys would test a lookup the backend must never perform. One test reads the real projection, to prove the loader points at the file phase 2 committed.
- [x] 3.2 `backend/i18n/catalog.py` — `translate(key, language=None, **params)`, `lru_cache`d per-language loader.
- [x] 3.3 Absent key returns the key, logs a warning, does not raise. **A key present only in EN serves EN rather than the raw key** — one-sided keys are a phase-4 CI failure, not a runtime crash.
- [x] 3.4 Interpolation mirrors the frontend's `replaceAll`, deliberately **not** `str.format`: format raises on an unsupplied placeholder and chokes on any catalog string holding a literal brace. An unsupplied placeholder stays visible — a cosmetic defect, where failing report generation would be an outage. Interpolated values are inserted verbatim, verified with a value that is itself a catalog key.
- [x] 3.5 A key with no surface prefix raises `ValueError`. Deliberately different from a missing key: a malformed key is a **call-site defect**, deterministic and caught by any test on that path, whereas a missing key is data and degrades. Rendering `nav.home` into a PDF would put a sidebar label in a report.

Mutation-checked, 5 mutations, all caught:

| mutation | caught by |
|---|---|
| prefix guard removed | `test_a_key_without_a_surface_prefix_is_rejected` |
| missing key raises | `test_every_declared_surface_prefix_is_accepted` |
| missing-key warning silenced | `test_absent_key_logs_a_warning` |
| `str.format` instead of replace | `test_a_missing_parameter_is_left_visible_rather_than_raising` |
| language resolver deleted | `test_an_unsupported_language_resolves_to_the_default` |

⚠️ **The last one initially passed with the resolver deleted** — 20/20 green against
broken code. Asserting that `translate(..., "fr")` returns English does not test language
resolution: with the resolver gone the lookup misses in the empty `fr` catalog and the
*missing-key* path serves English anyway, so the test was satisfied by a mechanism it did
not name. Rewritten to assert on `_resolve_language` directly and on a warning that says
"unsupported", which is distinct from the missing-key warning that also names a language.

## 4. Parity gate

**There is no parity gate to extend.** Verified 2026-08-02: nothing in `.github/workflows/`,
`frontend/package.json`, `frontend/scripts/` or `frontend/__tests__/` checks EN/ES parity, and
`LanguageContext.tsx` casts the catalog to `Record<Language, Record<string, string>>`, so the
type system does not check it either. The two sides are at exact parity today (3,402 keys each,
zero one-sided, zero duplicates) purely by discipline. This phase writes the gate.

- [x] 4.1 `scripts/check-i18n-parity.mjs` checks the **frontend** catalog. The AST reader was first extracted to `scripts/lib/i18n-catalog.mjs`, shared with the generator — parsing the catalog twice, two different ways, is how two gates end up vouching for different files.
- [x] 4.2 The same gate checks the backend projection, and `test_i18n_catalog_projection.py::TestParity` checks it again from the suite. Overlap is deliberate: the projection is what the backend loads, and a one-sided key there is a report rendering a bare key to a reader.
- [x] 4.3 Mutation-checked, **4/4 caught**, both directions × both surfaces. Each failure names the key and the missing language.
- [x] 4.4 Green against the catalog as it stands (`en=3402 es=3402`, zero one-sided) — it lands enforcing rather than grandfathering violations.
- [x] 4.5 Stated in the script's own header, in its failure output, and in the CI step comment: **presence only**. A fluent mistranslation, an English string pasted into the Spanish block, or a literal `TODO` all pass.

| mutation | surface | result |
|---|---|---|
| key added to `en` only | `translations.ts` | exit 1 — *'mutation.only_in_en' is missing from 'es'* |
| key added to `es` only | `translations.ts` | exit 1 — *'mutation.solo_en_es' is missing from 'en'* |
| key deleted from `catalog.es.json` | projection | exit 1 — names the key and `es` |
| key deleted from `catalog.en.json` | projection | exit 1 — names the key and `en` |
| unmodified | both | exit 0 |

The pytest side catches the projection mutations too (3 tests fail).

`TestParity` deliberately compares **key sets, not counts**: `len(en) == len(es)` would pass
while every key differed. A second test pins that intent so a future simplification to a
length check has to be a deliberate act rather than a slip.

## 5. Locale resolution

- [x] 5.1 `test_i18n_locale_resolution.py`, 30 tests, RED on a missing module. Covers the chain plus `Accept-Language` parsing: q-value ordering, `q=0` meaning *not acceptable*, regional variants (`es-MX` → `es`), unsupported tags skipped rather than fatal, and malformed headers (the header is attacker-controllable and must never 500).
- [x] 5.2 `backend/i18n/locale.py` — `resolve_language`, `resolve_report_language`, and `language_dependency` wired with FastAPI `Query`/`Header` markers.
- [x] 5.3 An unsupported language falls back to the default, succeeds, and logs. **An unsupported explicit parameter does not fall through to the header**: the caller named a language and it is unavailable, and honouring the browser instead would hide that behind a plausible-looking result.
- [x] 5.4 `resolve_report_language` **takes no header argument at all**, so it cannot consult one. A resolver that accepted it and chose not to read it is one refactor away from reading it; a test asserts the signature, making the boundary structural rather than conventional.

Mutation-checked, 6 mutations:

| mutation | result |
|---|---|
| explicit parameter ignored | 5 failed |
| `q=0` entries kept | **28 passed — NOT caught** |
| q-ordering dropped | 2 failed |
| report resolver accepts a header | 1 failed |
| unsupported-language warning silenced | 1 failed |
| regional variant not stripped (`es-MX` ≠ `es`) | 2 failed |

⚠️ The `q=0` test did not discriminate. `("es;q=0,en;q=0.4", "en")` passes whether `q=0`
entries are **dropped** or merely **ranked last**, because the ordering alone already
picks `en`. Fixed by adding `("es;q=0", "en")` and `("es;q=0,en;q=0", "en")`, where the
rejected entry is the only candidate — now 2 tests fail on that mutation.

That is the fourth non-discriminating test caught in this change. The pattern is always
the same: **the fixture supplies a second mechanism that produces the same observable
result**, so the assertion never depends on the one under test.

## 6. Migrate strings

Ordered by count so the largest surfaces land first; each module is independently revertable.

**The module list below was rebuilt from `inventory.md` on 2026-08-05.** The original
list contradicted the inventory in three ways, and one of them was destructive:

- **6.6 named `services/field_correspondence.py`.** Correction 2 classifies its 10
  Spanish strings as **input-matching aliases** — `"Identificador único": "canonical_id"`,
  provenance `header_alias` — that map incoming CSV headers so users can upload Spanish
  spreadsheets. Verified in the code before removing it from scope. Migrating them would
  break Spanish imports, which is the exact damage the inventory warned about.
- **6.7 named `analyzers/correlation.py`.** Its only accented string is the English
  docstring `"""Compute pairwise Cramér's V between categorical fields."""` — one of the
  27 false positives matched on orthography rather than language. Nothing to migrate.
- **`services/agentic_research_chat.py` appeared nowhere**, despite being the second
  largest module at 12 strings. It would have fallen under "remaining single-string
  modules", which it is not.

**23 of the 70 are in dead modules and are out of scope** (decided 2026-08-05):

| module | strings | importers in `backend/` | tests |
|---|---|---|---|
| `services/domain_neutral_labels.py` | 14 | **0** | only in top-level `tests/`, which CI does not run |
| `services/audience_presets.py` | 9 | **0** | only in top-level `tests/`, which CI does not run |

Nothing in the application imports either one — verified across the whole repo by symbol,
not just by import line. Their tests give an appearance of coverage over code no user can
reach. Migrating them would mean adding ~23 catalog keys and rewiring modules nobody
calls. They are left untouched; **deleting them is a separate decision** and is not part
of an i18n change.

This exposes a gap in the task-1 methodology worth carrying forward: the inventory
classified each string **by reading it**, which caught the 47 false positives and the 14
input aliases — but it judged "user-facing" from the string's *content*, never from
whether any user can reach it. A perfectly user-facing Spanish string inside a module
nothing imports is still not user-facing.

`routers/demo.py` was checked the same way and **is** live — `app.include_router(demo.router)`
in `main.py:547`. An import-line grep missed it; the router mount is what settles it.

Scope is therefore **47 strings across 8 live modules**. Ordered by count, largest first;
each module independently revertable. Surface prefix per module in brackets.

### The split is by surface, not by size

An earlier version of this list grouped the modules by string count. That is the same
mistake corrections 2 and 3 already caught twice in this change — **grouping by an
incidental attribute instead of the property that decides the work.** The property here
is whether the surface has a language signal available at the call site, and it separates
the 47 strings into two groups with entirely different risk:

| surface | modules | strings | is English-by-default a regression? |
|---|---|---|---|
| **report** | `impact_projection`, `pattern_discovery`, `researcher_topic_analytics` | 18 | **No.** Reports already default to English by decision (2026-07-31) and ignore `Accept-Language`; phase 8 adds the explicit parameter. Migrating with the default *is* the intended behaviour. |
| **API** | `agentic_research_chat`, `enrichment_worker`, `dashboards`, `demo`, `assistant_actions` | 29 | **Yes.** These answer a client that knows its language. They are Spanish-only today, so a bare `translate(key)` would take Spanish away from the readers who currently have it. |

**Group B therefore threads the resolved language** through `language_dependency`, which
phase 5 landed in `main` and nothing yet uses. That is not scope creep: migrating a
string means the migrated version is at least as good as the one it replaced, and
swapping "Spanish for everyone" for "English for everyone" is not a migration, it is
breaking half the readers. The catalog exists so that both work.

Deferring it was considered and rejected: phase 8 is explicitly about reports, so nothing
later in this plan would revisit the chat, and the note would outlive the intention.

Group A — report surface, no threading required (one PR):

- [x] 6.1 `services/impact_projection.py` — 10 [`report.`], all static. The three-band recommendation/brief-angle pairs collapse to a `band` variable plus two keyed lookups, so the branching stays and the copy leaves.
- [x] 6.2 `services/pattern_discovery.py` — **11 strings, not the 6 the inventory recorded** (see correction 4 below) [`report.`]; the 4 composed sentences became English in 1b and take no key
- [x] 6.3 `services/researcher_topic_analytics.py` — 2 metric descriptions [`report.`]

**Correction 4 — the extractor missed Spanish that carries no accent.**

The inventory recorded 6 static strings in `pattern_discovery.py`. There are **11**. The
three it missed have no accented character at all:

| missed | |
|---|---|
| `"Dependencia fuerte de una fuente"` | provider-gap label |
| `"Posibles variantes duplicadas"` | duplicate-variants label |
| `"Entidad puente en el grafo"` | collaboration-bridge label |

This is the **mirror image of the false-positive problem**, and it has the same root. The
extractor keyed partly on orthography, so English docstrings entered the inventory *for
having* accents (`Cramér's V`, `Kölner Phonetik`) and real Spanish stayed out *for lacking
them*. Correction 1 documented only the first half, because classifying by reading fixes
what an extractor **over-includes** and can never reveal what it **left out**.

Practical consequence for group B: locate strings by **structure** — the dict keys a
module renders (`"label":`, `"recommended_action":`, `"description":`) — not by
orthography. Group A's real total is **23 strings, not 18**.

Group B — API surface, resolved language threaded from the request (one PR):

- [x] 6.4 `services/agentic_research_chat.py` — **15 keys** [`chat.`]. Language threaded router → `ask()` → `_compose_answer()` / `_follow_ups()`. The three follow-up triples collapse to `_FOLLOW_UP_SUFFIXES`, so the module holds the *choice* and the catalog holds the text. ⚠️ the inventory's line numbers were stale (PR #239 moved them) — located by structure instead
- [~] 6.5 `enrichment_worker.py` — **removed from this change** (2026-08-05). Not a string migration.

  `_record_failure` writes `evidence` and `recommendations` into
  `attributes_json["enrichment_failure"]`, and the worker runs in the background with no
  request — so there is no `Accept-Language` and no parameter to thread. `translate()` at
  write time would **freeze a language into the row**: the rendered text is stored and the
  key is gone, so an operator who later chooses Spanish still reads English. Production
  rows already have the mirror of this defect today, in Spanish.

  Doing it properly means persisting the **key and its parameters** and translating at
  read time. That changes the stored shape and needs a reader that tolerates old rows
  (text) and new rows (key) at once — a data decision with a back-compat dimension, not
  an i18n one. Its 13 strings (9 remediation hints + 4 `evidence` sentences, again more
  than the inventory's 11) go to a separate change.

  Everything else in group B is **request-scoped**, so `translate(key, language)` resolves
  when the response is built and nothing is persisted.
- [x] 6.6 `routers/dashboards.py` — 2 [`dashboard.`]
- [~] `routers/demo.py` — **removed, same reason as 6.5.** `_DEMO_PORTAL_TITLE` and `_DEMO_PORTAL_DESCRIPTION` are written into a `models.CatalogPortal` row, so translating at write time freezes the language into stored data. Joins the persistence change.
- [x] 6.7 `services/assistant_actions.py` — **6 keys, not 2** [`chat.`]: the inventory counted `description=` and missed `label=`. `REGISTRY` now stores catalog **keys**, resolved in `list_capabilities(language)` at read time; an operator override still passes through untranslated, because those are the operator's words.

**The real fault line in phase 6 is not report-vs-API — it is resolve-on-read vs freeze-on-write.**

The surface split was right about which strings need a threaded language, but two modules
fail a prior test: they *persist* their text. `enrichment_worker` writes `evidence` and
`recommendations` into `attributes_json`; `demo` writes a portal title and description into
a `CatalogPortal` row. Translating at write time stores a rendered string and discards the
key, so no later language choice can recover it — and production rows already carry Spanish
frozen that way. Both go to a separate change that persists key + params and translates on
read, tolerating old rows.

Everything migrated in group B resolves when the response is built:

| module | keys | resolved |
|---|---|---|
| `agentic_research_chat` | 15 | per request, threaded from the router |
| `assistant_actions` | 6 | per request, in `list_capabilities(language)` |
| `routers/dashboards` | 2 | per request |
- [x] 6.8 Swept every migrated module by **AST**, reading each string literal rather than matching a shape. Found **5 more strings** and migrated them. Input aliases confirmed verbatim; both dead modules untouched since before the track. Left behind as a regression gate — `test_no_spanish_literal_survives_in_a_migrated_module`, 6 modules, mutation-checked (reintroducing one literal turns it red).

**Correction 5 — the same blind spot, three times, each in a different disguise.**

| sweep | matched on | missed |
|---|---|---|
| the inventory's extractor | orthography (accents) | 3 accent-free labels |
| the group A migration | `"label":` / `"recommended_action":` | 3 `"evidence":` fields |
| the first verification grep | a hand-written word list | 1 string in an `else` branch |

Every one matched **a shape someone had already seen**. Reading the AST removes the
guess: it can still misjudge a literal, but it cannot fail to look at one. The gate
states what it does *not* cover — modules nobody listed, and meaning as opposed to
vocabulary.
- [x] 6.9 The section-wide assertion deferred from 1b.1 now holds: with 6.1–6.3 landed, `pattern_discovery` carries no Spanish literal at all, which is a stronger statement than the section-level one originally planned and is enforced per-module by 6.8's gate.

## 7. Email

- [x] 7.1 Subject and body are two keys, not four: the body is **one message with a `{link}` placeholder** rather than three concatenated fragments, because a translator needs the whole sentence to translate it. `{platform}` and `{link}` interpolate verbatim.
- [x] 7.2 `test_i18n_email.py`, 9 tests: subject and body per language, English default, explicit parameter beating the header, the platform name interpolated rather than translated, the reset link surviving in both languages, and the catalog-sentinel check.

⚠️ **These tests broke a neighbour before they passed.** `/auth/password-reset/request`
allows 10/hour per IP and every test here goes through it, so the file exhausted the quota
and `test_auth.py`'s long-standing reset test failed with **429 while passing in
isolation**. An autouse fixture resets the limiter around each test. Worth remembering
that a rate-limited endpoint makes test count a shared resource.

⚠️ **Newlines nearly did not survive the catalog.** The body has real line breaks;
`translations.ts` string literals cannot span lines. Hand-rolled escaping silently dropped
them and the generator rejected the file. Fixed by emitting the literal with
`json.dumps`, and verified end to end — the projection reads back 5 real newlines and the
`{link}` placeholder intact.
- [x] 7.3 `DEPLOY-NOTE.md` in this change directory. States who is affected (anyone with no Spanish language signal — Spanish speakers keep their exact wording), why it is safe, what to watch, and how to roll back. It also lists the three endpoints that gained a `language` parameter, since that reached the published SDK.

## 8. Report language

- [x] 8.1 `test_i18n_report_language.py`, RED first.
- [x] 8.2 `?language=` on all four endpoints. Titles are translated at the **single render boundary** keyed by section id, not in each of the ~14 collectors, so a new section cannot forget to.
- [x] 8.3 All three formats tested. ⚠️ **Excel needed its own key space.** A sheet name is capped at 31 chars and forbids `/ \ ? * [ ] :`; `_safe_sheet_title` truncates rather than failing, so a violation cuts a tab mid-word in silence. `report.sheet.*` holds purpose-built short names; PPTX takes the full title, a slide heading having no limit.
- [x] 8.4 **This one caught a real defect of mine.** The first implementation gave *English* short sheet names too — renaming `Entity Statistics` to `Entity Stats` in a file users download. Seven existing tests went red, and the parity guard was right: 8.4 says omitting the parameter preserves behaviour, and a renamed tab is a change a caller sees.

  The fix was to revert the improvement, not to update the assertions. **English keeps the long title it always had, including the two Excel already truncates.** The constraint test now states two different true things rather than one uniform rule that was false for English: Spanish names need no truncation; English names are exactly what they were.
- [x] 8.5 `report.disclosure.analysis_language`, inserted first so a reader meets the limitation before the text it applies to. Only on non-English artefacts — an English report has no mixture to explain.
- [x] 8.6 +84 spec lines and both clients across all four endpoints. Largest contract move of the track; the three before it were one endpoint each.

## 9. Verification

- [x] 9.1 3790 passed, 9 skipped, 0 failed on the phase 8 merge; re-run for this change.
- [x] 9.2 Rendered real reports in both languages and **read them**. This is the task that earned its place in the plan.

  **Reading found what no test could.** A Spanish report is **6 Spanish lines against 32 English ones**: section titles and the disclosure translate; structural headings (`Executive Summary`, `Executive interpretation`), the stakeholder framing (`Leadership / Strategy`, `Framed for Leadership / Strategy: …`), empty-state messages (`No entities in this domain yet.`) and metric labels (`Total Entities`, `Valid`, `Pending`) do not.

  **Why every sweep missed it:** the whole track was framed as *find Spanish text and move it to the catalog*. Task 1's inventory looked for **Spanish strings** — 127 candidates, 47 false positives, five corrections. These were **always English**, so nothing had reason to look at them. Producing a genuinely Spanish report means translating text that was never the reported defect.

  Decided with the product owner: **close #209 on the defect it reported, and make the disclosure honest** about what remains English (option A + C). A follow-up issue covers full Spanish reports.
- [x] 9.3 **The original bug is gone: the English report contains zero Spanish lines.** Measured on the rendered artefact, not on source.
- [x] 9.4 Comment posted on #209, plus a follow-up issue for full Spanish reports and one for the 15 strings in modules that persist their text.

## 10. At archive (2026-09-27)

- [x] 10.1 `backend-locale-resolution`'s last requirement was rewritten before
      publishing, because the follow-up to 9.2 moved the boundary it described.
      It said prose composed from data stays English; #268 then put the counted
      takeaways in the catalog (#288, one sentence per count so Spanish can
      inflect the verb) and closed the remaining gaps (#314), which also
      narrowed `report.disclosure.analysis_language`. The requirement is now
      "Only text the system authors is localised", and names what stays
      English exactly as that disclosure does: analyzer prose, provider-supplied
      names, and four Excel sheets' headings and metric labels.
