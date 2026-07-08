# PR-19: Chart generation engine

**Status:** Complete  
**Framework version:** `daily-2026-06`  
**Builds on:** [PR-9: Daily run import](PR-9-daily-run-import.md) · [PR-4: Pass 2 image optimization](PR-4-pass2-image-optimization.md)

## Summary

Adds two deterministic Python chart generators — SPX price charts (01–07) from yfinance and CNN Fear & Greed charts (08–15) from the CNN API — replacing the manual screenshot workflow. The canonical 15-chart pack is now fully scriptable end-to-end.

## Problem / motivation

Previously, all 15 daily charts required manual screenshots: 7 TradingView price panels and 8 CNN Fear & Greed pages. This was error-prone, inconsistent, and required an operator to capture PNGs at the right resolution every trading day. Automating the chart generation eliminates the manual step, ensures pixel-perfect consistency, and enables the full engine run to be triggered in one command sequence.

## Solution

### SPX price charts (`price_charts.py`)

| Chart | Timeframe | Resolution | Panels |
|-------|-----------|------------|--------|
| 01 — Intraday | 1D (1-min) | 1024×896 | Candles + RSI |
| 02 — 5-day | 5D (1-hour) | 1024×896 | Candles + RSI + MFI |
| 03–06 — Daily | 1M/3M/6M/1Y | 1024×896 | Candles + RSI + MFI |
| 07 — 3-year | 3Y (weekly) | 1024×896 | Candles + RSI + MFI |

- Data via yfinance (`^GSPC`), 2000-day lookback for full indicator computation
- Integer-index x-axis (no calendar gap compression)
- Indicators: SMA 20/50/200, Bollinger Bands 20-2, RSI-14, MFI-14
- TradingView-inspired colour palette (green/red candles)
- Image cost: 37×32 = 1,184 visual tokens per chart at Opus 4.8 pricing

### Fear & Greed charts (`fear_greed.py`)

| Chart | Source field | Size |
|-------|-------------|------|
| 08 — Index time series | `fear_and_greed_historical` | 812×588 |
| 09 — Market momentum | `market_momentum_sp500` + `sp125` | 812×588 |
| 10 — Stock price strength | `stock_price_strength` | 812×588 |
| 11 — McClellan breadth | `stock_price_breadth` | 812×588 |
| 12 — Put/call ratio | `put_call_options` | 812×588 |
| 13 — VIX volatility | `market_volatility_vix` + `vix_50` | 812×588 |
| 14 — Safe haven demand | `safe_haven_demand` | 812×588 |
| 15 — Junk bond spread | `junk_bond_demand` | 812×588 |

- Data from CNN's production API (same source as cnn.com)
- Zone colour fills (Extreme Fear → Extreme Greed)
- Current-value annotation bbox on each chart
- Raw API response saved as `fear_greed_raw.json` alongside PNGs
- Image cost: 29×21 = 609 visual tokens per chart at Opus 4.8 pricing

### CLI integration

Two new commands in `cli.py`:

```bash
python -m src.cli fetch-fear-greed              # charts 08–15
python -m src.cli generate-price-charts          # charts 01–07
```

Both default output to `Images/<date>/`, matching the `import-run` intake directory.

### `.gitignore`

Added `Images/` to repo-root `.gitignore` — generated PNGs are build artifacts, not source.

## Files touched

| File | Change |
|------|--------|
| `.gitignore` | **New** — `Images/` (generated chart artifacts) |
| `src/fear_greed.py` | **New** — CNN Fear & Greed fetch + 8 chart generators |
| `src/price_charts.py` | **New** — SPX price chart generators (01–07) with indicators |
| `src/cli.py` | `fetch-fear-greed` + `generate-price-charts` commands |
| `pyproject.toml` | Add `matplotlib>=3.9.0` dependency |
| `requirements.txt` | Add `matplotlib>=3.9.0` dependency |
| `tests/test_fear_greed.py` | **New** — fetch, chart PNG, data-missing skip, integration |
| `tests/test_price_charts.py` | **New** — indicators unit tests, chart generation, integration |
| `tests/fixtures/cnn_fear_greed_sample.json` | **New** — fixture for offline chart tests |

## Tests / verification

```bash
cd spx-analyst
pytest tests/test_fear_greed.py tests/test_price_charts.py -q
```

- Fear & greed: mocked fetch returns fixture; all 8 chart generators produce correct-size PNGs; missing data skipped gracefully; integration test generates all 8 from fixture
- Price charts: SMA/RSI/MFI/BBands unit tests; intraday + 5-day chart generation with dimension checks; empty-data skip; integration test mocks yfinance and generates all 7 charts

## Image sizing rationale

Both chart sizes hit the minimum Claude tile count (4 tiles each) at resolutions proven readable in production:
- 1024×896 → 37×28-pixel patches = 1,184 tokens
- 812×588 → 29×21 patches = 609 tokens

At Opus 4.8 pricing ($5/MTok input), the full 15-chart pack costs ~$0.07 per run — the floor for a readable 3-panel layout. Per [Claude 28×28 patch formula](https://docs.anthropic.com/en/docs/build-with-claude/vision).
