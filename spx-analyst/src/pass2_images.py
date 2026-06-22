"""Deterministic Pass 2 image selection (PR-4).

Product contract — non-neutral qualitative row heuristic (v1):
- Evaluation uses only the documented token lists below; no fuzzy matching beyond
  substring checks for qualifying-list entries.
- A row qualifies for matrix expansion when its ``signal`` field (lowercased),
  after stripping whitespace:
  1. Is non-empty, and
  2. Does not consist solely of tokens from the neutral-only list, and
  3. Contains at least one token from the qualifying list (substring match allowed
     only for qualifying-list entries).
- Ambiguity rule: if a signal matches both a neutral-only token and a qualifying
  token, prefer expansion in v1 (conservative against signal loss).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import files
from .config import Settings
from .prompts import DECISION_MATRIX_ROWS, PRECOMPUTE_OWNED_MATRIX_ROWS
from .schemas import ChartEntry, DailyManifest, DailyState

NEUTRAL_ONLY_TOKENS: frozenset[str] = frozenset(
    {"neutral", "within", "monitor", "insufficient", "stable", "unknown", "none"}
)

QUALIFYING_TOKENS: tuple[str, ...] = (
    "trim",
    "bear",
    "bull",
    "caution",
    "diverg",
    "widen",
    "tighten",
    "fear",
    "greed",
    "extreme",
    "elevated",
    "oversold",
    "overbought",
    "distribution",
    "regime shift",
    "defensive",
    "attractive",
    "weak",
    "strong",
    "deteriorat",
    "improv",
)

TREND_REGIME_MATURING_TOKENS: frozenset[str] = frozenset({"maturing", "diverg", "flatten"})

# All qualitative rows (not precompute-owned).
ALL_QUALITATIVE_MATRIX_ROWS: frozenset[str] = frozenset(DECISION_MATRIX_ROWS) - frozenset(
    PRECOMPUTE_OWNED_MATRIX_ROWS
)

# Qualitative rows that may auto-add charts (excludes rows that never auto-add).
MATRIX_EXPANSION_ROWS: frozenset[str] = ALL_QUALITATIVE_MATRIX_ROWS - frozenset(
    {"Leverage Risk State", "Overall Signal Balance", "Recommended Action"}
)

TECHNICAL_TIMEFRAME_RANK: dict[str, int] = {
    "intraday": 0,
    "5day": 1,
    "1month": 2,
    "3month": 3,
    "6month": 4,
    "1year": 5,
    "3year": 6,
}


@dataclass
class UnresolvedChartRef:
    original_ref: str
    outcome: str
    message: str


@dataclass
class Pass2ImagePlan:
    attached: list[Path]
    reference_only: list[ChartEntry]
    selection_reason: dict[str, list[str]]
    unresolved_chart_refs: list[UnresolvedChartRef] = field(default_factory=list)


def qualitative_matrix_rows() -> frozenset[str]:
    """All qualitative decision-matrix rows (product boundary vs precompute-owned)."""
    return ALL_QUALITATIVE_MATRIX_ROWS


def matrix_expansion_rows() -> frozenset[str]:
    """Qualitative rows eligible for matrix-driven chart expansion."""
    return MATRIX_EXPANSION_ROWS


def resolve_pass2_images(
    run_dir: Path,
    manifest: DailyManifest,
    daily_state: DailyState,
    settings: Settings,
) -> Pass2ImagePlan:
    """Select Pass 2 chart attachments post-enforcement."""
    ordered = manifest.ordered_charts()
    charts_by_file: dict[str, ChartEntry] = {c.file: c for c in ordered}
    all_paths = files.chart_paths(run_dir, manifest)

    if not settings.pass2_image_optimization_enabled:
        return Pass2ImagePlan(
            attached=all_paths,
            reference_only=[],
            selection_reason={c.file: ["optimization_disabled"] for c in ordered},
        )

    reasons: dict[str, list[str]] = {}
    protected_files: set[str] = set()
    matrix_added_files: set[str] = set()
    unresolved: list[UnresolvedChartRef] = []

    seen_unresolved: set[str] = set()

    # Step 1: protected conflict refs
    for divergence in daily_state.conflicting_evidence:
        for ref in divergence.chart_refs:
            matched = _resolve_chart_ref(ref, charts_by_file)
            if matched is None:
                if ref not in seen_unresolved:
                    seen_unresolved.add(ref)
                    unresolved.append(
                        UnresolvedChartRef(
                            original_ref=ref,
                            outcome="no_manifest_match",
                            message=f"chart ref {ref!r} did not match any manifest file",
                        )
                    )
                continue
            protected_files.add(matched.file)
            _append_reason(reasons, matched.file, "conflict_ref")

    # Step 2: matrix-driven expansion
    row_signals = _matrix_signals(daily_state)
    attached_so_far: set[str] = set(protected_files)

    for row_label in sorted(MATRIX_EXPANSION_ROWS, key=lambda r: DECISION_MATRIX_ROWS.index(r)):
        signal = row_signals.get(row_label, "")
        if not _qualifies_for_expansion(signal):
            continue

        chart = _select_chart_for_row(row_label, signal, ordered, set())
        if chart is None:
            continue

        _append_reason(reasons, chart.file, f"matrix_layer:{row_label}")
        if chart.file in attached_so_far:
            continue

        attached_so_far.add(chart.file)
        matrix_added_files.add(chart.file)

    # Step 3: conservative redundancy pruning (matrix-added only)
    pruned_matrix = _apply_pruning(
        matrix_added_files,
        protected_files,
        charts_by_file,
    )
    final_files = protected_files | pruned_matrix
    reasons = {k: v for k, v in reasons.items() if k in final_files}

    attached = [run_dir / files.CHARTS_DIRNAME / c.file for c in ordered if c.file in final_files]
    reference_only = [c for c in ordered if c.file not in final_files]

    return Pass2ImagePlan(
        attached=attached,
        reference_only=reference_only,
        selection_reason=reasons,
        unresolved_chart_refs=unresolved,
    )


def _append_reason(reasons: dict[str, list[str]], filename: str, reason: str) -> None:
    existing = reasons.setdefault(filename, [])
    if reason not in existing:
        existing.append(reason)


def _resolve_chart_ref(ref: str, charts_by_file: dict[str, ChartEntry]) -> ChartEntry | None:
    basename = Path(ref).name.lower()
    for file, entry in charts_by_file.items():
        if file.lower() == basename:
            return entry
    return None


def _matrix_signals(daily_state: DailyState) -> dict[str, str]:
    return {row.signal_layer: row.signal for row in daily_state.decision_matrix.rows}


def _qualifies_for_expansion(signal: str) -> bool:
    normalized = signal.strip().lower()
    if not normalized:
        return False

    has_qualifying = any(token in normalized for token in QUALIFYING_TOKENS)
    if not has_qualifying:
        return False

    word_tokens = normalized.split()
    if word_tokens and all(t in NEUTRAL_ONLY_TOKENS for t in word_tokens):
        return False

    return True


def _select_chart_for_row(
    row_label: str,
    signal: str,
    ordered: list[ChartEntry],
    attached: set[str],
) -> ChartEntry | None:
    signal_lower = signal.lower()

    if row_label == "Trend Regime":
        prefer_tf = {"3month", "6month"} if any(t in signal_lower for t in TREND_REGIME_MATURING_TOKENS) else None
        if prefer_tf:
            for tf in ("3month", "6month"):
                chart = _first_chart(
                    ordered,
                    attached,
                    category="technical",
                    timeframe=tf,
                )
                if chart:
                    return chart
        return _longest_technical(ordered, attached)

    if row_label == "Intraday Close Position":
        return _first_chart(ordered, attached, timeframe="intraday")

    if row_label in ("RSI / MFI State", "20-Day SMA Status", "Bollinger Band State"):
        return _first_chart(ordered, attached, category="technical", timeframe="1month")

    if row_label == "Credit Condition":
        return _first_chart(ordered, attached, category="credit")

    if row_label == "Breadth Condition":
        mcclellan = _first_chart(
            ordered,
            attached,
            category="breadth",
            filename_contains="mcclellan",
        )
        if mcclellan:
            return mcclellan
        return _first_chart(ordered, attached, category="breadth")

    if row_label == "VIX Regime":
        return _first_chart(ordered, attached, category="volatility")

    return None


def _first_chart(
    ordered: list[ChartEntry],
    attached: set[str],
    *,
    category: str | None = None,
    timeframe: str | None = None,
    filename_contains: str | None = None,
) -> ChartEntry | None:
    for chart in ordered:
        if chart.file in attached:
            continue
        if category and chart.category != category:
            continue
        if timeframe and chart.timeframe != timeframe:
            continue
        if filename_contains:
            needle = filename_contains.lower()
            if needle not in chart.file.lower() and needle not in chart.label.lower():
                continue
        return chart
    return None


def _longest_technical(ordered: list[ChartEntry], attached: set[str]) -> ChartEntry | None:
    candidates = [
        c
        for c in ordered
        if c.category == "technical" and c.file not in attached and c.timeframe in TECHNICAL_TIMEFRAME_RANK
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda c: TECHNICAL_TIMEFRAME_RANK[c.timeframe or ""])


def _apply_pruning(
    matrix_added: set[str],
    protected: set[str],
    charts_by_file: dict[str, ChartEntry],
) -> set[str]:
    """Return matrix-added filenames after conservative redundancy pruning."""
    result = set(matrix_added)
    attached_categories = {charts_by_file[f].category for f in (protected | result) if f in charts_by_file}

    def is_attached(file: str) -> bool:
        return file in protected or file in result

    def drop(file: str) -> None:
        if file in result and file not in protected:
            result.discard(file)

    for fname in list(result):
        if fname in protected:
            continue
        chart = charts_by_file.get(fname)
        if chart is None:
            continue

        tf = chart.timeframe
        cat = chart.category

        # 5day technical when 1month technical attached
        if cat == "technical" and tf == "5day":
            if _any_attached(charts_by_file, is_attached, category="technical", timeframe="1month"):
                drop(fname)
                continue

        # 3year when 6month or 1year attached
        if cat == "technical" and tf == "3year":
            if _any_attached(
                charts_by_file,
                is_attached,
                category="technical",
                timeframe={"6month", "1year"},
            ):
                drop(fname)
                continue

        # 1year when both 3month and 6month attached
        if cat == "technical" and tf == "1year":
            has_3m = _any_attached(charts_by_file, is_attached, category="technical", timeframe="3month")
            has_6m = _any_attached(charts_by_file, is_attached, category="technical", timeframe="6month")
            if has_3m and has_6m:
                drop(fname)
                continue

        # 52wk breadth when McClellan attached
        if cat == "breadth" and "52wk" in fname.lower():
            if _any_attached(
                charts_by_file,
                is_attached,
                category="breadth",
                filename_contains="mcclellan",
            ):
                drop(fname)
                continue

        # F&G momentum (09_*) when F&G overview (08_*) attached
        if fname.startswith("09_") or "fear_greed_momentum" in fname.lower():
            if _any_attached(
                charts_by_file,
                is_attached,
                filename_prefix="08_",
            ) or _any_attached(
                charts_by_file,
                is_attached,
                filename_contains="fear_greed_index",
            ):
                drop(fname)
                continue

        # Safe haven (14_*): keep when F&G overview attached (v1 default — do not prune)
        _ = attached_categories  # referenced for clarity; safe haven always kept

    return result


def _any_attached(
    charts_by_file: dict[str, ChartEntry],
    is_attached,
    *,
    category: str | None = None,
    timeframe: str | set[str] | None = None,
    filename_contains: str | None = None,
    filename_prefix: str | None = None,
) -> bool:
    for file, chart in charts_by_file.items():
        if not is_attached(file):
            continue
        if category and chart.category != category:
            continue
        if timeframe is not None:
            if isinstance(timeframe, set):
                if chart.timeframe not in timeframe:
                    continue
            elif chart.timeframe != timeframe:
                continue
        if filename_contains:
            needle = filename_contains.lower()
            if needle not in file.lower() and needle not in chart.label.lower():
                continue
        if filename_prefix and not file.startswith(filename_prefix):
            continue
        return True
    return False
