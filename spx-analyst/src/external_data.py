"""Load the daily external market context (forward/trailing EPS only)."""

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
    return ExternalContext(date=date)


def load_external_context(
    date: str,
    run_dir: Path,
    *,
    settings: Settings | None = None,
) -> FetchResult:
    settings = settings or get_settings()
    path = run_dir / EXTERNAL_CONTEXT_FILENAME

    if path.exists():
        context = ExternalContext.model_validate(read_json(path))
        warnings: list[str] = []
        if context.forward_eps is None:
            warnings.append("forward_eps is null — valuation and ERP will be incomplete")
        if context.trailing_eps is None:
            warnings.append("trailing_eps is null — trailing P/E will be incomplete")
        return FetchResult(context=context, warnings=warnings)

    context = blank_context(date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(context.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.warning("external_context.json not found for %s; wrote a blank template", date)
    return FetchResult(
        context=context,
        warnings=[f"external_context.json missing; wrote blank template at {path} — fill forward_eps and trailing_eps"],
    )
