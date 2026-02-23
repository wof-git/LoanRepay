#!/bin/bash
# Restore LoanRepay SQLite database from a backup file
# Usage: restore.sh [backup_file]
#   If no backup file is given, lists available backups.
set -e

DB_PATH="${LOANREPAY_DB:-/volume3/Wof/repo/LoanRepay/data/loanrepay.db}"
BACKUP_DIR="${LOANREPAY_BACKUP_DIR:-/volume3/Wof/repo/LoanRepay/backups}"
COMPOSE_FILE="${LOANREPAY_COMPOSE:-/volume3/Wof/repo/LoanRepay/docker/compose.yaml}"
APP_URL="${LOANREPAY_URL:-http://localhost:5050}"

# If no argument, list available backups
if [ -z "$1" ]; then
    echo "Available backups in ${BACKUP_DIR}:"
    if [ -d "${BACKUP_DIR}" ]; then
        ls -lhrt "${BACKUP_DIR}"/loanrepay_*.db 2>/dev/null || echo "  (none found)"
    else
        echo "  Backup directory does not exist: ${BACKUP_DIR}"
    fi
    echo ""
    echo "Usage: $0 <backup_file>"
    exit 0
fi

BACKUP_FILE="$1"

# Validate backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

# Validate backup is a valid SQLite database
echo "Validating backup integrity..."
INTEGRITY=$(sqlite3 "${BACKUP_FILE}" "PRAGMA integrity_check;" 2>&1)
if [ "$INTEGRITY" != "ok" ]; then
    echo "ERROR: Backup file failed integrity check: ${INTEGRITY}" >&2
    exit 1
fi
echo "  Integrity check: ok"

# Stop the container
echo "Stopping LoanRepay container..."
docker compose -f "${COMPOSE_FILE}" stop

# Safety copy of current database
if [ -f "${DB_PATH}" ]; then
    SAFETY_COPY="${DB_PATH}.pre-restore.$(date +%Y%m%d_%H%M%S)"
    echo "Backing up current database to ${SAFETY_COPY}..."
    cp "${DB_PATH}" "${SAFETY_COPY}"
fi

# Remove WAL/SHM files (stale journal from stopped container)
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm"

# Copy backup into place
echo "Restoring from ${BACKUP_FILE}..."
cp "${BACKUP_FILE}" "${DB_PATH}"

# Restart container
echo "Starting LoanRepay container..."
docker compose -f "${COMPOSE_FILE}" start

# Health check (wait up to 15 seconds)
echo "Waiting for app to come up..."
for i in $(seq 1 15); do
    if curl -sf "${APP_URL}/api/loans" > /dev/null 2>&1; then
        echo "  Health check passed!"
        echo ""
        echo "Restore complete. Current DB: ${DB_PATH}"
        [ -n "${SAFETY_COPY}" ] && echo "Pre-restore backup: ${SAFETY_COPY}"
        exit 0
    fi
    sleep 1
done

echo "WARNING: Health check failed after 15s. App may still be starting." >&2
echo "Check with: docker compose -f ${COMPOSE_FILE} logs" >&2
exit 1
