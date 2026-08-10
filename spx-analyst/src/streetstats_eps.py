"""Fetch and normalize StreetStats S&P 500 EPS history."""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings, get_settings
from .schemas import EpsHistory, EpsHistoryEntry

TOKEN_PATH = "/api/token"
GROWTH_PATH = "/api/valuation/market/growth"
USER_AGENT = "spx-analyst/0.1"


class StreetStatsError(Exception):
    """Raised when StreetStats cannot provide a valid EPS history payload."""


@dataclass(frozen=True)
class StreetStatsFetch:
    history: EpsHistory
    source_as_of_date: str
    forward_eps: float
    trailing_eps: float
    retrieved_at: str
    response_sha256: str
    history_sha256: str


def _request_json(
    url: str,
    *,
    headers: Mapping[str, str] | None,
    timeout: float,
) -> tuple[Any, bytes]:
    request_headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": USER_AGENT,
    }
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers, method="GET")

    try:
        with urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if not 200 <= status < 300:
                raise StreetStatsError(f"StreetStats returned HTTP {status}")
            body = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                body = gzip.decompress(body)
    except StreetStatsError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise StreetStatsError(f"StreetStats request failed: {exc}") from exc

    try:
        return json.loads(body), body
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StreetStatsError(f"StreetStats returned invalid JSON: {exc}") from exc


def _positive_float(value: object, field: str, source_date: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StreetStatsError(f"StreetStats row {source_date} has invalid {field}")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise StreetStatsError(f"StreetStats row {source_date} has invalid {field}")
    return result


def _normalize_history(payload: object) -> EpsHistory:
    if not isinstance(payload, dict):
        raise StreetStatsError("StreetStats growth response is not an object")
    raw_history = payload.get("growthHistory")
    if not isinstance(raw_history, list) or not raw_history:
        raise StreetStatsError("StreetStats growth response has no growthHistory")

    entries: list[EpsHistoryEntry] = []
    for raw in raw_history:
        if not isinstance(raw, dict):
            raise StreetStatsError("StreetStats growthHistory contains a non-object row")
        raw_date = raw.get("Date")
        if not isinstance(raw_date, str):
            raise StreetStatsError("StreetStats growthHistory contains a row without Date")
        try:
            source_date = dt.date.fromisoformat(raw_date).isoformat()
        except ValueError as exc:
            raise StreetStatsError(f"StreetStats row has invalid Date: {raw_date!r}") from exc
        entries.append(
            EpsHistoryEntry(
                effective_from=source_date,
                forward_eps=_positive_float(raw.get("ntmE"), "ntmE", source_date),
                trailing_eps=_positive_float(raw.get("ltmE"), "ltmE", source_date),
            )
        )

    entries.sort(key=lambda entry: entry.effective_from)
    try:
        return EpsHistory(entries=entries)
    except ValueError as exc:
        raise StreetStatsError(f"invalid StreetStats EPS history: {exc}") from exc


def _normalized_history_sha256(history: EpsHistory) -> str:
    canonical = json.dumps(
        history.model_dump(mode="json", exclude_none=True),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def fetch_streetstats_history(
    run_date: str,
    *,
    settings: Settings | None = None,
) -> StreetStatsFetch:
    """Fetch the complete growth history once and select the run-date row."""
    settings = settings or get_settings()
    try:
        target = dt.date.fromisoformat(run_date)
    except ValueError as exc:
        raise StreetStatsError(f"invalid run date: {run_date!r}") from exc

    base_url = settings.streetstats_base_url.rstrip("/")
    token_payload, _ = _request_json(
        f"{base_url}{TOKEN_PATH}",
        headers=None,
        timeout=settings.streetstats_timeout_seconds,
    )
    if not isinstance(token_payload, dict) or not isinstance(token_payload.get("token"), str):
        raise StreetStatsError("StreetStats token response has no token")

    payload, raw_body = _request_json(
        f"{base_url}{GROWTH_PATH}",
        headers={"Authorization": f"Bearer {token_payload['token']}"},
        timeout=settings.streetstats_timeout_seconds,
    )
    history = _normalize_history(payload)
    qualifying = [
        entry
        for entry in history.entries
        if dt.date.fromisoformat(entry.effective_from) <= target
    ]
    if not qualifying:
        raise StreetStatsError(f"StreetStats has no EPS row on or before {run_date}")
    selected = max(qualifying, key=lambda entry: entry.effective_from)

    return StreetStatsFetch(
        history=history,
        source_as_of_date=selected.effective_from,
        forward_eps=selected.forward_eps,
        trailing_eps=selected.trailing_eps,
        retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        response_sha256=hashlib.sha256(raw_body).hexdigest(),
        history_sha256=_normalized_history_sha256(history),
    )
