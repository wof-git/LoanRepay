#!/bin/bash
set -e

# Source .env from project root if it exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [ -f "${ENV_FILE}" ]; then
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
fi

NAS_HOST="${LOANREPAY_NAS_HOST:?Set LOANREPAY_NAS_HOST (e.g. user@host)}"
NAS_PATH="${LOANREPAY_NAS_PATH:?Set LOANREPAY_NAS_PATH (e.g. /volume3/Wof/repo/LoanRepay)}"
NAS_URL="${LOANREPAY_NAS_URL:?Set LOANREPAY_NAS_URL (e.g. http://host:5050)}"

echo "=== Pulling latest from Gitea on NAS ==="
ssh ${NAS_HOST} "
  export PATH=/usr/local/bin:\$PATH
  cd ${NAS_PATH}
  git pull origin master
"

echo "=== Building and starting on NAS ==="
ssh ${NAS_HOST} "
  export PATH=/usr/local/bin:\$PATH
  cd ${NAS_PATH}
  mkdir -p data
  docker compose -f docker/compose.yaml down 2>/dev/null || true
  docker compose -f docker/compose.yaml up --build -d
  sleep 5
  docker compose -f docker/compose.yaml ps
"

echo "=== Setting up backup directory ==="
ssh ${NAS_HOST} "
  mkdir -p ${NAS_PATH}/backups
  chmod +x ${NAS_PATH}/scripts/backup.sh
"
echo "NOTE: Configure daily backup via Synology DSM Task Scheduler if not already set up:"
echo "  Command: ${NAS_PATH}/scripts/backup.sh >> ${NAS_PATH}/backups/backup.log 2>&1"
echo "  Schedule: Daily at 2:00 AM"

echo "=== Smoke test ==="
curl -sf ${NAS_URL}/health && echo " OK" || echo " FAILED"

echo "=== Deployed to ${NAS_URL}/ ==="
