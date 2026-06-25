"""Tests for investor-facing divergence titles."""

from src.divergence_titles import investor_divergence_title, rewrite_divergence_headings
from src.schemas import Divergence


def _div(div_id: str, weight: str = "high") -> Divergence:
    return Divergence(
        id=div_id,
        layers=["technicals"],
        bullish_read="Bull case",
        bearish_read="Bear case",
        framework_rule="Rule",
        weight=weight,
        chart_refs=["01.png"],
    )


def test_investor_divergence_title_humanizes_id():
    title = investor_divergence_title(_div("erp_at_ceiling_vs_bounce"))
    assert title == "ERP at ceiling vs bounce"


def test_investor_divergence_title_acronyms():
    title = investor_divergence_title(_div("fib_resistance_overhead"))
    assert title == "Fibonacci resistance overhead"


def test_rewrite_divergence_headings():
    body = "**erp_at_ceiling_vs_bounce** (high): Bullish read here."
    out = rewrite_divergence_headings(body, [_div("erp_at_ceiling_vs_bounce")])
    assert "**ERP at ceiling vs bounce** (high):" in out
    assert "erp_at_ceiling_vs_bounce" not in out


def test_rewrite_divergence_headings_weight_inside_bold():
    body = "**oversold_vs_no_capitulation (medium):** Bearish read here."
    out = rewrite_divergence_headings(body, [_div("oversold_vs_no_capitulation", "medium")])
    assert "**Oversold vs no capitulation** (medium):" in out
    assert "oversold_vs_no_capitulation" not in out
