#!/bin/bash
set -e
cd "$(dirname "$0")/.."
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
echo "Dev environment ready."
