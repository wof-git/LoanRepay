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

echo "=== Smoke test ==="
curl -sf http://wofnas.tail6c8ab5.ts.net:5050/health && echo " OK" || echo " FAILED"

echo "=== Deployed to http://wofnas.tail6c8ab5.ts.net:5050/ ==="
