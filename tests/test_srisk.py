"""Tests for cbsrm.risk.srisk + cbsrm.risk.garch_dcc_sim."""
from __future__ import annotations

import math

import numpy as np
import pytest

from cbsrm.risk import (
    GARCHDCCParams,
    GARCHDCCSimulator,
    LRMESMonteCarlo,
    SRISKCalculator,
    SRISKResult,
    srisk_panel,
)


# ─── GARCHDCCParams validation ─────────────────────────────────────


def test_default_params_pass_stationarity():
    p = GARCHDCCParams()  # no exception
    assert 0.0 < p.beta_firm < 1.0


def test_params_reject_nonstationary_firm():
    with pytest.raises(ValueError, match="non-stationary"):
        GARCHDCCParams(alpha_firm=0.5, beta_firm=0.6)  # 0.5 + 0.6 >= 1.0


def test_params_reject_dcc_out_of_unit():
    with pytest.raises(ValueError, match="DCC"):
        GARCHDCCParams(dcc_a=0.6, dcc_b=0.5)  # a + b > 1


def test_params_reject_rho_outside_unit():
    with pytest.raises(ValueError, match="rho_bar"):
        GARCHDCCParams(rho_bar=1.5)


# ─── Simulator basic properties ────────────────────────────────────


def test_simulate_shape():
    sim = GARCHDCCSimulator(horizon=30, n_paths=200, seed=42)
    out = sim.simulate()
    assert out.shape == (200, 2)


def test_simulate_seed_deterministic():
    s1 = GARCHDCCSimulator(horizon=30, n_paths=100, seed=7).simulate()
    s2 = GARCHDCCSimulator(horizon=30, n_paths=100, seed=7).simulate()
    np.testing.assert_array_equal(s1, s2)


def test_simulate_different_seeds_differ():
    s1 = GARCHDCCSimulator(horizon=30, n_paths=100, seed=1).simulate()
    s2 = GARCHDCCSimulator(horizon=30, n_paths=100, seed=2).simulate()
    assert not np.allclose(s1, s2)


def test_simulate_correlation_close_to_rho_bar():
    # With a large n_paths and modest horizon, realised correlation should
    # land near rho_bar (mean of the DCC process).
    p = GARCHDCCParams(rho_bar=0.7, rho0=0.7)
    sim = GARCHDCCSimulator(params=p, horizon=60, n_paths=20_000, seed=1)
    out = sim.simulate()
    realised = np.corrcoef(out[:, 0], out[:, 1])[0, 1]
    # Loose tolerance since the realised correlation of cumulative returns
    # can drift from instantaneous rho due to vol clustering.
    assert 0.5 < realised < 0.85


def test_simulate_diagnostics_keys():
    sim = GARCHDCCSimulator(horizon=10, n_paths=200, seed=1)
    d = sim.simulate_with_diagnostics()
    for k in ("n_paths", "horizon", "params", "firm_cum_mean", "firm_cum_std",
              "market_cum_mean", "market_cum_std", "realised_correlation"):
        assert k in d


# ─── LRMES Monte Carlo ─────────────────────────────────────────────


def test_lrmes_returns_zero_when_no_crisis_paths():
    # Tiny horizon + low vol → market won't hit -40%
    p = GARCHDCCParams(
        omega_firm=1e-8, alpha_firm=0.01, gamma_firm=0.01, beta_firm=0.5,
        omega_market=1e-8, alpha_market=0.01, gamma_market=0.01, beta_market=0.5,
        sigma0_firm=0.001, sigma0_market=0.001,
    )
    mc = LRMESMonteCarlo(params=p, horizon_days=5, n_paths=500,
                         crisis_threshold=-0.40, seed=42)
    res = mc.compute()
    assert res["lrmes"] == 0.0
    assert res["n_crisis_paths"] == 0
    assert "warning" in res


def test_lrmes_nonzero_in_high_vol_regime():
    # Higher vol → market frequently breaches -40% over 126 days
    p = GARCHDCCParams(
        omega_firm=5e-5, alpha_firm=0.05, gamma_firm=0.10, beta_firm=0.85,
        omega_market=4e-5, alpha_market=0.05, gamma_market=0.10, beta_market=0.85,
        sigma0_firm=0.035, sigma0_market=0.025, rho_bar=0.6, rho0=0.6,
    )
    mc = LRMESMonteCarlo(params=p, horizon_days=126, n_paths=5_000,
                         crisis_threshold=-0.40, seed=42)
    res = mc.compute()
    assert res["n_crisis_paths"] > 0
    assert res["lrmes"] > 0.0       # firm loses some equity in crisis paths


def test_lrmes_monotone_in_correlation():
    # Higher rho_bar → firm more exposed in market crashes → larger LRMES
    common = dict(
        omega_firm=4e-5, alpha_firm=0.05, gamma_firm=0.10, beta_firm=0.85,
        omega_market=4e-5, alpha_market=0.05, gamma_market=0.10, beta_market=0.85,
        sigma0_firm=0.030, sigma0_market=0.025,
    )
    p_low = GARCHDCCParams(rho_bar=0.10, rho0=0.10, **common)
    p_high = GARCHDCCParams(rho_bar=0.85, rho0=0.85, **common)
    lo = LRMESMonteCarlo(params=p_low, horizon_days=126, n_paths=5_000,
                         crisis_threshold=-0.30, seed=42).compute()
    hi = LRMESMonteCarlo(params=p_high, horizon_days=126, n_paths=5_000,
                         crisis_threshold=-0.30, seed=42).compute()
    assert hi["lrmes"] > lo["lrmes"]


# ─── SRISK calculator ─────────────────────────────────────────────


def test_srisk_calculator_default_k_is_eight_percent():
    c = SRISKCalculator()
    assert c.k == 0.08


def test_srisk_rejects_invalid_k():
    with pytest.raises(ValueError, match="k must be"):
        SRISKCalculator(k=-0.1)
    with pytest.raises(ValueError, match="k must be"):
        SRISKCalculator(k=1.5)


def test_srisk_rejects_negative_inputs():
    c = SRISKCalculator()
    with pytest.raises(ValueError):
        c.compute(firm="x", market_cap_W=-1, book_debt_D=100, lrmes=0.5)
    with pytest.raises(ValueError):
        c.compute(firm="x", market_cap_W=100, book_debt_D=-1, lrmes=0.5)


def test_srisk_identity_no_crisis():
    # If LRMES = 0, SRISK = k*D - (1-k)*W. With D=W and k=0.08:
    # SRISK = 0.08*W - 0.92*W = -0.84*W < 0 → surplus
    c = SRISKCalculator(k=0.08)
    r = c.compute(firm="bigbank", market_cap_W=100, book_debt_D=100, lrmes=0.0)
    assert r.srisk == pytest.approx(-0.84 * 100, abs=1e-9)
    assert r.is_shortfall is False


def test_srisk_identity_full_wipeout():
    # If LRMES = 1, firm equity goes to zero. SRISK = k*D - 0 = k*D
    c = SRISKCalculator(k=0.08)
    r = c.compute(firm="bigbank", market_cap_W=100, book_debt_D=1000, lrmes=1.0)
    assert r.srisk == pytest.approx(0.08 * 1000)
    assert r.is_shortfall is True


def test_srisk_monotone_in_lrmes():
    c = SRISKCalculator(k=0.08)
    rs = [c.compute(firm="bb", market_cap_W=100, book_debt_D=500, lrmes=L)
          for L in (0.1, 0.3, 0.5, 0.7, 0.9)]
    srisks = [r.srisk for r in rs]
    for i in range(len(srisks) - 1):
        assert srisks[i] < srisks[i + 1]


def test_srisk_monotone_in_debt():
    c = SRISKCalculator(k=0.08)
    r_low = c.compute(firm="x", market_cap_W=100, book_debt_D=100, lrmes=0.5)
    r_high = c.compute(firm="x", market_cap_W=100, book_debt_D=1000, lrmes=0.5)
    assert r_high.srisk > r_low.srisk


def test_srisk_metadata_preserved():
    c = SRISKCalculator(k=0.08)
    r = c.compute(firm="x", market_cap_W=100, book_debt_D=100, lrmes=0.5,
                  metadata={"source": "test", "as_of": "2026-05-20"})
    assert r.metadata["source"] == "test"
    assert r.metadata["as_of"] == "2026-05-20"


# ─── Panel aggregator ─────────────────────────────────────────────


def test_panel_aggregates_and_sorts():
    inputs = [
        {"firm": "small", "market_cap_W": 50, "book_debt_D": 50, "lrmes": 0.2},
        {"firm": "big", "market_cap_W": 500, "book_debt_D": 5000, "lrmes": 0.4},
        {"firm": "mid", "market_cap_W": 200, "book_debt_D": 1500, "lrmes": 0.3},
    ]
    out = srisk_panel(inputs, k=0.08)
    assert out["n_firms"] == 3
    # Sorted by SRISK desc — big bank should be top
    assert out["per_firm"][0]["firm"] == "big"
    # Total srisk: only positive
    assert out["total_srisk"] >= 0
    # Net srisk: positives - surpluses
    assert out["total_srisk_net"] == sum(r["srisk"] for r in out["per_firm"])


def test_panel_total_only_positive():
    # All firms in surplus → total_srisk = 0
    inputs = [
        {"firm": f"f{i}", "market_cap_W": 100, "book_debt_D": 50, "lrmes": 0.0}
        for i in range(3)
    ]
    out = srisk_panel(inputs, k=0.08)
    assert out["total_srisk"] == 0
    assert out["total_srisk_net"] < 0
    assert out["n_shortfall"] == 0
    assert out["n_surplus"] == 3


def test_panel_k_override():
    inputs = [{"firm": "x", "market_cap_W": 100, "book_debt_D": 500, "lrmes": 0.5}]
    out_low = srisk_panel(inputs, k=0.045)
    out_high = srisk_panel(inputs, k=0.10)
    # Higher k → higher required capital → higher SRISK
    assert out_high["per_firm"][0]["srisk"] > out_low["per_firm"][0]["srisk"]
