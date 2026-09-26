#!/usr/bin/env bash
# UKIP backup evidence recorder — issue #370, openspec change automate-backup-evidence.
#
# Runs on the production host (systemd timer), next to the reachability probe.
# For the newest object of each backup scope it downloads the stored bytes once,
# computes SHA-256 over exactly those bytes (never the provider ETag, which is
# not a full-object checksum), runs `gzip -t` on database dumps, and writes one
# evidence document per backup into the signals directory. The backend mounts
# that directory read-only and ingests each document as a `backup` event with
# operator `system:backup-recorder`. The application never receives a
# credential; this script never prints one.
#
# Credentials come from the systemd EnvironmentFile (root-owned, mode 600),
# never from this file. Required environment:
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  read-only: ListBucket + GetObject
#                                              on the backup prefix only
#   AWS_DEFAULT_REGION                         bucket region
#   S3_BACKUP_ENDPOINT, S3_BACKUP_BUCKET, S3_BACKUP_PREFIX
# Optional:
#   UKIP_EVIDENCE_OUT_DIR   default /var/lib/ukip/signals/backup-evidence
#   UKIP_BACKUP_ENVIRONMENT default production (must match the backend's)
#   UKIP_BACKUP_PROVIDER    default s3-compatible
#   UKIP_AWS_RUNNER         aws | docker | auto (default), as in the probe
#   UKIP_AWS_IMAGE          default amazon/aws-cli:latest
#
# Scopes are told apart by object suffix, the rule the backend already applies
# to legacy rows: `.sql.gz` is a database dump, `.tar` a volume archive.
#
# A download that does not complete, or that yields a different number of bytes
# than the listing reports, writes no document: a network error must never be
# recorded as a failed backup. Only a complete dump that fails `gzip -t` is
# recorded as `gzip_ok: false`, which the backend records as `failed`.
set -euo pipefail

OUT_DIR=${UKIP_EVIDENCE_OUT_DIR:-/var/lib/ukip/signals/backup-evidence}
ENVIRONMENT=${UKIP_BACKUP_ENVIRONMENT:-production}
PROVIDER=${UKIP_BACKUP_PROVIDER:-s3-compatible}
RECORDER="ukip-backup-evidence-recorder/1"
KEEP_DAYS=14
: "${S3_BACKUP_ENDPOINT:?S3_BACKUP_ENDPOINT is required}"
: "${S3_BACKUP_BUCKET:?S3_BACKUP_BUCKET is required}"
: "${S3_BACKUP_PREFIX:?S3_BACKUP_PREFIX is required}"

RUNNER=${UKIP_AWS_RUNNER:-auto}
if [ "$RUNNER" = "auto" ]; then
  if command -v aws >/dev/null 2>&1; then RUNNER=aws; else RUNNER=docker; fi
fi
case "$RUNNER" in
  aws|docker) ;;
  *)
    echo "UKIP_AWS_RUNNER must be aws, docker or auto (got: $RUNNER)" >&2
    exit 2
    ;;
esac

aws_cli() {
  if [ "$RUNNER" = "aws" ]; then
    aws "$@"
  else
    # `-e NAME` forwards the value from this process's environment. Writing
    # `-e NAME=value` would publish the credential in the host's process list.
    docker run --rm -i --network host \
      -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION \
      "${UKIP_AWS_IMAGE:-amazon/aws-cli:latest}" "$@"
  fi
}

# newest <suffix> → "key<TAB>size<TAB>last_modified", or nothing when there is none.
# The CLI paginates the whole listing before applying --query.
newest() {
  aws_cli s3api list-objects-v2 \
    --endpoint-url "$S3_BACKUP_ENDPOINT" \
    --bucket "$S3_BACKUP_BUCKET" \
    --prefix "$S3_BACKUP_PREFIX" \
    --query "reverse(sort_by(Contents[?ends_with(Key, '$1')], &LastModified))[0].[Key, Size, LastModified]" \
    --output text
}

WORK=$(mktemp -d)
chmod 0700 "$WORK"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$OUT_DIR"
chmod 0755 "$OUT_DIR"
failures=0

record() {
  local scope=$1 suffix=$2 line key size last_modified relative doc_name doc tmp sha actual gzip_ok observed_at
  if ! line=$(newest "$suffix"); then
    echo "scope=$scope listing_failed" >&2
    return 1
  fi
  if [ -z "$line" ] || [ "$line" = "None" ]; then
    echo "scope=$scope no_object"
    return 0
  fi
  IFS=$'\t' read -r key size last_modified <<<"$line"

  relative=${key#"$S3_BACKUP_PREFIX"}
  # The key goes into JSON by printf; refuse anything that would need escaping
  # rather than write a document the backend would have to guess about.
  case "$relative" in
    *\"*|*\\*|*$'\n'*|"") echo "scope=$scope key_needs_escaping_refused" >&2; return 1 ;;
  esac
  case "$size" in
    ''|*[!0-9]*) echo "scope=$scope invalid_size_in_listing" >&2; return 1 ;;
  esac

  doc_name="$scope-${relative//\//_}.json"
  doc="$OUT_DIR/$doc_name"
  if [ -e "$doc" ]; then
    echo "scope=$scope backup_id=$relative already_recorded"
    return 0
  fi

  if ! aws_cli s3 cp --endpoint-url "$S3_BACKUP_ENDPOINT" \
      "s3://$S3_BACKUP_BUCKET/$key" - > "$WORK/object" 2>"$WORK/cp.err"; then
    echo "scope=$scope backup_id=$relative download_failed" >&2
    return 1
  fi
  actual=$(wc -c < "$WORK/object" | tr -d ' ')
  if [ "$actual" != "$size" ]; then
    echo "scope=$scope backup_id=$relative truncated expected=$size got=$actual" >&2
    return 1
  fi
  sha=$(sha256sum "$WORK/object" | cut -d' ' -f1)
  if [ "$scope" = "database" ]; then
    if gzip -t "$WORK/object" 2>/dev/null; then gzip_ok=true; else gzip_ok=false; fi
  else
    gzip_ok=null
  fi
  rm -f "$WORK/object"

  observed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # Write then rename: the backend must never read a half-written document.
  tmp=$(mktemp "$OUT_DIR/.tmp.XXXXXX")
  printf '{"schema_version": 1, "recorder": "%s", "observed_at": "%s", "environment": "%s", "scope": "%s", "backup_id": "%s", "completed_at": "%s", "size_bytes": %s, "sha256": "%s", "gzip_ok": %s, "provider": "%s"}\n' \
    "$RECORDER" "$observed_at" "$ENVIRONMENT" "$scope" "$relative" "$last_modified" "$size" "$sha" "$gzip_ok" "$PROVIDER" > "$tmp"
  chmod 0644 "$tmp"
  mv -f "$tmp" "$doc"
  echo "scope=$scope backup_id=$relative size=$size gzip_ok=$gzip_ok recorded"
}

record database .sql.gz || failures=$((failures + 1))
record volume .tar || failures=$((failures + 1))

# The backend accepts documents up to 14 days old; keep no more than that.
find "$OUT_DIR" -maxdepth 1 -type f -name '*.json' -mtime +"$KEEP_DAYS" -delete

# A failed scope leaves the other scope's evidence written, and the unit marked
# failed so systemd shows it.
[ "$failures" -eq 0 ]
