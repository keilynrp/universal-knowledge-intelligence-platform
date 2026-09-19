#!/usr/bin/env bash
# UKIP backup provider reachability probe — B4 of issue #320.
#
# Runs on the production host (systemd timer or Dokploy schedule), lists the
# backup prefix with the READ-ONLY provider credential, and writes a two-field
# heartbeat document that the backend reads through a read-only mount. The
# application never receives a provider credential; this script never prints
# one, and the document carries no path, bucket or key material.
#
# Credentials come from the systemd EnvironmentFile (root-owned, mode 600),
# never from this file. Required environment:
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  read-only, list-only credential
#   AWS_DEFAULT_REGION                         bucket region
#   S3_BACKUP_ENDPOINT, S3_BACKUP_BUCKET, S3_BACKUP_PREFIX
# Optional:
#   UKIP_REACHABILITY_OUT   default /var/lib/ukip/signals/backup-provider-reachability.json
#
# An unreachable provider is recorded as `false`, not as a missing file: the
# backend then reports `explicit_unreachable` rather than a dead-probe state.
# If this script itself stops running, the document ages out and the backend
# fails closed on its own after PROVIDER_REACHABILITY_MAX_AGE_MINUTES.
set -euo pipefail

OUT=${UKIP_REACHABILITY_OUT:-/var/lib/ukip/signals/backup-provider-reachability.json}
: "${S3_BACKUP_ENDPOINT:?S3_BACKUP_ENDPOINT is required}"
: "${S3_BACKUP_BUCKET:?S3_BACKUP_BUCKET is required}"
: "${S3_BACKUP_PREFIX:?S3_BACKUP_PREFIX is required}"

mkdir -p "$(dirname "$OUT")"
observed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if aws s3api list-objects-v2 \
      --endpoint-url "$S3_BACKUP_ENDPOINT" \
      --bucket "$S3_BACKUP_BUCKET" \
      --prefix "$S3_BACKUP_PREFIX" \
      --max-items 1 >/dev/null 2>&1; then
  reachable=true
else
  reachable=false
fi

# Write then rename: the backend must never observe a half-written document.
tmp=$(mktemp "${OUT}.XXXXXX")
printf '{"reachable": %s, "observed_at": "%s"}\n' "$reachable" "$observed_at" > "$tmp"
chmod 0644 "$tmp"
mv -f "$tmp" "$OUT"

echo "provider_reachable=$reachable observed_at=$observed_at"
