## ADDED Requirements

### Requirement: Backend user-facing text is defined in a message catalog
The backend SHALL NOT contain user-facing text as literals at its call sites. Every label, operator-facing message and outbound email subject SHALL be retrieved from the message catalog by key.

#### Scenario: A label is rendered from a key
- **WHEN** a report section renders its title
- **THEN** the text comes from the catalog for the resolved language, and no natural-language literal appears at the call site

#### Scenario: A Spanish literal is reintroduced
- **WHEN** a module gains a user-facing Spanish string literal
- **THEN** CI fails, naming the file and the string

### Requirement: The catalog shares one key space with the frontend
The backend catalog SHALL be derived from the frontend catalog (`frontend/app/i18n/translations.ts`) rather than maintained as a second, independent store, so a string is defined once.

#### Scenario: The derived projection is stale
- **WHEN** the frontend catalog changes and the committed backend projection is not regenerated
- **THEN** CI fails, because a projection that disagrees with its source is the drift this capability exists to prevent

#### Scenario: Keys are namespaced by surface
- **WHEN** a backend key is added
- **THEN** it carries a surface prefix (for example `report.`, `email.`, `validation.`), so backend and frontend keys cannot collide within the shared space

### Requirement: Both languages are present for every key
Every key in the catalog SHALL have an English and a Spanish value. English is the reference language.

#### Scenario: A key ships in one language only
- **WHEN** a key is added with an English value and no Spanish value, or the reverse
- **THEN** the parity gate fails, naming the key and the missing language

#### Scenario: The gate is a completeness check, not a quality one
- **WHEN** a Spanish value is present but a mistranslation
- **THEN** the gate passes — it verifies that both languages exist, and this limitation SHALL be stated where the gate is documented rather than left implied

### Requirement: A missing key degrades rather than fails
Retrieving an absent key SHALL return the key itself and log a warning. It SHALL NOT raise.

#### Scenario: A report is generated with a key that does not exist
- **WHEN** a section requests an absent key during report generation
- **THEN** the report is produced with the key rendered in place of the text, and a warning is logged
- **AND** generation completes, because a cosmetic defect must not fail an expensive artefact

### Requirement: Interpolated values are preserved
A message with placeholders SHALL keep its interpolation arguments across languages, and the interpolated values SHALL NOT be translated.

#### Scenario: A message interpolates a data value
- **WHEN** a message embeds a concept name supplied by a provider
- **THEN** the surrounding text is in the resolved language and the concept name appears exactly as the provider supplied it
