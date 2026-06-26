"""Canonical 15-chart pack definition — single source of truth for manifest chart entries."""

from __future__ import annotations

from typing import Any

from .schemas import ChartEntry

CHART_PACK_SIZE = 15

CHART_PACK: list[ChartEntry] = [
    ChartEntry(
        order=1,
        file="01_spx_intraday.png",
        label="SPX intraday price (1-day)",
        category="technical",
        timeframe="intraday",
    ),
    ChartEntry(
        order=2,
        file="02_spx_5day.png",
        label="SPX 5-day with SMA 50/200, Bollinger Bands, RSI-14, MFI",
        category="technical",
        timeframe="5day",
    ),
    ChartEntry(
        order=3,
        file="03_spx_1month.png",
        label="SPX 1-month with SMA 50/200, Bollinger Bands, RSI-14, MFI",
        category="technical",
        timeframe="1month",
    ),
    ChartEntry(
        order=4,
        file="04_spx_3month.png",
        label="SPX 3-month with SMA 50/200, Bollinger Bands, RSI-14, MFI",
        category="technical",
        timeframe="3month",
    ),
    ChartEntry(
        order=5,
        file="05_spx_6month.png",
        label="SPX 6-month with SMA 50/200, Bollinger Bands, RSI-14, MFI",
        category="technical",
        timeframe="6month",
    ),
    ChartEntry(
        order=6,
        file="06_spx_1year.png",
        label="SPX 1-year with SMA 50/200, Bollinger Bands, RSI-14, MFI",
        category="technical",
        timeframe="1year",
    ),
    ChartEntry(
        order=7,
        file="07_spx_3year.png",
        label="SPX 3-year with SMA 50/200, Bollinger Bands, RSI-14, MFI",
        category="technical",
        timeframe="3year",
    ),
    ChartEntry(
        order=8,
        file="08_fear_greed_index.png",
        label="CNN Fear & Greed Index overview",
        category="sentiment",
        timeframe="1year",
    ),
    ChartEntry(
        order=9,
        file="09_fear_greed_momentum.png",
        label="Fear & Greed market momentum: S&P 500 vs 125-day MA",
        category="sentiment",
        timeframe="1year",
    ),
    ChartEntry(
        order=10,
        file="10_breadth_52wk_highs_lows.png",
        label="Stock price strength: net new 52-week highs/lows on NYSE",
        category="breadth",
        timeframe="1year",
    ),
    ChartEntry(
        order=11,
        file="11_breadth_mcclellan.png",
        label="Stock price breadth: McClellan Volume Summation Index",
        category="breadth",
        timeframe="1year",
    ),
    ChartEntry(
        order=12,
        file="12_put_call_ratio.png",
        label="5-day average put/call ratio",
        category="sentiment",
        timeframe="1year",
    ),
    ChartEntry(
        order=13,
        file="13_vix_volatility.png",
        label="Market volatility: VIX and its 50-day MA",
        category="volatility",
        timeframe="1year",
    ),
    ChartEntry(
        order=14,
        file="14_safe_haven_demand.png",
        label="Safe haven demand: difference in 20-day stock vs bond returns",
        category="sentiment",
        timeframe="1year",
    ),
    ChartEntry(
        order=15,
        file="15_junk_bond_spread.png",
        label="Junk bond demand: yield spread junk vs investment grade",
        category="credit",
        timeframe="1year",
    ),
]

CANONICAL_CHART_FILES = [c.file for c in CHART_PACK]


def build_manifest(date: str, close: float, *, index_symbol: str = "SPX") -> dict[str, Any]:
    """Assemble a full daily manifest dict for the canonical 15-chart pack."""
    charts = [c.model_dump(mode="json") for c in CHART_PACK]
    return {
        "date": date,
        "index_symbol": index_symbol,
        "close": close,
        "chart_count": CHART_PACK_SIZE,
        "charts": charts,
    }
