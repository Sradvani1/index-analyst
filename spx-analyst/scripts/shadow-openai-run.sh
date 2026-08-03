#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

export TZ=America/New_York
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/shadow-openai-$TODAY.log"

exec > "$LOG_FILE" 2>&1

echo "=== $TODAY: shadow-openai run started ==="

cd "$PROJECT_DIR"
source .venv/bin/activate

# Load shadow environment
if [ -f .env.shadow-openai ]; then
    set -a; source .env.shadow-openai; set +a
else
    echo "ERROR: .env.shadow-openai not found"
    exit 1
fi

echo "=== $TODAY: checking if market is open ==="
MARKET_STATUS=$(python -c "
import yfinance as yf
d = yf.Ticker('^GSPC').history(period='1d')
print('ok' if not d.empty else 'closed')
" 2>/dev/null) || MARKET_STATUS='ok'

if [ "$MARKET_STATUS" = "closed" ]; then
    echo "  market closed — skipping to avoid API waste"
    echo "=== $TODAY: done ==="
    exit 0
fi

echo "=== $TODAY: prepare ==="
python -m src.cli prepare --date "$TODAY" --force

if [ -f "$PROJECT_DIR/output/shadow-openai/$TODAY/$TODAY-analysis.md" ]; then
    echo "=== $TODAY: output already exists — skipping run ==="
else
    echo "=== $TODAY: run (OpenAI gpt-5.6-terra) ==="
    python -m src.cli run --date "$TODAY"
fi

echo "=== $TODAY: shadow-openai done ==="