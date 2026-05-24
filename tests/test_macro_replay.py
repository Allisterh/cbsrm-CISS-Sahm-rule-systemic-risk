"""
Tests for cbsrm.diagnostics.macro_replay.replay_macro_events
============================================================

Covers:
  - returned schema (column names + order, row count)
  - hotter direction propagation from the scorer
  - hand-built pre/post log-return computation on a clean ramp
  - missing-required-column ValueError
  - empty-input ValueError (both events and prices)
  - non-positive window ValueError
  - fixture round-trip end-to-end (events.csv + prices.csv)
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cbsrm.diagnostics.macro_replay import replay_macro_events


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "notebooks" / "crisis_replay" / "fixtures"


# ─── Helpers ─────────────────────────────────────────────────────────


def _simple_events() -> pd.DataFrame:
    return pd.DataFrame([
        {"event": "CPI", "date": "2024-05-15", "actual": 3.4,
         "consensus": 3.2, "previous": 3.5},
        {"event": "NFP", "date": "2024-08-02", "actual": 114.0,
         "consensus": 175.0, "previous": 179.0},
    ])


def _simple_prices() -> pd.DataFrame:
    """Linear ramp price panel covering all event dates ± 10 days."""
    idx = pd.date_range("2024-05-01", "2024-08-15", freq="D")
    spy = 400.0 + np.arange(len(idx))  # +$1 per calendar day
    tlt = 100.0 - 0.5 * np.arange(len(idx))  # -$0.50 per calendar day
    return pd.DataFrame({"SPY": spy, "TLT": tlt}, index=idx)


# ─── Schema ───────────────────────────────────────────────────────────


def test_returned_schema_columns_and_rowcount():
    events = _simple_events()
    prices = _simple_prices()
    out = replay_macro_events(events, prices,
                              pre_window_days=5, post_window_days=5)

    expected_cols = [
        "event", "date", "actual", "consensus",
        "surprise", "surprise_z", "direction", "severity", "risk_bias",
        "price_series", "pre_return", "post_return",
    ]
    assert list(out.columns) == expected_cols
    # 2 events × 2 series = 4 rows
    assert len(out) == 4
    # event names canonicalised by scorer
    assert set(out["event"].unique()) == {"CPI", "NFP"}
    assert set(out["price_series"].unique()) == {"SPY", "TLT"}


# ─── Direction propagation ───────────────────────────────────────────


def test_hotter_direction_propagated_from_scorer():
    """CPI actual > consensus by 2 default-scale σ should be 'hotter'."""
    events = pd.DataFrame([
        {"event": "CPI", "date": "2024-05-15",
         "actual": 3.6, "consensus": 3.0},   # +0.6 vs default scale 0.15 → z=4
    ])
    prices = _simple_prices()
    out = replay_macro_events(events, prices,
                              pre_window_days=5, post_window_days=5)
    # All rows for this event share the same direction
    assert (out["direction"] == "hotter_than_expected").all()
    # severity should be 'extreme' for |z|>>2.5
    assert (out["severity"] == "extreme").all()
    # risk_bias on a hot CPI = rates up / equities down per the registry
    assert (out["risk_bias"] == "rates_up_equities_down").all()


# ─── Hand-built return math ──────────────────────────────────────────


def test_pre_post_return_match_hand_calculation():
    """On a deterministic linear ramp, log returns are pin-down.

    Event date = 2024-06-15, pre/post window = 5 calendar days.
    SPY at 2024-06-10 = 400 + 40 = 440
    SPY at 2024-06-15 = 400 + 45 = 445
    SPY at 2024-06-20 = 400 + 50 = 450
    pre_return  = ln(445 / 440)
    post_return = ln(450 / 445)
    """
    events = pd.DataFrame([
        {"event": "CPI", "date": "2024-06-15", "actual": 3.2, "consensus": 3.2},
    ])
    prices = _simple_prices()
    out = replay_macro_events(events, prices,
                              pre_window_days=5, post_window_days=5)

    spy_row = out[out["price_series"] == "SPY"].iloc[0]
    expected_pre = math.log(445.0 / 440.0)
    expected_post = math.log(450.0 / 445.0)
    assert spy_row["pre_return"] == pytest.approx(expected_pre, rel=1e-9)
    assert spy_row["post_return"] == pytest.approx(expected_post, rel=1e-9)

    tlt_row = out[out["price_series"] == "TLT"].iloc[0]
    # TLT: 100 - 0.5*45 = 77.5 at 2024-06-15,
    #      100 - 0.5*40 = 80.0 at 2024-06-10,
    #      100 - 0.5*50 = 75.0 at 2024-06-20
    assert tlt_row["pre_return"] == pytest.approx(math.log(77.5 / 80.0), rel=1e-9)
    assert tlt_row["post_return"] == pytest.approx(math.log(75.0 / 77.5), rel=1e-9)


# ─── Error paths ─────────────────────────────────────────────────────


def test_missing_required_column_raises():
    bad_events = pd.DataFrame([
        {"event": "CPI", "date": "2024-05-15", "actual": 3.4},  # no consensus
    ])
    prices = _simple_prices()
    with pytest.raises(ValueError, match="missing required column"):
        replay_macro_events(bad_events, prices)


def test_empty_events_raises():
    empty_events = pd.DataFrame(columns=["event", "date", "actual", "consensus"])
    prices = _simple_prices()
    with pytest.raises(ValueError, match="empty"):
        replay_macro_events(empty_events, prices)


def test_empty_prices_raises():
    events = _simple_events()
    empty_prices = pd.DataFrame()
    with pytest.raises(ValueError, match="empty"):
        replay_macro_events(events, empty_prices)


def test_non_positive_window_raises():
    events = _simple_events()
    prices = _simple_prices()
    with pytest.raises(ValueError, match="pre_window_days"):
        replay_macro_events(events, prices, pre_window_days=0)
    with pytest.raises(ValueError, match="post_window_days"):
        replay_macro_events(events, prices, post_window_days=-1)


def test_non_dataframe_inputs_raise():
    prices = _simple_prices()
    with pytest.raises(ValueError, match="events_df must be a pandas DataFrame"):
        replay_macro_events({"event": ["CPI"]}, prices)  # type: ignore[arg-type]
    events = _simple_events()
    with pytest.raises(ValueError, match="prices_df must be a pandas DataFrame"):
        replay_macro_events(events, [1, 2, 3])  # type: ignore[arg-type]


# ─── Fixture round-trip ──────────────────────────────────────────────


def test_fixture_round_trip_runs_clean():
    """End-to-end: load shipped fixtures, run replay, sanity-check shape."""
    events = pd.read_csv(FIXTURES / "events.csv")
    prices = pd.read_csv(FIXTURES / "prices.csv",
                         index_col="date", parse_dates=True)
    out = replay_macro_events(events, prices,
                              pre_window_days=5, post_window_days=5)

    # 8 events × 2 series
    assert len(out) == 8 * 2
    # All returns finite (fixture covers all dates ±15d)
    assert out["pre_return"].notna().all()
    assert out["post_return"].notna().all()
    # All directions are valid scorer outputs
    assert set(out["direction"].unique()).issubset(
        {"hotter_than_expected", "cooler_than_expected", "in_line"}
    )


def test_unknown_event_in_fixture_surfaces_value_error():
    bad = pd.DataFrame([
        {"event": "MADE_UP_PRINT", "date": "2024-05-15",
         "actual": 1.0, "consensus": 1.0},
    ])
    prices = _simple_prices()
    with pytest.raises(ValueError, match="unknown event"):
        replay_macro_events(bad, prices)
