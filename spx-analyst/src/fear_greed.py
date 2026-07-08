"""Fetch CNN Fear & Greed Index data and generate chart images.

Charts are 812x588 px @ 200 DPI = 29x21 = 609 visual tokens at Opus 4.8 pricing
($5/MTok ≈ $0.003/image).  200 DPI renders 6 pt text at 17 px for reliable
readability within Claude's 28x28-patch tiling.  The pipeline's ``_encode_image``
in ``anthropic_client.py`` further caps long-edge at 1568 px (Pass 1) / 1092 px
(Pass 2) — charts are already small enough to pass through unchanged.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

matplotlib.use("Agg")

logger = logging.getLogger(__name__)

API_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

ZONE_COLORS: dict[str, str] = {
    "extreme fear": "#d32f2f",
    "fear": "#f57c00",
    "neutral": "#fbc02d",
    "greed": "#7cb342",
    "extreme greed": "#2e7d32",
}

W = 812
H = 588
DPI = 200

SERIES_COLORS: dict[str, str] = {
    "stock_price_strength": "#00897b",
    "stock_price_breadth": "#7b1fa2",
    "put_call_options": "#e65100",
    "safe_haven_demand": "#2e7d32",
    "junk_bond_demand": "#f9a825",
}

RAW_DATA_FILENAME = "fear_greed_raw.json"


def _parse_timestamp(ms: float) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _rating_label(rating: str | None) -> str:
    if not rating:
        return "N/A"
    return rating.replace("_", " ").title()


def _setup_ax(ax: plt.Axes) -> None:
    ax.grid(True, alpha=0.3, color="#cccccc", linewidth=0.4)
    ax.tick_params(axis="both", colors="#666666", labelsize=7)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    for spine in ax.spines.values():
        spine.set_color("#dddddd")


def _build_fig() -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(1, 1, dpi=DPI)
    fig.set_size_inches(W / DPI + 1e-10, H / DPI + 1e-10, forward=True)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    _setup_ax(ax)
    return fig, ax


def _plot_line(ax: plt.Axes, entries: list[dict], color: str, *, ls: str = "-", label: str | None = None) -> None:
    dates = [_parse_timestamp(e["x"]) for e in entries]
    vals = [e["y"] for e in entries]
    ax.plot(dates, vals, color=color, linewidth=1.5, ls=ls, label=label, zorder=3)


def _set_bounds(ax: plt.Axes, *series: list[dict]) -> None:
    all_vals = []
    all_dates = []
    for s in series:
        if s:
            all_vals.extend(e["y"] for e in s)
            all_dates.extend(_parse_timestamp(e["x"]) for e in s)
    if not all_dates:
        return
    vmin, vmax = min(all_vals), max(all_vals)
    vr = vmax - vmin or 1
    ax.set_xlim(all_dates[0], all_dates[-1])
    ax.set_ylim(vmin - vr * 0.08, vmax + vr * 0.08)


def _current_annotation(ax: plt.Axes, val: float, rating: str, score: float | None = None, *, val_label: str = "") -> None:
    color = ZONE_COLORS.get(rating, "#333333")
    lines = [f"{val_label} {val:.2f}" if val_label else f"{val:.2f}"]
    if score is not None:
        lines.append(f"Score: {score:.0f}")
    ax.text(
        0.97, 0.95, "\n".join(lines),
        transform=ax.transAxes, va="top", ha="right",
        fontsize=8, fontweight="bold", color=color,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=color, alpha=0.85),
    )


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout(pad=0.5)
    fig.savefig(path, dpi=DPI, facecolor="white", pad_inches=0)
    plt.close(fig)


# --- Data fetching -----------------------------------------------------------

def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.cnn.com",
            "Referer": "https://www.cnn.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_fear_greed_data() -> dict[str, Any]:
    start = (date.today() - timedelta(days=365)).isoformat()
    url = f"{API_URL}/{start}"
    logger.info("fetching CNN Fear & Greed from %s", url)
    return _fetch_json(url)


# --- Chart 08: Fear & Greed Index time series --------------------------------

def generate_index_ts(data: dict[str, Any], output_path: Path) -> None:
    raw = (data.get("fear_and_greed_historical") or {}).get("data", [])
    if not raw:
        logger.warning("fear_and_greed_historical data missing; skipping chart 08")
        return
    fg = data.get("fear_and_greed", {})
    fig, ax = _build_fig()
    _set_bounds(ax, raw)
    _plot_line(ax, raw, "#333333", label="Fear & Greed Index")
    ax.legend(fontsize=6, loc="upper left", framealpha=0.8, edgecolor="#dddddd")
    ax.axhline(y=raw[-1]["y"], color="#333333", linewidth=0.8, ls=":", alpha=0.4, zorder=2)
    for lo, hi, _, c in [
        (0, 25, "Extreme Fear", "#d32f2f"),
        (25, 45, "Fear", "#f57c00"),
        (45, 55, "Neutral", "#fbc02d"),
        (55, 75, "Greed", "#7cb342"),
        (75, 100, "Extreme Greed", "#2e7d32"),
    ]:
        bot = lo if lo > 0 else -999
        ax.axhspan(bot, hi, alpha=0.06, color=c, linewidth=0, zorder=0)
    _current_annotation(ax, raw[-1]["y"], fg.get("rating", ""), fg.get("score"), val_label="Index")
    _save(fig, output_path)
    logger.info("wrote index time-series chart 08 to %s", output_path)


# --- Chart 09: Market Momentum -----------------------------------------------

def generate_momentum(data: dict[str, Any], output_path: Path) -> None:
    sp500 = (data.get("market_momentum_sp500") or {}).get("data", [])
    sp125 = (data.get("market_momentum_sp125") or {}).get("data", [])
    if not sp500 or not sp125:
        logger.warning("momentum data missing; skipping chart 09")
        return
    fig, ax = _build_fig()
    _set_bounds(ax, sp500, sp125)
    _plot_line(ax, sp500, "#1565c0", label="S&P 500")
    _plot_line(ax, sp125, "#d32f2f", ls="--", label="125-Day MA")
    ax.legend(fontsize=6, loc="upper left", framealpha=0.8, edgecolor="#dddddd")
    ax.axhline(y=sp125[-1]["y"], color="#d32f2f", linewidth=0.8, ls=":", alpha=0.4, zorder=2)
    comp125 = data.get("market_momentum_sp125", {})
    _current_annotation(ax, sp125[-1]["y"], comp125.get("rating", ""), comp125.get("score"), val_label="125-Day MA")
    _save(fig, output_path)
    logger.info("wrote momentum chart 09 to %s", output_path)


# --- Charts 10–15: Component time series -------------------------------------

def _component_chart(data: dict, key: str, color: str, legend_label: str, val_label: str, path: Path) -> None:
    comp = data.get(key) or {}
    raw = comp.get("data", [])
    if not raw:
        logger.warning("%s data missing; skipping %s", key, path.name)
        return
    fig, ax = _build_fig()
    _set_bounds(ax, raw)
    _plot_line(ax, raw, color, label=legend_label)
    ax.legend(fontsize=6, loc="upper left", framealpha=0.8, edgecolor="#dddddd")
    ax.axhline(y=raw[-1]["y"], color=color, linewidth=0.8, ls=":", alpha=0.4, zorder=2)
    _current_annotation(ax, raw[-1]["y"], comp.get("rating", ""), comp.get("score"), val_label=val_label)
    _save(fig, path)
    logger.info("wrote %s to %s", key, path)


def generate_stock_price_strength(data: dict[str, Any], output_path: Path) -> None:
    _component_chart(data, "stock_price_strength", SERIES_COLORS["stock_price_strength"], "NYSE 52-Week Highs/Lows", "Strength", output_path)


def generate_stock_price_breadth(data: dict[str, Any], output_path: Path) -> None:
    _component_chart(data, "stock_price_breadth", SERIES_COLORS["stock_price_breadth"], "McClellan Vol Summation Index", "Breadth", output_path)


def generate_put_call_ratio(data: dict[str, Any], output_path: Path) -> None:
    _component_chart(data, "put_call_options", SERIES_COLORS["put_call_options"], "Put/Call Ratio (5-Day Avg)", "P/C Ratio", output_path)


def generate_market_volatility(data: dict[str, Any], output_path: Path) -> None:
    vix = (data.get("market_volatility_vix") or {}).get("data", [])
    vix50 = (data.get("market_volatility_vix_50") or {}).get("data", [])
    if not vix or not vix50:
        logger.warning("market_volatility data missing; skipping chart 13")
        return
    fig, ax = _build_fig()
    _set_bounds(ax, vix, vix50)
    _plot_line(ax, vix, "#1565c0", label="VIX")
    _plot_line(ax, vix50, "#d32f2f", ls="--", label="50-Day MA")
    ax.legend(fontsize=6, loc="upper left", framealpha=0.8, edgecolor="#dddddd")
    ax.axhline(y=vix[-1]["y"], color="#1565c0", linewidth=0.8, ls=":", alpha=0.4, zorder=2)
    comp = data.get("market_volatility_vix", {})
    _current_annotation(ax, vix[-1]["y"], comp.get("rating", ""), comp.get("score"), val_label="VIX")
    _save(fig, output_path)
    logger.info("wrote market volatility chart 13 to %s", output_path)


def generate_safe_haven_demand(data: dict[str, Any], output_path: Path) -> None:
    _component_chart(data, "safe_haven_demand", SERIES_COLORS["safe_haven_demand"], "Stock vs Bond Returns (20-Day)", "Safe Haven", output_path)


def generate_junk_bond_demand(data: dict[str, Any], output_path: Path) -> None:
    _component_chart(data, "junk_bond_demand", SERIES_COLORS["junk_bond_demand"], "Junk Bond Yield Spread", "Junk Spread", output_path)


# --- Public entry point ------------------------------------------------------

def fetch_and_generate(output_dir: Path) -> dict[str, Path]:
    """Fetch CNN data and generate all 8 charts (08–15).

    Raw API response is saved as ``fear_greed_raw.json`` alongside the PNGs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    data = fetch_fear_greed_data()

    (output_dir / RAW_DATA_FILENAME).write_text(json.dumps(data, indent=2), encoding="utf-8")

    generators: list[tuple[str, Any]] = [
        ("08_fear_greed_index.png", generate_index_ts),
        ("09_fear_greed_momentum.png", generate_momentum),
        ("10_breadth_52wk_highs_lows.png", generate_stock_price_strength),
        ("11_breadth_mcclellan.png", generate_stock_price_breadth),
        ("12_put_call_ratio.png", generate_put_call_ratio),
        ("13_vix_volatility.png", generate_market_volatility),
        ("14_safe_haven_demand.png", generate_safe_haven_demand),
        ("15_junk_bond_spread.png", generate_junk_bond_demand),
    ]

    paths: dict[str, Path] = {}
    for filename, gen_fn in generators:
        p = output_dir / filename
        gen_fn(data, p)
        paths[filename] = p

    return paths
