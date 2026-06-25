"""Investor-facing labels for conflicting-evidence items."""

from __future__ import annotations

from .schemas import Divergence

_ACRONYM_WORDS: dict[str, str] = {
    "erp": "ERP",
    "mc": "Monte Carlo",
    "fib": "Fibonacci",
    "vix": "VIX",
    "sma": "SMA",
    "rsi": "RSI",
    "mfi": "MFI",
}


def investor_divergence_title(div: Divergence) -> str:
    """Turn a divergence id into a short investor-facing heading."""
    words = div.id.replace("_", " ").split()
    parts: list[str] = []
    for index, word in enumerate(words):
        low = word.lower()
        if low == "vs":
            parts.append("vs")
        elif low in _ACRONYM_WORDS:
            parts.append(_ACRONYM_WORDS[low])
        elif index == 0:
            parts.append(word.capitalize())
        else:
            parts.append(low)
    return " ".join(parts)


def rewrite_divergence_headings(body: str, divergences: list[Divergence]) -> str:
    """Replace snake_case divergence ids in bold headings with investor titles."""
    result = body
    for div in divergences:
        title = investor_divergence_title(div)
        weight = div.weight
        result = result.replace(f"**{div.id}**", f"**{title}**")
        result = result.replace(f"**{div.id} ({weight}):**", f"**{title}** ({weight}):")
        hyphen_id = div.id.replace("_", "-")
        if hyphen_id != div.id:
            result = result.replace(f"**{hyphen_id}**", f"**{title}**")
            result = result.replace(f"**{hyphen_id} ({weight}):**", f"**{title}** ({weight}):")
    return result
