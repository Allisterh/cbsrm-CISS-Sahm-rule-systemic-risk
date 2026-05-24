"""
Tests for cbsrm.macro.phase_classifier — deterministic Acemoglu-style
macro/market phase labeller.
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from cbsrm.macro.phase_classifier import (
    DEFAULT_CONFIG,
    PHASE_LABELS,
    RISK_POSTURES,
    RULE_VERSION,
    SUPPORTED_FEATURES,
    PhaseClassifierConfig,
    classify_phase,
)


# ─── Schema / constants ─────────────────────────────────────────────


def test_phase_labels_cover_required_set():
    required = {
        "expansion", "overheating", "slowdown", "contraction",
        "disinflationary_recovery", "stagflationary_stress",
        "financial_stress", "indeterminate",
    }
    assert required.issubset(set(PHASE_LABELS))


def test_supported_features_includes_all_documented():
    required = {
        "growth_z", "inflation_z", "unemployment_z", "rates_z",
        "credit_spread_z", "volatility_z", "liquidity_z", "systemic_risk_z",
    }
    assert required.issubset(set(SUPPORTED_FEATURES))


def test_single_row_output_schema():
    out = classify_phase({"growth_z": 1.0, "inflation_z": 0.0, "credit_spread_z": -0.7})
    required = {
        "phase", "score", "dominant_drivers", "risk_posture",
        "input_features_used", "rule_version", "spec",
    }
    assert required.issubset(out.keys())
    assert out["rule_version"] == RULE_VERSION
    assert out["phase"] in PHASE_LABELS
    assert out["risk_posture"] in RISK_POSTURES
    assert 0.0 <= out["score"] <= 1.0


# ─── Phase rules ───────────────────────────────────────────────────


def test_expansion_phase_triggered():
    out = classify_phase({
        "growth_z": 1.2, "inflation_z": 0.2, "credit_spread_z": -0.8,
    })
    assert out["phase"] == "expansion"
    assert out["risk_posture"] == "risk_on"
    assert "growth_z" in out["dominant_drivers"]


def test_overheating_phase_triggered():
    out = classify_phase({
        "growth_z": 1.5, "inflation_z": 1.5, "rates_z": 0.8,
    })
    assert out["phase"] == "overheating"
    assert out["risk_posture"] == "defensive"


def test_slowdown_phase_triggered():
    out = classify_phase({
        "growth_z": -0.7, "inflation_z": 0.0, "credit_spread_z": 0.2,
    })
    assert out["phase"] == "slowdown"
    assert out["risk_posture"] == "defensive"


def test_contraction_phase_triggered():
    out = classify_phase({
        "growth_z": -1.5, "unemployment_z": 1.3, "credit_spread_z": 0.9,
    })
    assert out["phase"] == "contraction"
    assert out["risk_posture"] == "risk_off"


def test_disinflationary_recovery_triggered():
    out = classify_phase({
        "growth_z": 0.4, "inflation_z": -0.8, "unemployment_z": -0.7,
    })
    assert out["phase"] == "disinflationary_recovery"
    assert out["risk_posture"] == "risk_on"


def test_stagflationary_stress_triggered():
    # Hot inflation + weak growth, no acute financial stress
    out = classify_phase({
        "growth_z": -0.8, "inflation_z": 1.3, "credit_spread_z": 0.3,
    })
    assert out["phase"] == "stagflationary_stress"
    assert out["risk_posture"] == "defensive"


def test_financial_stress_triggered_by_credit_spread():
    out = classify_phase({
        "growth_z": 0.5, "credit_spread_z": 2.0, "volatility_z": 0.5,
    })
    assert out["phase"] == "financial_stress"
    assert out["risk_posture"] == "stress_mitigation"


def test_financial_stress_triggered_by_volatility():
    out = classify_phase({
        "growth_z": 0.5, "credit_spread_z": 0.5, "volatility_z": 2.0,
    })
    assert out["phase"] == "financial_stress"


def test_financial_stress_triggered_by_systemic_risk():
    out = classify_phase({
        "growth_z": 0.5, "inflation_z": 0.0, "systemic_risk_z": 1.6,
    })
    assert out["phase"] == "financial_stress"


def test_financial_stress_overrides_overheating():
    """Even with a hot-growth/hot-inflation print, acute financial stress wins."""
    out = classify_phase({
        "growth_z": 1.5, "inflation_z": 1.5, "credit_spread_z": 2.0,
    })
    assert out["phase"] == "financial_stress"


def test_stagflation_overrides_overheating():
    """Hot inflation + weak growth must NOT be labelled overheating."""
    out = classify_phase({
        "growth_z": -0.7, "inflation_z": 1.2, "rates_z": 0.5,
    })
    assert out["phase"] == "stagflationary_stress"


def test_indeterminate_for_near_zero_features():
    out = classify_phase({
        "growth_z": 0.1, "inflation_z": 0.05, "credit_spread_z": -0.1,
    })
    assert out["phase"] == "indeterminate"
    assert out["risk_posture"] == "balanced"
    assert out["score"] == 0.0


def test_indeterminate_when_too_few_features():
    # Only 2 features supplied; min_features_for_classification = 3
    out = classify_phase({"growth_z": 1.5, "inflation_z": 1.5})
    assert out["phase"] == "indeterminate"
    assert "INSUFFICIENT_FEATURES" in out["spec"]["rules_fired"]


# ─── Validation ────────────────────────────────────────────────────


def test_nan_input_raises():
    with pytest.raises(ValueError, match="non-finite"):
        classify_phase({"growth_z": float("nan"), "inflation_z": 0.0,
                        "credit_spread_z": 0.0})


def test_inf_input_raises():
    with pytest.raises(ValueError, match="non-finite"):
        classify_phase({"growth_z": float("inf"), "inflation_z": 0.0,
                        "credit_spread_z": 0.0})


def test_unknown_feature_key_raises():
    with pytest.raises(ValueError, match="unsupported feature key"):
        classify_phase({"growth_z": 1.0, "inflaton_z": 1.0,
                        "credit_spread_z": -0.5})


def test_unsupported_input_type_raises():
    with pytest.raises(ValueError, match="must be a dict"):
        classify_phase([1.0, 0.0, -0.5])   # type: ignore[arg-type]


def test_non_numeric_value_raises():
    with pytest.raises(ValueError, match="must be a finite number"):
        classify_phase({"growth_z": "hot", "inflation_z": 0.0,
                        "credit_spread_z": 0.0})


# ─── DataFrame batch mode ──────────────────────────────────────────


def test_dataframe_batch_returns_dataframe():
    df = pd.DataFrame([
        {"growth_z": 1.2, "inflation_z": 0.2, "credit_spread_z": -0.8},
        {"growth_z": -1.5, "unemployment_z": 1.3, "credit_spread_z": 0.9},
        {"growth_z": 0.4, "inflation_z": -0.8, "unemployment_z": -0.7},
    ], index=["t1", "t2", "t3"])
    out = classify_phase(df)
    assert isinstance(out, pd.DataFrame)
    assert list(out.index) == ["t1", "t2", "t3"]
    assert set(out.columns) >= {
        "phase", "score", "dominant_drivers", "risk_posture", "n_features_used",
    }
    assert out.loc["t1", "phase"] == "expansion"
    assert out.loc["t2", "phase"] == "contraction"
    assert out.loc["t3", "phase"] == "disinflationary_recovery"


def test_dataframe_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        classify_phase(pd.DataFrame(columns=["growth_z", "inflation_z"]))


def test_dataframe_unknown_column_raises():
    df = pd.DataFrame([{"growth_z": 1.0, "rng_z": 0.5}])
    with pytest.raises(ValueError, match="unsupported column"):
        classify_phase(df)


def test_dataframe_with_nans_drops_per_row():
    df = pd.DataFrame([
        {"growth_z": 1.2, "inflation_z": 0.2, "credit_spread_z": -0.8,
         "volatility_z": float("nan")},
    ])
    out = classify_phase(df)
    # NaN is dropped per-row, surviving 3 features → not "indeterminate"
    assert out.iloc[0]["phase"] == "expansion"


# ─── Series input ──────────────────────────────────────────────────


def test_pandas_series_input_supported():
    s = pd.Series({"growth_z": 1.2, "inflation_z": 0.2,
                   "credit_spread_z": -0.8})
    out = classify_phase(s)
    assert isinstance(out, dict)
    assert out["phase"] == "expansion"


# ─── Synonyms ──────────────────────────────────────────────────────


def test_labor_slack_z_treated_as_unemployment():
    out_uz = classify_phase({
        "growth_z": -1.5, "unemployment_z": 1.3, "credit_spread_z": 0.9,
    })
    out_ls = classify_phase({
        "growth_z": -1.5, "labor_slack_z": 1.3, "credit_spread_z": 0.9,
    })
    assert out_uz["phase"] == out_ls["phase"] == "contraction"


# ─── Determinism ───────────────────────────────────────────────────


def test_determinism_repeated_calls_match():
    payload = {"growth_z": 0.7, "inflation_z": -0.8, "unemployment_z": -0.6}
    out_a = classify_phase(payload)
    out_b = classify_phase(payload)
    out_c = classify_phase(payload.copy())
    # Compare on the stable surface (lists/strings/floats), not the nested
    # `spec` which contains a config dict that's structurally identical.
    for key in ("phase", "score", "risk_posture", "dominant_drivers",
                "input_features_used", "rule_version"):
        assert out_a[key] == out_b[key] == out_c[key]


def test_dominant_drivers_sorted_by_magnitude():
    out = classify_phase({
        "growth_z": 0.6,            # |z| 0.6 → below threshold
        "inflation_z": -2.5,        # |z| 2.5
        "unemployment_z": -1.2,     # |z| 1.2
        "credit_spread_z": -0.4,    # below threshold
    })
    # threshold=1.0 by default → inflation_z first (|2.5|), then unemployment_z (|1.2|)
    drivers = out["dominant_drivers"]
    assert drivers[0] == "inflation_z"
    assert drivers[1] == "unemployment_z"
    assert "growth_z" not in drivers
    assert "credit_spread_z" not in drivers


# ─── Custom config ─────────────────────────────────────────────────


def test_custom_config_changes_threshold_behaviour():
    # Default: |z| >= 1.0 → driver. Lower threshold to 0.3 and re-check.
    cfg = PhaseClassifierConfig(driver_threshold=0.3)
    out = classify_phase(
        {"growth_z": 0.5, "inflation_z": -0.4, "unemployment_z": -0.35},
        config=cfg,
    )
    # All three features pass the lower threshold → all become drivers
    assert set(out["dominant_drivers"]) == {
        "growth_z", "inflation_z", "unemployment_z",
    }


def test_score_is_bounded():
    """Extreme inputs must not push score above 1.0."""
    out = classify_phase({
        "growth_z": 10.0, "inflation_z": 10.0, "credit_spread_z": -5.0,
    })
    # This is overheating territory
    assert out["phase"] == "overheating"
    assert 0.0 <= out["score"] <= 1.0


def test_default_config_singleton_immutable():
    """DEFAULT_CONFIG should be a frozen dataclass — assignment must raise."""
    with pytest.raises(Exception):
        DEFAULT_CONFIG.growth_hot = 99.0   # type: ignore[misc]
