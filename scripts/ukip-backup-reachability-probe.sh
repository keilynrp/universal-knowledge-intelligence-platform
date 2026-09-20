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
#   UKIP_AWS_RUNNER         aws | docker | auto (default). The production host
#                           has Docker but no AWS CLI, so `auto` uses `aws` when
#                           it is installed and otherwise runs the pinned
#                           amazon/aws-cli image. Both paths write the same
#                           document; keeping them here is what stops a
#                           hand-written wrapper from living unreviewed on the
#                           server.
#   UKIP_AWS_IMAGE          default amazon/aws-cli:latest
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

RUNNER=${UKIP_AWS_RUNNER:-auto}
if [ "$RUNNER" = "auto" ]; then
  if command -v aws >/dev/null 2>&1; then RUNNER=aws; else RUNNER=docker; fi
fi

# A misconfigured runner must fail loudly. Reporting "unreachable" here would
# blame the provider for our own typo, and the backend cannot tell them apart.
case "$RUNNER" in
  aws|docker) ;;
  *)
    echo "UKIP_AWS_RUNNER must be aws, docker or auto (got: $RUNNER)" >&2
    exit 2
    ;;
esac

list_objects() {
  if [ "$RUNNER" = "aws" ]; then
    aws s3api list-objects-v2 \
      --endpoint-url "$S3_BACKUP_ENDPOINT" \
      --bucket "$S3_BACKUP_BUCKET" \
      --prefix "$S3_BACKUP_PREFIX" \
      --max-items 1
  else
    # `-e NAME` forwards the value from this process's environment. Writing
    # `-e NAME=value` would publish the credential in the host's process list.
    docker run --rm --network host \
      -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \
      "${UKIP_AWS_IMAGE:-amazon/aws-cli:latest}" s3api list-objects-v2 \
      --endpoint-url "$S3_BACKUP_ENDPOINT" \
      --bucket "$S3_BACKUP_BUCKET" \
      --prefix "$S3_BACKUP_PREFIX" \
      --max-items 1
  fi
}

mkdir -p "$(dirname "$OUT")"
observed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if list_objects >/dev/null 2>&1; then
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
