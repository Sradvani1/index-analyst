"""Shared display formatting for reports and chat preload (presentation only)."""

from __future__ import annotations


def format_price(value: float) -> str:
    """Format a price level for human-readable output (two decimals, thousands sep)."""
    return f"{value:,.2f}"


def format_event_headline(text: str) -> str:
    """Presentation-only: soften ALL-CAPS label before first ':'; body unchanged."""
    if ":" not in text:
        return text
    label, sep, body = text.partition(":")
    label_stripped = label.strip()
    if not label_stripped:
        return text
    letters = [c for c in label_stripped if c.isalpha()]
    if not letters:
        return text
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio < 0.8:
        return text
    formatted = label_stripped.title()
    return f"{formatted}{sep}{body}"
