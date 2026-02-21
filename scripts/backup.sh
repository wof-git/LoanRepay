#!/bin/bash
# WAL-safe SQLite backup for LoanRepay
# Uses sqlite3 .backup command (safe with WAL mode, no app restart needed)
set -e

DB_PATH="${LOANREPAY_DB:-/volume3/Wof/repo/LoanRepay/data/loanrepay.db}"
BACKUP_DIR="${LOANREPAY_BACKUP_DIR:-/volume3/Wof/repo/LoanRepay/backups}"
KEEP_DAYS="${LOANREPAY_BACKUP_KEEP_DAYS:-14}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/loanrepay_${TIMESTAMP}.db"

mkdir -p "${BACKUP_DIR}"

if [ ! -f "${DB_PATH}" ]; then
    echo "Database not found: ${DB_PATH}"
    exit 1
fi

sqlite3 "${DB_PATH}" ".backup '${BACKUP_FILE}'"

echo "Backup created: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

# Delete backups older than KEEP_DAYS
find "${BACKUP_DIR}" -name "loanrepay_*.db" -mtime +${KEEP_DAYS} -delete 2>/dev/null || true

REMAINING=$(find "${BACKUP_DIR}" -name "loanrepay_*.db" | wc -l)
echo "Backups retained: ${REMAINING}"
