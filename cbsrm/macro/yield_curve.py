"""
Yield-curve indicator + Estrella-Mishkin recession-probability probit.

Methodology
-----------

Two complementary measurements from the US Treasury yield curve, both
established in the financial-stability literature:

1. **Inversion state.** The 10-year minus 3-month spread (T10Y3M, FRED) is
   the canonical leading indicator of US recessions. Negative values =
   inverted curve. Persistent inversion (>= 60 trading days) precedes 8 of
   the last 8 NBER-dated US recessions.

2. **Recession probability (Estrella & Mishkin, NY Fed).** Probit model
   regressing the next-12-month recession indicator on the current 10Y-3M
   spread:

       P(recession_{t+12} = 1 | spread_t) = Phi(beta_0 + beta_1 * spread_t)

   Published coefficients (Estrella & Mishkin 1996, NBER Working Paper #5379,
   refreshed by NY Fed staff through 2025):

       beta_0 = -0.5450
       beta_1 = -0.5898

   where the spread is in percentage points and Phi(.) is the standard-normal
   CDF. Output values in [0, 1] interpretable as "probability of US recession
   12 months out, conditional on current curve."

References
----------

- Estrella, A., & Mishkin, F. S. (1996). The yield curve as a predictor of
  US recessions. Current Issues in Economics and Finance, 2(7).
- NY Fed (2025). Probability of US Recession Predicted by Treasury Spread.
  https://www.newyorkfed.org/research/capital_markets/ycfaq

Notes
-----

The CBSRM implementation uses the daily FRED-published series T10Y3M (the
constant-maturity 10Y minus 3M Treasury spread) at daily cadence. The
recession-probability is computed pointwise and emits as a daily series.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from cbsrm.i18n import with_i18n
from cbsrm.indicators.base import IndicatorResult


# ─── Estrella-Mishkin probit coefficients (NY Fed convention) ──────────
ESTRELLA_MISHKIN_BETA_0: float = -0.5450
ESTRELLA_MISHKIN_BETA_1: float = -0.5898

# Threshold (days) for "persistent inversion" classification
PERSISTENT_INVERSION_DAYS_DEFAULT: int = 60


def _standard_normal_cdf(x: float) -> float:
    """Phi(x) — the standard normal CDF. Pure-Python, no scipy needed."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def estrella_mishkin_recession_prob(
    spread: float,
    *,
    beta_0: float = ESTRELLA_MISHKIN_BETA_0,
    beta_1: float = ESTRELLA_MISHKIN_BETA_1,
) -> float:
    """Recession probability 12 months out given current spread.

    Parameters
    ----------
    spread : float
        Current 10Y-3M spread in percentage points (e.g. -0.50 means
        the 3-month yield exceeds the 10-year by 50 basis points).
    beta_0, beta_1 : float
        Probit coefficients. Defaults are the NY-Fed-published Estrella-Mishkin
        values.

    Returns
    -------
    float
        Probability in [0, 1].
    """
    z = beta_0 + beta_1 * spread
    return _standard_normal_cdf(z)


@dataclass
class YieldCurveIndicator:
    """Yield-curve inversion + recession probability indicator."""

    id: str = "YIELD-CURVE-US"
    version: str = "1.0.0"
    source: str = (
        "Federal Reserve Bank of New York (2025). Probability of US Recession "
        "Predicted by Treasury Spread (Estrella-Mishkin probit). "
        "https://www.newyorkfed.org/research/capital_markets/ycfaq. "
        "Spread series: FRED T10Y3M."
    )
    series_id: str = "T10Y3M"
    persistent_inversion_days: int = PERSISTENT_INVERSION_DAYS_DEFAULT

    def required_series(self) -> list[str]:
        return [self.series_id]

    def compute(self, data: pd.DataFrame) -> IndicatorResult:
        """Compute yield-curve metrics + Estrella-Mishkin recession probability.

        Parameters
        ----------
        data : pd.DataFrame
            Must contain a column named after ``self.series_id`` (default
            ``T10Y3M``). Values are 10Y-3M Treasury spread in percentage points.

        Returns
        -------
        IndicatorResult
            ``values`` is the recession-probability series (daily, [0, 1]).
            ``subindex_values`` carries spread / is_inverted / days_inverted_run.
        """
        col = self.series_id
        if col not in data.columns:
            raise ValueError(
                f"{self.id}.compute() requires column '{col}'; "
                f"got columns {list(data.columns)}"
            )
        spread = data[col].dropna().astype(float)

        if spread.empty:
            return IndicatorResult(
                indicator_id=self.id,
                version=self.version,
                values=pd.Series(dtype=float, name=self.id),
                subindex_values=None,
                metadata={"source": self.source, "n_obs": 0},
            )

        # Recession probability per day
        rec_prob = spread.apply(estrella_mishkin_recession_prob).rename(self.id)

        # Inversion flag (spread < 0) and run-length (days_inverted_consecutive)
        is_inverted = (spread < 0.0).astype(int).rename("is_inverted")

        # Rolling run-length of consecutive inversion days
        run = []
        c = 0
        for v in is_inverted.values:
            c = c + 1 if v == 1 else 0
            run.append(c)
        days_inverted_run = pd.Series(run, index=spread.index, name="days_inverted_run")

        # Persistent-inversion flag
        persistent = (days_inverted_run >= self.persistent_inversion_days).astype(int).rename(
            "persistent_inversion"
        )

        sub = pd.concat(
            [spread.rename("spread_pp"), is_inverted, days_inverted_run, persistent],
            axis=1,
        )

        latest_spread = float(spread.iloc[-1])
        latest_prob = float(rec_prob.iloc[-1])
        latest_inverted = bool(is_inverted.iloc[-1])
        latest_run = int(days_inverted_run.iloc[-1])

        meta: dict[str, Any] = with_i18n({
            "source": self.source,
            "series_id": self.series_id,
            "n_obs": int(spread.size),
            "first_date": str(spread.index.min()),
            "last_date": str(spread.index.max()),
            "latest_spread_pp": latest_spread,
            "latest_recession_prob_12mo": latest_prob,
            "latest_is_inverted": latest_inverted,
            "latest_days_inverted_run": latest_run,
            "persistent_inversion_days_threshold": self.persistent_inversion_days,
            "interpretation": (
                "Recession probability 12 months out, conditional on current "
                "10Y-3M Treasury spread, via Estrella-Mishkin probit. "
                "Persistent inversion = run-length >= "
                f"{self.persistent_inversion_days} trading days."
            ),
            "model": {
                "beta_0": ESTRELLA_MISHKIN_BETA_0,
                "beta_1": ESTRELLA_MISHKIN_BETA_1,
            },
        }, "yield_curve.interpretation")

        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=rec_prob,
            subindex_values=sub,
            metadata=meta,
        )
