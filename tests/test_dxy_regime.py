"""Tests for cbsrm.macro.dxy_regime."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cbsrm.indicators.base import IIndicator
from cbsrm.macro.dxy_regime import (
    DXYRegimeIndicator,
    LOOKBACK_DAYS_DEFAULT,
)


def test_implements_protocol():
    dxy = DXYRegimeIndicator()
    assert isinstance(dxy, IIndicator)
    assert dxy.id == "DXY-REGIME-US"


def test_required_series():
    assert DXYRegimeIndicator().required_series() == ["DTWEXBGS"]


def test_compute_neutral_regime():
    # Constant level for 400 days -> z ~ 0
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    df = pd.DataFrame({"DTWEXBGS": [120.0] * 400}, index=idx)
    res = DXYRegimeIndicator().compute(df)
    # No variance -> z is nan; regime falls to NEUTRAL or INSUFFICIENT
    assert res.metadata["regime"] in ("NEUTRAL", "INSUFFICIENT_HISTORY")


def test_compute_strong_dollar_bull_regime():
    # Sustained rise that ends well above its 252-day mean
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    # First 252 days hover around 100; next 148 days rise to 130
    levels = np.concatenate(
        [
            100.0 + np.random.RandomState(0).normal(0, 0.5, 252),
            np.linspace(100.0, 130.0, 148),
        ]
    )
    df = pd.DataFrame({"DTWEXBGS": levels}, index=idx)
    res = DXYRegimeIndicator().compute(df)
    # Latest z should be strongly positive
    assert res.metadata["latest_z_score"] >= 1.5
    assert res.metadata["regime"] == "STRONG_DOLLAR_BULL"


def test_compute_strong_dollar_bear_regime():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    levels = np.concatenate(
        [
            120.0 + np.random.RandomState(1).normal(0, 0.5, 252),
            np.linspace(120.0, 95.0, 148),
        ]
    )
    df = pd.DataFrame({"DTWEXBGS": levels}, index=idx)
    res = DXYRegimeIndicator().compute(df)
    assert res.metadata["latest_z_score"] <= -1.5
    assert res.metadata["regime"] == "STRONG_DOLLAR_BEAR"


def test_compute_raises_on_missing_column():
    df = pd.DataFrame({"WRONG": [1.0]})
    with pytest.raises(ValueError, match="DTWEXBGS"):
        DXYRegimeIndicator().compute(df)


def test_compute_empty():
    df = pd.DataFrame({"DTWEXBGS": []}, dtype=float)
    res = DXYRegimeIndicator().compute(df)
    assert res.values.empty


def test_lookback_configurable():
    dxy = DXYRegimeIndicator(lookback_days=180)
    assert dxy.lookback_days == 180
    assert LOOKBACK_DAYS_DEFAULT == 252


def test_subindex_columns_present():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    df = pd.DataFrame(
        {"DTWEXBGS": 100.0 + np.linspace(0, 10, 300)}, index=idx
    )
    res = DXYRegimeIndicator().compute(df)
    assert "level" in res.subindex_values.columns
    assert "z_score_252d" in res.subindex_values.columns
    assert "log_ret_3m" in res.subindex_values.columns
