"""Tests for Pass 2 dynamic image selection (PR-4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from src.config import Settings
from src.files import load_manifest
from src.pass2_images import Pass2ImagePlan, qualitative_matrix_rows, resolve_pass2_images
from src.prompts import (
    DECISION_MATRIX_ROWS,
    PRECOMPUTE_OWNED_MATRIX_ROWS,
    build_report_prompt,
    load_system_role,
)
from src.schemas import DailyManifest, DailyState, DecisionMatrix, DecisionMatrixRow

from tests.conftest import SAMPLE_STATE, make_settings
from tests.sample_analysis_context import sample_analysis_context

FIXTURES = Path(__file__).parent / "fixtures" / "pass2_images"
STANDARD_MANIFEST = Path(__file__).parent.parent / "data" / "runs" / "2026-06-10" / "manifest.json"


def _build_full_run_dir(tmp_path: Path, manifest_path: Path | None = None) -> Path:
    manifest_path = manifest_path or STANDARD_MANIFEST
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_dir = tmp_path / "runs" / raw["date"]
    charts = run_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    for chart in raw["charts"]:
        Image.new("RGB", (64, 64), color=(100, 100, 100)).save(charts / chart["file"])
    (run_dir / "manifest.json").write_text(json.dumps(raw), encoding="utf-8")
    return run_dir


def _matrix_from_signals(signals: dict[str, str]) -> DecisionMatrix:
    rows = []
    for layer in DECISION_MATRIX_ROWS:
        sig = signals.get(layer, "neutral")
        rows.append(DecisionMatrixRow(signal_layer=layer, current_reading="n/a", signal=sig))
    return DecisionMatrix(rows=rows)


def _state_with(
    *,
    conflicts: list[dict] | None = None,
    matrix_signals: dict[str, str] | None = None,
    date: str = "2026-06-10",
) -> DailyState:
    data = dict(SAMPLE_STATE)
    data["date"] = date
    if conflicts is not None:
        data["conflicting_evidence"] = conflicts
    if matrix_signals is not None:
        data["decision_matrix"] = {"rows": [r.model_dump() for r in _matrix_from_signals(matrix_signals).rows]}
    return DailyState.model_validate(data)


def _resolve(tmp_path: Path, daily_state: DailyState, settings: Settings | None = None) -> Pass2ImagePlan:
    run_dir = _build_full_run_dir(tmp_path)
    manifest = load_manifest(run_dir)
    settings = settings or make_settings(tmp_path)
    settings.pass2_image_optimization_enabled = True
    return resolve_pass2_images(run_dir, manifest, daily_state, settings)


def _attached_names(plan: Pass2ImagePlan) -> list[str]:
    return [p.name for p in plan.attached]


def test_qualitative_row_scope_matches_precompute_owned_boundary():
    expected = frozenset(DECISION_MATRIX_ROWS) - frozenset(PRECOMPUTE_OWNED_MATRIX_ROWS)
    assert qualitative_matrix_rows() == expected


def test_protected_refs_always_attached(tmp_path):
    state = _state_with(
        conflicts=[
            {
                "id": "DIV-1",
                "layers": ["credit"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "high",
                "chart_refs": ["15_junk_bond_spread.png"],
            }
        ],
        matrix_signals={"Credit Condition": "neutral"},
    )
    plan = _resolve(tmp_path, state)
    assert "15_junk_bond_spread.png" in _attached_names(plan)
    assert "conflict_ref" in plan.selection_reason["15_junk_bond_spread.png"]


def test_multi_reason_audit(tmp_path):
    state = _state_with(
        conflicts=[
            {
                "id": "DIV-1",
                "layers": ["credit"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "high",
                "chart_refs": ["15_junk_bond_spread.png"],
            }
        ],
        matrix_signals={"Credit Condition": "widening — caution"},
    )
    plan = _resolve(tmp_path, state)
    reasons = plan.selection_reason["15_junk_bond_spread.png"]
    assert "conflict_ref" in reasons
    assert "matrix_layer:Credit Condition" in reasons


def test_pruning_never_removes_protected(tmp_path):
    state = _state_with(
        conflicts=[
            {
                "id": "DIV-1",
                "layers": ["technicals"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "high",
                "chart_refs": ["02_spx_5day.png"],
            }
        ],
        matrix_signals={
            "RSI / MFI State": "overbought caution",
            "20-Day SMA Status": "neutral",
            "Bollinger Band State": "neutral",
        },
    )
    plan = _resolve(tmp_path, state)
    assert "02_spx_5day.png" in _attached_names(plan)
    assert "03_spx_1month.png" in _attached_names(plan)


def test_matrix_expansion_credit(tmp_path):
    state = _state_with(
        matrix_signals={"Credit Condition": "widening spreads"},
    )
    plan = _resolve(tmp_path, state)
    assert "15_junk_bond_spread.png" in _attached_names(plan)
    assert "matrix_layer:Credit Condition" in plan.selection_reason["15_junk_bond_spread.png"]


def test_matrix_expansion_breadth_mcclellan_preferred(tmp_path):
    state = _state_with(
        matrix_signals={"Breadth Condition": "distribution weak"},
    )
    plan = _resolve(tmp_path, state)
    assert "11_breadth_mcclellan.png" in _attached_names(plan)
    assert "10_breadth_52wk_highs_lows.png" not in _attached_names(plan)


def test_matrix_expansion_vix(tmp_path):
    state = _state_with(
        matrix_signals={"VIX Regime": "elevated fear"},
    )
    plan = _resolve(tmp_path, state)
    assert "13_vix_volatility.png" in _attached_names(plan)


def test_redundancy_prune_5day_when_1month_matrix(tmp_path):
    state = _state_with(
        matrix_signals={
            "Trend Regime": "bullish extension",
            "RSI / MFI State": "overbought",
        },
    )
    plan = _resolve(tmp_path, state)
    assert "03_spx_1month.png" in _attached_names(plan)
    assert "02_spx_5day.png" not in _attached_names(plan)


def test_redundancy_not_when_only_protected_refs(tmp_path):
    state = _state_with(
        conflicts=[
            {
                "id": "DIV-1",
                "layers": ["technicals"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "high",
                "chart_refs": ["02_spx_5day.png"],
            }
        ],
        matrix_signals={"Trend Regime": "neutral"},
    )
    plan = _resolve(tmp_path, state)
    assert "02_spx_5day.png" in _attached_names(plan)


def test_zero_chart_day(tmp_path):
    state = _state_with(
        conflicts=[],
        matrix_signals={
            "Trend Regime": "neutral",
            "Credit Condition": "monitor",
            "VIX Regime": "stable",
        },
    )
    plan = _resolve(tmp_path, state)
    assert plan.attached == []
    assert len(plan.reference_only) == 15

    role = load_system_role("Role.")
    bundle = build_report_prompt(
        system_role=role,
        framework="FW",
        daily_state=state,
        manifest=load_manifest(_build_full_run_dir(tmp_path)),
        external_context=__import__("src.schemas", fromlist=["ExternalContext"]).ExternalContext(
            date="2026-06-10"
        ),
        analysis_context=sample_analysis_context("2026-06-10"),
        pass2_attached=[],
        pass2_reference_only=plan.reference_only,
        pass2_optimization_enabled=True,
    )
    assert "no chart images are attached" in bundle.body


def test_fixture_golden_cases(tmp_path):
    for name in ("conflict_heavy.json", "neutral_zero_chart.json", "matrix_add.json"):
        case = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        state = _state_with(
            conflicts=case.get("conflicting_evidence", []),
            matrix_signals=case.get("matrix_signals", {}),
        )
        plan = _resolve(tmp_path, state)
        assert _attached_names(plan) == case["expected_attached"], name
        if "expected_reference_count" in case:
            assert len(plan.reference_only) == case["expected_reference_count"], name
        if case.get("expected_pruned_absent"):
            for f in case["expected_pruned_absent"]:
                assert f not in _attached_names(plan), name


def test_2026_06_10_reference_subset(tmp_path):
    state = _state_with(
        conflicts=[
            {
                "id": "extension_vs_credit",
                "layers": ["valuation", "credit"],
                "bullish_read": "Trend holds",
                "bearish_read": "Credit stress",
                "framework_rule": "Credit warning",
                "weight": "high",
                "chart_refs": ["03_spx_1month.png", "15_junk_bond_spread.png"],
            },
            {
                "id": "breadth_vs_price",
                "layers": ["breadth"],
                "bullish_read": "ATH",
                "bearish_read": "McClellan weak",
                "framework_rule": "Breadth divergence",
                "weight": "medium",
                "chart_refs": ["11_breadth_mcclellan.png"],
            },
        ],
        matrix_signals={
            "Trend Regime": "bullish maturing",
            "Intraday Close Position": "upper third",
            "RSI / MFI State": "overbought caution",
            "20-Day SMA Status": "above",
            "Bollinger Band State": "upper band",
            "Credit Condition": "widening",
            "Breadth Condition": "diverging weak",
            "VIX Regime": "elevated",
            "Leverage Risk State": "neutral",
            "Overall Signal Balance": "mixed",
            "Recommended Action": "hold_and_monitor",
        },
    )
    plan = _resolve(tmp_path, state)
    attached = _attached_names(plan)
    assert 5 <= len(attached) <= 9
    for ref in ("03_spx_1month.png", "11_breadth_mcclellan.png", "15_junk_bond_spread.png"):
        assert ref in attached
    assert len(attached) < 15


def test_feature_flag_off_full_manifest(tmp_path):
    run_dir = _build_full_run_dir(tmp_path)
    manifest = load_manifest(run_dir)
    state = _state_with(matrix_signals={"Credit Condition": "widening"})
    settings = make_settings(tmp_path)
    settings.pass2_image_optimization_enabled = False
    plan = resolve_pass2_images(run_dir, manifest, state, settings)
    assert len(plan.attached) == 15
    assert plan.reference_only == []
    assert all(v == ["optimization_disabled"] for v in plan.selection_reason.values())

    bundle = build_report_prompt(
        system_role=load_system_role("R"),
        framework="FW",
        daily_state=state,
        manifest=manifest,
        external_context=__import__("src.schemas", fromlist=["ExternalContext"]).ExternalContext(
            date="2026-06-10"
        ),
        analysis_context=sample_analysis_context("2026-06-10"),
        pass2_attached=[c for c in manifest.ordered_charts()],
        pass2_reference_only=[],
        pass2_optimization_enabled=False,
    )
    assert "Today's chart pack (images attached in this order)" in bundle.body
    assert "Pass 2 chart pack" not in bundle.body


def test_unresolved_refs_warning_continues(tmp_path):
    state = _state_with(
        conflicts=[
            {
                "id": "DIV-1",
                "layers": ["x"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "low",
                "chart_refs": ["nonexistent_chart.png"],
            }
        ],
    )
    plan = _resolve(tmp_path, state)
    assert len(plan.unresolved_chart_refs) == 1
    assert plan.unresolved_chart_refs[0].outcome == "no_manifest_match"


def test_unresolved_refs_deduped_across_divergences(tmp_path):
    bad_ref = "missing.png"
    state = _state_with(
        conflicts=[
            {
                "id": "DIV-1",
                "layers": ["x"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "low",
                "chart_refs": [bad_ref],
            },
            {
                "id": "DIV-2",
                "layers": ["y"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "low",
                "chart_refs": [bad_ref],
            },
        ],
    )
    plan = _resolve(tmp_path, state)
    assert len(plan.unresolved_chart_refs) == 1
    assert plan.unresolved_chart_refs[0].original_ref == bad_ref


def test_pruned_chart_drops_stale_selection_reason(tmp_path):
    state = _state_with(
        conflicts=[
            {
                "id": "DIV-1",
                "layers": ["technicals"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "high",
                "chart_refs": ["04_spx_3month.png", "05_spx_6month.png"],
            }
        ],
        matrix_signals={"Trend Regime": "bullish strong"},
    )
    plan = _resolve(tmp_path, state)
    attached = set(_attached_names(plan))
    assert "07_spx_3year.png" not in attached
    assert set(plan.selection_reason.keys()) == attached
    assert "07_spx_3year.png" not in plan.selection_reason


def test_selection_reason_keys_match_attached_only(tmp_path):
    plan = _resolve(
        tmp_path,
        _state_with(
            conflicts=[
                {
                    "id": "DIV-1",
                    "layers": ["credit"],
                    "bullish_read": "a",
                    "bearish_read": "b",
                    "framework_rule": "r",
                    "weight": "high",
                    "chart_refs": ["15_junk_bond_spread.png"],
                }
            ],
            matrix_signals={"Credit Condition": "widening — caution", "VIX Regime": "elevated"},
        ),
    )
    assert set(plan.selection_reason.keys()) == set(_attached_names(plan))


def test_attached_manifest_order_deduped(tmp_path):
    state = _state_with(
        conflicts=[
            {
                "id": "DIV-1",
                "layers": ["x"],
                "bullish_read": "a",
                "bearish_read": "b",
                "framework_rule": "r",
                "weight": "high",
                "chart_refs": ["15_junk_bond_spread.png"],
            }
        ],
        matrix_signals={"Credit Condition": "widening"},
    )
    plan = _resolve(tmp_path, state)
    manifest = load_manifest(_build_full_run_dir(tmp_path))
    order_idx = {c.file: c.order for c in manifest.ordered_charts()}
    attached_orders = [order_idx[p.name] for p in plan.attached]
    assert attached_orders == sorted(attached_orders)
    assert len(attached_orders) == len(set(attached_orders))


def test_downscale_dimensions():
    from src.anthropic_client import _user_content
    from src.prompts import PromptBundle

    bundle = PromptBundle(system_role="r", framework="f", body="b")
    paths = [Path("x.png")]

    with patch("src.anthropic_client._encode_image") as mock_encode:
        mock_encode.return_value = {"type": "image", "source": {}}
        _user_content(bundle, paths, 1568)
        mock_encode.assert_called_with(paths[0], 1568)
        mock_encode.reset_mock()
        _user_content(bundle, paths, 1092)
        mock_encode.assert_called_with(paths[0], 1092)


def test_downscale_uses_pass1_dim_when_flag_off():
    from src.anthropic_client import AnthropicClient
    from src.prompts import PromptBundle

    settings = Settings(anthropic_api_key="test")
    settings.pass2_image_optimization_enabled = False
    settings.pass2_image_max_dimension = 1092
    settings.image_max_dimension = 1568

    bundle = PromptBundle(system_role="r", framework="f", body="b")
    paths = [Path("x.png")]

    with patch("src.anthropic_client._encode_image") as mock_encode, patch.object(
        AnthropicClient, "_create"
    ) as mock_create:
        mock_encode.return_value = {"type": "image", "source": {}}
        mock_response = type(
            "R",
            (),
            {
                "content": [
                    type(
                        "B",
                        (),
                        {
                            "type": "text",
                            "text": "# SPX Daily Analysis — 2026-06-10\n\n## 0. Structural Regime Classification\n",
                        },
                    )()
                ],
                "model_dump": lambda self, mode="json": {"ok": True},
            },
        )()
        mock_create.return_value = mock_response
        client = AnthropicClient(settings)
        client.run_markdown_report(bundle, paths, pass2_audit={})
        mock_encode.assert_called_with(paths[0], 1568)
