"""Governance checks for the ER-BCP-001 backup-freshness workflow and its
accompanying reconciliation/evidence documents (issue #320, Phase A).

These are plain text/structure contracts, matching the style already used by
test_backup_configuration_contract.py and test_backup_runbook_contract.py —
no live network or provider access is involved.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "backup-freshness.yml"
RECONCILIATION = ROOT / "docs" / "operating" / "ER-BCP-001-HISTORICAL-RECONCILIATION.md"
READINESS_DOSSIER = (
    ROOT
    / "docs"
    / "operating"
    / "templates"
    / "ER-BCP-001_READINESS_EVIDENCE_TEMPLATE.md"
)
RUNBOOK = ROOT / "docs" / "operating" / "BACKUP_RESTORE_RUNBOOK.md"

REQUIRED_SECRETS = {
    "S3_BACKUP_ENDPOINT",
    "S3_BACKUP_BUCKET",
    "S3_BACKUP_RO_ACCESS_KEY_ID",
    "S3_BACKUP_RO_SECRET_ACCESS_KEY",
}

# Application-side secrets that must never appear in this workflow again —
# corrected on strategic review (PR #321, issue #320): every route under
# /ops, including the read-only status endpoint, currently requires `admin`
# scope (backend/api_key_scopes.py), which is too broad to store in a
# GitHub-hosted scheduled workflow.
FORBIDDEN_SECRETS = {
    "UKIP_BACKUP_EVIDENCE_API_KEY",
    "UKIP_BACKUP_EVIDENCE_API_BASE_URL",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workflow_is_valid_yaml_with_expected_triggers_and_permissions():
    doc = yaml.safe_load(_read(WORKFLOW))

    assert "schedule" in doc[True] or "schedule" in doc.get("on", {})
    on = doc.get("on") or doc.get(True)
    assert "schedule" in on
    assert "workflow_dispatch" in on
    assert doc["permissions"] == {"contents": "read"}


def test_workflow_only_references_the_expected_secrets():
    text = _read(WORKFLOW)

    for secret in REQUIRED_SECRETS:
        assert f"secrets.{secret}" in text

    referenced = set(re.findall(r"secrets\.([A-Z0-9_]+)", text))
    assert referenced == REQUIRED_SECRETS


REPOSITORY_VARIABLES = {"S3_BACKUP_PREFIX"}


def test_workflow_reads_prefix_from_a_non_secret_variable():
    # Phase B (issue #320): the Phase A draft hardcoded the key prefix "pg/",
    # but Dokploy writes to "<appName>/<prefix>/", so the scheduled run would
    # report backup_missing against a bucket holding valid backups. The
    # prefix is not a credential: it must be `vars.*`, keep the old fallback,
    # and no variable may carry anything else.
    text = _read(WORKFLOW)

    assert "PREFIX: ${{ inputs.prefix || vars.S3_BACKUP_PREFIX || 'pg/' }}" in text

    referenced = set(re.findall(r"vars\.([A-Z0-9_]+)", text))
    assert referenced == REPOSITORY_VARIABLES


def test_dispatch_prefix_input_does_not_shadow_the_repository_variable():
    # A non-empty input default would win over vars.S3_BACKUP_PREFIX on every
    # manual run, so a dispatch would observe a different prefix than the
    # schedule does.
    doc = yaml.safe_load(_read(WORKFLOW))
    on = doc.get("on") or doc.get(True)

    assert on["workflow_dispatch"]["inputs"]["prefix"]["default"] == ""


def test_workflow_holds_no_application_credential():
    # Corrected on strategic review (PR #321, issue #320): the workflow must
    # not require a broad admin-scoped UKIP API key, and must not reference
    # either the evidence-API key or base-URL secret it used to require.
    text = _read(WORKFLOW)

    for secret in FORBIDDEN_SECRETS:
        assert secret not in text, f"forbidden application secret referenced: {secret!r}"


def test_workflow_does_not_post_backup_events_or_call_application_api():
    # The workflow must not mutate application state and must not call any
    # UKIP application endpoint at all — it observes the provider read-only.
    text = _read(WORKFLOW)

    assert "curl" not in text
    assert "-X POST" not in text
    assert "Authorization:" not in text


def test_workflow_does_not_map_etag_to_integrity_ref():
    # Corrected on strategic review: an S3 ETag is not guaranteed to be a
    # full-object checksum and must never be mapped into integrity_ref. The
    # string "integrity_ref" may still appear in prose explaining why it is
    # deliberately absent as a mapped field.
    text = _read(WORKFLOW)

    assert "arg integrity_ref" not in text
    assert '"integrity_ref"' not in text
    assert "integrity_ref: $" not in text
    assert "provider_etag" in text
    assert "NOT integrity evidence" in text
    assert "integrity_missing" in text


def test_workflow_distinguishes_object_observation_from_overall_authority():
    # Corrected on strategic review: the workflow must not claim overall
    # backup-assurance health while the authoritative endpoint could
    # independently report critical.
    text = _read(WORKFLOW)
    lowered = text.lower()

    assert "not the overall backup-assurance authority" in lowered
    assert "get /ops/backups/status" in lowered
    assert "backup freshness ok" not in lowered
    assert "rpo passed" not in lowered
    assert "backup assurance healthy" not in lowered


def test_workflow_holds_no_local_freshness_policy():
    # Second strategic review round (PR #321, issue #320): a corrected draft
    # removed the application-call defects but reintroduced a local
    # WARNING_AFTER_HOURS=24 / CRITICAL_AFTER_HOURS=26 projection that failed
    # runs based on locally computed object age — recreating the exact
    # duplicated-authority risk already rejected against the historical
    # workflow's MAX_AGE_HOURS. The workflow must hold no local RPO/freshness
    # policy threshold of any kind; it may only fail on directly observable
    # provider conditions (missing object, non-positive size, invalid or
    # future timestamp).
    text = _read(WORKFLOW)

    assert "WARNING_AFTER_HOURS" not in text
    assert "CRITICAL_AFTER_HOURS" not in text
    assert "MAX_AGE_HOURS" not in text
    assert re.search(r'["\']24["\']', text) is None
    assert re.search(r'["\']26["\']', text) is None


def test_workflow_labels_observed_age_as_informational_only():
    text = _read(WORKFLOW)
    lowered = text.lower()

    assert "observed object age" in lowered
    assert "not an rpo/freshness pass-fail decision" in lowered
    assert "rpo/freshness policy remains authoritative in the backend/evidence process" in lowered


def test_workflow_never_asserts_reachability_directly():
    text = _read(WORKFLOW)

    assert "UKIP_BACKUP_PROVIDER_REACHABLE" not in text


def test_workflow_guards_on_missing_secrets_before_using_them():
    text = _read(WORKFLOW)
    lines = text.splitlines()

    guard_index = next(
        i
        for i, line in enumerate(lines)
        if "missing repository secrets" in line.lower()
    )
    observe_index = next(
        i for i, line in enumerate(lines) if "aws s3api list-objects-v2" in line
    )
    assert guard_index < observe_index


def test_reconciliation_doc_states_the_audited_numbers():
    text = _read(RECONCILIATION)
    normalized = " ".join(text.split())

    assert "282 commits behind" in normalized
    assert "2 commits unique to it" in normalized
    assert ".github/workflows/backup-freshness.yml" in text
    assert "docs/operating/BACKUP_RESTORE_RUNBOOK.md" in text
    assert "ARCHITECTURE_DECISION_REQUIRED: none" in text


def test_reconciliation_doc_covers_all_three_dispositions():
    lowered = _read(RECONCILIATION).lower()

    assert "still missing from main" in lowered
    assert "superseded" in lowered
    assert "rejected as obsolete or unsafe" in lowered


def test_readiness_dossier_covers_required_evidence_fields():
    text = _read(READINESS_DOSSIER).lower()

    required_fields = (
        "provider configuration evidence",
        "backup cycle #1",
        "backup cycle #2",
        "isolated restore drill",
        "achieved rpo",
        "achieved rto",
        "alembic revision",
        "tenant-isolation",
        "integrity/data-usability",
        "provider reachability",
        "operator",
        "evidence reference",
        "residual risk",
        "durable-state review",
        "ukip_static_data",
    )
    for field in required_fields:
        assert field in text, f"missing required evidence field: {field!r}"


def test_readiness_dossier_does_not_change_control_maturity():
    text = _read(READINESS_DOSSIER)

    assert "Maturity before this dossier: `specified`" in text


def test_runbook_documents_the_automated_observation_workflow():
    text = _read(RUNBOOK)

    assert "backup-freshness.yml" in text
    assert "ER-BCP-001-HISTORICAL-RECONCILIATION.md" in text
    assert "ER-BCP-001_READINESS_EVIDENCE_TEMPLATE.md" in text
    assert "Operator Actions Pending" in text


def test_runbook_does_not_require_admin_ci_identity():
    # Corrected on strategic review: §13 must no longer instruct operators
    # to create a dedicated admin-role UKIP identity/API key for CI, and
    # must instead document that evidence ingestion stays manual/trusted
    # service until a least-privilege mechanism exists.
    text = _read(RUNBOOK)
    lowered = text.lower()

    for secret in FORBIDDEN_SECRETS:
        assert secret not in text
    assert "dedicated admin-role ukip identity" not in lowered
    assert "least-privilege" in lowered


def test_control_register_and_enterprise_controls_are_untouched_by_phase_a():
    # Phase A must not change ER-BCP-001 maturity. Anchoring on the exact
    # current maturity string keeps this test meaningful (it would fail if
    # someone bumped maturity without updating this guard deliberately).
    register = _read(ROOT / "docs" / "product" / "ENTERPRISE_CONTROL_REGISTER.md")
    controls = _read(ROOT / "backend" / "enterprise_controls.py")

    assert (
        "| ER-BCP-001 | PostgreSQL and required state can be restored within measured objectives | P0 | specified | auditable |"
        in register
    )
    assert '"ER-BCP-001",' in controls
    assert '"specified",\n        "auditable",' in controls
