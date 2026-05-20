"""
US dollar broad-trade-weighted index (DXY-equivalent) trend regime indicator.

Methodology
-----------

Tracks the trend regime of the trade-weighted broad US dollar index
(FRED ``DTWEXBGS``). The classic ICE DXY is narrower (6 currencies); the
trade-weighted broad index is the more economically meaningful measure used
by the Fed Board for international financial conditions work.

Computation
~~~~~~~~~~~

For each day ``t``, compute the rolling z-score of the index level over a
trailing 252-trading-day (~1-year) window and additionally the 3-month
log-return:

    z_t        = ( level_t - mean_252(level) ) / std_252(level)
    ret_3m_t   = log(level_t) - log(level_{t-63})

Composite trend score: ``z_t`` (the level standardisation captures longer-run
regime); ``ret_3m_t`` enters the metadata for the operator's secondary check.

Regime classification (on ``z_t``):

* ``z >= +1.5``  — STRONG_DOLLAR_BULL
* ``+0.5 <= z < +1.5``  — DOLLAR_BULL
* ``-0.5 < z < +0.5``  — NEUTRAL
* ``-1.5 < z <= -0.5``  — DOLLAR_BEAR
* ``z <= -1.5``  — STRONG_DOLLAR_BEAR

Why this matters for systemic risk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A persistently strong dollar is associated with:
* tighter global financial conditions (Bruno-Shin 2015, Avdjiev et al. 2018)
* emerging-market deleveraging stress
* downward pressure on commodity prices and EM equities

A weakening dollar relaxes those constraints. The DXY regime is therefore a
useful cross-jurisdictional macro input alongside the ECB-CISS series.

Reference
---------

- Federal Reserve Board H.10, Foreign Exchange Rates (weekly).
- FRED series DTWEXBGS: Nominal Broad U.S. Dollar Index.
  https://fred.stlouisfed.org/series/DTWEXBGS
- Bruno, V., & Shin, H. S. (2015). Cross-border banking and global liquidity.
  Review of Economic Studies, 82(2), 535-564.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cbsrm.i18n import with_i18n
from cbsrm.indicators.base import IndicatorResult


LOOKBACK_DAYS_DEFAULT = 252
RETURN_HORIZON_DAYS_DEFAULT = 63
MIN_OBS_FOR_Z = 60


@dataclass
class DXYRegimeIndicator:
    """Broad trade-weighted USD index trend regime."""

    id: str = "DXY-REGIME-US"
    version: str = "1.0.0"
    source: str = (
        "Federal Reserve Board H.10 (Foreign Exchange Rates). "
        "FRED series DTWEXBGS (Nominal Broad U.S. Dollar Index, daily). "
        "https://fred.stlouisfed.org/series/DTWEXBGS"
    )
    series_id: str = "DTWEXBGS"
    lookback_days: int = LOOKBACK_DAYS_DEFAULT
    return_horizon_days: int = RETURN_HORIZON_DAYS_DEFAULT

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

        roll = level.rolling(window=self.lookback_days, min_periods=MIN_OBS_FOR_Z)
        z = ((level - roll.mean()) / roll.std(ddof=0).replace(0.0, np.nan)).rename(
            self.id
        ).dropna()

        log_level = np.log(level.replace(0.0, np.nan)).dropna()
        ret_3m = (log_level - log_level.shift(self.return_horizon_days)).rename(
            "log_ret_3m"
        )

        sub = pd.concat([level.rename("level"), z.rename("z_score_252d"), ret_3m], axis=1)

        latest_z = float(z.iloc[-1]) if not z.empty else float("nan")
        latest_ret_3m = float(ret_3m.dropna().iloc[-1]) if not ret_3m.dropna().empty else float("nan")
        latest_level = float(level.iloc[-1])

        if pd.isna(latest_z):
            regime = "INSUFFICIENT_HISTORY"
        elif latest_z >= 1.5:
            regime = "STRONG_DOLLAR_BULL"
        elif latest_z >= 0.5:
            regime = "DOLLAR_BULL"
        elif latest_z <= -1.5:
            regime = "STRONG_DOLLAR_BEAR"
        elif latest_z <= -0.5:
            regime = "DOLLAR_BEAR"
        else:
            regime = "NEUTRAL"

        meta: dict[str, Any] = with_i18n({
            "source": self.source,
            "series_id": self.series_id,
            "n_obs": int(z.size),
            "lookback_days": self.lookback_days,
            "first_date": str(z.index.min()) if not z.empty else None,
            "last_date": str(z.index.max()) if not z.empty else None,
            "latest_level": latest_level,
            "latest_z_score": latest_z,
            "latest_log_return_3m": latest_ret_3m,
            "regime": regime,
            "interpretation": (
                f"Rolling z-score of broad USD index over trailing "
                f"{self.lookback_days}-day window. |z|>=1.5 is strong regime."
            ),
        }, "dxy_regime.interpretation")
        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=z,
            subindex_values=sub,
            metadata=meta,
        )
