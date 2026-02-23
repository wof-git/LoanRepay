#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime

# Read JSON input from stdin
try:
    data = json.load(sys.stdin)
except Exception:
    print("error")
    sys.exit(0)

# Extract model ID (short form)
model_id = data.get("model", {}).get("id", "unknown")
# Simplify: claude-sonnet-4-5-20250929 → sonnet-4-5
model_short = model_id.replace("claude-", "")
if model_short.count("-") >= 3:
    parts = model_short.rsplit("-", 1)
    if parts[-1].isdigit() and len(parts[-1]) == 8:
        model_short = parts[0]

# Get git branch
try:
    result = subprocess.run(
        ["git", "-C", os.path.expanduser("~/projects/LoanRepay"), "branch", "--show-current"],
        capture_output=True,
        text=True,
        timeout=2,
    )
    git_branch = result.stdout.strip() or "no-git"
except Exception:
    git_branch = "no-git"

# Timestamp
timestamp = datetime.now().strftime("%H:%M")

# Context usage
ctx = data.get("context_window", {})
usage = ctx.get("current_usage", {})
if usage:
    current = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    size = ctx.get("context_window_size", 1)
    pct = int(current * 100 / size) if size else 0
else:
    pct = 0

# Create 10-char bar
filled = pct // 10
bar = "█" * filled + "░" * (10 - filled)

print(f"{model_short} | {git_branch} | {bar} {pct}% | {timestamp}", end="")
