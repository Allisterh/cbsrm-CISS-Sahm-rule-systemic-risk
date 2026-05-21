"""
Bivariate GJR-GARCH(1,1) + DCC simulator for SRISK / LRMES Monte Carlo.

Methodology (matches Brownlees-Engle 2017 §3 and Engle 2002)
-----------------------------------------------------------

Firm return ``r_{i,t}`` and market return ``r_{m,t}`` are modelled as::

    r_{i,t} = sigma_{i,t} * eps_{i,t}
    r_{m,t} = sigma_{m,t} * eps_{m,t}

where ``(eps_{i,t}, eps_{m,t})`` are jointly standard-normal with time-varying
conditional correlation ``rho_t`` and each conditional variance follows a
GJR-GARCH(1,1) process::

    sigma_{j,t}^2 = omega_j + alpha_j * r_{j,t-1}^2
                  + gamma_j * r_{j,t-1}^2 * I(r_{j,t-1} < 0)
                  + beta_j * sigma_{j,t-1}^2

The correlation ``rho_t`` follows the scalar DCC(1,1) recursion::

    Q_t  =  (1 - a - b) * Q_bar  +  a * (z_{t-1} z_{t-1}^T)  +  b * Q_{t-1}
    R_t  =  diag(Q_t)^{-1/2}  Q_t  diag(Q_t)^{-1/2}

where ``z_t`` is the vector of standardised residuals and ``Q_bar`` is the
unconditional covariance of the standardised series. ``rho_t`` is the off-
diagonal of ``R_t``.

Why this matters for SRISK
~~~~~~~~~~~~~~~~~~~~~~~~~~

The 6-month / -40% market shock that defines LRMES is a *conditional*
expectation. Plugging Gaussian iid returns into a -40% threshold gives
trivially small or zero LRMES on firms with low unconditional beta. With
GJR-GARCH-DCC dynamics, two effects appear:

1. Volatility clustering: a market drawdown raises ``sigma_m`` (and via
   asymmetric ``gamma_m``, more so for negative shocks), making continued
   declines materially more probable.
2. Time-varying correlation: in crises, ``rho_t`` rises (Engle 2002 Fig 4).
   Conditional on the market hitting -40%, the firm's expected loss given
   beta is amplified by the elevated ``rho_t``.

Both are essential for LRMES to track the empirically observed pattern.

Parameter defaults
~~~~~~~~~~~~~~~~~~

Brownlees-Engle 2017 used market-cap-weighted estimates of these parameters
from ~70 large US financials over 2000–2014. We expose them as ``GARCHDCCParams``
defaults but **all calibration is the caller's responsibility** — the
defaults are reasonable for "a US-listed financial vs S&P 500" but operators
running on non-US firms or non-financial sectors should fit their own.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


# ─── Parameter set ──────────────────────────────────────────────────


@dataclass
class GARCHDCCParams:
    """Parameters for the bivariate GJR-GARCH(1,1) + DCC simulator.

    Single-asset GARCH parameters apply to BOTH the firm and the market
    individually (so we keep two copies, one per asset).

    Reasonable defaults: typical estimates for large US financials vs S&P 500.
    """
    # Firm-side GJR-GARCH(1,1)
    omega_firm: float = 1e-5
    alpha_firm: float = 0.03
    gamma_firm: float = 0.08      # asymmetry coefficient (negative-shock kicker)
    beta_firm: float = 0.88

    # Market-side GJR-GARCH(1,1)
    omega_market: float = 5e-6
    alpha_market: float = 0.02
    gamma_market: float = 0.10
    beta_market: float = 0.88

    # DCC(1,1) parameters on the correlation process
    dcc_a: float = 0.03
    dcc_b: float = 0.95

    # Unconditional correlation (Q_bar's off-diagonal)
    rho_bar: float = 0.55

    # Initial conditional variances (chosen near unconditional level)
    sigma0_firm: float = 0.020    # ~ 2% daily vol
    sigma0_market: float = 0.012  # ~ 1.2% daily vol

    # Initial conditional correlation
    rho0: float = 0.55

    def __post_init__(self) -> None:
        for j, (a, g, b) in enumerate([
            (self.alpha_firm, self.gamma_firm, self.beta_firm),
            (self.alpha_market, self.gamma_market, self.beta_market),
        ]):
            persistence = a + 0.5 * g + b
            if persistence >= 1.0:
                label = "firm" if j == 0 else "market"
                raise ValueError(
                    f"GJR-GARCH non-stationary on {label}: "
                    f"alpha + 0.5*gamma + beta = {persistence:.3f} >= 1.0"
                )
        if not (0.0 <= self.dcc_a + self.dcc_b < 1.0):
            raise ValueError(
                f"DCC parameters require dcc_a + dcc_b in [0, 1); "
                f"got {self.dcc_a + self.dcc_b:.3f}"
            )
        if not (-1.0 < self.rho_bar < 1.0):
            raise ValueError(f"rho_bar must be in (-1, 1); got {self.rho_bar}")


# ─── Simulator ──────────────────────────────────────────────────────


@dataclass
class GARCHDCCSimulator:
    """Bivariate GJR-GARCH + DCC path simulator.

    Pure-numpy, no SciPy / arch dependency. The simulator generates
    ``n_paths`` independent sample paths each of length ``horizon`` and
    returns the cumulative log-returns for firm and market at horizon end.

    Usage::

        params = GARCHDCCParams(rho_bar=0.6)
        sim = GARCHDCCSimulator(params=params, horizon=126, n_paths=10_000, seed=42)
        cum = sim.simulate()
        # cum is an (n_paths, 2) array of cumulative log-returns at H:
        #   column 0 = firm, column 1 = market
    """
    params: GARCHDCCParams = field(default_factory=GARCHDCCParams)
    horizon: int = 126           # 6 months ≈ 126 trading days
    n_paths: int = 10_000
    seed: int | None = None

    def simulate(self) -> np.ndarray:
        """Return an (n_paths, 2) array of cumulative log-returns at horizon."""
        rng = np.random.default_rng(self.seed)
        p = self.params
        H = self.horizon
        N = self.n_paths

        # State arrays: shape (N,) for each variable
        sigma2_f = np.full(N, p.sigma0_firm ** 2)
        sigma2_m = np.full(N, p.sigma0_market ** 2)
        rho = np.full(N, p.rho0)
        # DCC's Q matrix lives in (1,1)/(2,2)=1 form for standardised residuals;
        # for the scalar DCC recursion we track the off-diagonal q_t separately.
        # See Engle (2002) eq. (28).
        q12 = np.full(N, p.rho0)
        q11 = np.ones(N)
        q22 = np.ones(N)

        cum_f = np.zeros(N)
        cum_m = np.zeros(N)

        # Pre-draw all bivariate standard-normal shocks. We need z = (z1, z2)
        # with target correlation rho_t; easiest is to draw uncorrelated u and
        # transform per step.
        u = rng.standard_normal(size=(H, N, 2))

        for t in range(H):
            # Sample (eps_f, eps_m) ~ N(0, [[1, rho_t], [rho_t, 1]])
            u1 = u[t, :, 0]
            u2 = u[t, :, 1]
            eps_f = u1
            eps_m = rho * u1 + np.sqrt(np.clip(1.0 - rho ** 2, 0.0, 1.0)) * u2

            sigma_f = np.sqrt(sigma2_f)
            sigma_m = np.sqrt(sigma2_m)
            r_f = sigma_f * eps_f
            r_m = sigma_m * eps_m
            cum_f += r_f
            cum_m += r_m

            # GJR-GARCH(1,1) volatility updates
            neg_f = (r_f < 0).astype(float)
            neg_m = (r_m < 0).astype(float)
            r_f2 = r_f * r_f
            r_m2 = r_m * r_m
            sigma2_f = (
                p.omega_firm
                + p.alpha_firm * r_f2
                + p.gamma_firm * r_f2 * neg_f
                + p.beta_firm * sigma2_f
            )
            sigma2_m = (
                p.omega_market
                + p.alpha_market * r_m2
                + p.gamma_market * r_m2 * neg_m
                + p.beta_market * sigma2_m
            )

            # DCC(1,1) scalar recursion on the off-diagonal of Q
            #   q_{t} = (1 - a - b) * q_bar + a * eps_f * eps_m + b * q_{t-1}
            q12 = (
                (1.0 - p.dcc_a - p.dcc_b) * p.rho_bar
                + p.dcc_a * (eps_f * eps_m)
                + p.dcc_b * q12
            )
            q11 = (
                (1.0 - p.dcc_a - p.dcc_b) * 1.0
                + p.dcc_a * (eps_f * eps_f)
                + p.dcc_b * q11
            )
            q22 = (
                (1.0 - p.dcc_a - p.dcc_b) * 1.0
                + p.dcc_a * (eps_m * eps_m)
                + p.dcc_b * q22
            )
            denom = np.sqrt(np.maximum(q11 * q22, 1e-12))
            rho = np.clip(q12 / denom, -0.999, 0.999)

        out = np.stack([cum_f, cum_m], axis=1)
        return out

    def simulate_with_diagnostics(self) -> dict[str, Any]:
        """Simulate and also return summary diagnostics for the caller."""
        cum = self.simulate()
        out = {
            "n_paths": self.n_paths,
            "horizon": self.horizon,
            "params": self.params.__dict__,
            "firm_cum_mean": float(cum[:, 0].mean()),
            "firm_cum_std": float(cum[:, 0].std(ddof=0)),
            "market_cum_mean": float(cum[:, 1].mean()),
            "market_cum_std": float(cum[:, 1].std(ddof=0)),
            "realised_correlation": float(
                np.corrcoef(cum[:, 0], cum[:, 1])[0, 1]
            ),
        }
        return out
