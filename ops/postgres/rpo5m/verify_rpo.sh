#!/usr/bin/env bash
set -euo pipefail

# Fails if no WAL file has been archived recently enough.
# Intended for monitoring alert hooks.
#
# Required env:
# - GOG_WAL_ARCHIVE_DIR
# Optional env:
# - GOG_RPO_SECONDS (default 300)

: "${GOG_WAL_ARCHIVE_DIR:?GOG_WAL_ARCHIVE_DIR is required}"
RPO_SECONDS="${GOG_RPO_SECONDS:-300}"

if [[ ! -d "${GOG_WAL_ARCHIVE_DIR}" ]]; then
    echo "CRITICAL: archive directory does not exist: ${GOG_WAL_ARCHIVE_DIR}"
    exit 2
fi

LATEST_FILE="$(find "${GOG_WAL_ARCHIVE_DIR}" -maxdepth 1 -type f -printf '%T@ %p\n' | sort -nr | head -n1 | awk '{print $2}')"

if [[ -z "${LATEST_FILE}" ]]; then
    echo "CRITICAL: no archived WAL files found"
    exit 2
fi

NOW="$(date +%s)"
MTIME="$(stat -c %Y "${LATEST_FILE}")"
AGE="$((NOW - MTIME))"

if (( AGE > RPO_SECONDS )); then
    echo "CRITICAL: latest archived WAL is ${AGE}s old (> ${RPO_SECONDS}s)"
    exit 2
fi

echo "OK: latest archived WAL age ${AGE}s (<= ${RPO_SECONDS}s)"
