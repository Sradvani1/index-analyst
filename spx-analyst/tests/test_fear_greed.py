"""Tests for CNN Fear & Greed fetching and chart generation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from src.fear_greed import (
    W,
    fetch_and_generate,
    fetch_fear_greed_data,
    generate_index_ts,
    generate_junk_bond_demand,
    generate_market_volatility,
    generate_momentum,
    generate_put_call_ratio,
    generate_safe_haven_demand,
    generate_stock_price_breadth,
    generate_stock_price_strength,
)

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "cnn_fear_greed_sample.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


# --- Fetch tests -------------------------------------------------------------

@patch("src.fear_greed._fetch_json")
def test_fetch_fear_greed_data(mock_fetch):
    mock_fetch.return_value = _load_fixture()
    data = fetch_fear_greed_data()
    assert "fear_and_greed" in data
    assert "fear_and_greed_historical" in data
    for key in ("stock_price_strength", "stock_price_breadth", "put_call_options",
                "market_volatility_vix", "safe_haven_demand", "junk_bond_demand"):
        assert key in data


# --- All 8 chart generators --------------------------------------------------

CHART_GENERATORS: list[tuple[str, object, list[str]]] = [
    ("08_fear_greed_index.png", generate_index_ts, ["fear_and_greed_historical"]),
    ("09_fear_greed_momentum.png", generate_momentum, ["market_momentum_sp500", "market_momentum_sp125"]),
    ("10_breadth_52wk_highs_lows.png", generate_stock_price_strength, ["stock_price_strength"]),
    ("11_breadth_mcclellan.png", generate_stock_price_breadth, ["stock_price_breadth"]),
    ("12_put_call_ratio.png", generate_put_call_ratio, ["put_call_options"]),
    ("13_vix_volatility.png", generate_market_volatility, ["market_volatility_vix", "market_volatility_vix_50"]),
    ("14_safe_haven_demand.png", generate_safe_haven_demand, ["safe_haven_demand"]),
    ("15_junk_bond_spread.png", generate_junk_bond_demand, ["junk_bond_demand"]),
]


@pytest.mark.parametrize("filename,generator,required_keys", CHART_GENERATORS)
@patch("src.fear_greed._fetch_json")
def test_all_charts_generate_png(mock_fetch, filename, generator, required_keys, tmp_path):
    mock_fetch.return_value = _load_fixture()
    data = fetch_fear_greed_data()
    output = tmp_path / filename
    generator(data, output)
    assert output.is_file(), f"{filename} was not created"
    img = Image.open(output)
    assert img.size == (W, 588), f"{filename}: expected {W}x588, got {img.size}"


@pytest.mark.parametrize("filename,generator,required_keys", CHART_GENERATORS)
@patch("src.fear_greed._fetch_json")
def test_chart_skips_when_data_missing(mock_fetch, filename, generator, required_keys, tmp_path):
    data = _load_fixture()
    for key in required_keys:
        data.pop(key, None)
    mock_fetch.return_value = data
    data = fetch_fear_greed_data()
    output = tmp_path / filename
    generator(data, output)
    assert not output.exists(), f"{filename} should have been skipped"


# --- Integration -------------------------------------------------------------

@patch("src.fear_greed._fetch_json")
def test_fetch_and_generate_all(mock_fetch, tmp_path):
    mock_fetch.return_value = _load_fixture()
    paths = fetch_and_generate(tmp_path)
    assert len(paths) == 8
    for name in sorted(paths):
        p = paths[name]
        assert p.is_file(), f"{name} was not created"
        assert p.stat().st_size > 1000


@patch("src.fear_greed._fetch_json")
def test_fetch_and_generate_saves_raw_json(mock_fetch, tmp_path):
    mock_fetch.return_value = _load_fixture()
    fetch_and_generate(tmp_path)
    raw = tmp_path / "fear_greed_raw.json"
    assert raw.is_file()
    assert raw.stat().st_size > 100
    parsed = json.loads(raw.read_text(encoding="utf-8"))
    assert "fear_and_greed" in parsed
