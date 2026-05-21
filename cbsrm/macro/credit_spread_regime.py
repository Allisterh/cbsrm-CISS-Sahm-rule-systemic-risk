"""
Credit-spread regime indicator.

Tracks the ICE BofA US High-Yield Index Option-Adjusted Spread
(FRED ``BAMLH0A0HYM2``) as a forward-looking measure of credit stress.
High-yield OAS leads tighter funding conditions, credit-event clustering,
and equity drawdowns by 1–3 months historically (Gilchrist-Zakrajsek 2012).

Computation
~~~~~~~~~~~

Let ``OAS_t`` = HY OAS in basis points.

    z_t   = (OAS_t - mean_252(OAS)) / std_252(OAS)
    chg_t = OAS_t - OAS_{t-21}       (1-month bps change)

Regime classification (on level + 1-month change combined):

* ``OAS_t >= 1000`` OR ``chg_t >= +200`` → CREDIT_STRESS_ACUTE
* ``OAS_t >= 700``  OR ``chg_t >= +100`` → CREDIT_STRESS_RISING
* ``OAS_t <= 350``  → CREDIT_BENIGN
* otherwise → CREDIT_NORMAL

The 350 / 700 / 1000 bp thresholds are calibrated against the 2008Q4
(>1700 bps), 2011 EU debt (~900 bps), 2020 COVID (~1100 bps), and 2022
inflation (~600 bps) episodes.

Reference
---------
- ICE BofA US High Yield Index Option-Adjusted Spread.
- FRED BAMLH0A0HYM2: https://fred.stlouisfed.org/series/BAMLH0A0HYM2
- Gilchrist, S., & Zakrajsek, E. (2012). Credit spreads and business cycle
  fluctuations. *American Economic Review*, 102(4), 1692-1720.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cbsrm.indicators.base import IndicatorResult


LOOKBACK_DAYS_DEFAULT = 252
MIN_OBS_FOR_Z = 60


@dataclass
class CreditSpreadRegimeIndicator:
    """ICE BofA US HY OAS regime classifier."""

    id: str = "CREDIT-SPREAD-REGIME-US"
    version: str = "1.0.0"
    source: str = (
        "ICE BofA US High Yield Index Option-Adjusted Spread. "
        "FRED series BAMLH0A0HYM2 (daily, percent). "
        "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"
    )
    series_id: str = "BAMLH0A0HYM2"
    lookback_days: int = LOOKBACK_DAYS_DEFAULT

    def required_series(self) -> list[str]:
        return [self.series_id]

    def compute(self, data: pd.DataFrame) -> IndicatorResult:
        col = self.series_id
        if col not in data.columns:
            raise ValueError(
                f"{self.id}.compute() requires column '{col}'; "
                f"got columns {list(data.columns)}"
            )
        # FRED publishes BAMLH0A0HYM2 in percent — multiply by 100 to get bps.
        spread_bps = (data[col].dropna().astype(float) * 100.0).rename(self.id)
        if spread_bps.empty:
            return IndicatorResult(
                indicator_id=self.id,
                version=self.version,
                values=pd.Series(dtype=float, name=self.id),
                metadata={"source": self.source, "n_obs": 0},
            )

        roll = spread_bps.rolling(window=self.lookback_days, min_periods=MIN_OBS_FOR_Z)
        z = ((spread_bps - roll.mean()) / roll.std(ddof=0).replace(0.0, np.nan)).rename(
            "z_score_252d"
        )
        change_1m = (spread_bps - spread_bps.shift(21)).rename("change_1m_bps")

        sub = pd.concat([spread_bps.rename("hy_oas_bps"), z, change_1m], axis=1)

        latest_level = float(spread_bps.iloc[-1])
        latest_chg = float(change_1m.dropna().iloc[-1]) if not change_1m.dropna().empty else float("nan")
        latest_z = float(z.dropna().iloc[-1]) if not z.dropna().empty else float("nan")

        if (latest_level >= 1000.0) or (not np.isnan(latest_chg) and latest_chg >= 200.0):
            regime = "CREDIT_STRESS_ACUTE"
        elif (latest_level >= 700.0) or (not np.isnan(latest_chg) and latest_chg >= 100.0):
            regime = "CREDIT_STRESS_RISING"
        elif latest_level <= 350.0:
            regime = "CREDIT_BENIGN"
        else:
            regime = "CREDIT_NORMAL"

        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=spread_bps,
            subindex_values=sub,
            metadata={
                "source": self.source,
                "series_id": self.series_id,
                "n_obs": int(spread_bps.size),
                "first_date": str(spread_bps.index.min()),
                "last_date": str(spread_bps.index.max()),
                "latest_hy_oas_bps": latest_level,
                "latest_1m_change_bps": latest_chg,
                "latest_z_252d": latest_z,
                "regime": regime,
                "thresholds": {
                    "stress_acute_level_bps": 1000.0,
                    "stress_rising_level_bps": 700.0,
                    "benign_level_bps": 350.0,
                    "stress_acute_1m_change_bps": 200.0,
                    "stress_rising_1m_change_bps": 100.0,
                },
                "interpretation": (
                    "HY OAS regime classifier. Level >= 1000 bps OR 1-month "
                    "change >= 200 bps signals acute credit stress."
                ),
            },
        )
