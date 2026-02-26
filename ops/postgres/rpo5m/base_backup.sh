#!/usr/bin/env bash
set -euo pipefail

# Creates a compressed base backup for PITR.
# Run this from cron/systemd (recommended daily).
#
# Required env:
# - PGHOST, PGPORT, PGUSER, PGPASSWORD
# - GOG_BASEBACKUP_DIR
# Optional env:
# - GOG_BASEBACKUP_RETENTION_DAYS (default 14)

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${GOG_BASEBACKUP_DIR:?GOG_BASEBACKUP_DIR is required}"

RETENTION_DAYS="${GOG_BASEBACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST_DIR="${GOG_BASEBACKUP_DIR}/${TIMESTAMP}"

mkdir -p "${DEST_DIR}"

pg_basebackup \
  --host "${PGHOST}" \
  --port "${PGPORT}" \
  --username "${PGUSER}" \
  --pgdata "${DEST_DIR}" \
  --format tar \
  --gzip \
  --wal-method stream \
  --checkpoint fast \
  --verbose

# Retention cleanup
find "${GOG_BASEBACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} +
