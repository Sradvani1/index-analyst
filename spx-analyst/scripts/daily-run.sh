#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

export TZ=America/New_York
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/daily-run-$TODAY.log"

exec > "$LOG_FILE" 2>&1

echo "=== $TODAY: daily-run.sh started ==="

cd "$PROJECT_DIR"
source .venv/bin/activate
set -a; source .env; set +a

echo "=== $TODAY: prepare ==="
python -m src.cli prepare --date "$TODAY" --force

if [ -f "$PROJECT_DIR/output/$TODAY/$TODAY-analysis.md" ]; then
    echo "=== $TODAY: output already exists — skipping run ==="
else
    echo "=== $TODAY: run ==="
    python -m src.cli run --date "$TODAY"
fi

echo "=== $TODAY: done ==="
