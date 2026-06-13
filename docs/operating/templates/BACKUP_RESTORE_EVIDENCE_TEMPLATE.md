# Backup and Restore Evidence

Use one copy for each backup review or isolated restore drill. Do not include
passwords, tokens, credentials, database URLs, connection strings, bucket keys,
or backup contents.

## Identification

- Control ID: `ER-BCP-001`
- Evidence date:
- Environment:
- Provider:
- Backup ID:
- Provider backup job ID:
- Provider restore job ID:
- Release:
- Alembic revision:
- Storage region:
- Retention class:
- Operator:
- Approver:

## Recovery Objectives

| Objective | Expected | Achieved | Result |
| --- | --- | --- | --- |
| Expected RPO | 24 hours | Achieved RPO: | Pass / Fail |
| Expected RTO | 4 hours | Achieved RTO: | Pass / Fail |

- Backup completed at:
- Restore started at:
- Validation completed at:

## Backup Evidence

- PostgreSQL size:
- PostgreSQL integrity reference:
- PostgreSQL encryption confirmed:
- `ukip_static_data` snapshot or manifest:
- Static-data integrity reference:
- Bucket versioning confirmed:
- Object lock or immutability status:
- Evidence API event ID:
- `/ops/backups/status` result:
- `/ops/checks` backup freshness result:

## Validation

| Validation | Evidence or report reference | Result | Notes |
| --- | --- | --- | --- |
| Isolated target confirmed | | Pass / Fail | |
| Required PostgreSQL tables present | | Pass / Fail | |
| Alembic revision matches release | | Pass / Fail | |
| Tenant isolation passes | | Pass / Fail | |
| `ukip_static_data` restored | | Pass / Fail | |
| ChromaDB re-index completed | | Pass / Fail | |
| DuckDB artifacts reconstructed | | Pass / Fail | |
| Redis started without restored source-of-record state | | Pass / Fail | |
| Schedulers, webhooks, and notifications remained disabled | | Pass / Fail | |
| Drill cleanup and sanitization completed | | Pass / Fail | |

- Validator report path or immutable reference:
- Report checksum:

## Exceptions and Remediation

### Failures

- None recorded / describe:

### Corrective actions

| Action | Owner | Due date | Status |
| --- | --- | --- | --- |
| | | | |

### Residual risks

- None recorded / describe:

## Approval

- Final result: Passed / Passed with risk / Failed
- Operator decision and timestamp:
- Approver decision and timestamp:
- Incident cutover approval, if applicable:
- Follow-up evidence reference:
