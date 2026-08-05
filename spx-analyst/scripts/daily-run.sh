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

run_with_retry() {
    local max_attempts=3
    local attempt=1
    local status
    while true; do
        if "$@"; then
            return 0
        else
            status=$?
        fi
        attempt=$((attempt + 1))
        if [ "$attempt" -gt "$max_attempts" ]; then
            echo "  command failed after $max_attempts attempts" >&2
            return "$status"
        fi
        echo "  command failed; retrying ($attempt/$max_attempts) in 30s" >&2
        sleep 30
    done
}

echo "=== $TODAY: checking if market is open ==="
MARKET_STATUS=$(python - 2>/dev/null <<'PY'
import datetime as dt
import time
from zoneinfo import ZoneInfo

import yfinance as yf
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    Holiday,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
)


class NYSECalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


today = dt.datetime.now(ZoneInfo("America/New_York")).date()

# Non-trading day (weekend or NYSE holiday) -> skip deterministically.
if today.weekday() >= 5 or today in set(
    NYSECalendar().holidays(dt.datetime(today.year, 1, 1), dt.datetime(today.year + 1, 1, 1)).date
):
    print("closed")
    raise SystemExit(0)

# Trading day: wait for yfinance to publish today's daily bar. Right after the
# 16:00 ET close the bar can be missing for hours; running before it exists
# makes `prepare` fail on the required session.
POLL_SECONDS = 15 * 60
MAX_ATTEMPTS = 16  # up to 4 hours after the scheduled fire time
for attempt in range(1, MAX_ATTEMPTS + 1):
    df = yf.Ticker("^GSPC").history(
        start=today.isoformat(),
        end=(today + dt.timedelta(days=1)).isoformat(),
        auto_adjust=True,
    )
    if not df.empty and df.index[-1].date() == today:
        print("ok")
        raise SystemExit(0)
    if attempt < MAX_ATTEMPTS:
        time.sleep(POLL_SECONDS)
print("nodata")
PY
) || MARKET_STATUS='error'

case "$MARKET_STATUS" in
    closed)
        echo "  market closed — skipping to avoid API waste"
        echo "=== $TODAY: done ==="
        exit 0
        ;;
    nodata|error)
        echo "  market data for $TODAY not available after 4h — run aborted"
        echo "=== $TODAY: done (failed) ==="
        exit 1
        ;;
esac

echo "=== $TODAY: prepare ==="
python -m src.cli prepare --date "$TODAY" --force

if [ -f "$PROJECT_DIR/output/$TODAY/$TODAY-analysis.md" ]; then
    echo "=== $TODAY: output already exists — skipping run ==="
else
    echo "=== $TODAY: run ==="
    run_with_retry python -m src.cli run --date "$TODAY"
fi

echo "=== $TODAY: generating PDF ==="
python -m src.cli export-report --date "$TODAY" || echo "  (PDF export skipped)"

echo "=== $TODAY: copying PDF to iCloud ==="
PDF_SRC="$PROJECT_DIR/daily_pdfs/$TODAY-investor-report.pdf"
ICLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/SPX"
if [ -f "$PDF_SRC" ]; then
    mkdir -p "$ICLOUD_DIR" 2>/dev/null
    cp "$PDF_SRC" "$ICLOUD_DIR/" && echo "  copied to iCloud/SPX/$TODAY-investor-report.pdf"
fi

echo "=== $TODAY: done ==="
