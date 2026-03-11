#!/usr/bin/env bash
set -euo pipefail

# Called by PostgreSQL archive_command:
#   archive_wal.sh %p %f
#
# Required env:
# - GOG_WAL_ARCHIVE_DIR: local or mounted path where WAL files are copied
# Optional env:
# - GOG_WAL_COMPRESS: set to "1" to gzip WAL files

SOURCE_PATH="${1:?missing source WAL path}"
WAL_FILE_NAME="${2:?missing WAL filename}"

: "${GOG_WAL_ARCHIVE_DIR:?GOG_WAL_ARCHIVE_DIR is required}"
GOG_WAL_COMPRESS="${GOG_WAL_COMPRESS:-0}"

mkdir -p "${GOG_WAL_ARCHIVE_DIR}"

if [[ "${GOG_WAL_COMPRESS}" == "1" ]]; then
    gzip -c "${SOURCE_PATH}" > "${GOG_WAL_ARCHIVE_DIR}/${WAL_FILE_NAME}.gz"
else
    cp "${SOURCE_PATH}" "${GOG_WAL_ARCHIVE_DIR}/${WAL_FILE_NAME}"
fi
