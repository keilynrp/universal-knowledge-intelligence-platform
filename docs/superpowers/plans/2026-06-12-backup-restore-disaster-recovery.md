# Backup, Restore, and Disaster Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement UKIP's repository-side backup assurance controls for RPO 24h / RTO 4h, including evidence records, freshness monitoring, operations APIs, restore validation tooling, and an executable Dokploy/S3 runbook.

**Architecture:** Dokploy/PostgreSQL remains responsible for creating encrypted backups in S3-compatible storage. UKIP stores provider-neutral backup and drill metadata, evaluates freshness through existing operational checks, exposes admin-only evidence, and supplies an isolated restore validator; credentials and payloads never pass through the web application.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy/Alembic, Pydantic, pytest, PostgreSQL tooling, Docker Compose, Dokploy, S3-compatible storage.

---

## File Map

**Create**

- `backend/backup_assurance.py` - evidence schemas, persistence helpers, freshness evaluation, and redaction.
- `backend/schemas_backup.py` - API request/response contracts for backup evidence.
- `backend/routers/backup_ops.py` - admin-only metadata ingestion and evidence endpoints.
- `backend/scripts/validate_restore.py` - isolated restored-environment validation command.
- `backend/tests/test_backup_assurance.py` - unit tests for evidence and freshness.
- `backend/tests/test_backup_ops_api.py` - authorization and API lifecycle tests.
- `backend/tests/test_restore_validation.py` - restore validation behavior tests.
- `alembic/versions/<generated_revision>_backup_assurance_events.py` - append-only backup/drill evidence table created by `alembic revision`.
- `docs/operating/BACKUP_RESTORE_RUNBOOK.md` - operator procedure and drill checklist.
- `docs/operating/templates/BACKUP_RESTORE_EVIDENCE_TEMPLATE.md` - human-readable evidence export template.

**Modify**

- `backend/models.py` - add `BackupAssuranceEvent`.
- `backend/main.py` - register the backup operations router.
- `backend/ops_checks.py` - include backup freshness and recommended action.
- `backend/routers/analytics_ops.py` - expose backup overview alongside existing ops surfaces if a dedicated router prefix is not used.
- `backend/tests/conftest.py` - clean backup evidence rows between tests.
- `backend/tests/test_sprint104_ops_checks.py` - pin backup check aggregation.
- `docker-compose.prod.yml` - pass non-secret backup metadata/check settings to the backend and migrate ops service.
- `.env.dokploy.example` - document provider-neutral metadata variables.
- `.env.example` - document disabled local defaults.
- `docs/operating/DOKPLOY_VPS_RUNBOOK.md`
- `docs/operating/DOKPLOY_PRODUCTION_CHECKLIST.md`
- `docs/legal/ROPA.md`
- `docs/legal/PRIVACY_CONTROLS_OVERVIEW.md`
- `docs/legal/DPA_BASELINE.md`
- `docs/legal/SUBPROCESSOR_REGISTER.md`
- `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
- `docs/product/TRACEABILITY_MATRIX.md`
- `backend/enterprise_controls.py`

### Task 1: Persist Backup and Restore Evidence

**Files:**
- Modify: `backend/models.py`
- Create: the file printed by `alembic revision -m "backup assurance events"` under `alembic/versions/`
- Create: `backend/backup_assurance.py`
- Create: `backend/tests/test_backup_assurance.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Write failing persistence tests**

Create:

```python
from datetime import datetime, timedelta, timezone

from backend import models
from backend.backup_assurance import record_event


def test_record_backup_event_persists_non_secret_metadata(db_session):
    event = record_event(
        db_session,
        event_type="backup",
        status="completed",
        environment="production",
        provider="dokploy",
        backup_id="backup-20260612-001",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        completed_at=datetime.now(timezone.utc),
        release="sha-abc123",
        alembic_revision="e5f6a7b8c0d1",
        size_bytes=1024,
        integrity_ref="sha256:abc",
        encrypted=True,
        storage_region="mx-central",
        retention_class="daily",
        operator="ops@example.test",
        evidence={"provider_state": "completed"},
    )
    assert event.id is not None
    persisted = db_session.query(models.BackupAssuranceEvent).one()
    assert persisted.backup_id == "backup-20260612-001"
    assert "secret" not in (persisted.evidence_json or "").lower()


def test_record_restore_drill_keeps_expected_and_achieved_objectives(db_session):
    event = record_event(
        db_session,
        event_type="restore_drill",
        status="passed",
        environment="drill",
        provider="dokploy",
        backup_id="backup-20260612-001",
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        completed_at=datetime.now(timezone.utc),
        operator="ops@example.test",
        expected_rpo_hours=24,
        expected_rto_hours=4,
        achieved_rpo_hours=18,
        achieved_rto_hours=2,
        evidence={"tenant_isolation": "passed"},
    )
    assert event.achieved_rpo_hours == 18
    assert event.achieved_rto_hours == 2
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pytest backend/tests/test_backup_assurance.py -v
```

Expected: FAIL because the model and module do not exist.

- [ ] **Step 3: Add the append-only evidence model**

Add `BackupAssuranceEvent` to `backend/models.py` with:

```python
class BackupAssuranceEvent(Base):
    __tablename__ = "backup_assurance_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(30), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    environment = Column(String(50), nullable=False, index=True)
    provider = Column(String(80), nullable=False)
    backup_id = Column(String(200), nullable=True, index=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True, index=True)
    release = Column(String(120), nullable=True)
    alembic_revision = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    integrity_ref = Column(String(200), nullable=True)
    encrypted = Column(Boolean, nullable=True)
    storage_region = Column(String(120), nullable=True)
    retention_class = Column(String(30), nullable=True)
    operator = Column(String(120), nullable=False)
    expected_rpo_hours = Column(Float, nullable=True)
    expected_rto_hours = Column(Float, nullable=True)
    achieved_rpo_hours = Column(Float, nullable=True)
    achieved_rto_hours = Column(Float, nullable=True)
    evidence_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
```

Generate an Alembic revision and implement exact upgrade/downgrade operations
for this table and its indexes.

- [ ] **Step 4: Add the persistence helper**

Implement `record_event()` in `backend/backup_assurance.py`. It must:

- accept only `backup` or `restore_drill`;
- accept terminal statuses `completed`, `failed`, `passed`, or `passed_with_risk`;
- reject evidence keys matching `secret`, `password`, `token`, `credential`,
  `database_url`, or `connection_string`, case-insensitively;
- serialize evidence with sorted keys;
- normalize timezone-aware datetimes to UTC-naive values for SQLAlchemy parity;
- commit and refresh the event.

- [ ] **Step 5: Add test cleanup**

Add `"backup_assurance_events"` to the cleanup list in
`backend/tests/conftest.py` before tables with referenced identities.

- [ ] **Step 6: Run persistence tests and migration smoke**

Run:

```powershell
pytest backend/tests/test_backup_assurance.py -v
python -m alembic upgrade head
```

Expected: tests PASS and migration reaches head.

- [ ] **Step 7: Commit**

```powershell
git add backend/models.py backend/backup_assurance.py backend/tests/test_backup_assurance.py backend/tests/conftest.py alembic/versions
git commit -m "feat: persist backup assurance evidence"
```

### Task 2: Evaluate Backup Freshness

**Files:**
- Modify: `backend/backup_assurance.py`
- Modify: `backend/tests/test_backup_assurance.py`

- [ ] **Step 1: Write failing freshness tests**

Append tests for:

```python
from backend.backup_assurance import evaluate_backup_freshness


def test_freshness_is_ok_at_24_hours():
    now = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    result = evaluate_backup_freshness(
        latest_completed_at=now - timedelta(hours=24),
        now=now,
        size_bytes=100,
        integrity_ref="etag:abc",
        provider_reachable=True,
    )
    assert result["status"] == "ok"


def test_freshness_warns_between_24_and_26_hours():
    now = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    result = evaluate_backup_freshness(
        latest_completed_at=now - timedelta(hours=25),
        now=now,
        size_bytes=100,
        integrity_ref="etag:abc",
        provider_reachable=True,
    )
    assert result["status"] == "warning"


def test_freshness_is_critical_when_stale_or_invalid():
    now = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    stale = evaluate_backup_freshness(
        latest_completed_at=now - timedelta(hours=27),
        now=now,
        size_bytes=100,
        integrity_ref="etag:abc",
        provider_reachable=True,
    )
    missing_integrity = evaluate_backup_freshness(
        latest_completed_at=now,
        now=now,
        size_bytes=100,
        integrity_ref=None,
        provider_reachable=True,
    )
    assert stale["status"] == "critical"
    assert missing_integrity["status"] == "critical"
```

- [ ] **Step 2: Run tests and verify missing function failure**

Run:

```powershell
pytest backend/tests/test_backup_assurance.py -v
```

Expected: FAIL importing `evaluate_backup_freshness`.

- [ ] **Step 3: Implement deterministic freshness evaluation**

Add:

```python
BACKUP_RPO_HOURS = 24
BACKUP_CRITICAL_AFTER_HOURS = 26


def evaluate_backup_freshness(
    *,
    latest_completed_at: datetime | None,
    now: datetime,
    size_bytes: int | None,
    integrity_ref: str | None,
    provider_reachable: bool,
) -> dict:
    ...
```

Return `status`, `age_hours`, `rpo_hours`, `critical_after_hours`, and reason
codes. Use `ok <= 24`, `warning <= 26`, otherwise `critical`. Missing backup,
zero size, missing integrity, or unreachable provider is `critical`.

- [ ] **Step 4: Add latest-event query helper**

Implement:

```python
def latest_completed_backup(db: Session, environment: str) -> BackupAssuranceEvent | None:
```

It filters `event_type="backup"`, `status="completed"`, and environment, then
orders by `completed_at DESC, id DESC`.

- [ ] **Step 5: Run unit tests**

Run:

```powershell
pytest backend/tests/test_backup_assurance.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/backup_assurance.py backend/tests/test_backup_assurance.py
git commit -m "feat: evaluate backup freshness"
```

### Task 3: Add Admin-Only Backup Evidence APIs

**Files:**
- Create: `backend/schemas_backup.py`
- Create: `backend/routers/backup_ops.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_backup_ops_api.py`

- [ ] **Step 1: Write failing API tests**

Create tests proving:

- viewer receives `403`;
- admin can post backup metadata without payload credentials;
- secret-like evidence keys produce `422`;
- `GET /ops/backups` returns newest-first events;
- `GET /ops/backups/status` returns freshness and RPO thresholds.

Use this payload:

```python
payload = {
    "event_type": "backup",
    "status": "completed",
    "environment": "production",
    "provider": "dokploy",
    "backup_id": "backup-001",
    "started_at": "2026-06-12T10:00:00Z",
    "completed_at": "2026-06-12T10:05:00Z",
    "release": "sha-abc",
    "alembic_revision": "head-1",
    "size_bytes": 2048,
    "integrity_ref": "etag:abc",
    "encrypted": True,
    "storage_region": "mx-central",
    "retention_class": "daily",
    "operator": "ops@example.test",
    "evidence": {"provider_state": "completed"},
}
```

- [ ] **Step 2: Run tests and verify 404/import failure**

Run:

```powershell
pytest backend/tests/test_backup_ops_api.py -v
```

Expected: FAIL because the router is absent.

- [ ] **Step 3: Define Pydantic contracts**

Create request and response models with:

- UTC datetimes;
- `size_bytes >= 0`;
- non-empty operator/provider/environment;
- event/status literals;
- evidence dictionary limited to 50 keys and JSON-compatible scalar/list/dict
  values.

- [ ] **Step 4: Implement router**

Expose:

```text
POST /ops/backups/events
GET  /ops/backups
GET  /ops/backups/status
```

All endpoints require `super_admin` or `admin`. POST records metadata only.
List defaults to 20 and caps at 100. Status uses the latest completed backup for
the requested environment.

- [ ] **Step 5: Register router**

Import and include `backup_ops.router` in `backend/main.py`.

- [ ] **Step 6: Run API tests**

Run:

```powershell
pytest backend/tests/test_backup_ops_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/schemas_backup.py backend/routers/backup_ops.py backend/main.py backend/tests/test_backup_ops_api.py
git commit -m "feat: expose backup assurance operations API"
```

### Task 4: Integrate Backup Freshness into Operational Checks

**Files:**
- Modify: `backend/ops_checks.py`
- Modify: `backend/tests/test_sprint104_ops_checks.py`
- Modify: `backend/tests/test_backup_assurance.py`

- [ ] **Step 1: Write failing ops-check tests**

Add tests that monkeypatch or persist:

- no production backup -> `backup_freshness` is `critical`;
- 25-hour backup -> `warning`;
- fresh valid backup -> `ok`;
- critical backup adds a restore/backup recommended action;
- aggregate report includes the new check ID.

Update existing expected check IDs and summary counts explicitly.

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pytest backend/tests/test_sprint104_ops_checks.py -v
```

Expected: FAIL because `backup_freshness` is absent.

- [ ] **Step 3: Implement `_backup_freshness_check`**

Use environment settings:

```text
UKIP_BACKUP_MONITOR_ENABLED=0
UKIP_BACKUP_ENVIRONMENT=production
UKIP_BACKUP_PROVIDER_REACHABLE=1
```

When monitoring is disabled, return `skipped`. When enabled, query the latest
event and evaluate freshness. Do not query S3 from the HTTP request path.

- [ ] **Step 4: Add recommended actions**

For warning:

```text
Verify the current backup job and confirm a successful recovery point before the 26-hour critical threshold.
```

For critical:

```text
Treat backup protection as unavailable: restore provider access or complete a valid backup, then follow BACKUP_RESTORE_RUNBOOK.md.
```

- [ ] **Step 5: Run ops tests**

Run:

```powershell
pytest backend/tests/test_sprint104_ops_checks.py backend/tests/test_backup_assurance.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/ops_checks.py backend/tests/test_sprint104_ops_checks.py backend/tests/test_backup_assurance.py
git commit -m "feat: monitor backup freshness in ops checks"
```

### Task 5: Add Restore Validation Command

**Files:**
- Create: `backend/scripts/validate_restore.py`
- Create: `backend/tests/test_restore_validation.py`

- [ ] **Step 1: Write failing validation tests**

Tests must call pure helpers and assert:

- production-like URL is rejected unless `--allow-production-target` is set;
- missing required tables fails;
- Alembic revision mismatch fails;
- two fixture tenants with cross-tenant visibility fail;
- passing validation produces structured JSON without secrets;
- output includes achieved RPO/RTO when timestamps are supplied.

- [ ] **Step 2: Run tests and verify import failure**

Run:

```powershell
pytest backend/tests/test_restore_validation.py -v
```

Expected: FAIL because the script module does not exist.

- [ ] **Step 3: Implement validation helpers**

Provide:

```python
def validate_target_url(database_url: str, allow_production_target: bool) -> None
def validate_required_tables(inspector) -> list[dict]
def validate_alembic_revision(connection, expected_revision: str | None) -> dict
def validate_tenant_isolation(session, tenant_a: int, tenant_b: int) -> dict
def build_report(...) -> dict
```

The command is read-only. It must never execute migrations, delete data, send
webhooks, start schedulers, or contact external enrichment providers.

- [ ] **Step 4: Add CLI**

Required arguments:

```text
--database-url
--environment
--backup-id
--operator
--expected-revision
--backup-completed-at
--restore-started-at
--output
```

Optional:

```text
--tenant-a
--tenant-b
--allow-production-target
```

Exit `0` only when every required validation passes.

- [ ] **Step 5: Run tests**

Run:

```powershell
pytest backend/tests/test_restore_validation.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/scripts/validate_restore.py backend/tests/test_restore_validation.py
git commit -m "feat: add isolated restore validation command"
```

### Task 6: Add Production Configuration Contract

**Files:**
- Modify: `docker-compose.prod.yml`
- Modify: `.env.dokploy.example`
- Modify: `.env.example`
- Create: `backend/tests/test_backup_configuration_contract.py`

- [ ] **Step 1: Write failing configuration tests**

Read files as text and assert:

```python
REQUIRED_ENV = {
    "UKIP_BACKUP_MONITOR_ENABLED",
    "UKIP_BACKUP_ENVIRONMENT",
    "UKIP_BACKUP_PROVIDER_REACHABLE",
    "UKIP_BACKUP_RPO_HOURS",
    "UKIP_BACKUP_CRITICAL_AFTER_HOURS",
}
```

All variables must appear in production compose and Dokploy example. No S3
secret key, database dump credential, or bucket access token may be introduced
into application environment variables.

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
pytest backend/tests/test_backup_configuration_contract.py -v
```

Expected: FAIL because variables are absent.

- [ ] **Step 3: Add non-secret settings**

Production defaults:

```yaml
UKIP_BACKUP_MONITOR_ENABLED: ${UKIP_BACKUP_MONITOR_ENABLED:-1}
UKIP_BACKUP_ENVIRONMENT: ${UKIP_BACKUP_ENVIRONMENT:-production}
UKIP_BACKUP_PROVIDER_REACHABLE: ${UKIP_BACKUP_PROVIDER_REACHABLE:-1}
UKIP_BACKUP_RPO_HOURS: ${UKIP_BACKUP_RPO_HOURS:-24}
UKIP_BACKUP_CRITICAL_AFTER_HOURS: ${UKIP_BACKUP_CRITICAL_AFTER_HOURS:-26}
```

Local `.env.example` defaults monitoring to `0`.

- [ ] **Step 4: Run contract tests**

Run:

```powershell
pytest backend/tests/test_backup_configuration_contract.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docker-compose.prod.yml .env.dokploy.example .env.example backend/tests/test_backup_configuration_contract.py
git commit -m "chore: define backup monitoring configuration"
```

### Task 7: Write the Backup and Restore Runbook

**Files:**
- Create: `docs/operating/BACKUP_RESTORE_RUNBOOK.md`
- Create: `docs/operating/templates/BACKUP_RESTORE_EVIDENCE_TEMPLATE.md`
- Modify: `docs/operating/DOKPLOY_VPS_RUNBOOK.md`
- Modify: `docs/operating/DOKPLOY_PRODUCTION_CHECKLIST.md`
- Create: `backend/tests/test_backup_runbook_contract.py`

- [ ] **Step 1: Write failing runbook contract tests**

Assert the runbook contains:

- `RPO: 24 hours`;
- `RTO: 4 hours`;
- `7 daily`, `4 weekly`, `3 monthly`;
- `26 hours`;
- PostgreSQL and `ukip_static_data` as restorable;
- Redis, ChromaDB, and DuckDB as reconstructible;
- isolated restore requirement;
- exact validator command;
- disable schedulers/webhooks/notifications in drill;
- evidence template link;
- incident cutover requires separate approval.

- [ ] **Step 2: Run test and verify missing file failure**

Run:

```powershell
pytest backend/tests/test_backup_runbook_contract.py -v
```

Expected: FAIL because the runbook is absent.

- [ ] **Step 3: Write the runbook**

Include:

1. ownership and escalation;
2. Dokploy PostgreSQL backup setup;
3. S3 bucket encryption, region, versioning/object-lock guidance;
4. retention configuration;
5. static volume backup;
6. how provider automation posts metadata to `/ops/backups/events`;
7. freshness verification through `/ops/checks`;
8. isolated drill provisioning;
9. database and static restore;
10. exact `python -m backend.scripts.validate_restore ...` command;
11. ChromaDB re-index;
12. cleanup/sanitization;
13. evidence completion and approval;
14. incident restore/cutover decision.

- [ ] **Step 4: Add evidence template**

The template captures backup ID, release, revision, region, operator, approver,
expected/achieved RPO/RTO, validation table, failures, corrective actions,
report checksum, and final result.

- [ ] **Step 5: Link operational docs**

Replace generic “test backup and restore” wording with links to the runbook and
explicitly state that provider provisioning and the first drill are operator
actions.

- [ ] **Step 6: Run contract tests**

Run:

```powershell
pytest backend/tests/test_backup_runbook_contract.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add docs/operating/BACKUP_RESTORE_RUNBOOK.md docs/operating/templates/BACKUP_RESTORE_EVIDENCE_TEMPLATE.md docs/operating/DOKPLOY_VPS_RUNBOOK.md docs/operating/DOKPLOY_PRODUCTION_CHECKLIST.md backend/tests/test_backup_runbook_contract.py
git commit -m "docs: add backup restore runbook"
```

### Task 8: Reconcile Legal and Enterprise Claims

**Files:**
- Modify: `docs/legal/ROPA.md`
- Modify: `docs/legal/PRIVACY_CONTROLS_OVERVIEW.md`
- Modify: `docs/legal/DPA_BASELINE.md`
- Modify: `docs/legal/SUBPROCESSOR_REGISTER.md`
- Modify: `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
- Modify: `docs/product/TRACEABILITY_MATRIX.md`
- Modify: `backend/enterprise_controls.py`
- Create: `backend/tests/test_backup_claim_consistency.py`

- [ ] **Step 1: Write failing claim-consistency tests**

Assert:

- no document says the runbook is approved before it exists;
- no document says a restore drill passed unless a committed evidence record is
  referenced;
- all legal docs use RPO 24h and RTO 4h;
- `ER-BCP-001` is `implemented`, not `verified`, after repository-side
  implementation;
- the next gate explicitly requires two backup cycles and one restore drill;
- the subprocessor register retains explicit operator placeholders for provider
  and region until provisioned.

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
pytest backend/tests/test_backup_claim_consistency.py -v
```

Expected: FAIL on premature or inconsistent claims.

- [ ] **Step 3: Reconcile claims**

Use this honest status after code/runbook implementation but before real
provisioning:

```text
Repository controls and runbook implemented; provider configuration, two
successful backup cycles, and the first isolated restore drill remain pending.
```

Advance `ER-BCP-001` from `identified` to `implemented` only after all automated
tests and the runbook exist. Do not mark `verified`.

- [ ] **Step 4: Run enterprise parity lint and tests**

Run:

```powershell
python scripts/lint_enterprise_readiness.py
pytest backend/tests/test_backup_claim_consistency.py backend/tests/test_enterprise_controls.py backend/tests/test_enterprise_readiness_docs.py -v
```

Expected: lint and tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add docs/legal docs/product/ENTERPRISE_CONTROL_REGISTER.md docs/product/TRACEABILITY_MATRIX.md backend/enterprise_controls.py backend/tests/test_backup_claim_consistency.py
git commit -m "docs: align backup assurance claims"
```

### Task 9: Final Automated Verification

**Files:**
- Verify all files from Tasks 1-8.

- [ ] **Step 1: Run focused backup suite**

Run:

```powershell
pytest backend/tests/test_backup_assurance.py backend/tests/test_backup_ops_api.py backend/tests/test_restore_validation.py backend/tests/test_backup_configuration_contract.py backend/tests/test_backup_runbook_contract.py backend/tests/test_backup_claim_consistency.py -v
```

Expected: PASS.

- [ ] **Step 2: Run operational and enterprise regressions**

Run:

```powershell
pytest backend/tests/test_sprint104_ops_checks.py backend/tests/test_sprint104_enterprise_readiness.py backend/tests/test_enterprise_controls.py backend/tests/test_enterprise_readiness_docs.py -v
```

Expected: PASS.

- [ ] **Step 3: Run migration and full backend suite**

Run:

```powershell
python -m alembic upgrade head
pytest backend/tests -q
```

Expected: migration reaches head and backend tests PASS with documented skips.

- [ ] **Step 4: Run static consistency checks**

Run:

```powershell
python scripts/lint_enterprise_readiness.py
git diff --check
rg -n "runbook approved|first restore drill completed|RPO [^2]|RTO [^4]" docs/legal docs/operating docs/product
```

Expected:

- enterprise lint passes;
- no whitespace errors;
- no premature operational claims;
- objectives remain RPO 24h and RTO 4h.

- [ ] **Step 5: Commit final corrections when required**

If verification changes files:

```powershell
git add backend docs scripts docker-compose.prod.yml .env.example .env.dokploy.example
git commit -m "fix: finalize backup assurance verification"
```

Do not create an empty commit.

### Task 10: Perform Operator Provisioning and First Drill

**Files:**
- Create after execution: `docs/operating/evidence/ER-BCP-001/YYYY-MM-DD-backup-restore-drill.md`, using the drill completion date
- Update after successful evidence: `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
- Update after successful evidence: `backend/enterprise_controls.py`

- [ ] **Step 1: Provision operator-owned resources**

In Dokploy/provider consoles:

- configure encrypted daily PostgreSQL backups;
- configure backup of `ukip_static_data`;
- configure S3-compatible off-site destination;
- set 7 daily, 4 weekly, and 3 monthly retention;
- record provider and region in the subprocessor register;
- enable versioning or object lock where supported.

- [ ] **Step 2: Connect provider automation to evidence API**

After each terminal backup, post non-secret metadata to:

```text
POST /ops/backups/events
```

Use an admin credential dedicated to operations and do not include S3 or
database credentials in the payload.

- [ ] **Step 3: Observe two successful cycles**

Confirm:

- `/ops/backups/status` is `ok`;
- `/ops/checks` includes `backup_freshness=ok`;
- alert delivery was tested for a simulated stale condition;
- both backup events have size, integrity, encryption, region, and retention
  metadata.

- [ ] **Step 4: Execute isolated restore drill**

Follow `BACKUP_RESTORE_RUNBOOK.md`, run the validator, rebuild ChromaDB, and
complete the evidence template.

- [ ] **Step 5: Review maturity**

If RPO <= 24 hours, RTO <= 4 hours, every required validation passes, and
evidence is approved, advance `ER-BCP-001` from `implemented` to `verified`.

Do not advance to `operated` or `auditable` until their observation and evidence
requirements are separately satisfied.

- [ ] **Step 6: Commit drill evidence and maturity update**

```powershell
git add docs/operating/evidence/ER-BCP-001 docs/product/ENTERPRISE_CONTROL_REGISTER.md backend/enterprise_controls.py docs/product/TRACEABILITY_MATRIX.md
git commit -m "ops: record first backup restore drill"
```
