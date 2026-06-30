"""Fetch and compute market series from yfinance (^GSPC, ^VIX, ^TNX)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .config import Settings, get_settings
from .files import write_json
from .schemas import DailyManifest, MarketDataContext
from .structure import PriceBar

logger = logging.getLogger(__name__)

MARKET_HISTORY_FILENAME = "market_history.json"
MANIFEST_CLOSE_WARN_PCT = 0.0015
GSPC_LOOKBACK_DAYS = 300
VIX_LOOKBACK_DAYS = 60
TNX_LOOKBACK_SESSIONS = 25


@dataclass(frozen=True)
class MarketSeries:
    bars: list[PriceBar]
    vix: pd.Series
    tnx: pd.Series
    as_of_date: date


def _parse_run_date(date_str: str) -> date:
    return date.fromisoformat(date_str)


def _session_date_from_index(idx: object) -> date:
    if hasattr(idx, "date"):
        return idx.date()  # type: ignore[union-attr]
    return _parse_run_date(str(idx)[:10])


def _finite(value: float) -> bool:
    return math.isfinite(value)


def _bar_is_valid(bar: PriceBar) -> bool:
    return all(_finite(v) for v in (bar.open, bar.high, bar.low, bar.close))


def series_has_valid_bars(series: MarketSeries) -> bool:
    """True when every bar has finite OHLC (cache integrity check)."""
    return bool(series.bars) and all(_bar_is_valid(b) for b in series.bars)


def _cache_covers_run_date(series: MarketSeries, run_date: str) -> bool:
    """True when cached VIX/TNX/SPX extend through the run date with finite values."""
    target = _parse_run_date(run_date)
    if not series_has_valid_bars(series) or not len(series.vix) or not len(series.tnx):
        return False
    if not _finite(float(series.vix.iloc[-1])) or not _finite(float(series.tnx.iloc[-1])):
        return False
    vix_last = max(series.vix.index)
    tnx_last = max(series.tnx.index)
    spx_last = series.bars[-1].session_date
    return spx_last >= target and vix_last >= target and tnx_last >= target


def _fetch_session_ohlc(ticker: str, session: date) -> dict[str, float] | None:
    """Fetch one session via Ticker.history (repairs bulk-download NaN rows)."""
    import yfinance as yf

    end = session + timedelta(days=1)
    df = yf.Ticker(ticker).history(
        start=session.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
    )
    if df.empty or pd.isna(df.iloc[-1]["Close"]):
        return None
    row = df.iloc[-1]
    return {
        "Open": float(row["Open"]),
        "High": float(row["High"]),
        "Low": float(row["Low"]),
        "Close": float(row["Close"]),
    }


def _sanitize_ohlc_df(
    df: pd.DataFrame,
    ticker: str,
    *,
    required_sessions: frozenset[date] | None = None,
) -> pd.DataFrame:
    """Repair NaN OHLC rows from bulk download; drop unreparable stubs; fail on required dates."""
    if df.empty:
        raise ValueError(f"yfinance returned no data for {ticker}")

    required = required_sessions or frozenset()
    out = df.copy()

    for idx in out.index:
        if not pd.isna(out.loc[idx, "Close"]):
            continue
        session = _session_date_from_index(idx)
        logger.warning(
            "yfinance bulk download returned NaN OHLC for %s on %s; attempting session repair",
            ticker,
            session,
        )
        repaired = _fetch_session_ohlc(ticker, session)
        if repaired is None:
            continue
        for col, val in repaired.items():
            out.loc[idx, col] = val
        logger.info("repaired %s session %s via Ticker.history", ticker, session)

    bad = out["Close"].isna()
    if bad.any():
        bad_dates = [_session_date_from_index(idx) for idx in out.index[bad]]
        for session in bad_dates:
            if session in required:
                raise ValueError(
                    f"yfinance could not obtain OHLC for {ticker} on required session "
                    f"{session.isoformat()}"
                )
        logger.warning(
            "dropping %d session(s) with NaN close for %s: %s",
            int(bad.sum()),
            ticker,
            [d.isoformat() for d in bad_dates],
        )
        out = out.loc[~bad]

    if out.empty:
        raise ValueError(f"no valid OHLC rows remain for {ticker}")
    return out


def _backfill_close_series_to_target(
    closes: pd.Series,
    ticker: str,
    target: date,
) -> pd.Series:
    """Fill sessions missing from bulk download through run date (session-level fetch)."""
    if closes.empty:
        raise ValueError(f"empty close series for {ticker}")

    out = closes.sort_index().copy()
    last_bulk = max(out.index)
    d = last_bulk + timedelta(days=1)
    while d <= target:
        if d.weekday() >= 5:
            d += timedelta(days=1)
            continue
        if d not in out.index or not _finite(float(out[d])):
            ohlc = _fetch_session_ohlc(ticker, d)
            if ohlc is not None:
                logger.info(
                    "backfilled %s session %s via Ticker.history (missing in bulk)",
                    ticker,
                    d.isoformat(),
                )
                out[d] = ohlc["Close"]
        d += timedelta(days=1)

    if target not in out.index or not _finite(float(out[target])):
        raise ValueError(
            f"yfinance could not obtain {ticker} close for required session "
            f"{target.isoformat()}"
        )
    return out.sort_index()


def _close_series_from_bulk(
    df: pd.DataFrame,
    ticker: str,
    target: date,
    *,
    tail_sessions: int | None = None,
) -> pd.Series:
    """Build a close series from bulk download, backfilled through run date."""
    sanitized = _sanitize_ohlc_df(df, ticker, required_sessions=frozenset())
    if tail_sessions is not None:
        sanitized = sanitized.tail(tail_sessions)
    closes = sanitized["Close"].copy()
    closes.index = pd.to_datetime(closes.index).date
    return _backfill_close_series_to_target(closes, ticker, target)


def _bars_from_df(df: pd.DataFrame) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for idx, row in df.iterrows():
        d = idx.date() if hasattr(idx, "date") else _parse_run_date(str(idx)[:10])
        bars.append(
            PriceBar(
                session_date=d,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
            )
        )
    return bars


def _fetch_ticker(ticker: str, start: date, end: date) -> pd.DataFrame:
    import yfinance as yf

    # yfinance end is exclusive; add one day
    end_excl = end + timedelta(days=1)
    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=end_excl.isoformat(),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        raise ValueError(f"yfinance returned no data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df


def _fetch_ticker_sanitized(
    ticker: str,
    start: date,
    end: date,
    *,
    required_sessions: frozenset[date] | None = None,
) -> pd.DataFrame:
    df = _fetch_ticker(ticker, start, end)
    return _sanitize_ohlc_df(df, ticker, required_sessions=required_sessions)


def fetch_market_series(
    run_date: str,
    *,
    settings: Settings | None = None,
) -> MarketSeries:
    settings = settings or get_settings()
    target = _parse_run_date(run_date)
    start = target - timedelta(days=int(GSPC_LOOKBACK_DAYS * 1.6))

    gspc_df = _fetch_ticker_sanitized(
        settings.spx_ticker, start, target, required_sessions=frozenset({target})
    )
    gspc_df = gspc_df.tail(GSPC_LOOKBACK_DAYS)

    vix_start = target - timedelta(days=int(VIX_LOOKBACK_DAYS * 1.6))
    vix_df = _fetch_ticker(settings.vix_ticker, vix_start, target)
    vix = _close_series_from_bulk(
        vix_df, settings.vix_ticker, target, tail_sessions=VIX_LOOKBACK_DAYS
    )

    tnx_start = target - timedelta(days=int(TNX_LOOKBACK_SESSIONS * 2))
    tnx_df = _fetch_ticker(settings.treasury_ticker, tnx_start, target)
    tnx = _close_series_from_bulk(
        tnx_df, settings.treasury_ticker, target, tail_sessions=TNX_LOOKBACK_SESSIONS
    )

    bars = _bars_from_df(gspc_df)
    if not bars or not _bar_is_valid(bars[-1]):
        raise ValueError(f"SPX series for {run_date} has no valid closing bar")
    as_of = bars[-1].session_date

    return MarketSeries(bars=bars, vix=vix, tnx=tnx, as_of_date=as_of)


def market_series_from_cache(payload: dict) -> MarketSeries:
    bars = [
        PriceBar(
            session_date=_parse_run_date(b["session_date"]),
            open=b["open"],
            high=b["high"],
            low=b["low"],
            close=b["close"],
        )
        for b in payload["bars"]
    ]
    vix = pd.Series(payload["vix"], index=[_parse_run_date(d) for d in payload["vix_dates"]])
    tnx = pd.Series(payload["tnx"], index=[_parse_run_date(d) for d in payload["tnx_dates"]])
    as_of = _parse_run_date(payload["as_of_date"])
    return MarketSeries(bars=bars, vix=vix, tnx=tnx, as_of_date=as_of)


def cache_market_series(run_dir: Path, series: MarketSeries) -> None:
    if not series_has_valid_bars(series):
        raise ValueError("refusing to cache market series with invalid OHLC bars")
    if len(series.vix) == 0 or len(series.tnx) == 0:
        raise ValueError("refusing to cache market series with empty VIX/TNX history")
    if not _finite(float(series.vix.iloc[-1])) or not _finite(float(series.tnx.iloc[-1])):
        raise ValueError("refusing to cache market series with invalid VIX/TNX close")
    payload = {
        "as_of_date": series.as_of_date.isoformat(),
        "bars": [
            {
                "session_date": b.session_date.isoformat(),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
            }
            for b in series.bars
        ],
        "vix_dates": [d.isoformat() for d in series.vix.index],
        "vix": [float(v) for v in series.vix.values],
        "tnx_dates": [d.isoformat() for d in series.tnx.index],
        "tnx": [float(v) for v in series.tnx.values],
    }
    write_json(run_dir / MARKET_HISTORY_FILENAME, payload)


def load_or_fetch_market_series(
    run_date: str,
    run_dir: Path,
    *,
    settings: Settings | None = None,
    force_fetch: bool = False,
) -> MarketSeries:
    cache_path = run_dir / MARKET_HISTORY_FILENAME
    if cache_path.exists() and not force_fetch:
        from .files import read_json

        cached = market_series_from_cache(read_json(cache_path))
        if series_has_valid_bars(cached) and _cache_covers_run_date(cached, run_date):
            return cached
        logger.warning(
            "cached %s is stale or invalid; refetching from yfinance",
            cache_path.name,
        )
    series = fetch_market_series(run_date, settings=settings)
    cache_market_series(run_dir, series)
    return series


def _sma(values: np.ndarray, window: int) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=float)
    if len(values) < window:
        return out
    for i in range(window - 1, len(values)):
        out[i] = float(np.mean(values[i - window + 1 : i + 1]))
    return out


def realized_vol_annualized(closes: np.ndarray, window: int) -> float:
    if len(closes) < window + 1:
        return 0.2
    log_ret = np.diff(np.log(closes[-window - 1 :]))
    daily = float(np.std(log_ret, ddof=1))
    return daily * np.sqrt(252)


def build_market_data_context(
    series: MarketSeries,
    manifest: DailyManifest,
) -> MarketDataContext:
    closes = np.array([b.close for b in series.bars], dtype=float)
    spx_close = float(closes[-1])
    if not _finite(spx_close):
        raise ValueError("market series last SPX close is not finite")
    warnings: list[str] = []

    as_of = series.as_of_date.isoformat()
    if as_of != manifest.date:
        warnings.append(
            f"run date ({manifest.date}) is not the latest yfinance session "
            f"({as_of}); using prior trading day bar for all math"
        )

    if manifest.close > 0:
        drift = abs(spx_close - manifest.close) / manifest.close
        if drift > MANIFEST_CLOSE_WARN_PCT:
            warnings.append(
                f"manifest.close ({manifest.close}) differs from yfinance close "
                f"({spx_close}) by {drift * 100:.2f}% — using yfinance for all math"
            )

    sma200 = _sma(closes, 200)
    sma50 = _sma(closes, 50)
    pct_above_200 = 0.0
    if not math.isnan(sma200[-1]) and sma200[-1] > 0:
        pct_above_200 = (spx_close / sma200[-1] - 1.0) * 100.0

    vol_20 = realized_vol_annualized(closes, 20)

    vix_val = float(series.vix.iloc[-1]) if len(series.vix) else 20.0
    tnx_val = float(series.tnx.iloc[-1]) if len(series.tnx) else 4.0

    return MarketDataContext(
        spx_close=spx_close,
        vix=vix_val,
        us10y=tnx_val,
        as_of_date=series.as_of_date.isoformat(),
        pct_above_200dma=round(pct_above_200, 4),
        realized_vol_20d=round(vol_20, 6),
        sma_50=round(float(sma50[-1]), 4) if not math.isnan(sma50[-1]) else spx_close,
        sma_200=round(float(sma200[-1]), 4) if not math.isnan(sma200[-1]) else spx_close,
        precompute_warnings=warnings,
    )
