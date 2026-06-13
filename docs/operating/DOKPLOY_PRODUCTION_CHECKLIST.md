# Dokploy Production Checklist

For the full step-by-step rollout path, use:

- [D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_VPS_RUNBOOK.md](D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_VPS_RUNBOOK.md)
- [D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_STEP_BY_STEP_SETUP.md](D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_STEP_BY_STEP_SETUP.md)
- [D:\universal-knowledge-intelligence-platform\.env.dokploy.example](D:\universal-knowledge-intelligence-platform\.env.dokploy.example)
- [D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_PILOT_DEPLOYMENT_VALUES.md](D:\universal-knowledge-intelligence-platform\docs\operating\DOKPLOY_PILOT_DEPLOYMENT_VALUES.md)
- [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md)

This guide defines the minimum operational bar for a UKIP "pilot production"
deployment on a VPS managed with Dokploy.

The repository procedure is implemented. Provider provisioning, two successful
backup cycles, and the first isolated restore drill remain pending operator
actions. They require provider-side execution and approved evidence.

## Target Topology

- Frontend: `https://ukip.inbounduxd.com`
- API: `https://api.ukip.inbounduxd.com`
- PostgreSQL: separate Dokploy-managed database
- Deploy mode: prebuilt images from GHCR, not builds on the VPS
- Backend replicas: `1` while schedulers still run in-process

## Why This Shape

UKIP is ready for controlled production-like validation with large datasets, but
not yet for fully open commercial SaaS traffic. The main current constraint is
that scheduled imports and scheduled reports still run inside the backend web
process. A single backend replica avoids duplicate scheduler execution.

## Required Dokploy Resources

1. One application using [D:\universal-knowledge-intelligence-platform\docker-compose.prod.yml](D:\universal-knowledge-intelligence-platform\docker-compose.prod.yml)
2. One PostgreSQL database with persistent storage
3. One S3-compatible backup target for database and volume backups
4. Two domains:
   - `ukip.inbounduxd.com`
   - `api.ukip.inbounduxd.com`
5. GHCR registry credentials if packages are private

## GHCR Images

The Docker workflow now publishes:

- `ghcr.io/<owner>/ukip-backend:latest`
- `ghcr.io/<owner>/ukip-backend:sha-<commit>`
- `ghcr.io/<owner>/ukip-frontend:latest`
- `ghcr.io/<owner>/ukip-frontend:sha-<commit>`

For the first controlled deployment, pin Dokploy to the `sha-<commit>` tags,
not `latest`.

## Minimum Environment Variables

### Backend

- `UKIP_BACKEND_IMAGE`
- `DATABASE_URL`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH`
- `JWT_SECRET_KEY`
- `SESSION_SECRET_KEY`
- `ENCRYPTION_KEY`
- `ALLOWED_ORIGINS=https://ukip.inbounduxd.com`
- `RUN_DB_MIGRATIONS_ON_START=0`
- `SCHOLAR_USE_FREE_PROXIES=0`

### Frontend

- `UKIP_FRONTEND_IMAGE`
- `NEXT_PUBLIC_API_URL=https://api.ukip.inbounduxd.com`

### Conservative Flags

- `SENTRY_ENABLED=0`
- `SENTRY_ENABLE_TRACING=0`
- `UKIP_ENABLE_LLM_QUERY_REFORMULATION=0`

## Deployment Sequence

1. Provision PostgreSQL in Dokploy.
2. Configure automatic backups and verify the target bucket.
3. Set all environment variables in Dokploy.
4. Run the `ukip-migrate` service once before opening traffic.
5. Start `ukip-backend`.
6. Verify `GET /health` through Dokploy health checks.
7. Start `ukip-frontend`.
8. Bind domains and TLS certificates.
9. Run a smoke test:
   - login
   - `/health`
   - `/audit/feed`
   - `/branding/settings`
   - one import flow
   - one authority-resolution flow

## Massive Data Readiness Gate

Use the VPS for the first massive-data rehearsal only when all of these are
true:

- backend and frontend run from GHCR images
- PostgreSQL persistence is active
- provider provisioning and two successful backup cycles are evidenced
- the first isolated restore drill is approved under
  [BACKUP_RESTORE_RUNBOOK.md](BACKUP_RESTORE_RUNBOOK.md)
- Dokploy health checks are green for at least 24 hours
- backend logs show no repeating scheduler loop errors
- one realistic bulk import finished successfully

## Recommended First VPS Size

For the first production-like data rehearsal:

- `4 vCPU`
- `8 GB RAM`
- `120+ GB SSD`

If vector storage and heavy enrichment run simultaneously, prefer:

- `8 vCPU`
- `16 GB RAM`

## Things We Should Not Do Yet

- do not run multiple backend replicas
- do not enable Sentry tracing by default
- do not enable LLM query reformulation by default
- do not rely on bind mounts for stateful production data
- do not deploy straight from source builds on the VPS
