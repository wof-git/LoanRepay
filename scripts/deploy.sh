#!/bin/bash
set -e
NAS_HOST="WOFNASadmin@wofnas.tail6c8ab5.ts.net"
NAS_PATH="/volume3/Wof/repo/LoanRepay"

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
curl -sf http://wofnas.tail6c8ab5.ts.net:5050/health && echo " OK" || echo " FAILED"

echo "=== Deployed to http://wofnas.tail6c8ab5.ts.net:5050/ ==="
