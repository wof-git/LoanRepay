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

echo "=== Setting up daily backup cron ==="
ssh ${NAS_HOST} "
  mkdir -p ${NAS_PATH}/backups
  chmod +x ${NAS_PATH}/scripts/backup.sh
  # Remove any existing LoanRepay backup cron entry, then add fresh
  (crontab -l 2>/dev/null | grep -v '${NAS_PATH}/scripts/backup.sh') | crontab -
  (crontab -l 2>/dev/null; echo '0 2 * * * ${NAS_PATH}/scripts/backup.sh >> ${NAS_PATH}/backups/backup.log 2>&1') | crontab -
  echo 'Cron installed:'
  crontab -l | grep backup
"

echo "=== Smoke test ==="
curl -sf http://wofnas.tail6c8ab5.ts.net:5050/health && echo " OK" || echo " FAILED"

echo "=== Deployed to http://wofnas.tail6c8ab5.ts.net:5050/ ==="
