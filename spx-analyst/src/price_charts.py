"""Generate SPX price charts (01–07) from yfinance data.

Timeframes: 1D (1-min), 5D (1-hour), 1M/3M/6M/1Y (daily), 3Y (weekly).
Each chart: candlesticks, SMA 20/50/200, BB 20-2, RSI-14, MFI-14.

All x-axes use equally-spaced integer indices so bars are never compressed
by calendar gaps (weekends, holidays).  Date labels are overlaid manually.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from matplotlib.patches import Rectangle

matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# --- Dimensions ---
W = 1024
H = 896
DPI = 150

# --- Colour palette (TradingView-inspired) ---
UP = "#089981"
DN = "#f23645"

SMA20_C = "#8b5cf6"
SMA50_C = "#f59e0b"
SMA200_C = "#3b82f6"

BB_C = "#3b82f6"
BB_FILL = "#3b82f6"

RSI_C = "#8b5cf6"
MFI_C = "#059669"
OB_C = "#f23645"
OS_C = "#089981"
NEUTRAL_C = "#bbbbbb"

# --- Data constants ---
DAILY_LOOKBACK = 2000
INTRADAY_INTERVAL = "1m"
INTRADAY_PERIOD = "5d"
HOURLY_PERIOD = "3mo"


# --- Data model ---


@dataclass
class PriceData:
    run_date: date
    close: float

    dates: list[date]
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    volumes: np.ndarray

    weekly_dates: list[date]
    weekly_opens: np.ndarray
    weekly_highs: np.ndarray
    weekly_lows: np.ndarray
    weekly_closes: np.ndarray
    weekly_volumes: np.ndarray

    intraday: pd.DataFrame | None
    hourly: pd.DataFrame | None


# --- Fetching ---


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _fetch_daily(run_date: date) -> pd.DataFrame:
    start = run_date - timedelta(days=int(DAILY_LOOKBACK * 1.5))
    # yfinance end is exclusive; push +1 so run_date is included
    df = yf.download("^GSPC", start=start.isoformat(), end=(run_date + timedelta(days=1)).isoformat(), auto_adjust=True)
    if df.empty:
        raise ValueError("yfinance returned empty daily DataFrame for ^GSPC")
    return _flatten(df).sort_index()


def _resample_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    weekly = daily.resample("W-FRI", label="right", closed="right").agg({
        "Open": "first", "High": "max", "Low": "min",
        "Close": "last", "Volume": "sum",
    })
    return weekly.dropna()


def _fetch_intraday(run_date: date) -> pd.DataFrame | None:
    try:
        df = yf.download("^GSPC", period=INTRADAY_PERIOD, interval=INTRADAY_INTERVAL, auto_adjust=True)
        if df.empty:
            return None
        df = _flatten(df).sort_index()
        last_date = df.index[-1].date()
        df = df[df.index.date == last_date]
        return df if not df.empty else None
    except Exception as exc:
        logger.warning("intraday fetch failed: %s", exc)
        return None


def _fetch_hourly(run_date: date) -> pd.DataFrame | None:
    try:
        df = yf.download("^GSPC", interval="1h", period=HOURLY_PERIOD, auto_adjust=True)
        if df.empty:
            return None
        df = _flatten(df).sort_index()
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except Exception as exc:
        logger.warning("hourly fetch failed: %s", exc)
        return None


def fetch_price_data(run_date: date | None = None) -> PriceData:
    if run_date is None:
        run_date = date.today()
    daily = _fetch_daily(run_date)
    weekly = _resample_weekly(daily)

    def _c(col: str) -> np.ndarray:
        return daily[col].to_numpy(dtype=float)

    def _dates() -> list[date]:
        return [d.date() if hasattr(d, "date") else d for d in daily.index]

    def _wc(col: str) -> np.ndarray:
        return weekly[col].to_numpy(dtype=float)

    def _wdates() -> list[date]:
        return [d.date() if hasattr(d, "date") else d for d in weekly.index]

    return PriceData(
        run_date=run_date,
        close=float(_c("Close")[-1]),
        dates=_dates(),
        opens=_c("Open"),
        highs=_c("High"),
        lows=_c("Low"),
        closes=_c("Close"),
        volumes=_c("Volume"),
        weekly_dates=_wdates(),
        weekly_opens=_wc("Open"),
        weekly_highs=_wc("High"),
        weekly_lows=_wc("Low"),
        weekly_closes=_wc("Close"),
        weekly_volumes=_wc("Volume"),
        intraday=_fetch_intraday(run_date),
        hourly=_fetch_hourly(run_date),
    )


# --- Technical indicators ---


def _sma(values: np.ndarray, window: int) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=float)
    if len(values) < window:
        return out
    cumsum = np.cumsum(values)
    out[window - 1] = cumsum[window - 1] / window
    out[window:] = (cumsum[window:] - cumsum[:-window]) / window
    return out


def _bbands(close: np.ndarray, window: int = 20, num_std: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    middle = _sma(close, window)
    out_u = np.full_like(close, np.nan, dtype=float)
    out_l = np.full_like(close, np.nan, dtype=float)
    for i in range(window - 1, len(close)):
        s = float(np.std(close[i - window + 1 : i + 1], ddof=0))
        out_u[i] = middle[i] + num_std * s
        out_l[i] = middle[i] - num_std * s
    return out_u, middle, out_l


def _rsi(close: np.ndarray, window: int = 14) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=float)
    n = len(close)
    if n < window + 1:
        return out
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0).astype(float)
    losses = np.where(deltas < 0, -deltas, 0.0).astype(float)
    avg_g = float(np.mean(gains[:window]))
    avg_l = float(np.mean(losses[:window]))
    if avg_l == 0:
        out[window] = 100.0
    else:
        out[window] = 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    alpha = 1.0 / window
    for i in range(window + 1, n):
        avg_g = (1.0 - alpha) * avg_g + alpha * gains[i - 1]
        avg_l = (1.0 - alpha) * avg_l + alpha * losses[i - 1]
        if avg_l == 0:
            out[i] = 100.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return out


def _mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, window: int = 14) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=float)
    n = len(close)
    if n < window + 1:
        return out
    typical = (high + low + close) / 3.0
    raw_mf = typical * volume
    pos = np.zeros(n)
    neg = np.zeros(n)
    for i in range(1, n):
        if typical[i] > typical[i - 1]:
            pos[i] = raw_mf[i]
        elif typical[i] < typical[i - 1]:
            neg[i] = raw_mf[i]
    pos_s = np.full(n, np.nan)
    neg_s = np.full(n, np.nan)
    for i in range(window, n):
        pos_s[i] = float(np.sum(pos[i - window + 1 : i + 1]))
        neg_s[i] = float(np.sum(neg[i - window + 1 : i + 1]))
    mask = neg_s > 0
    out[mask] = 100.0 - 100.0 / (1.0 + pos_s[mask] / neg_s[mask])
    out[~mask & ~np.isnan(pos_s)] = 100.0
    return out


def _has_valid(values: np.ndarray) -> bool:
    return bool(np.any(~np.isnan(values)))


# --- Chart helpers ---


def _style_ax(ax: plt.Axes, *, ylabel: str = "", fontsize: int = 8) -> None:
    ax.set_facecolor("white")
    ax.grid(True, alpha=0.25, color="#cccccc", linewidth=0.4)
    ax.tick_params(axis="both", colors="#555555", labelsize=fontsize)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("bottom", "left"):
        ax.spines[side].set_color("#cccccc")
        ax.spines[side].set_linewidth(0.6)
    if ylabel:
        ax.set_ylabel(ylabel, color="#555555", fontsize=fontsize + 1)


def _os_hline(ax: plt.Axes, y: float, color: str, ls: str = "--", alpha: float = 0.5) -> None:
    ax.axhline(y=y, color=color, linewidth=0.7, ls=ls, alpha=alpha, zorder=1)


def _candlesticks(ax: plt.Axes, x, o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray,
                  *, width: float = 0.6) -> None:
    for i in range(len(x)):
        color = UP if c[i] >= o[i] else DN
        ax.plot([x[i], x[i]], [l[i], h[i]], color=color, linewidth=0.8, zorder=2)
        rect = Rectangle(
            (x[i] - width / 2, min(o[i], c[i])),
            width, abs(c[i] - o[i]),
            facecolor=color, edgecolor=color, linewidth=0.4, zorder=3,
        )
        ax.add_patch(rect)


def _add_sma(ax: plt.Axes, x, values: np.ndarray, color: str, label: str, zorder: int = 4) -> None:
    if _has_valid(values):
        ax.plot(x, values, color=color, linewidth=1.1, alpha=0.85, label=label, zorder=zorder)


def _add_bbands(ax: plt.Axes, x, upper: np.ndarray, _mid: np.ndarray, lower: np.ndarray) -> None:
    if _has_valid(upper):
        ax.fill_between(x, lower, upper, alpha=0.08, color=BB_FILL, linewidth=0, zorder=0)
        ax.plot(x, upper, color=BB_C, linewidth=0.7, ls="--", alpha=0.55, zorder=2)
        ax.plot(x, lower, color=BB_C, linewidth=0.7, ls="--", alpha=0.55, zorder=2)


def _yzoom(ax: plt.Axes, *arrays: np.ndarray, pad_frac: float = 0.06) -> None:
    combined = np.concatenate([a for a in arrays if _has_valid(a)])
    if len(combined) == 0:
        return
    vmin, vmax = float(np.nanmin(combined)), float(np.nanmax(combined))
    pad = (vmax - vmin) * pad_frac or vmin * 0.02
    # Asymmetric padding: extra headroom above for legends, BB bands
    ax.set_ylim(vmin - pad * 0.2, vmax + pad * 1.5)


def _build_osc_panel(ax: plt.Axes, x, values: np.ndarray, color: str,
                     ob: float, os: float, label: str) -> None:
    _style_ax(ax, ylabel=label, fontsize=8)
    ax.plot(x, values, color=color, linewidth=1.0, zorder=3)
    _os_hline(ax, ob, OB_C)
    _os_hline(ax, os, OS_C)
    _os_hline(ax, 50, NEUTRAL_C, ls=":", alpha=0.35)
    ax.set_ylim(0, 100)


def _multi_panel() -> tuple[plt.Figure, plt.Axes, plt.Axes, plt.Axes]:
    fig, axes = plt.subplots(
        3, 1, figsize=(W / DPI, H / DPI), dpi=DPI,
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1], "hspace": 0.07},
    )
    fig.patch.set_facecolor("white")
    ax1, ax2, ax3 = axes
    _style_ax(ax1)
    ax1.tick_params(axis="x", labelbottom=False)
    _style_ax(ax2)
    ax2.tick_params(axis="x", labelbottom=False)
    _style_ax(ax3, fontsize=8)
    return fig, ax1, ax2, ax3


# --- Date tick helpers (integer-index x-axis) ---


def _format_date(d: date) -> str:
    today = date.today()
    if d.year == today.year:
        return d.strftime("%b %d")
    return d.strftime("%b %d %Y")


def _daily_tick_labels(dates: list[date], n_ticks: int = 8) -> tuple[list[int], list[str]]:
    """Pick ~n_ticks evenly-spaced indices for a daily/weekly bar series."""
    n = len(dates)
    if n <= n_ticks:
        idx = list(range(n))
    else:
        step = max(1, n // (n_ticks - 1))
        idx = list(range(0, n, step))
        if idx[-1] != n - 1:
            idx.append(n - 1)
    labels = [_format_date(dates[i]) for i in idx]
    return idx, labels


def _set_x_limits(ax: plt.Axes, n_bars: int) -> None:
    ax.set_xlim(-0.5, n_bars - 0.5)


def _chart_legend(ax: plt.Axes, *, ncol: int = 4) -> None:
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=SMA20_C, linewidth=1.1, label="SMA 20"),
        Line2D([0], [0], color=SMA50_C, linewidth=1.1, label="SMA 50"),
        Line2D([0], [0], color=SMA200_C, linewidth=1.1, label="SMA 200"),
        Line2D([0], [0], color=BB_C, linewidth=0.7, ls="--", label="BB 20-2"),
    ]
    ax.legend(
        handles=handles, fontsize=7, loc="upper left",
        framealpha=0.85, edgecolor="#dddddd", labelcolor="#333333",
        ncol=ncol,
    )


# --- Per-chart generators ---


def generate_intraday_chart(data: PriceData, path: Path) -> None:
    """1D — 1-minute candlesticks, SMAs, BB, RSI.  MFI omitted per spec."""
    if data.intraday is None or data.intraday.empty:
        logger.warning("no intraday data; skipping chart 01")
        return
    df = data.intraday.copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    opens = df["Open"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    n_bars = len(closes)
    x = list(range(n_bars))

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(W / DPI, H / DPI), dpi=DPI,
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.07},
    )
    fig.patch.set_facecolor("white")
    _style_ax(ax1)
    ax1.tick_params(axis="x", labelbottom=False)

    _candlesticks(ax1, x, opens, highs, lows, closes, width=0.6)

    bb_u, bb_m, bb_l = _bbands(closes, 20, 2.0)
    _add_bbands(ax1, x, bb_u, bb_m, bb_l)
    s20 = _sma(closes, 20)
    s50 = _sma(closes, 50)
    s200 = _sma(closes, 200)
    _add_sma(ax1, x, s20, SMA20_C, "SMA 20")
    _add_sma(ax1, x, s50, SMA50_C, "SMA 50")
    _add_sma(ax1, x, s200, SMA200_C, "SMA 200")
    _yzoom(ax1, closes, lows, highs, s20, s50, s200, bb_u, bb_l)
    _chart_legend(ax1)

    _build_osc_panel(ax2, x, _rsi(closes, 14), RSI_C, 70, 30, "RSI")

    # Time labels: every ~60 minutes
    step = max(1, n_bars // 10)
    tick_pos = list(range(0, n_bars, step))
    if tick_pos[-1] != n_bars - 1:
        tick_pos.append(n_bars - 1)
    tick_lbl = [df.index[i].strftime("%-I:%M %p") for i in tick_pos]
    ax2.set_xticks(tick_pos)
    ax2.set_xticklabels(tick_lbl, fontsize=7, rotation=30, ha="right")
    _set_x_limits(ax2, n_bars)

    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.07, top=0.98, hspace=0.06)
    fig.savefig(path, dpi=DPI, facecolor="white", pad_inches=0)
    plt.close(fig)
    logger.info("wrote intraday chart to %s", path)


def generate_hourly_five_day(data: PriceData, path: Path) -> None:
    """5D — 1-hour candlesticks with full indicator set.

    Indicators (SMA 20/50/200, BB 20-2, RSI-14, MFI-14) are computed on the
    **full** hourly dataset so SMA-200 has sufficient lookback.  Only the last 5
    trading days are plotted, with indicator values mapped from the full array.
    """
    hourly = data.hourly
    if hourly is None or hourly.empty:
        logger.warning("no hourly data; skipping 5-day chart")
        return
    full = hourly.copy()

    # Compute indicators on the FULL hourly array
    fc = full["Close"].to_numpy(dtype=float)
    full_bb_u, full_bb_m, full_bb_l = _bbands(fc, 20, 2.0)
    full_s20 = _sma(fc, 20)
    full_s50 = _sma(fc, 50)
    full_s200 = _sma(fc, 200)
    full_rsi = _rsi(fc, 14)
    full_mfi = _mfi(
        full["High"].to_numpy(dtype=float),
        full["Low"].to_numpy(dtype=float),
        fc,
        full["Volume"].to_numpy(dtype=float),
        14,
    )

    # Filter to last 5 trading days for display
    trading_dates = sorted(set(d.date() for d in full.index))[-5:]
    mask = np.array([d.date() in trading_dates for d in full.index])
    indices = np.where(mask)[0]
    df = full.iloc[indices]
    if df.empty:
        logger.warning("no hourly data in trading window; skipping 5-day chart")
        return

    n_bars = len(df)
    x = list(range(n_bars))

    opens = df["Open"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    volumes = df["Volume"].to_numpy(dtype=float)

    fig, ax1, ax2, ax3 = _multi_panel()
    _candlesticks(ax1, x, opens, highs, lows, closes, width=0.6)

    _add_bbands(ax1, x, full_bb_u[indices], full_bb_m[indices], full_bb_l[indices])
    _add_sma(ax1, x, full_s20[indices], SMA20_C, "SMA 20")
    _add_sma(ax1, x, full_s50[indices], SMA50_C, "SMA 50")
    _add_sma(ax1, x, full_s200[indices], SMA200_C, "SMA 200")
    _yzoom(ax1, closes, lows, highs,
           full_s20[indices], full_s50[indices], full_s200[indices],
           full_bb_u[indices], full_bb_l[indices])
    _chart_legend(ax1)

    _build_osc_panel(ax2, x, full_rsi[indices], RSI_C, 70, 30, "RSI")
    _build_osc_panel(ax3, x, full_mfi[indices], MFI_C, 80, 20, "MFI")

    # One tick per trading day — locate first bar of each date
    seen: dict[date, int] = {}
    for i, dt in enumerate(df.index):
        d = dt.date()
        if d not in seen:
            seen[d] = i
    tick_pos = sorted(seen.values())
    tick_lbl = [df.index[i].strftime("%b %d") for i in tick_pos]
    ax3.set_xticks(tick_pos)
    ax3.set_xticklabels(tick_lbl, fontsize=7, rotation=30, ha="right")
    _set_x_limits(ax3, n_bars)
    ax2.tick_params(axis="x", labelbottom=False)
    ax1.tick_params(axis="x", labelbottom=False)

    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.07, top=0.98, hspace=0.06)
    fig.savefig(path, dpi=DPI, facecolor="white", pad_inches=0)
    plt.close(fig)
    logger.info("wrote 5-day hourly chart to %s", path)


def _render_daily_chart(data: PriceData, timeframe: str, ndays: int, path: Path) -> None:
    """Render a daily candlestick chart (1M / 3M / 6M / 1Y)."""
    n = len(data.closes)
    end = n
    start = max(0, n - ndays)
    if start >= end:
        logger.warning("not enough daily data for %s chart", timeframe)
        return

    d = data.dates[start:end]
    opens = data.opens[start:end]
    highs = data.highs[start:end]
    lows = data.lows[start:end]
    closes = data.closes[start:end]
    n_bars = len(closes)
    x = list(range(n_bars))

    bb_u, bb_m, bb_l = _bbands(data.closes, 20, 2.0)
    s20 = _sma(data.closes, 20)
    s50 = _sma(data.closes, 50)
    s200 = _sma(data.closes, 200)

    fig, ax1, ax2, ax3 = _multi_panel()
    _candlesticks(ax1, x, opens, highs, lows, closes, width=0.6)

    bb_u_s, bb_m_s, bb_l_s = bb_u[start:end], bb_m[start:end], bb_l[start:end]
    _add_bbands(ax1, x, bb_u_s, bb_m_s, bb_l_s)
    _add_sma(ax1, x, s20[start:end], SMA20_C, "SMA 20")
    _add_sma(ax1, x, s50[start:end], SMA50_C, "SMA 50")
    _add_sma(ax1, x, s200[start:end], SMA200_C, "SMA 200")
    _yzoom(ax1, closes, lows, highs, s20[start:end], s50[start:end],
           s200[start:end], bb_u_s, bb_l_s)
    _chart_legend(ax1)

    rsi_all = _rsi(data.closes, 14)
    mfi_all = _mfi(data.highs, data.lows, data.closes, data.volumes, 14)
    _build_osc_panel(ax2, x, rsi_all[start:end], RSI_C, 70, 30, "RSI")
    _build_osc_panel(ax3, x, mfi_all[start:end], MFI_C, 80, 20, "MFI")

    tick_pos, tick_lbl = _daily_tick_labels(d, 8)
    ax3.set_xticks(tick_pos)
    ax3.set_xticklabels(tick_lbl, fontsize=7, rotation=30, ha="right")
    _set_x_limits(ax3, n_bars)
    ax2.tick_params(axis="x", labelbottom=False)
    ax1.tick_params(axis="x", labelbottom=False)

    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.07, top=0.98, hspace=0.06)
    fig.savefig(path, dpi=DPI, facecolor="white", pad_inches=0)
    plt.close(fig)
    logger.info("wrote %s chart to %s", timeframe, path)


def _render_weekly_chart(data: PriceData, n_weeks: int, path: Path) -> None:
    """3Y — weekly candlesticks resampled from daily."""
    n = len(data.weekly_closes)
    end = n
    start = max(0, n - n_weeks)
    if start >= end:
        logger.warning("not enough weekly data for 3-year chart")
        return

    d = data.weekly_dates[start:end]
    opens = data.weekly_opens[start:end]
    highs = data.weekly_highs[start:end]
    lows = data.weekly_lows[start:end]
    closes = data.weekly_closes[start:end]
    n_bars = len(closes)
    x = list(range(n_bars))

    bb_u, bb_m, bb_l = _bbands(data.weekly_closes, 20, 2.0)
    s20 = _sma(data.weekly_closes, 20)
    s50 = _sma(data.weekly_closes, 50)
    s200 = _sma(data.weekly_closes, 200)

    fig, ax1, ax2, ax3 = _multi_panel()
    _candlesticks(ax1, x, opens, highs, lows, closes, width=0.6)

    bb_u_s, bb_m_s, bb_l_s = bb_u[start:end], bb_m[start:end], bb_l[start:end]
    _add_bbands(ax1, x, bb_u_s, bb_m_s, bb_l_s)
    _add_sma(ax1, x, s20[start:end], SMA20_C, "SMA 20")
    _add_sma(ax1, x, s50[start:end], SMA50_C, "SMA 50")
    _add_sma(ax1, x, s200[start:end], SMA200_C, "SMA 200")
    _yzoom(ax1, closes, lows, highs, s20[start:end], s50[start:end],
           s200[start:end], bb_u_s, bb_l_s)
    _chart_legend(ax1)

    rsi_all = _rsi(data.weekly_closes, 14)
    mfi_all = _mfi(data.weekly_highs, data.weekly_lows, data.weekly_closes, data.weekly_volumes, 14)
    _build_osc_panel(ax2, x, rsi_all[start:end], RSI_C, 70, 30, "RSI")
    _build_osc_panel(ax3, x, mfi_all[start:end], MFI_C, 80, 20, "MFI")

    step = max(1, n_bars // 5)
    tick_pos = list(range(0, n_bars, step))
    if tick_pos[-1] != n_bars - 1:
        tick_pos.append(n_bars - 1)
    tick_lbl = [d[i].strftime("%b '%y") for i in tick_pos]
    ax3.set_xticks(tick_pos)
    ax3.set_xticklabels(tick_lbl, fontsize=7, rotation=30, ha="right")
    _set_x_limits(ax3, n_bars)
    ax2.tick_params(axis="x", labelbottom=False)
    ax1.tick_params(axis="x", labelbottom=False)

    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.07, top=0.98, hspace=0.06)
    fig.savefig(path, dpi=DPI, facecolor="white", pad_inches=0)
    plt.close(fig)
    logger.info("wrote 3-year weekly chart to %s", path)


# --- Timeframe definitions ---

TIMEFRAMES: dict[str, int] = {
    "1month": 21,
    "3month": 63,
    "6month": 126,
    "1year": 252,
}

CHART_MAP: list[tuple[str, str | None]] = [
    ("01_spx_intraday.png", None),
    ("02_spx_5day.png", "5day"),
    ("03_spx_1month.png", "1month"),
    ("04_spx_3month.png", "3month"),
    ("05_spx_6month.png", "6month"),
    ("06_spx_1year.png", "1year"),
    ("07_spx_3year.png", "3year"),
]


def fetch_and_generate(output_dir: Path, run_date: date | None = None) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = fetch_price_data(run_date)
    paths: dict[str, Path] = {}

    for filename, timeframe in CHART_MAP:
        p = output_dir / filename
        if timeframe is None:
            generate_intraday_chart(data, p)
        elif timeframe == "5day":
            generate_hourly_five_day(data, p)
        elif timeframe == "3year":
            _render_weekly_chart(data, 156, p)
        else:
            ndays = TIMEFRAMES.get(timeframe)
            if ndays is not None:
                _render_daily_chart(data, timeframe, ndays, p)
        if p.is_file():
            paths[filename] = p

    return paths
