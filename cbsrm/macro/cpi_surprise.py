"""
CPI surprise indicator.

Like ``NFPMomentumIndicator`` for non-farm payrolls, this is a momentum
proxy for true consensus-survey surprise. The pure-FRED implementation
publishes a rolling z-score of YoY CPI inflation vs the trailing 3-year
median. Replacement with a true ``actual − consensus`` series is deferred
to v0.5 when a consensus adapter ships.

Computation
~~~~~~~~~~~

Let ``P_t`` = FRED ``CPIAUCSL`` (CPI for All Urban Consumers, monthly SA).

    yoy_t        = log(P_t) - log(P_{t-12})
    trend_3y_t   = rolling_median(yoy, window=36 months, min_periods=12)
    iqr_3y_t     = rolling_iqr(yoy, window=36 months, min_periods=12)
    surprise_t   = (yoy_t - trend_3y_t) / (0.7413 * iqr_3y_t)   ← Gaussian-eq z

The 0.7413 = 1 / (sqrt(2) * inverse_erf(0.5)) factor converts IQR to a
standard-deviation-equivalent under a Gaussian baseline (more robust than
straight std).

Classification:
    surprise >= +1   → INFLATION_OVERSHOOT
    surprise <= -1   → DISINFLATION
    otherwise         → AT_TREND

Reference
---------
- US Bureau of Labor Statistics, CPI release.
- FRED CPIAUCSL: https://fred.stlouisfed.org/series/CPIAUCSL
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cbsrm.indicators.base import IndicatorResult


LOOKBACK_MONTHS_DEFAULT = 36
MIN_OBS_FOR_Z = 12

# Gaussian conversion: IQR = 1.349 * sigma  →  sigma = IQR / 1.349
# But for z-scoring we want IQR-to-sigma in the other direction: scale = 1/1.349
IQR_TO_SIGMA = 1.0 / 1.349


@dataclass
class CPISurpriseIndicator:
    """Rolling YoY CPI surprise (momentum proxy)."""

    id: str = "CPI-SURPRISE-US"
    version: str = "1.0.0"
    source: str = (
        "US BLS Consumer Price Index. FRED series CPIAUCSL "
        "(CPI for All Urban Consumers: All Items, monthly SA). "
        "https://fred.stlouisfed.org/series/CPIAUCSL"
    )
    series_id: str = "CPIAUCSL"
    lookback_months: int = LOOKBACK_MONTHS_DEFAULT

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
        # YoY = log change over 12 months
        yoy = (log_level - log_level.shift(12)).dropna()

        roll = yoy.rolling(window=self.lookback_months, min_periods=MIN_OBS_FOR_Z)
        trend = roll.median()

        # Robust IQR: (Q3 - Q1) where Q1 = 0.25 quantile, Q3 = 0.75
        q1 = roll.quantile(0.25)
        q3 = roll.quantile(0.75)
        iqr = (q3 - q1).replace(0.0, np.nan)
        sigma_eq = iqr * IQR_TO_SIGMA

        surprise = ((yoy - trend) / sigma_eq).rename(self.id).dropna()

        if surprise.empty:
            classification = "INSUFFICIENT_HISTORY"
            latest_surprise = float("nan")
            latest_yoy = float(yoy.iloc[-1]) if not yoy.empty else float("nan")
        else:
            latest_surprise = float(surprise.iloc[-1])
            latest_yoy = float(yoy.iloc[-1])
            if latest_surprise >= 1.0:
                classification = "INFLATION_OVERSHOOT"
            elif latest_surprise <= -1.0:
                classification = "DISINFLATION"
            else:
                classification = "AT_TREND"

        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=surprise,
            metadata={
                "source": self.source,
                "series_id": self.series_id,
                "n_obs": int(surprise.size),
                "lookback_months": self.lookback_months,
                "first_date": str(surprise.index.min()) if not surprise.empty else None,
                "last_date": str(surprise.index.max()) if not surprise.empty else None,
                "latest_surprise_z": latest_surprise,
                "latest_yoy_inflation_pct": latest_yoy * 100.0,
                "classification": classification,
                "interpretation": (
                    "Robust z-score of YoY CPI inflation vs trailing "
                    f"{self.lookback_months}-month median (IQR-based scale). "
                    "z>=+1 INFLATION_OVERSHOOT, z<=-1 DISINFLATION."
                ),
            },
        )
