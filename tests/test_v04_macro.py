"""Tests for the three v0.4 macro indicators (CPI, oil, credit spread)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cbsrm.indicators.base import IIndicator
from cbsrm.macro import (
    CPISurpriseIndicator,
    CreditSpreadRegimeIndicator,
    OilMacroIndicator,
)


# ─── CPI surprise ──────────────────────────────────────────────────


def test_cpi_implements_protocol():
    assert isinstance(CPISurpriseIndicator(), IIndicator)
    assert CPISurpriseIndicator().required_series() == ["CPIAUCSL"]


def test_cpi_inflation_overshoot_classification():
    # Stable 2% growth (mom), then 12 months of 0.7%/month (~9% YoY) → overshoot
    idx = pd.date_range("2010-01-01", periods=72, freq="MS")
    levels = np.zeros(72)
    levels[0] = 100.0
    for i in range(1, 72):
        g = 0.002 if i < 60 else 0.007  # last 12 months hot
        levels[i] = levels[i - 1] * (1.0 + g)
    df = pd.DataFrame({"CPIAUCSL": levels}, index=idx)
    res = CPISurpriseIndicator().compute(df)
    assert res.metadata["classification"] == "INFLATION_OVERSHOOT"


def test_cpi_disinflation_classification():
    idx = pd.date_range("2010-01-01", periods=72, freq="MS")
    levels = np.zeros(72)
    levels[0] = 100.0
    for i in range(1, 72):
        g = 0.005 if i < 60 else -0.001  # last 12 months mild deflation
        levels[i] = levels[i - 1] * (1.0 + g)
    df = pd.DataFrame({"CPIAUCSL": levels}, index=idx)
    res = CPISurpriseIndicator().compute(df)
    assert res.metadata["classification"] == "DISINFLATION"


def test_cpi_classification_set():
    # The classifier should only ever emit values from this fixed set.
    rng = np.random.RandomState(42)
    idx = pd.date_range("2010-01-01", periods=72, freq="MS")
    growth_rates = 0.0025 + rng.normal(0, 0.0005, 72)
    levels = np.empty(72)
    levels[0] = 100.0
    for i in range(1, 72):
        levels[i] = levels[i - 1] * (1.0 + growth_rates[i])
    df = pd.DataFrame({"CPIAUCSL": levels}, index=idx)
    res = CPISurpriseIndicator().compute(df)
    assert res.metadata["classification"] in (
        "INFLATION_OVERSHOOT", "DISINFLATION", "AT_TREND", "INSUFFICIENT_HISTORY",
    )


def test_cpi_rejects_missing_column():
    with pytest.raises(ValueError, match="CPIAUCSL"):
        CPISurpriseIndicator().compute(pd.DataFrame({"WRONG": [1.0]}))


# ─── Oil macro ──────────────────────────────────────────────────────


def test_oil_implements_protocol():
    assert isinstance(OilMacroIndicator(), IIndicator)
    assert OilMacroIndicator().required_series() == ["DCOILWTICO"]


def test_oil_spike_classification():
    # 252 days flat at 60, then ramp to 100 → YoY log ≈ +0.51
    idx = pd.date_range("2020-01-01", periods=520, freq="B")
    levels = np.concatenate([
        np.full(252, 60.0),
        np.linspace(60.0, 100.0, 268),
    ])
    df = pd.DataFrame({"DCOILWTICO": levels}, index=idx)
    res = OilMacroIndicator().compute(df)
    assert res.metadata["regime"] == "OIL_SPIKE"


def test_oil_crash_classification():
    idx = pd.date_range("2020-01-01", periods=520, freq="B")
    levels = np.concatenate([
        np.full(252, 100.0),
        np.linspace(100.0, 50.0, 268),
    ])
    df = pd.DataFrame({"DCOILWTICO": levels}, index=idx)
    res = OilMacroIndicator().compute(df)
    assert res.metadata["regime"] == "OIL_CRASH"


def test_oil_rangebound_classification():
    idx = pd.date_range("2020-01-01", periods=520, freq="B")
    # Sinusoidal around 75, ±3
    levels = 75.0 + 3.0 * np.sin(np.linspace(0, 8 * np.pi, 520))
    df = pd.DataFrame({"DCOILWTICO": levels}, index=idx)
    res = OilMacroIndicator().compute(df)
    assert res.metadata["regime"] == "OIL_RANGEBOUND"


def test_oil_rejects_missing_column():
    with pytest.raises(ValueError, match="DCOILWTICO"):
        OilMacroIndicator().compute(pd.DataFrame({"WRONG": [1.0]}))


# ─── Credit spread regime ──────────────────────────────────────────


def test_credit_implements_protocol():
    assert isinstance(CreditSpreadRegimeIndicator(), IIndicator)
    assert CreditSpreadRegimeIndicator().required_series() == ["BAMLH0A0HYM2"]


def test_credit_acute_classification():
    # 1000+ bps level → ACUTE
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    # FRED publishes in percent — 12.0% = 1200 bps
    df = pd.DataFrame({"BAMLH0A0HYM2": [4.0] * 200 + [12.0] * 100}, index=idx)
    res = CreditSpreadRegimeIndicator().compute(df)
    assert res.metadata["regime"] == "CREDIT_STRESS_ACUTE"


def test_credit_acute_by_rapid_change():
    # Level moves from 400 bps to 650 bps within the last 21 days.
    # 21-day change at the last observation = (6.5 - 4.0) * 100 = 250 bps,
    # which exceeds the 200 bps acute-change threshold.
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    vals = [4.0] * 285 + [6.5] * 15
    df = pd.DataFrame({"BAMLH0A0HYM2": vals}, index=idx)
    res = CreditSpreadRegimeIndicator().compute(df)
    assert res.metadata["regime"] == "CREDIT_STRESS_ACUTE"


def test_credit_benign_classification():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    df = pd.DataFrame({"BAMLH0A0HYM2": [3.0] * 300}, index=idx)
    res = CreditSpreadRegimeIndicator().compute(df)
    assert res.metadata["regime"] == "CREDIT_BENIGN"


def test_credit_normal_classification():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    df = pd.DataFrame({"BAMLH0A0HYM2": [5.0] * 300}, index=idx)
    res = CreditSpreadRegimeIndicator().compute(df)
    assert res.metadata["regime"] == "CREDIT_NORMAL"


def test_credit_rejects_missing_column():
    with pytest.raises(ValueError, match="BAMLH0A0HYM2"):
        CreditSpreadRegimeIndicator().compute(pd.DataFrame({"WRONG": [1.0]}))


def test_credit_value_in_bps_not_percent():
    # FRED's 5% should appear as 500 bps internally
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    df = pd.DataFrame({"BAMLH0A0HYM2": [5.0] * 10}, index=idx)
    res = CreditSpreadRegimeIndicator().compute(df)
    assert res.metadata["latest_hy_oas_bps"] == pytest.approx(500.0)
