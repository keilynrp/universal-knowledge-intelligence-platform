# backend-locale-resolution Specification

## Purpose
The language of backend output is resolved by an explicit precedence chain, reports take their language from the request rather than the operator's browser, outbound email follows the resolved language, and the boundary of what is not translated is stated to the reader. Created by archiving change backend-i18n-message-catalog.
## Requirements
### Requirement: A request's language is resolved by an explicit precedence chain
The backend SHALL resolve the language for a request in this order: an explicit language parameter on the request, then the `Accept-Language` header, then the configured default. The default SHALL be English.

#### Scenario: An explicit parameter wins
- **WHEN** a request carries a language parameter and an `Accept-Language` header naming a different language
- **THEN** the parameter is used, because generation is frequently performed on behalf of an audience rather than by the reader

#### Scenario: No signal is present
- **WHEN** a request carries neither a parameter nor a usable header
- **THEN** English is used

#### Scenario: An unsupported language is requested
- **WHEN** a request asks for a language the catalog does not carry
- **THEN** the request succeeds in the default language rather than failing
- **AND** the fallback is logged, so an unsupported request is observable rather than silent

### Requirement: Report generation accepts a language and ignores the header
`POST /reports/generate` SHALL accept an optional language, and the generated artefact SHALL use it for all catalog-sourced text in every format. Report generation SHALL NOT consult `Accept-Language`: it takes the explicit parameter, otherwise the configured default.

#### Scenario: A Spanish report is requested
- **WHEN** a report is generated with the language set to Spanish
- **THEN** its section titles, labels and disclosures are Spanish across PDF, PPTX and Excel alike

#### Scenario: The parameter is omitted
- **WHEN** a report is generated with no language
- **THEN** the artefact is produced in the configured default, preserving the behaviour of callers written before this parameter existed

#### Scenario: The operator's browser language differs from the request
- **WHEN** a report is generated with no language parameter by an operator whose `Accept-Language` is Spanish
- **THEN** the artefact is English, because a report is produced for an audience rather than for whoever triggered it, and the operator's locale must not leak into someone else's document

### Requirement: Outbound email uses the resolved language
Email the backend sends SHALL take its subject and body text from the catalog in the resolved language rather than a hard-coded language.

#### Scenario: A password reset is requested
- **WHEN** a password-reset email is sent
- **THEN** its subject comes from the catalog in the resolved language, not a Spanish literal

### Requirement: Only text the system authors is localised
Text the system authors (section titles, labels, empty states, and takeaways that state a finding, including those inflected on a count) SHALL come from the catalog in the resolved language. Prose produced by analyzer services, values supplied by external providers, and the column headings and metric labels of the Excel export's Summary, Entities, Harmonization and Methodology sheets SHALL remain in English regardless of the resolved language. This boundary SHALL be stated to the reader rather than left to be discovered.

#### Scenario: A Spanish report states a counted finding
- **WHEN** a report is generated in Spanish and a section's takeaway is composed from a count in the data
- **THEN** the takeaway is the catalog's Spanish sentence for that count, inflected as Spanish requires
- **AND** the interpolated values are unchanged

#### Scenario: Analyzer prose stays English
- **WHEN** a Spanish report includes prose produced by an analyzer service
- **THEN** that prose is English, and this is expected rather than a defect

#### Scenario: A Spanish report names a concept
- **WHEN** a Spanish report cites a concept sourced from OpenAlex
- **THEN** the concept appears in English, as the provider supplies it

#### Scenario: The limitation is disclosed
- **WHEN** an artefact is generated in a language other than English
- **THEN** it states which text remains English (analyzer prose, provider-supplied names, and the Excel sheets named above), so a reader is not left to interpret the mixture as an error
