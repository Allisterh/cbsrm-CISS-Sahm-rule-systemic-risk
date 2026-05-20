"""
Non-farm payrolls (NFP) momentum indicator.

Methodology
-----------

Without access to a real-time consensus-forecast feed (Bloomberg, Refinitiv,
Trading Economics), CBSRM v0.3 publishes a *momentum* indicator rather than a
true *surprise* indicator. The two diverge in the short run but agree on the
medium-run direction of US labour-market health.

Computation
~~~~~~~~~~~

Let ``P_t`` be the monthly seasonally-adjusted total non-farm payrolls level
(FRED ``PAYEMS``). Define:

    momentum_t = z_t = ( delta_t  -  mean_lookback(delta) ) / std_lookback(delta)

where ``delta_t = log(P_t) - log(P_{t-1})`` (month-over-month log growth) and
``mean_lookback``, ``std_lookback`` are rolling mean and standard deviation
over ``lookback_months`` (default 60 months = 5 years).

Interpretation
~~~~~~~~~~~~~~

* ``z_t > +1``  — payroll growth roughly one standard deviation above the
  5-year norm. Labour market accelerating; supports risk-on regime.
* ``z_t ~ 0``   — at trend.
* ``z_t < -1``  — payroll growth materially below the 5-year norm. Labour
  market decelerating; risk-off pressure.
* ``z_t < -2``  — severe deceleration; recession signal often coincident.

The standardisation makes the indicator comparable across cycles even though
the secular trend in US payroll growth has flattened.

Upgrades planned for v0.4
~~~~~~~~~~~~~~~~~~~~~~~~~

When a consensus-forecast adapter is added (Trading Economics free tier or
similar), this module will also expose ``actual - consensus`` as a separate
column and rename to ``NFPSurpriseIndicator``.

Reference
---------

- US Bureau of Labor Statistics, Employment Situation report (monthly).
- FRED series PAYEMS: All Employees, Total Nonfarm.
  https://fred.stlouisfed.org/series/PAYEMS
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cbsrm.i18n import with_i18n
from cbsrm.indicators.base import IndicatorResult


DEFAULT_LOOKBACK_MONTHS = 60
MIN_OBS_FOR_Z = 12   # need at least 1 year before we can compute a meaningful z


@dataclass
class NFPMomentumIndicator:
    """NFP MoM-growth rolling z-score."""

    id: str = "NFP-MOMENTUM-US"
    version: str = "1.0.0"
    source: str = (
        "US Bureau of Labor Statistics, Employment Situation (monthly); "
        "FRED series PAYEMS (Total Nonfarm Payrolls). "
        "https://fred.stlouisfed.org/series/PAYEMS"
    )
    series_id: str = "PAYEMS"
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS

    def required_series(self) -> list[str]:
        return [self.series_id]

    def compute(self, data: pd.DataFrame) -> IndicatorResult:
        col = self.series_id
        if col not in data.columns:
            raise ValueError(
                f"{self.id}.compute() requires column '{col}'; "
                f"got columns {list(data.columns)}"
            )
        levels = data[col].dropna().astype(float)
        if levels.empty:
            return IndicatorResult(
                indicator_id=self.id,
                version=self.version,
                values=pd.Series(dtype=float, name=self.id),
                metadata={"source": self.source, "n_obs": 0},
            )

        # MoM log growth
        log_levels = np.log(levels.replace(0.0, np.nan)).dropna()
        delta = log_levels.diff().dropna()

        # Rolling z-score with min_periods guard
        roll = delta.rolling(window=self.lookback_months, min_periods=MIN_OBS_FOR_Z)
        mean = roll.mean()
        std = roll.std(ddof=0)
        z = ((delta - mean) / std.replace(0.0, np.nan)).rename(self.id).dropna()

        latest_z = float(z.iloc[-1]) if not z.empty else float("nan")
        latest_delta_pct = float(delta.iloc[-1] * 100.0) if not delta.empty else float("nan")

        # Coincident classification
        if math.isnan(latest_z):
            classification = "INSUFFICIENT_HISTORY"
        elif latest_z >= 1.0:
            classification = "ACCELERATING"
        elif latest_z <= -2.0:
            classification = "SEVERE_DECELERATION"
        elif latest_z <= -1.0:
            classification = "DECELERATING"
        else:
            classification = "AT_TREND"

        meta: dict[str, Any] = with_i18n({
            "source": self.source,
            "series_id": self.series_id,
            "n_obs": int(z.size),
            "lookback_months": self.lookback_months,
            "first_date": str(z.index.min()) if not z.empty else None,
            "last_date": str(z.index.max()) if not z.empty else None,
            "latest_z": latest_z,
            "latest_mom_log_growth_pct": latest_delta_pct,
            "classification": classification,
            "interpretation": (
                "Rolling z-score of MoM log payroll growth vs trailing "
                f"{self.lookback_months}-month window. z>=+1 ACCELERATING, "
                "z<=-1 DECELERATING, z<=-2 SEVERE_DECELERATION."
            ),
        }, "nfp_momentum.interpretation")
        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=z,
            metadata=meta,
        )
