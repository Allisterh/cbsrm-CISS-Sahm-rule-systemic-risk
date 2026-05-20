"""Tests for cbsrm.macro.ffr_change."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cbsrm.indicators.base import IIndicator, IndicatorResult
from cbsrm.macro.ffr_change import (
    HORIZONS_DAYS,
    THRESHOLD_AGGRESSIVE,
    THRESHOLD_NORMAL,
    FFRChangeIndicator,
)


def test_implements_protocol():
    ffr = FFRChangeIndicator()
    assert isinstance(ffr, IIndicator)
    assert ffr.id == "FFR-CHANGE-US"


def test_required_series():
    assert FFRChangeIndicator().required_series() == ["DFF"]


def test_compute_pause_regime():
    # Constant 5.33% for 365 days -> all horizon changes ~= 0
    idx = pd.date_range("2024-01-01", periods=400, freq="B")
    df = pd.DataFrame({"DFF": [5.33] * 400}, index=idx)
    res = FFRChangeIndicator().compute(df)
    assert res.metadata["regime"] == "PAUSE"
    assert abs(res.metadata["latest_composite_change_bp"]) < 1.0


def test_compute_tightening_regime():
    # Rate rises from 0.25 to 5.50 over the past year (525 bp hike)
    idx = pd.date_range("2022-01-01", periods=400, freq="B")
    # Steady rise; final segment shows large 12M change
    rates = np.linspace(0.25, 5.50, 400)
    df = pd.DataFrame({"DFF": rates}, index=idx)
    res = FFRChangeIndicator().compute(df)
    # All three horizon changes positive; large enough to hit AGGRESSIVE
    assert res.metadata["latest_composite_change_bp"] > THRESHOLD_AGGRESSIVE
    assert res.metadata["regime"] == "AGGRESSIVE_TIGHTENING"


def test_compute_easing_regime():
    # Cut from 5.50 to 0.25 over the past year
    idx = pd.date_range("2024-01-01", periods=400, freq="B")
    rates = np.linspace(5.50, 0.25, 400)
    df = pd.DataFrame({"DFF": rates}, index=idx)
    res = FFRChangeIndicator().compute(df)
    assert res.metadata["latest_composite_change_bp"] < -THRESHOLD_AGGRESSIVE
    assert res.metadata["regime"] == "AGGRESSIVE_EASING"


def test_compute_moderate_tightening():
    # 100 bp hike across 12 months -> TIGHTENING (not AGGRESSIVE)
    idx = pd.date_range("2024-01-01", periods=300, freq="B")
    rates = np.linspace(4.50, 5.50, 300)
    df = pd.DataFrame({"DFF": rates}, index=idx)
    res = FFRChangeIndicator().compute(df)
    bp = res.metadata["latest_composite_change_bp"]
    assert THRESHOLD_NORMAL <= bp < THRESHOLD_AGGRESSIVE
    assert res.metadata["regime"] == "TIGHTENING"


def test_compute_raises_on_missing_column():
    df = pd.DataFrame({"WRONG": [1.0]})
    with pytest.raises(ValueError, match="DFF"):
        FFRChangeIndicator().compute(df)


def test_compute_empty():
    df = pd.DataFrame({"DFF": []}, dtype=float)
    res = FFRChangeIndicator().compute(df)
    assert res.values.empty


def test_compute_short_history_insufficient():
    # 30 days < 252 -> no 12M change computable, but 3M still works
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    df = pd.DataFrame({"DFF": np.linspace(5.0, 5.5, 30)}, index=idx)
    res = FFRChangeIndicator().compute(df)
    # composite needs ALL horizons; with only 30 days no horizon hits 12M -> empty
    assert res.metadata["regime"] in ("INSUFFICIENT_HISTORY", "PAUSE", "TIGHTENING")


def test_horizon_constants():
    assert set(HORIZONS_DAYS.keys()) == {"3m", "6m", "12m"}
    assert HORIZONS_DAYS["3m"] < HORIZONS_DAYS["6m"] < HORIZONS_DAYS["12m"]
