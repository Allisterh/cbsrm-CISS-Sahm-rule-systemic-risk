"""Tests for cbsrm.macro.nfp_momentum."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cbsrm.indicators.base import IIndicator, IndicatorResult
from cbsrm.macro.nfp_momentum import (
    DEFAULT_LOOKBACK_MONTHS,
    NFPMomentumIndicator,
)


def test_implements_protocol():
    nfp = NFPMomentumIndicator()
    assert isinstance(nfp, IIndicator)
    assert nfp.id == "NFP-MOMENTUM-US"
    assert nfp.version == "1.0.0"


def test_required_series():
    assert NFPMomentumIndicator().required_series() == ["PAYEMS"]


def test_compute_steady_growth_yields_near_zero_z():
    # 0.1% monthly growth, constant -> z should converge to ~0 in steady state
    idx = pd.date_range("2010-01-01", periods=120, freq="MS")
    level = 100.0 * (1.001 ** np.arange(120))
    df = pd.DataFrame({"PAYEMS": level}, index=idx)
    res = NFPMomentumIndicator(lookback_months=60).compute(df)
    # Z scores after lookback window has filled should be small
    tail = res.values.iloc[-12:]
    assert abs(tail.mean()) < 0.5


def test_compute_acceleration_classification():
    # Steady growth then sudden acceleration
    idx = pd.date_range("2010-01-01", periods=180, freq="MS")
    level = np.zeros(180)
    level[0] = 100.0
    for i in range(1, 180):
        # Last few months: triple the growth
        g = 0.001 if i < 170 else 0.005
        level[i] = level[i - 1] * (1.0 + g)
    df = pd.DataFrame({"PAYEMS": level}, index=idx)
    res = NFPMomentumIndicator(lookback_months=60).compute(df)
    # Latest z should be elevated
    assert res.metadata["latest_z"] > 1.0


def test_compute_severe_deceleration_classification():
    idx = pd.date_range("2010-01-01", periods=180, freq="MS")
    level = np.zeros(180)
    level[0] = 100.0
    for i in range(1, 180):
        # Growth steady at 0.2%, last month contracts 1%
        g = 0.002 if i < 179 else -0.01
        level[i] = level[i - 1] * (1.0 + g)
    df = pd.DataFrame({"PAYEMS": level}, index=idx)
    res = NFPMomentumIndicator(lookback_months=60).compute(df)
    assert res.metadata["latest_z"] < -2.0
    assert res.metadata["classification"] == "SEVERE_DECELERATION"


def test_compute_raises_on_missing_column():
    df = pd.DataFrame({"WRONG": [1.0, 2.0]})
    with pytest.raises(ValueError, match="PAYEMS"):
        NFPMomentumIndicator().compute(df)


def test_compute_empty_data():
    df = pd.DataFrame({"PAYEMS": []}, dtype=float)
    res = NFPMomentumIndicator().compute(df)
    assert res.values.empty


def test_compute_short_history_classification():
    # Only 6 months of data — less than MIN_OBS_FOR_Z. Should not crash.
    idx = pd.date_range("2024-01-01", periods=6, freq="MS")
    df = pd.DataFrame({"PAYEMS": [100.0, 100.5, 101.0, 101.4, 101.7, 102.0]}, index=idx)
    res = NFPMomentumIndicator().compute(df)
    # z series will be empty (need MIN_OBS_FOR_Z months)
    assert res.metadata["classification"] == "INSUFFICIENT_HISTORY"


def test_lookback_configurable():
    nfp = NFPMomentumIndicator(lookback_months=24)
    assert nfp.lookback_months == 24
    assert nfp.lookback_months != DEFAULT_LOOKBACK_MONTHS
