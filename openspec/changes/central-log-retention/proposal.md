# Keep request and proxy logs past the container, for a year

> **Closes:** incident response plan §11 gap 3 (no central log retention).
> **Owner decisions (2026-09-27):** 30 days searchable, 1 year as immutable
> evidence; the Traefik access log is included.
> **Prerequisite:** #408, the SSO callback stops putting tokens in the redirect
> URL. Until it ships, the proxy log is not turned on.

## Why

The request log is the only record of an ordinary read. Since #375 the audit
log covers exports, bulk reads, API-key reads and reads of the audit log
itself, but a first page of an ordinary list leaves no row; since #376 each
request line names the user and the session or key behind it. That line lives
in the container's stdout, in Docker's default `json-file` driver, and nothing
copies it anywhere.

It is shorter-lived than the plan says. The plan says container logs "vanish
with the container"; every merge to `main` deploys, and a deploy recreates the
container. The window of evidence is therefore the time since the last merge,
which on an ordinary day is hours. The first tabletop took 6 h 22 min to
detect. A merge in that window, including a responder deploying a fix before
capturing, and §7 step 1 returns an empty file.

The access log of Traefik is the only place that sees requests refused before
authentication (scans, credential stuffing, 401s). **Correction (2026-09-28):**
this proposal first said it was not on at all. Dokploy's own configuration
turns it on, for its "Requests" view: JSON, to
`/etc/dokploy/traefik/dynamic/access.log` on the host, with no size or age
limit, filtered to requests slower than 10 ms or retried, and **keeping query
strings**. So it is partial, unbounded, and already stores what this change
must not keep for a year (reset tokens in `?reset_token=`, for example).

## What Changes

- **A log shipper on the host**, installed like the backup evidence recorder
  (#370): a systemd service with its own write-only AWS credential and no
  application credential. It follows the Docker log file of `ukip-backend`
  and Traefik's access-log file as they are written, so a container recreated
  by a deploy no longer takes unread lines with it.
- **Two tiers of retention:**
  - **30 days in CloudWatch Logs**, searchable during an investigation, and the
    base any later anomaly detection (gap 6) would build on.
  - **1 year in a new S3 bucket with Object Lock in `GOVERNANCE` mode**,
    compressed, as evidence nobody with an ordinary credential can alter or
    delete.
- **Traefik's existing access log is corrected**, in the file Dokploy's
  "Requests" view reads: every request instead of only slow ones, and no query
  string on any router, so no URL that carries a capability is kept for a
  year.
- **Shipping has a heartbeat.** A shipper that stops is silent by nature; it
  pings its own Healthchecks.io check, which pages through the integration set
  up for #377.
- **Capture before deploy, starting now.** §7 and §5 say, before any code
  lands, that nothing is merged during an incident until the logs are captured.
  That closes the worst case while the rest is built.
- **§7 step 1 becomes a query**, not `docker logs`: CloudWatch for the last 30
  days, the S3 archive beyond them.
- **The legal records follow**: ROPA activity 3 states the destinations and the
  two retention periods instead of "per hosting configuration", and the
  subprocessor register records that AWS now receives request logs (IP
  addresses and customer staff user IDs), in the S3 row that still reads
  `[OPERATOR TO FILL]`.

## Non-goals

- Anomaly detection on logins or access patterns (gap 6). This change makes
  the data exist and last; watching it is the next change.
- Logs of the frontend, the engine and Redis: none of them sees an access that
  the backend or Traefik does not.
- Auditing every read in the database. #375 chose classes on purpose; this
  change makes the remainder durable instead of moving it.
- Fixing the client address the backend records in `audit_logs.ip_address`, if
  the check in the design confirms it is a proxy's. It deserves its own issue:
  it is an application fix with its own tests, and it matters with or without
  retention.

## Impact

- New host artefacts under `deploy/log-shipper/`: the shipper configuration,
  its systemd unit, and the IAM policy documents for the write-only and the
  read-only principals. A configuration test pins what it ships, where, and
  that query strings are dropped.
- Traefik's access-log configuration, applied in Dokploy and kept in the repo
  as the reviewed copy.
- `docs/operating/INCIDENT_RESPONSE_PLAN.md` §5, §7, §11 gap 3; a new
  `docs/operating/LOG_RETENTION_RUNBOOK.md`.
- `docs/legal/ROPA.md`, `docs/legal/SUBPROCESSOR_REGISTER.md`.
- No application code, no migration, no endpoint change.
- **Operator actions:** the bucket, the log groups and their retention, the two
  IAM principals, the Traefik setting in Dokploy, the shipper install, and a
  test that proves a log line survives a redeploy.
