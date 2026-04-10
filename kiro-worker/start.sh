#!/bin/bash
# start.sh — Start the kiro-worker with guaranteed correct source path.
# This script ensures the editable install always points to the right source
# regardless of what kiro-cli may have done to the .pth file.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKER_SRC="$REPO_ROOT/kiro-worker/src"
PTH_FILE="$REPO_ROOT/kiro-worker/.venv/lib/python3.12/site-packages/__editable__.kiro_worker-1.0.0.pth"

# Ensure pth file points to correct source
current=$(cat "$PTH_FILE" 2>/dev/null)
if [ "$current" != "$WORKER_SRC" ]; then
    echo "Fixing .pth file: $current -> $WORKER_SRC"
    chmod 644 "$PTH_FILE" 2>/dev/null
    echo "$WORKER_SRC" > "$PTH_FILE"
    chmod 444 "$PTH_FILE"
fi

cd "$REPO_ROOT/kiro-worker"
source .venv/bin/activate
exec uvicorn kiro_worker.main:app --host 0.0.0.0 --port 4000
