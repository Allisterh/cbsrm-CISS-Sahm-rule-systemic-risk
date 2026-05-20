"""Tests for cbsrm.macro.macro_composite."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cbsrm.indicators.base import IIndicator
from cbsrm.macro.macro_composite import (
    MACRO_REGIMES,
    MacroCompositeIndicator,
    classify_regime,
)


def _good_metas() -> tuple[dict, dict, dict, dict]:
    """Four sub-indicator metas that should classify RISK_ON."""
    yc = {
        "n_obs": 1000,
        "latest_recession_prob_12mo": 0.05,
        "latest_days_inverted_run": 0,
        "persistent_inversion_days_threshold": 60,
    }
    nfp = {
        "n_obs": 100,
        "latest_z": 1.2,
        "classification": "ACCELERATING",
    }
    ffr = {
        "n_obs": 500,
        "regime": "EASING",
    }
    dxy = {
        "n_obs": 500,
        "regime": "DOLLAR_BEAR",
    }
    return yc, nfp, ffr, dxy


def _bad_metas() -> tuple[dict, dict, dict, dict]:
    """Four sub-indicator metas that should classify RISK_OFF."""
    yc = {
        "n_obs": 1000,
        "latest_recession_prob_12mo": 0.55,
        "latest_days_inverted_run": 100,
        "persistent_inversion_days_threshold": 60,
    }
    nfp = {
        "n_obs": 100,
        "latest_z": -2.5,
        "classification": "SEVERE_DECELERATION",
    }
    ffr = {
        "n_obs": 500,
        "regime": "AGGRESSIVE_TIGHTENING",
    }
    dxy = {
        "n_obs": 500,
        "regime": "STRONG_DOLLAR_BULL",
    }
    return yc, nfp, ffr, dxy


def test_implements_protocol():
    m = MacroCompositeIndicator()
    assert isinstance(m, IIndicator)
    assert m.id == "MACRO-COMPOSITE-US"


def test_required_series():
    assert set(MacroCompositeIndicator().required_series()) == {
        "T10Y3M", "PAYEMS", "DFF", "DTWEXBGS"
    }


def test_classify_risk_on():
    yc, nfp, ffr, dxy = _good_metas()
    v = classify_regime(yc, nfp, ffr, dxy)
    assert v["regime"] == "RISK_ON"
    assert v["composite_score"] >= 0.4
    assert v["override_triggers"] == []


def test_classify_risk_off_by_overrides():
    yc, nfp, ffr, dxy = _bad_metas()
    v = classify_regime(yc, nfp, ffr, dxy)
    assert v["regime"] == "RISK_OFF"
    # All three override triggers should fire
    assert "PERSISTENT_INVERSION_WITH_HIGH_RECESSION_PROB" in v["override_triggers"]
    assert "AGGRESSIVE_TIGHTENING" in v["override_triggers"]
    assert "SEVERE_PAYROLL_DECELERATION" in v["override_triggers"]


def test_classify_risk_off_by_score_alone():
    yc, nfp, ffr, dxy = _good_metas()
    # All sub-scores moderately negative but no overrides
    yc["latest_recession_prob_12mo"] = 0.45
    nfp["latest_z"] = -1.5
    nfp["classification"] = "DECELERATING"
    ffr["regime"] = "TIGHTENING"
    dxy["regime"] = "DOLLAR_BULL"
    v = classify_regime(yc, nfp, ffr, dxy)
    assert v["regime"] == "RISK_OFF"
    assert v["override_triggers"] == []


def test_classify_transition_up():
    yc, nfp, ffr, dxy = _good_metas()
    # Slightly positive composite -> TRANSITION_UP
    yc["latest_recession_prob_12mo"] = 0.20
    nfp["latest_z"] = 0.2
    nfp["classification"] = "AT_TREND"
    ffr["regime"] = "PAUSE"
    dxy["regime"] = "NEUTRAL"
    v = classify_regime(yc, nfp, ffr, dxy)
    assert v["regime"] == "TRANSITION_UP"


def test_classify_transition_down():
    yc, nfp, ffr, dxy = _good_metas()
    yc["latest_recession_prob_12mo"] = 0.35
    nfp["latest_z"] = -0.5
    nfp["classification"] = "AT_TREND"
    ffr["regime"] = "TIGHTENING"
    dxy["regime"] = "NEUTRAL"
    v = classify_regime(yc, nfp, ffr, dxy)
    assert v["regime"] == "TRANSITION_DOWN"


def test_classify_insufficient_history():
    yc, nfp, ffr, dxy = _good_metas()
    nfp["n_obs"] = 0
    v = classify_regime(yc, nfp, ffr, dxy)
    assert v["regime"] == "INSUFFICIENT_HISTORY"


def test_compute_full_pipeline_smoke():
    # Synthetic but realistic-shaped data for all four FRED series.
    rng = np.random.RandomState(42)
    n = 600
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    # T10Y3M: declining from +1.5 to -0.3 then partial recovery to +0.2
    t10y3m = np.concatenate(
        [np.linspace(1.5, -0.3, 400), np.linspace(-0.3, 0.2, 200)]
    )
    # PAYEMS: monthly, ~200 obs is plenty for 5-year window
    payems_idx = pd.date_range("2010-01-01", periods=180, freq="MS")
    payems = 130_000 * (1.0015 ** np.arange(180))
    # DFF: rising
    dff = np.linspace(0.25, 5.33, n)
    # DTWEXBGS: rangebound
    dtwex = 120.0 + rng.normal(0, 1.0, n).cumsum() / 50.0

    df = pd.DataFrame(
        {"T10Y3M": t10y3m, "DFF": dff, "DTWEXBGS": dtwex}, index=idx
    )
    # PAYEMS at monthly cadence — reindex to business days with forward-fill
    payems_s = pd.Series(payems, index=payems_idx, name="PAYEMS")
    df["PAYEMS"] = payems_s.reindex(df.index, method="ffill")

    res = MacroCompositeIndicator().compute(df)
    assert res.metadata["latest_regime"] in MACRO_REGIMES
    assert "yield_curve" in res.metadata["sub_indicators"]
    assert "nfp_momentum" in res.metadata["sub_indicators"]


def test_compute_raises_on_missing_column():
    df = pd.DataFrame({"T10Y3M": [1.0]})  # missing PAYEMS / DFF / DTWEXBGS
    with pytest.raises(ValueError):
        MacroCompositeIndicator().compute(df)


def test_macro_regimes_constant():
    assert "RISK_ON" in MACRO_REGIMES
    assert "RISK_OFF" in MACRO_REGIMES
    assert "TRANSITION_UP" in MACRO_REGIMES
    assert "TRANSITION_DOWN" in MACRO_REGIMES
    assert "INSUFFICIENT_HISTORY" in MACRO_REGIMES
