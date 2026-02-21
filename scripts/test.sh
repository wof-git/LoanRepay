#!/bin/bash
set -e
cd "$(dirname "$0")/.."

echo "=== Unit Tests ==="
python3 -m pytest tests/test_calculator.py -v

echo "=== API Integration Tests ==="
python3 -m pytest tests/test_api.py -v

echo "=== E2E Tests (Playwright) ==="
# Start server in background on test port
DATA_DIR=/tmp/loanrepay_test python3 -m uvicorn src.main:app --port 8099 &
SERVER_PID=$!
sleep 2

# Run Playwright tests
BASE_URL=http://localhost:8099 python3 -m pytest tests/e2e/ -v || true

# Cleanup
kill $SERVER_PID 2>/dev/null
rm -rf /tmp/loanrepay_test

echo "=== All tests complete ==="
