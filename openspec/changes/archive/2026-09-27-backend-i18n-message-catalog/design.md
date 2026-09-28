## Context

The backend emits user-facing text in two languages by accident. Roughly 70–95 string literals across ~16 modules are Spanish; everything around them is English. The clearest symptom is a production report whose Hidden Patterns section reads *"Concentración temática: Political science"* inside an otherwise-English document, and password-reset emails whose subject is Spanish for every recipient.

Nothing about this is a translation gap, because there is nothing to translate into. There is no catalog, no locale resolution, no language parameter on `POST /reports/generate`, and no `language` column on `User` — the frontend keeps the preference in `localStorage` under `app_lang`, which the server never sees.

The frontend already solved the *storage* problem: `frontend/app/i18n/translations.ts` holds 3,402 keys in EN and 3,402 in ES, at exact parity with no key on one side only. It did not solve the *enforcement* problem. There is no parity gate — not in CI, not in `frontend/__tests__`, not in `package.json`, and not in the type system, because `LanguageContext.tsx` casts the object to `Record<Language, Record<string, string>>` and a cast checks nothing. The parity that holds today is a property of the file as committed, maintained by whoever last edited it. Phase 4 therefore **writes** that gate rather than extending one, and points it at both catalogs: gating the backend projection while its source stays ungated would move the failure one file upstream instead of preventing it.

Two constraints shape everything below. **Server-rendered artefacts** — PDF, PPTX, Excel reports and outbound email — never pass through the frontend, so client-side translation cannot reach them. And **data values come from providers in their own language**: OpenAlex concepts, journal titles, author and institution names are English regardless of the reader.

## Goals / Non-Goals

**Goals:**
- One definition per string, shared with the frontend catalog rather than duplicated.
- A request can state the language it wants, and report generation honours it.
- Labels, operator-facing messages and email subjects are available in EN and ES.
- A new backend string cannot ship in one language only.

**Non-Goals:**
- **Localising generated analysis prose.** Sentences composed from data stay English. This is the decision that keeps the change finite, and it is written into the spec so it cannot erode.
- **Translating data values.** Concepts, journal titles, author and institution names pass through untouched.
- Adding languages beyond EN and ES.
- Changing the frontend catalog's contents or its existing gate.
- A `User.language` column. Locale arrives per request; persisting a preference is a separate change with its own migration and UI.

## Decisions

**A shared catalog, with the frontend's file as the source of truth.**
The alternative — a second Python-native catalog (gettext `.po`, or a dict module) — is how the two drift apart, which is the defect being fixed. Instead the backend reads the same key space. Keys are namespaced by surface (`report.section.hidden_patterns.title`, `email.password_reset.subject`) so backend and frontend keys never collide while living in one space.

`translations.ts` is TypeScript, not data, so the backend cannot import it directly. The build emits a JSON projection of the catalog that the backend loads; the gate asserts the projection is current. Parsing TypeScript from Python was rejected as fragile, and hand-maintaining a copy was rejected as exactly the drift in question.

**Locale resolution is an explicit chain, not a guess.**
In order: the request's explicit language parameter, then `Accept-Language`, then the configured default (`en`). Unknown or unsupported values fall back rather than error — a report with English labels is a degraded result, not a failed request. `Accept-Language` alone was rejected as the primary source because report generation is often triggered on behalf of an audience rather than by the reader's own browser.

**Missing key returns the key, loudly.**
At runtime a missing key renders its own key rather than raising — a half-translated report still delivers. It is logged at warning level, and the parity gate makes shipping one in the first place a CI failure rather than a runtime surprise. Raising was rejected: it converts a cosmetic defect into an outage on a path (report generation) that is expensive to re-run.

**The inventory is classified by hand before anything is migrated.**
Two heuristic counts disagree (96/17 and 71/16) and both contain false positives — docstrings holding "Cramér's V" or "English and Spanish names" are not user-facing. Each candidate is classified as label, operator message, email, analysis prose, or false positive, and only the first three are migrated. Migrating from a regex's output would translate docstrings and miss strings without accents.

**English is the key language.**
Keys are English-derived identifiers, and EN is the reference the ES side is checked against, matching the frontend.

## Risks / Trade-offs

- **A JSON projection can go stale** → the parity gate regenerates it and fails if it differs from the committed file, so a drifted projection is a red build rather than a wrong report.
- **A reader may expect fully Spanish reports and still see English findings** → this is the accepted product boundary, but it must be visible rather than discovered: the spec requires it be stated, so the limitation is documented where a reader meets it rather than surfacing as an apparent bug.
- **Namespacing one key space across two consumers invites collisions** → surface prefixes are required by the spec and checked by the gate.
- **A large mechanical migration can change behaviour by accident** — several of these literals are f-strings interpolating data → each migrated string keeps its interpolation arguments, and the migration is reviewed per module rather than as one sweep.
- **Email subjects are outward-facing** → they change what recipients see, so they are migrated with EN as the new default; anyone relying on the current Spanish subject in a filter will be affected. Worth calling out at deploy rather than discovering in a support ticket.
- **The parity gate only proves both languages exist, not that the ES text is correct** → machine-plausible but wrong Spanish still passes. The gate is a completeness check, not a quality one, and claiming otherwise would repeat the false confidence this project has already been bitten by.

## Migration Plan

1. Land the catalog, resolver and gate with no call sites migrated — inert, reversible, and the gate starts guarding immediately.
2. Migrate module by module, highest string count first, each independently revertable.
3. Add the language parameter to report generation last, once there is something for it to select.

Rollback is per step; nothing here changes stored data, so no data migration has to be undone. The one outward-facing step — email subjects — is called out separately at deploy.

## Resolved Questions

Both were settled with the product owner on 2026-07-31, before implementation.

- **`Accept-Language` does not apply to report generation.** Reports take the explicit parameter, then the configured default — the header is skipped. A report is produced for an audience, not for whoever pressed the button, and honouring the operator's browser locale would leak their language into someone else's artefact without anyone asking for it. The header still participates in the chain for the rest of the API, where the requester and the reader are the same person.
- **Nothing depends on the current Spanish password-reset subject.** It migrates like everything else, defaulting to English, and the change is called out in the deploy note because it is outward-facing.

## Open Questions

None outstanding. The two above were the blockers; the remaining unknowns (the exact string inventory) are resolved by task 1, which is a step of the work rather than a precondition for it.
