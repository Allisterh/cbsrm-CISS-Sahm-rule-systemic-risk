"""Tests for cbsrm.macro.yield_curve."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cbsrm.indicators.base import IIndicator, IndicatorResult
from cbsrm.macro.yield_curve import (
    ESTRELLA_MISHKIN_BETA_0,
    ESTRELLA_MISHKIN_BETA_1,
    YieldCurveIndicator,
    estrella_mishkin_recession_prob,
    _standard_normal_cdf,
)


def test_implements_protocol():
    yc = YieldCurveIndicator()
    assert isinstance(yc, IIndicator)
    assert yc.id == "YIELD-CURVE-US"
    assert yc.version == "1.0.0"
    assert "T10Y3M" in yc.source or "Treasury Spread" in yc.source


def test_required_series():
    assert YieldCurveIndicator().required_series() == ["T10Y3M"]


def test_phi_basic():
    assert _standard_normal_cdf(0.0) == pytest.approx(0.5, abs=1e-9)
    assert _standard_normal_cdf(1.96) == pytest.approx(0.975, abs=1e-3)
    assert _standard_normal_cdf(-1.96) == pytest.approx(0.025, abs=1e-3)


def test_recession_prob_at_zero_spread():
    # spread = 0 → z = beta_0 → Phi(-0.5450) ≈ 0.293
    p = estrella_mishkin_recession_prob(0.0)
    assert 0.28 < p < 0.31


def test_recession_prob_monotone_decreasing_in_spread():
    spreads = [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0]
    probs = [estrella_mishkin_recession_prob(s) for s in spreads]
    for i in range(len(probs) - 1):
        assert probs[i] > probs[i + 1], (
            f"prob must strictly decrease as spread rises; got {probs}"
        )


def test_recession_prob_deep_inversion_high():
    # spread = -3 (very inverted) → very high recession prob
    p = estrella_mishkin_recession_prob(-3.0)
    assert p > 0.85


def test_recession_prob_steep_curve_low():
    # spread = +3 (very steep, normal curve) → low recession prob
    p = estrella_mishkin_recession_prob(3.0)
    assert p < 0.05


def test_compute_passes_basic():
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    spreads = np.linspace(2.0, -1.0, 10)
    df = pd.DataFrame({"T10Y3M": spreads}, index=idx)
    res = YieldCurveIndicator().compute(df)
    assert isinstance(res, IndicatorResult)
    assert res.indicator_id == "YIELD-CURVE-US"
    assert len(res.values) == 10
    # First day spread = 2.0 → low prob; last day spread = -1.0 → higher
    assert res.values.iloc[0] < res.values.iloc[-1]


def test_compute_raises_on_missing_column():
    df = pd.DataFrame({"WRONG": [1.0, 2.0]})
    with pytest.raises(ValueError, match="T10Y3M"):
        YieldCurveIndicator().compute(df)


def test_compute_drops_nan():
    idx = pd.date_range("2020-01-01", periods=5, freq="B")
    df = pd.DataFrame({"T10Y3M": [1.0, np.nan, 0.5, np.nan, -0.5]}, index=idx)
    res = YieldCurveIndicator().compute(df)
    assert len(res.values) == 3


def test_compute_inversion_run_length():
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    # Pattern: positive, negative x 5, positive, negative x 3
    vals = [1.0, -0.1, -0.2, -0.1, -0.3, -0.5, 0.1, -0.2, -0.3, -0.4]
    df = pd.DataFrame({"T10Y3M": vals}, index=idx)
    res = YieldCurveIndicator().compute(df)
    runs = res.subindex_values["days_inverted_run"].tolist()
    assert runs == [0, 1, 2, 3, 4, 5, 0, 1, 2, 3]


def test_compute_persistent_inversion_threshold():
    yc = YieldCurveIndicator(persistent_inversion_days=3)
    idx = pd.date_range("2020-01-01", periods=8, freq="B")
    df = pd.DataFrame(
        {"T10Y3M": [1.0, -0.1, -0.1, -0.1, -0.1, -0.1, 0.0, 1.0]},
        index=idx,
    )
    res = yc.compute(df)
    persistent = res.subindex_values["persistent_inversion"].tolist()
    assert persistent == [0, 0, 0, 1, 1, 1, 0, 0]


def test_compute_metadata_complete():
    idx = pd.date_range("2020-01-01", periods=5, freq="B")
    df = pd.DataFrame({"T10Y3M": [1.0, 0.5, 0.0, -0.5, -1.0]}, index=idx)
    res = YieldCurveIndicator().compute(df)
    m = res.metadata
    assert m["series_id"] == "T10Y3M"
    assert m["latest_spread_pp"] == pytest.approx(-1.0)
    assert m["latest_is_inverted"] is True
    assert "Estrella-Mishkin" in m["interpretation"]
    assert m["model"]["beta_0"] == ESTRELLA_MISHKIN_BETA_0
    assert m["model"]["beta_1"] == ESTRELLA_MISHKIN_BETA_1


def test_compute_empty_data_returns_empty_result():
    df = pd.DataFrame({"T10Y3M": []}, dtype=float)
    res = YieldCurveIndicator().compute(df)
    assert res.values.empty
    assert res.metadata["n_obs"] == 0
