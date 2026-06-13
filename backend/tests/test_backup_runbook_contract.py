from pathlib import Path

from backend.scripts.validate_restore import _parser


ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs" / "operating" / "BACKUP_RESTORE_RUNBOOK.md"
EVIDENCE_TEMPLATE = (
    ROOT
    / "docs"
    / "operating"
    / "templates"
    / "BACKUP_RESTORE_EVIDENCE_TEMPLATE.md"
)
DOKPLOY_DOCS = (
    ROOT / "docs" / "operating" / "DOKPLOY_VPS_RUNBOOK.md",
    ROOT / "docs" / "operating" / "DOKPLOY_PRODUCTION_CHECKLIST.md",
)

VALIDATOR_COMMAND = """python -m backend.scripts.validate_restore \\
  --database-url "$DRILL_DATABASE_URL" \\
  --environment "isolated-drill" \\
  --backup-id "$BACKUP_ID" \\
  --operator "$OPERATOR" \\
  --expected-revision "$EXPECTED_REVISION" \\
  --backup-completed-at "$BACKUP_COMPLETED_AT" \\
  --restore-started-at "$RESTORE_STARTED_AT" \\
  --tenant-a "$TENANT_A" \\
  --tenant-b "$TENANT_B" \\
  --output "$VALIDATION_REPORT\""""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_backup_restore_runbook_contains_operational_contract():
    text = _read(RUNBOOK)
    lowered = text.lower()

    required_literals = (
        "RPO: 24 hours",
        "RTO: 4 hours",
        "7 daily",
        "4 weekly",
        "3 monthly",
        "26 hours",
        "PostgreSQL",
        "ukip_static_data",
        "Redis",
        "ChromaDB",
        "DuckDB",
    )
    for literal in required_literals:
        assert literal in text

    assert "isolated restore" in lowered
    assert VALIDATOR_COMMAND in text
    assert "disable schedulers, webhooks, and notifications" in lowered
    assert "templates/BACKUP_RESTORE_EVIDENCE_TEMPLATE.md" in text
    assert "incident cutover requires separate approval" in lowered
    assert "short-lived" in lowered
    assert "read-only database credential" in lowered
    assert "unset DRILL_DATABASE_URL" in text


def test_documented_validator_options_match_the_real_cli_parser():
    parser_options = {
        option
        for action in _parser()._actions
        for option in action.option_strings
        if option.startswith("--")
    }
    documented_options = {
        token
        for token in VALIDATOR_COMMAND.replace("\\", " ").split()
        if token.startswith("--")
    }
    required_parser_options = {
        option
        for action in _parser()._actions
        if action.required
        for option in action.option_strings
        if option.startswith("--")
    }

    assert documented_options <= parser_options
    assert required_parser_options <= documented_options
    assert {
        "--database-url",
        "--environment",
        "--backup-id",
        "--operator",
        "--expected-revision",
        "--backup-completed-at",
        "--restore-started-at",
        "--output",
    } <= documented_options


def test_backup_restore_runbook_distinguishes_restorable_and_reconstructible_data():
    text = _read(RUNBOOK).lower()

    assert "restorable" in text
    assert "postgresql" in text
    assert "ukip_static_data" in text
    assert "reconstructible" in text
    assert "redis" in text
    assert "chromadb" in text
    assert "duckdb" in text


def test_backup_restore_evidence_template_captures_required_fields():
    text = _read(EVIDENCE_TEMPLATE).lower()

    required_fields = (
        "backup id",
        "release",
        "alembic revision",
        "region",
        "operator",
        "approver",
        "expected rpo",
        "achieved rpo",
        "expected rto",
        "achieved rto",
        "validation",
        "failures",
        "corrective actions",
        "report checksum",
        "final result",
    )
    for field in required_fields:
        assert field in text


def test_dokploy_docs_link_runbook_and_keep_operator_actions_pending():
    for path in DOKPLOY_DOCS:
        text = _read(path)
        lowered = " ".join(text.lower().split())

        assert "BACKUP_RESTORE_RUNBOOK.md" in text
        assert "provider provisioning" in lowered
        assert "first isolated restore drill" in lowered
        assert "pending operator actions" in lowered
