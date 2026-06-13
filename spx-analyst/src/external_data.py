"""Load the daily external market context.

There is no automated fetching: all market context (VIX, US 10Y, Fear & Greed,
put/call, high-yield spread, headlines) is supplied by the user, both as chart
screenshots and as numeric values in each run's `external_context.json`. If that
file is missing, a blank template is written for the user to fill in.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings, get_settings
from .files import EXTERNAL_CONTEXT_FILENAME, read_json
from .schemas import ExternalContext

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    context: ExternalContext
    warnings: list[str] = field(default_factory=list)


def blank_context(date: str) -> ExternalContext:
    """An all-null context template for manual completion."""
    return ExternalContext(date=date)


def load_external_context(
    date: str,
    run_dir: Path,
    *,
    settings: Settings | None = None,
) -> FetchResult:
    """Load external_context.json, or write a blank template if it is missing."""
    settings = settings or get_settings()
    path = run_dir / EXTERNAL_CONTEXT_FILENAME

    if path.exists():
        context = ExternalContext.model_validate(read_json(path))
        return FetchResult(context=context, warnings=[])

    context = blank_context(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(context.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.warning("external_context.json not found for %s; wrote a blank template", date)
    return FetchResult(
        context=context,
        warnings=[f"external_context.json missing; wrote blank template at {path} — fill it in"],
    )
