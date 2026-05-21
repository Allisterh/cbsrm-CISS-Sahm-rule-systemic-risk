"""
Oil-macro indicator.

Tracks the West Texas Intermediate (WTI) crude-oil regime via FRED
``DCOILWTICO``. The macroeconomic role of oil regime:

* **Persistent oil-price spikes** (> +30% YoY) historically coincide with
  every major US recession since 1973 (Hamilton 2003, Killian 2008).
* **Oil-price crashes** (< -30% YoY) are associated with negative income
  shocks to producing nations / EM strain (1986, 1998, 2014-16, 2020).
* **Inverted-curve oil** (front-month above 12-month) signals immediate
  scarcity / hoarding (Pirrong 2011); we approximate this with the rolling
  YoY level change since the WTI futures curve is not on FRED.

Computation
~~~~~~~~~~~

For each observation date ``t``:

* ``log_yoy = log(WTI_t / WTI_{t-252})``
* ``log_3m = log(WTI_t / WTI_{t-63})``
* ``z_252 = (level_t - mean_252(level)) / std_252(level)``

Regime classification on ``log_yoy``:

* ``log_yoy >= +0.30``  → OIL_SPIKE
* ``log_yoy >= +0.10``  → OIL_RISING
* ``-0.10 < log_yoy < +0.10`` → OIL_RANGEBOUND
* ``log_yoy <= -0.10``  → OIL_FALLING
* ``log_yoy <= -0.30``  → OIL_CRASH

Reference
---------
- US Energy Information Administration spot-price data via FRED.
- FRED DCOILWTICO: https://fred.stlouisfed.org/series/DCOILWTICO
- Hamilton, J. D. (2003). What is an oil shock? *J. Econometrics* 113.
- Kilian, L. (2008). Exogenous oil supply shocks: How big are they and how
  much do they matter for the US economy? *Rev. Econ. Stat.* 90.
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
class OilMacroIndicator:
    """WTI crude-oil macroeconomic regime."""

    id: str = "OIL-MACRO"
    version: str = "1.0.0"
    source: str = (
        "US EIA spot price data via FRED. "
        "FRED series DCOILWTICO (WTI Crude, US Dollars per Barrel, daily). "
        "https://fred.stlouisfed.org/series/DCOILWTICO"
    )
    series_id: str = "DCOILWTICO"
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
        level = data[col].dropna().astype(float)
        if level.empty:
            return IndicatorResult(
                indicator_id=self.id,
                version=self.version,
                values=pd.Series(dtype=float, name=self.id),
                metadata={"source": self.source, "n_obs": 0},
            )

        log_level = np.log(level.replace(0.0, np.nan)).dropna()
        yoy = (log_level - log_level.shift(252)).rename(self.id)
        three_m = (log_level - log_level.shift(63)).rename("log_ret_3m")

        roll = level.rolling(window=self.lookback_days, min_periods=MIN_OBS_FOR_Z)
        z = ((level - roll.mean()) / roll.std(ddof=0).replace(0.0, np.nan)).rename(
            "z_score_252d"
        )

        sub = pd.concat([
            level.rename("wti_usd_bbl"),
            yoy.rename("log_yoy"),
            three_m,
            z,
        ], axis=1)
        yoy = yoy.dropna()

        if yoy.empty:
            regime = "INSUFFICIENT_HISTORY"
            latest_yoy = float("nan")
        else:
            latest_yoy = float(yoy.iloc[-1])
            if latest_yoy >= 0.30:
                regime = "OIL_SPIKE"
            elif latest_yoy >= 0.10:
                regime = "OIL_RISING"
            elif latest_yoy <= -0.30:
                regime = "OIL_CRASH"
            elif latest_yoy <= -0.10:
                regime = "OIL_FALLING"
            else:
                regime = "OIL_RANGEBOUND"

        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=yoy,
            subindex_values=sub,
            metadata={
                "source": self.source,
                "series_id": self.series_id,
                "n_obs": int(yoy.size),
                "first_date": str(yoy.index.min()) if not yoy.empty else None,
                "last_date": str(yoy.index.max()) if not yoy.empty else None,
                "latest_wti_usd_bbl": float(level.iloc[-1]),
                "latest_log_yoy": latest_yoy,
                "latest_log_yoy_pct": latest_yoy * 100.0 if not np.isnan(latest_yoy) else None,
                "regime": regime,
                "interpretation": (
                    "YoY log-return on WTI crude. "
                    "OIL_SPIKE/CRASH (|YoY|>=30%) historically aligns with "
                    "macro stress events."
                ),
            },
        )
