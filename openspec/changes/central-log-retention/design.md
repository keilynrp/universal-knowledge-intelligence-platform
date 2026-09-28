# Design — central log retention

## Shape

```
  VPS
  ┌───────────────────────────────────────────────────────────────────┐
  │  dokploy-traefik ── access log, JSON, no query strings ──┐        │
  │                                                          ▼        │
  │  ukip-backend ───── stdout, JSON, identity (#376) ───▶  SHIPPER   │
  │                                                     (systemd,     │
  │                                                      own AWS      │
  │                                                      credential,  │
  │                                                      write-only)  │
  └──────────────────────────────────────────────────────────┬────────┘
                                                             │
                           ┌─────────────────────────────────┴────────┐
                           ▼                                          ▼
               CloudWatch Logs, 30 days                  S3, Object Lock GOVERNANCE,
               /ukip/prod/backend                         1 year, gzip, by hour
               /ukip/prod/traefik                         ukip-prod-logs-<suffix>
               search now; gap 6 later                    evidence
```

## Decision 1: on the host, not in the compose file

Traefik is Dokploy's container, not a service in `docker-compose.prod.yml`, so
per-service `logging:` drivers cannot reach it. A daemon-wide driver would ship
every container on the host, Dokploy's own included. A shipper on the host that
follows exactly two sources is the smallest thing that covers both, and it
repeats the pattern the owner already accepted for backup evidence (#370): a
host service with its own narrow credential, installed from files reviewed in
this repo.

It reads the Docker log files as they are written and keeps its read position
on disk. A deploy that recreates `ukip-backend` loses only what the shipper had
not yet read, which is seconds, not the time since the last merge.

## Decision 2: two tiers, two stores

| | CloudWatch Logs | S3 archive |
|---|---|---|
| Retention | 30 days (log group setting) | 1 year (Object Lock default retention + lifecycle expiry at 366 days) |
| Purpose | answer "what did session X do" during an incident | prove it months later |
| Tamper resistance | IAM only | Object Lock `GOVERNANCE` |
| Reader | a read-only role, used by the operator | the same role, `GetObject` only |

Both are in AWS `us-east-2`, which already holds the backups: no new
subprocessor, and no written notice under DPA §8. A SaaS log service would be
one.

**A new bucket, not the backup bucket.** Different retention (1 year against
7 days), different writer, different readers. A misconfiguration of one does
not reach the other.

**`GOVERNANCE`, not `COMPLIANCE`.** The lines carry customer staff user IDs and
IP addresses, and the data lifecycle policy promises erasure on request.
`GOVERNANCE` stops an ordinary or stolen credential from deleting or shortening
retention; a principal holding `s3:BypassGovernanceRetention`, which nobody
uses day to day, can still honour a lawful erasure. `COMPLIANCE` would make
that promise impossible to keep for a year. It is also the mode the backup
bucket already uses.

## Decision 3: no credentials or capabilities in what is kept

Retention multiplies whatever a line leaks by a year.

- **Traefik:** the access log records the request path. It is configured to
  drop the query string on every router, not only the one known today to carry
  tokens, so a future URL with a capability is not kept either.
- **The SSO callback** (`backend/routers/auth_users.py`) redirects to
  `/login?token=<access>&refresh=<refresh>`. The refresh token is valid for 7
  days. Dropping query strings keeps it out of the log, but it still lands in
  browser history and can leak through `Referer`, so the flow itself is fixed
  first, as a prerequisite in its own issue: a short-lived, single-use code in
  the redirect, exchanged by the frontend with a `POST`. **The Traefik access
  log is not enabled until that ships.** The backend part of this change does
  not depend on it, because the backend log already records the path without
  the query.
- **Embed tokens** (`/embed/{token}/…`) are in the path, in both logs. See
  open question 4.

The configuration test (task 2.3) pins the dropped fields, so a later edit that
re-enables them fails in CI.

## Decision 4: two principals, neither of them the application

| Principal | Where | Allowed |
|---|---|---|
| `ukip-log-shipper` | the VPS, file readable by root only | `logs:CreateLogStream`, `logs:PutLogEvents` on the two groups; `s3:PutObject` on the archive prefix |
| `ukip-log-reader` | the operator, assumed when needed | `logs:StartQuery`, `logs:GetQueryResults`, `logs:FilterLogEvents`; `s3:GetObject`, `s3:ListBucket` on the archive |

The shipper cannot read what it wrote, delete it, or change retention. A
compromised VPS can add lines, not remove the ones already shipped. The
application holds no AWS credential for any of this.

## Decision 5: silence is detected

A shipper that stops produces no error anywhere anyone looks. It pings a
Healthchecks.io check every five minutes while it is delivering, and
Healthchecks.io pages through the Pushover integration from #377 when the pings
stop. The ping is sent only after a successful delivery, not on a timer alone,
so "running but failing to deliver" also pages.

## Decision 6: capture first, now

Documentation lands before any of the above. §7 step 1 and §5.1 say: during an
incident, nothing is merged to `main` until the logs are captured, because a
merge deploys and a deploy recreates the container. This is the whole
mitigation until the shipper runs, and a cheap one.

## Open questions

1. **Which shipper.** An Object Lock bucket refuses a `PutObject` without
   `Content-MD5` or an `x-amz-checksum-*` header. Whether Vector's `aws_s3`
   sink, Fluent Bit's `s3` output, or a CloudWatch export task / Firehose sends
   one is not confirmed. Task 1.1 is a one-hour spike against a scratch bucket
   that decides it; Vector is the first candidate because one process can feed
   both sinks.
2. **The client address.** The browser reaches the backend through Next.js's
   `/api/backend` rewrite, and uvicorn runs without `--forwarded-allow-ips`, so
   `request.client.host` is likely the frontend container's address for every
   browser request. If so, `client_ip` in the request log and
   `audit_logs.ip_address` (and the pivot from #384) all hold a proxy's
   address. Check before relying on either:
   `SELECT ip_address, count(*) FROM audit_logs WHERE created_at > now() - interval '7 days' GROUP BY 1 ORDER BY 2 DESC LIMIT 5;`
   The Traefik log is closer to the client, which is one reason it is in scope,
   but it is not the client either: Cloudflare proxies the origin
   (`docs/legal/SUBPROCESSOR_REGISTER.md`), so Traefik sees Cloudflare's edge
   address unless it trusts `CF-Connecting-IP` / `X-Forwarded-For` from
   Cloudflare's published ranges only. Task 2.2 must configure that, and 4.5
   must check that a known request shows its real address. The application fix is a separate issue (see proposal,
   non-goals).
3. **Who reads.** The design assumes the operator alone holds
   `ukip-log-reader`. Confirm, and whether it is assumed through the existing
   AWS account's SSO or an access key.
4. **Embed tokens in paths.** They are designed to be published in customer
   pages, so the risk is low; kept for a year they are still a list of every
   live widget. Options: keep them, or replace the token segment with a short
   hash in both logs. Recommended: hash, so a widget stays traceable without
   the log being a key ring.

## Risks

- **Shipper down:** lines accumulate in Docker's files and the heartbeat pages.
  If the container is recreated before the shipper recovers, the unread lines
  are lost: the same as today, and bounded by the paging delay.
- **CloudWatch or S3 unreachable:** the shipper buffers to disk and retries;
  the heartbeat stops after the delivery failures, and pages.
- **Cost:** at roughly 400 bytes per request line, even 100 000 requests a day
  is about 1.2 GB a month before compression. CloudWatch ingestion and a year
  of compressed S3 storage stay in single-digit dollars a month.
- **Disk:** Docker's `json-file` has no size limit today. The runbook adds
  `max-size`/`max-file` to the Docker daemon so the host cannot fill; the
  shipper, not Docker, is now what keeps history.
