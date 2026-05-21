"""
SRISK — Conditional capital-shortfall measure of systemic risk.

Reference
---------

Brownlees, C., & Engle, R. F. (2017). SRISK: A conditional capital shortfall
measure of systemic risk. *Review of Financial Studies*, 30(1), 48-79.
NYU Stern V-Lab: https://vlab.stern.nyu.edu/

Definition (from §2.1 of Brownlees-Engle)
-----------------------------------------

For firm *i*, SRISK is the expected capital shortfall conditional on a
systemic event::

    SRISK_i = E[ Capital_Shortfall_i  |  Crisis ]

The capital shortfall is the gap between the firm's required prudential
capital (`k` × book assets) and its actual capital (book equity, taken as
post-crisis market cap)::

    Shortfall_i = k * (D_i + W_i_post)  -  W_i_post

After substituting the dollar shortfall expression and using ``W_i_post =
W_i * (1 + cum_return_i)``::

    SRISK_i  =  k * D_i  -  (1 - k) * W_i * (1 - LRMES_i)

where:
    k         = prudential capital ratio (default 8% for US bank holding companies)
    D_i       = book debt (book liabilities) of firm i
    W_i       = current market capitalisation of firm i
    LRMES_i   = Long-Run Marginal Expected Shortfall, in [0, 1].
                The expected fraction *lost* in firm i's equity over the
                horizon, conditional on the market hitting the crisis
                threshold during that horizon.

LRMES (Brownlees-Engle 2017 §3.2): The expected *loss* in firm i's equity
conditional on the market cumulative-return falling below ``crisis_threshold``
(default -0.40) over the simulation horizon (default 126 trading days,
≈ 6 months). LRMES is computed via Monte Carlo from a bivariate GJR-GARCH-
DCC model (see ``cbsrm.risk.garch_dcc_sim``).

Interpretation
~~~~~~~~~~~~~~

* ``SRISK_i > 0``: firm would need an equity injection of $X to remain
  solvent in the simulated crisis.
* ``SRISK_i ≤ 0``: firm is over-capitalised relative to the crisis-conditional
  capital requirement — capital surplus, not shortfall.

Aggregated SRISK at the system level (``Σ SRISK_i⁺``) is the canonical
systemic-risk headline number — V-Lab publishes this for global SIFIs.

Validation
~~~~~~~~~~

Tests in ``tests/test_srisk.py`` validate:

* SRISK identity under known LRMES (no Monte Carlo).
* LRMES is monotone in correlation, vol, and horizon.
* Aggregation across multiple firms.
* k = 0 → SRISK = -W_i * (1 - LRMES_i) (negative for any LRMES).
* High-vol scenarios produce higher LRMES.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from cbsrm.risk.garch_dcc_sim import GARCHDCCParams, GARCHDCCSimulator


# Default Brownlees-Engle parameters
DEFAULT_K_BANK = 0.08        # 8% prudential ratio (US bank holding companies)
DEFAULT_K_INSURER = 0.045    # 4.5% prudential ratio (insurers, lighter cushion)
DEFAULT_CRISIS_THRESHOLD = -0.40
DEFAULT_HORIZON_DAYS = 126
DEFAULT_N_PATHS = 10_000


# ─── LRMES Monte Carlo ──────────────────────────────────────────────


@dataclass
class LRMESMonteCarlo:
    """Long-Run Marginal Expected Shortfall via GJR-GARCH-DCC Monte Carlo.

    LRMES is the expected fraction lost in the firm's equity conditional on
    the market hitting the crisis threshold over the simulation horizon.

    Computed as::

        LRMES = -E[ exp(cum_firm_log_return) - 1  |  cum_market_log_return < threshold ]

    The negation converts a return to a loss in [-1, ∞); LRMES ∈ [0, 1]
    intuitively means "fraction of equity lost". Values above 1 are possible
    in extreme synthetic cases (firm wiped out + leveraged additional loss)
    but the SRISK formula clamps the (1 - LRMES) term implicitly through
    the (1-k) coefficient; we DO NOT clamp LRMES itself so the diagnostic
    remains visible to operators.
    """
    params: GARCHDCCParams = field(default_factory=GARCHDCCParams)
    horizon_days: int = DEFAULT_HORIZON_DAYS
    crisis_threshold: float = DEFAULT_CRISIS_THRESHOLD   # market log-return threshold
    n_paths: int = DEFAULT_N_PATHS
    seed: int | None = None

    def compute(self) -> dict[str, Any]:
        """Run the Monte Carlo and return LRMES + diagnostics."""
        sim = GARCHDCCSimulator(
            params=self.params,
            horizon=self.horizon_days,
            n_paths=self.n_paths,
            seed=self.seed,
        )
        cum = sim.simulate()       # (n_paths, 2): [firm, market] log-returns
        firm_logret = cum[:, 0]
        mkt_logret = cum[:, 1]

        # Crisis condition: market log-return BELOW threshold (cum loss)
        crisis_mask = mkt_logret < self.crisis_threshold
        n_crisis = int(crisis_mask.sum())

        if n_crisis == 0:
            return {
                "lrmes": 0.0,
                "n_paths": self.n_paths,
                "n_crisis_paths": 0,
                "crisis_threshold": self.crisis_threshold,
                "horizon_days": self.horizon_days,
                "warning": (
                    "No simulated paths reached the crisis threshold; "
                    "raise n_paths or relax the threshold."
                ),
            }

        firm_simple_ret_in_crisis = np.exp(firm_logret[crisis_mask]) - 1.0
        lrmes = float(-firm_simple_ret_in_crisis.mean())

        return {
            "lrmes": lrmes,
            "n_paths": self.n_paths,
            "n_crisis_paths": n_crisis,
            "crisis_frequency": n_crisis / self.n_paths,
            "crisis_threshold": self.crisis_threshold,
            "horizon_days": self.horizon_days,
            "firm_simple_return_in_crisis_mean": float(firm_simple_ret_in_crisis.mean()),
            "firm_simple_return_in_crisis_std": float(firm_simple_ret_in_crisis.std(ddof=0)),
        }


# ─── SRISK calculator ──────────────────────────────────────────────


@dataclass(frozen=True)
class SRISKResult:
    """One SRISK reading for one firm."""
    firm: str
    market_cap_W: float
    book_debt_D: float
    k: float
    lrmes: float
    srisk: float            # USD; > 0 = capital shortfall
    is_shortfall: bool      # True iff srisk > 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SRISKCalculator:
    """Compute SRISK given the four primitives.

    LRMES is supplied directly so the caller can either (a) run
    ``LRMESMonteCarlo`` upstream, (b) pull V-Lab's published LRMES,
    or (c) provide a hand-set value for stress tests.
    """
    k: float = DEFAULT_K_BANK

    def __post_init__(self) -> None:
        if not (0.0 <= self.k <= 1.0):
            raise ValueError(f"k must be in [0, 1]; got {self.k}")

    def compute(
        self,
        *,
        firm: str,
        market_cap_W: float,
        book_debt_D: float,
        lrmes: float,
        metadata: dict[str, Any] | None = None,
    ) -> SRISKResult:
        if market_cap_W < 0:
            raise ValueError(f"market_cap_W must be non-negative; got {market_cap_W}")
        if book_debt_D < 0:
            raise ValueError(f"book_debt_D must be non-negative; got {book_debt_D}")

        # SRISK = k * D - (1 - k) * W * (1 - LRMES)
        srisk = self.k * book_debt_D - (1.0 - self.k) * market_cap_W * (1.0 - lrmes)

        return SRISKResult(
            firm=firm,
            market_cap_W=market_cap_W,
            book_debt_D=book_debt_D,
            k=self.k,
            lrmes=lrmes,
            srisk=srisk,
            is_shortfall=srisk > 0,
            metadata=dict(metadata or {}),
        )


# ─── Panel aggregator ──────────────────────────────────────────────


def srisk_panel(
    inputs: list[dict[str, Any]],
    *,
    k: float = DEFAULT_K_BANK,
) -> dict[str, Any]:
    """Compute SRISK for a list of firms and return the standard panel summary.

    Each input dict must have keys: ``firm``, ``market_cap_W``, ``book_debt_D``,
    ``lrmes``. Optional: ``metadata``.

    Output keys:
      - ``per_firm``:        list of ``SRISKResult`` dicts (sorted by SRISK desc)
      - ``total_srisk``:     sum of positive SRISK only (V-Lab convention)
      - ``total_srisk_net``: sum of all SRISK (positives - surpluses)
      - ``n_firms``, ``n_shortfall``, ``n_surplus``
    """
    calc = SRISKCalculator(k=k)
    results: list[SRISKResult] = []
    for row in inputs:
        results.append(calc.compute(
            firm=row["firm"],
            market_cap_W=row["market_cap_W"],
            book_debt_D=row["book_debt_D"],
            lrmes=row["lrmes"],
            metadata=row.get("metadata"),
        ))
    results.sort(key=lambda r: r.srisk, reverse=True)

    positive = sum(r.srisk for r in results if r.srisk > 0)
    net = sum(r.srisk for r in results)
    n_shortfall = sum(1 for r in results if r.is_shortfall)
    return {
        "per_firm": [r.__dict__ for r in results],
        "total_srisk": positive,
        "total_srisk_net": net,
        "n_firms": len(results),
        "n_shortfall": n_shortfall,
        "n_surplus": len(results) - n_shortfall,
        "k": k,
    }
