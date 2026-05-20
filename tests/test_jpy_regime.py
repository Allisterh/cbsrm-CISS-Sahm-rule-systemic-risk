"""Tests for cbsrm.macro.jpy_regime."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cbsrm.indicators.base import IIndicator
from cbsrm.macro.jpy_regime import JPYRegimeIndicator, LOOKBACK_DAYS_DEFAULT


def test_implements_protocol():
    jpy = JPYRegimeIndicator()
    assert isinstance(jpy, IIndicator)
    assert jpy.id == "JPY-REGIME"


def test_required_series():
    assert JPYRegimeIndicator().required_series() == ["DEXJPUS"]


def test_compute_neutral_regime():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    df = pd.DataFrame({"DEXJPUS": [110.0] * 400}, index=idx)
    res = JPYRegimeIndicator().compute(df)
    assert res.metadata["regime"] in ("NEUTRAL", "INSUFFICIENT_HISTORY")


def test_compute_usd_strong_jpy_weak_regime():
    idx = pd.date_range("2022-01-01", periods=400, freq="B")
    # First 252 days hover around 130; last 148 days surge to 160
    levels = np.concatenate(
        [
            130.0 + np.random.RandomState(0).normal(0, 0.5, 252),
            np.linspace(130.0, 160.0, 148),
        ]
    )
    df = pd.DataFrame({"DEXJPUS": levels}, index=idx)
    res = JPYRegimeIndicator().compute(df)
    assert res.metadata["latest_z_score"] >= 1.5
    assert res.metadata["regime"] == "USD_STRONG_JPY_WEAK"


def test_compute_usd_weak_jpy_strong_regime():
    idx = pd.date_range("2022-01-01", periods=400, freq="B")
    levels = np.concatenate(
        [
            160.0 + np.random.RandomState(1).normal(0, 0.5, 252),
            np.linspace(160.0, 125.0, 148),
        ]
    )
    df = pd.DataFrame({"DEXJPUS": levels}, index=idx)
    res = JPYRegimeIndicator().compute(df)
    assert res.metadata["latest_z_score"] <= -1.5
    assert res.metadata["regime"] == "USD_WEAK_JPY_STRONG"


def test_compute_raises_on_missing_column():
    df = pd.DataFrame({"WRONG": [1.0]})
    with pytest.raises(ValueError, match="DEXJPUS"):
        JPYRegimeIndicator().compute(df)


def test_compute_empty():
    df = pd.DataFrame({"DEXJPUS": []}, dtype=float)
    res = JPYRegimeIndicator().compute(df)
    assert res.values.empty


def test_lookback_default_is_252():
    assert LOOKBACK_DAYS_DEFAULT == 252


def test_subindex_columns_present():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    df = pd.DataFrame(
        {"DEXJPUS": 110.0 + np.linspace(0, 30, 300)}, index=idx
    )
    res = JPYRegimeIndicator().compute(df)
    cols = res.subindex_values.columns.tolist()
    assert "usd_jpy" in cols
    assert "z_score_252d" in cols
    assert "log_ret_3m" in cols


def test_metadata_includes_i18n():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    df = pd.DataFrame({"DEXJPUS": 110.0 + np.linspace(0, 20, 300)}, index=idx)
    res = JPYRegimeIndicator().compute(df)
    assert "interpretation_i18n" in res.metadata
    assert "ja" in res.metadata["interpretation_i18n"]
    assert "en" in res.metadata["interpretation_i18n"]
