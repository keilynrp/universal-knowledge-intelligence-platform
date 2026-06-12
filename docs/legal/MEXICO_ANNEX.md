# Mexico Annex — LFPDPPP Mapping (UKIP)

> **DISCLAIMER / AVISO:** Base template prepared by the UKIP engineering team.
> NOT legal advice. Requires review by qualified counsel before being signed
> or relied upon in any contract or compliance representation.

This annex maps the UKIP privacy pack to the Mexican *Ley Federal de
Protección de Datos Personales en Posesión de los Particulares* (LFPDPPP), for
use with Mexican customers (current pilots: Mexican universities). It must be
reviewed by counsel qualified in Mexican data-protection law before being
relied upon.

## 1. Roles (Art. 3 LFPDPPP)

| LFPDPPP role | Party | Notes |
|--------------|-------|-------|
| *Responsable* (data controller) | The Customer (research institution) | Decides purposes and means; owns the relationship with data subjects (*titulares*) |
| *Encargado* (data processor) | The UKIP operator | Processes personal data solely on the responsable's behalf and instructions, per [DPA_BASELINE.md](DPA_BASELINE.md) |

## 2. Derechos ARCO mapping

The LFPDPPP grants data subjects the rights of **A**cceso, **R**ectificación,
**C**ancelación, and **O**posición. The responsable services these requests;
UKIP provides the tooling:

| Derecho | Platform support | Evidence |
|---------|------------------|----------|
| **Acceso** (access) | DSAR export: portable JSON bundle of org-/subject-scoped data with audit evidence | EPIC-016 Slice 2; `POST /admin/data-lifecycle/export` |
| **Rectificación** (rectification) | Entity edit endpoints available to the responsable's authorized users (editor+ roles) | Entities PUT endpoints; harmonization tooling |
| **Cancelación** (erasure) | Cascade deletion across the relational database and the ChromaDB vector store, with confirmation echo and audit evidence | EPIC-016 Slice 3; `POST /admin/data-lifecycle/delete` |
| **Oposición** (objection) | **Honest note:** UKIP has no dedicated oposición workflow. Objection requests are handled by the Customer as responsable (e.g., by excluding the data subject's records from processing or requesting deletion via the cancelación tooling above) | — |

## 3. Aviso de privacidad

The *aviso de privacidad* (privacy notice) is the **responsable's**
obligation: the Customer must issue it to its data subjects. UKIP, as
encargado, provides the processing details the Customer needs to draft it:

- processing activities and purposes: [ROPA.md](ROPA.md);
- data categories and recipients (including public authority sources queried
  during authority resolution): [ROPA.md](ROPA.md) Activity 2;
- transfers / third parties: [SUBPROCESSOR_REGISTER.md](SUBPROCESSOR_REGISTER.md);
- security measures: [PRIVACY_CONTROLS_OVERVIEW.md](PRIVACY_CONTROLS_OVERVIEW.md).

## 4. Transfers (transferencias)

Disclosures to third parties are limited to the entries in
[SUBPROCESSOR_REGISTER.md](SUBPROCESSOR_REGISTER.md). Optional services
(Sentry telemetry, LLM providers) are default-OFF and engaged only on the
Customer's instruction, which the Customer should reflect in its aviso de
privacidad where required. Data residency is currently determined by the
hosting provider's region and is not yet a contractual commitment (open item
ER-DEP-001).

## 5. Encargado requirements (Art. 36 and Reglamento)

The DPA structure in [DPA_BASELINE.md](DPA_BASELINE.md) is designed to satisfy
the obligations commonly required of an encargado — processing only on the
responsable's documented instructions, confidentiality, security measures,
sub-processor controls, assistance with ARCO rights, and deletion/return on
termination — **subject to counsel review** confirming alignment with Art. 36
LFPDPPP and its Reglamento for the specific contract.

## 6. Security measures (Art. 19)

Art. 19 requires the responsable (and by extension the encargado) to establish
and maintain administrative, technical, and physical security measures. The
implemented measures and their evidence are documented in
[PRIVACY_CONTROLS_OVERVIEW.md](PRIVACY_CONTROLS_OVERVIEW.md), including an
honest register of measures not yet in place (incident response plan, external
pentest, data residency, first restore drill).

## 7. Data minimization note

UKIP processes predominantly professional, public-sphere data about
researchers (names, affiliations, publications, public identifiers). The
platform is not designed for *datos personales sensibles* (sensitive personal
data) as defined by Art. 3 LFPDPPP, and customers agree not to submit them
(see [DPA_BASELINE.md](DPA_BASELINE.md) Section 4).
