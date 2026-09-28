# Tasks — central log retention

Group 0 ships first and on its own: it is the only mitigation until the
shipper runs. Groups 1–3 are repo work and can ship as one PR once the spike
has chosen the shipper. Group 4 is operator work, and it is what closes gap 3.

## 0. Before anything is built

- [ ] 0.1 Plan §7 step 1 and §5.1: during an incident, nothing is merged to
      `main` until the logs are captured, because a merge deploys and a deploy
      recreates the container. Say it where a responder with a fix in hand
      will read it.
- [ ] 0.2 Open the prerequisite issue: the SSO callback stops putting tokens
      in the redirect URL (single-use, short-lived code exchanged by `POST`).
      The Traefik access log (4.4) waits for it; nothing else does.
- [ ] 0.3 Open the issue for the client address, if the query in design open
      question 2 shows a proxy's address in `audit_logs.ip_address`.
- [ ] 0.4 Owner answers to design open questions 3 (who reads) and 4 (embed
      tokens), recorded in design.md.

## 1. Choose the shipper

- [ ] 1.1 Spike, one hour, against a scratch bucket with Object Lock: does the
      candidate write to it (checksum header), resume from its read position
      after a restart, and deliver the same lines to CloudWatch? Vector first,
      Fluent Bit second. Record the result and the pinned version in
      design.md.

## 2. Reviewed host artefacts (`deploy/log-shipper/`)

- [ ] 2.1 Shipper configuration: two sources (`ukip-backend`, Traefik), two
      sinks (log groups `/ukip/prod/backend` and `/ukip/prod/traefik`; S3
      archive, gzip, hourly objects), a disk buffer, and a heartbeat after
      successful delivery. Credentials only from the environment file,
      never in the repo.
- [ ] 2.2 Traefik access-log configuration: JSON, query strings dropped on
      every router, request headers other than `User-Agent` dropped.
- [ ] 2.3 Configuration test: parses both files and fails if query strings or
      the `Authorization` header are kept, if a source or sink is missing, or
      if the heartbeat is not tied to delivery.
- [ ] 2.4 IAM policy documents for `ukip-log-shipper` (append and put only) and
      `ukip-log-reader` (query and get only), and a test that the shipper
      policy grants no `Get*`, `Delete*`, `Put*Retention*` or bypass action.
- [ ] 2.5 systemd unit, restart on failure, running as a dedicated user that
      can read the two log sources and nothing else it does not need.

## 3. Documentation

- [ ] 3.1 `docs/operating/LOG_RETENTION_RUNBOOK.md`: the bucket (Object Lock
      `GOVERNANCE`, 1-year default retention, expiry at 366 days), the two log
      groups at 30 days, both principals, the Docker daemon `max-size` and
      `max-file`, the install, rotation of the shipper credential, and how to
      query both tiers by `session_id`, `user_id` and client address.
- [ ] 3.2 Plan §7 step 1 becomes the query; §4 detection gaps and §11 gap 3
      say "in code" with what keeps it open, as gaps 2 and 8 do.
- [ ] 3.3 `docs/legal/ROPA.md` activity 3: destinations, 30 days and 1 year,
      readers. `docs/legal/SUBPROCESSOR_REGISTER.md`: fill the S3 row, and
      record that AWS receives request logs (IP addresses, customer staff user
      IDs). `docs/legal/MEXICO_ANNEX.md` §6: attributable request logs are no
      longer pending (#376).

## 4. Operator actions (not code)

- [ ] 4.1 Create the archive bucket and the two log groups with their
      retention, in `us-east-2`.
- [ ] 4.2 Create both principals from the policy documents.
- [ ] 4.3 Install the shipper and the Docker daemon limits; create its
      Healthchecks.io check with the Pushover integration at emergency.
- [ ] 4.4 After the SSO prerequisite ships: enable the Traefik access log in
      Dokploy from the reviewed copy.
- [ ] 4.5 Prove it: make a request, redeploy the backend, and find that
      request's line in CloudWatch and, after the hour closes, in S3. Stop the
      shipper and confirm the page arrives. Record both in the tabletop
      follow-up, then close gap 3.
