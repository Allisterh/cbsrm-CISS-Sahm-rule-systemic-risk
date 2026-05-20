"""
USD/JPY trend regime indicator.

Methodology
-----------

Mirrors the DXY regime indicator but specialised on the USD/JPY pair via FRED
``DEXJPUS`` (Japanese yen per US dollar, daily noon NY-Fed reference rate).

Why a dedicated JPY indicator?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Japan is the world's third-largest economy, the largest external creditor,
and the funding leg of the yen carry trade. Sustained JPY weakness historically
coincides with:

* Risk-on global equity sentiment (carry trade thrives in low-vol regimes)
* Tightening US/Japan rate-differential cycles
* Cross-border deleveraging pressure on Japanese institutional balance sheets
  exposed to foreign assets

Sustained JPY strength is associated with:

* Risk-off flight-to-quality (yen functions as a safe-haven currency)
* US easing cycles
* Japanese repatriation flows (e.g. post-2008, post-2020)

A USD/JPY regime indicator alongside DXY adds a true cross-currency
dimension to the macro layer; DXY-only treats Japan as one of many G10
currencies without distinguishing its safe-haven role.

Computation
~~~~~~~~~~~

Identical to ``DXYRegimeIndicator``: rolling 252-day z-score of the level.

Regime classification (on z-score of USD/JPY):

* ``z >= +1.5`` — USD_STRONG_JPY_WEAK (carry-favourable; risk-on; yen funding cheap)
* ``+0.5 <= z < +1.5`` — USD_MILD_BULL_JPY
* ``-0.5 < z < +0.5`` — NEUTRAL
* ``-1.5 < z <= -0.5`` — USD_MILD_BEAR_JPY
* ``z <= -1.5`` — USD_WEAK_JPY_STRONG (safe-haven flight; risk-off)

Reference
---------

- Federal Reserve Board H.10 (Foreign Exchange Rates).
- FRED series DEXJPUS: Japanese Yen / U.S. Dollar Foreign Exchange Rate.
  https://fred.stlouisfed.org/series/DEXJPUS
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
class JPYRegimeIndicator:
    """USD/JPY trend regime."""

    id: str = "JPY-REGIME"
    version: str = "1.0.0"
    source: str = (
        "Federal Reserve Board H.10 (Foreign Exchange Rates). "
        "FRED series DEXJPUS (Japanese Yen / U.S. Dollar Foreign Exchange Rate, daily). "
        "https://fred.stlouisfed.org/series/DEXJPUS"
    )
    series_id: str = "DEXJPUS"
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
                metadata=with_i18n(
                    {"source": self.source, "n_obs": 0},
                    "jpy_regime.interpretation",
                ),
            )

        roll = level.rolling(window=self.lookback_days, min_periods=MIN_OBS_FOR_Z)
        z = ((level - roll.mean()) / roll.std(ddof=0).replace(0.0, np.nan)).rename(
            self.id
        ).dropna()

        log_level = np.log(level.replace(0.0, np.nan)).dropna()
        ret_3m = (log_level - log_level.shift(self.return_horizon_days)).rename(
            "log_ret_3m"
        )

        sub = pd.concat([level.rename("usd_jpy"), z.rename("z_score_252d"), ret_3m], axis=1)

        latest_z = float(z.iloc[-1]) if not z.empty else float("nan")
        latest_ret_3m = (
            float(ret_3m.dropna().iloc[-1])
            if not ret_3m.dropna().empty else float("nan")
        )
        latest_level = float(level.iloc[-1])

        if pd.isna(latest_z):
            regime = "INSUFFICIENT_HISTORY"
        elif latest_z >= 1.5:
            regime = "USD_STRONG_JPY_WEAK"
        elif latest_z >= 0.5:
            regime = "USD_MILD_BULL_JPY"
        elif latest_z <= -1.5:
            regime = "USD_WEAK_JPY_STRONG"
        elif latest_z <= -0.5:
            regime = "USD_MILD_BEAR_JPY"
        else:
            regime = "NEUTRAL"

        meta: dict[str, Any] = with_i18n({
            "source": self.source,
            "series_id": self.series_id,
            "n_obs": int(z.size),
            "lookback_days": self.lookback_days,
            "first_date": str(z.index.min()) if not z.empty else None,
            "last_date": str(z.index.max()) if not z.empty else None,
            "latest_usd_jpy": latest_level,
            "latest_z_score": latest_z,
            "latest_log_return_3m": latest_ret_3m,
            "regime": regime,
        }, "jpy_regime.interpretation")
        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=z,
            subindex_values=sub,
            metadata=meta,
        )
