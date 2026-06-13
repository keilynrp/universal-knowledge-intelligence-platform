# Dokploy VPS Runbook for UKIP Pilot Production

This runbook is the operational path we recommend for the first stakeholder-facing
deployment of UKIP on a VPS managed through Dokploy.

It is intentionally optimized for a controlled pilot with science and technology
stakeholders, not for broad public SaaS traffic.

## Deployment Shape

- Frontend app: `https://ukip.example.org`
- Backend API: `https://api.ukip.example.org`
- Database: Dokploy-managed PostgreSQL with persistent storage
- Images: prebuilt GHCR images
- Backend replicas: `1`
- Frontend replicas: `1`

## Why This Shape

UKIP is ready for pilot production validation, but some operational behavior is
still intentionally conservative:

- scheduled imports and scheduled reports still run inside the backend process
- multi-replica backend deployment would currently risk duplicate scheduler work
- the safest first rollout is one backend replica with Dokploy-managed PostgreSQL

## Files to Use

- Compose file: [D:\universal-knowledge-intelligence-platform\docker-compose.prod.yml](D:\universal-knowledge-intelligence-platform\docker-compose.prod.yml)
- Env template: [D:\universal-knowledge-intelligence-platform\.env.dokploy.example](D:\universal-knowledge-intelligence-platform\.env.dokploy.example)
- Step-by-step setup: [D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_STEP_BY_STEP_SETUP.md](D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_STEP_BY_STEP_SETUP.md)
- Current pilot values: [D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_PILOT_DEPLOYMENT_VALUES.md](D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_PILOT_DEPLOYMENT_VALUES.md)
- High-level checklist: [D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_PRODUCTION_CHECKLIST.md](D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_PRODUCTION_CHECKLIST.md)
- Backup, restore, and disaster recovery procedure:
  [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md)

The repository procedure is implemented. Provider provisioning, two successful
backup cycles, and the first isolated restore drill remain pending operator
actions. Do not treat this document or a configured checkbox as completed
recovery evidence.

## Before Touching the VPS

1. Make sure GitHub Actions built and published both GHCR images.
2. Choose a pinned image tag for the rollout:
   - `ghcr.io/<owner>/ukip-backend:sha-<commit>`
   - `ghcr.io/<owner>/ukip-frontend:sha-<commit>`
3. Confirm the frontend image was built with the final API domain.
4. Generate production secrets:
   - `JWT_SECRET_KEY`
   - `SESSION_SECRET_KEY`
   - `ENCRYPTION_KEY`
5. Decide the pilot domains:
   - app domain
   - API domain
6. Decide the bootstrap admin account for the pilot.

The frontend Docker image embeds `NEXT_PUBLIC_API_URL` during build. Set the
GitHub Actions repository variable `NEXT_PUBLIC_API_URL` before building the
release image if the pilot API domain is not `https://api.ukip.inbounduxd.com`.

## Secret Generation

For the Fernet encryption key:

```powershell
.\.venv\Scripts\python.exe scripts\generate_fernet_key.py
```

For the JWT and session secrets, use long random values from your password
manager or a secure generator. Prefer at least 32 characters.

## Dokploy Resources

Create these resources first:

1. One PostgreSQL service with persistent storage
2. One Compose application for UKIP
3. One backup destination for PostgreSQL snapshots and any attached volume backups
4. Two domains with TLS:
   - app
   - API
5. GHCR registry credentials if the images are private

## GHCR Registry Access

If `docker manifest inspect ghcr.io/<owner>/ukip-backend:<tag>` returns
`unauthorized`, configure Dokploy registry credentials before deploying.

Use a GitHub token with package read access:

- scope: `read:packages`
- registry: `ghcr.io`
- username: the GitHub account with package access
- password/token: the generated token

Alternatively, make the GHCR packages public. For the first controlled pilot,
authenticated registry pulls are preferred.

## Recommended VPS Size

For the first science/technology pilot:

- `4 vCPU`
- `8 GB RAM`
- `120 GB SSD`

Prefer this larger size if you expect heavy enrichment or large bibliographic
loads during the pilot:

- `8 vCPU`
- `16 GB RAM`

## Dokploy App Setup

### 1. Create PostgreSQL

- provision a PostgreSQL service in Dokploy
- enable persistence
- enable automatic backups
- copy the resulting connection string

### 2. Create the UKIP Compose App

Use:

- repository: this repo
- compose file: `docker-compose.prod.yml`
- registry credentials: GHCR credentials if the package is private

### 3. Set Environment Variables

Load values from [D:\universal-knowledge-intelligence-platform\.env.dokploy.example](D:\universal-knowledge-intelligence-platform\.env.dokploy.example)
into the Dokploy environment screen.

Minimum required:

- `UKIP_BACKEND_IMAGE`
- `UKIP_FRONTEND_IMAGE`
- `DATABASE_URL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH`
- `JWT_SECRET_KEY`
- `SESSION_SECRET_KEY`
- `ENCRYPTION_KEY`
- `ALLOWED_ORIGINS`
- `NEXT_PUBLIC_API_URL`

Recommended for the first pilot:

- `RUN_DB_MIGRATIONS_ON_START=0`
- `SENTRY_ENABLED=0`
- `SENTRY_ENABLE_TRACING=0`
- `SCHOLAR_USE_FREE_PROXIES=0`
- `UKIP_ENABLE_LLM_QUERY_REFORMULATION=0`

## Migration Step

Do not rely on automatic schema migration for the first pilot release.

Run migrations once before opening traffic using the backend image:

```bash
alembic upgrade head
```

In Dokploy, do this as a one-off command or shell run against the backend image
with the same production environment variables.

After migrations finish successfully, start the main services.

## Deployment Sequence

1. Provision PostgreSQL
2. Set all environment variables
3. Run `alembic upgrade head`
4. Start `ukip-backend`
5. Verify backend health
6. Start `ukip-frontend`
7. Bind domains and enable TLS
8. Run smoke tests

## Required Smoke Tests

Run these immediately after deployment.

### Infrastructure

- `GET /health` returns `200`
- backend logs are stable for 10 minutes
- frontend loads with no API proxy failures

### Product Flow

- login with bootstrap admin
- import a science-oriented sample
- open internal catalog
- enrich one record
- open Executive Dashboard
- open Reports and generate one brief
- create one catalog portal from the imported batch
- open that portal in authenticated mode

### Pilot Readiness

- confirm CORS only allows the app domain
- confirm one database backup exists
- confirm rollback target image tags are recorded

## Rollback Plan

Keep the previous pinned image tags available.

Rollback procedure:

1. switch `UKIP_BACKEND_IMAGE` and `UKIP_FRONTEND_IMAGE` back to the previous SHA tags
2. redeploy the Compose app
3. if the issue is schema-related, stop and restore the latest tested database backup before reopening traffic

## Operational Constraints for the First Pilot

Keep these guardrails:

- one backend replica only
- no source builds on the VPS
- no `latest` tag pinning for the first pilot
- no open CORS policy
- no public signups
- no tracing-heavy telemetry by default

## What We Should Validate with Stakeholders

For science and technology stakeholders, the first production pilot should prove:

- import reliability for publication-oriented datasets
- enrichment quality for bibliographic records
- dashboard usefulness for quick portfolio reading
- report usefulness for executive or program review
- portal usefulness for friendlier discovery and consultation

## Exit Criteria for This Pilot Environment

We can call the Dokploy VPS deployment healthy when:

- health checks remain green for 24 hours
- at least one realistic import succeeds
- at least one catalog portal is created from a real batch
- one report is generated successfully
- provider provisioning and two successful backup cycles are evidenced
- the first isolated restore drill is approved using
  [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md)
- no recurring scheduler errors appear in backend logs
