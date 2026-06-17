"""ERP, forward/trailing P/E, and valuation context from precomputed market data."""

from __future__ import annotations

from typing import Literal, Optional, Sequence

from .schemas import ERPTrend, ExternalContext, MarketDataContext, ValuationContext

ERPTrendLiteral = Literal["expanding", "stable", "contracting"]
ERP_TREND_STABLE_BPS = 0.10  # 10 bps ERP change = stable band


def _erp_at_price(
    price: float,
    forward_eps: float,
    us10y_pct: float,
) -> float:
    forward_yield = forward_eps / price
    return forward_yield - (us10y_pct / 100.0)


def erp_reentry_floor_price(
    forward_eps: float,
    us10y_pct: float,
    target_erp: float = 0.005,
) -> Optional[float]:
    """SPX price where ERP rises to target (default 0.5%)."""
    if forward_eps <= 0:
        return None
    # ERP = forward_eps/price - us10y/100 = target_erp
    price = forward_eps / (target_erp + us10y_pct / 100.0)
    return round(price, 2)


def _classify_erp_trend(current: float, prior_avg: float) -> ERPTrend:
    delta = current - prior_avg
    if delta > ERP_TREND_STABLE_BPS:
        return "expanding"
    if delta < -ERP_TREND_STABLE_BPS:
        return "contracting"
    return "stable"


def compute_valuation_context(
    market: MarketDataContext,
    external: ExternalContext,
    tnx_history: Sequence[float],
) -> ValuationContext:
    price = market.spx_close
    forward_eps = external.forward_eps
    trailing_eps = external.trailing_eps

    forward_pe = None
    trailing_pe = None
    forward_yield = None
    erp = None
    erp_trend: ERPTrend | None = None
    floor = None

    if forward_eps and forward_eps > 0:
        forward_pe = round(price / forward_eps, 2)
        forward_yield = forward_eps / price
        erp = round(forward_yield - market.us10y / 100.0, 6)
        floor = erp_reentry_floor_price(forward_eps, market.us10y)

        if len(tnx_history) >= 2:
            prior_yields = list(tnx_history[:-1])[-20:]
            prior_erps = [
                _erp_at_price(price, forward_eps, y) for y in prior_yields
            ]
            prior_avg = sum(prior_erps) / len(prior_erps)
            erp_trend = _classify_erp_trend(erp, prior_avg)

    if trailing_eps and trailing_eps > 0:
        trailing_pe = round(price / trailing_eps, 2)

    return ValuationContext(
        forward_pe=forward_pe,
        trailing_pe=trailing_pe,
        forward_earnings_yield=round(forward_yield, 6) if forward_yield else None,
        erp=erp,
        erp_trend=erp_trend,
        erp_reentry_floor_at_0_5pct=floor,
    )
