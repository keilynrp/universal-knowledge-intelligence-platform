# UKIP Privacy & Legal Pack

> **DISCLAIMER / AVISO:** Base template prepared by the UKIP engineering team.
> NOT legal advice. Requires review by qualified counsel before being signed
> or relied upon in any contract or compliance representation.

This directory contains the minimum privacy/legal documentation pack for the
Universal Knowledge Intelligence Platform (UKIP), produced under EPIC-020.
It is an engineering-authored baseline: every claim in these documents is
grounded in implemented, verifiable platform controls. Where a control is not
yet in place, the documents say so explicitly.

## Contents

| File | Purpose | Primary audience |
|------|---------|------------------|
| [DPA_BASELINE.md](DPA_BASELINE.md) | Data processing agreement template (controller/processor terms + technical-measures annex) | Customer legal / procurement, counsel |
| [SUBPROCESSOR_REGISTER.md](SUBPROCESSOR_REGISTER.md) | Register of sub-processors and infrastructure providers | Customer privacy / security reviewers |
| [ROPA.md](ROPA.md) | Record of processing activities | Data protection officers, auditors |
| [PRIVACY_CONTROLS_OVERVIEW.md](PRIVACY_CONTROLS_OVERVIEW.md) | One-page control summary with evidence pointers, including open items | Procurement / security questionnaires |
| [MEXICO_ANNEX.md](MEXICO_ANNEX.md) | LFPDPPP (Mexico) mapping: responsable/encargado roles, derechos ARCO | Mexican customers and their counsel |

## Status

- **Baseline pack — pending professional legal review.** The enterprise-readiness
  gap register tracks this as `privacy_legal_pack` with status **partial**: the
  engineering baseline exists, but no qualified counsel has reviewed or approved
  any of these documents.
- All technical claims reference implemented features (EPIC-012 tenant isolation,
  EPIC-016 data lifecycle, EPIC-017 secrets rotation, EPIC-018 backup program,
  EPIC-019 CI security gates). Open gaps are listed honestly in
  [PRIVACY_CONTROLS_OVERVIEW.md](PRIVACY_CONTROLS_OVERVIEW.md).

## How to use this pack in a procurement conversation

1. **Share [PRIVACY_CONTROLS_OVERVIEW.md](PRIVACY_CONTROLS_OVERVIEW.md) first.**
   It answers most security-questionnaire items in one page, including what is
   *not* yet in place, which builds credibility.
2. **Use [DPA_BASELINE.md](DPA_BASELINE.md) as the negotiation starting point**,
   not as a final document. Commercial terms (liability, jurisdiction, breach
   notification timeframe) are intentionally left as `[NEGOTIATED]` placeholders.
3. **Attach [SUBPROCESSOR_REGISTER.md](SUBPROCESSOR_REGISTER.md) and
   [ROPA.md](ROPA.md)** when the customer's privacy team asks for processing
   details, and [MEXICO_ANNEX.md](MEXICO_ANNEX.md) for Mexican customers.
4. **Never sign any version of these documents without counsel review.** The
   disclaimer at the top of each file is not boilerplate; it is the actual
   status of the pack.
