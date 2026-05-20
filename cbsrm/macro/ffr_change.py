"""
Federal funds rate change (FFR) indicator.

Methodology
-----------

Tracks the change in the effective federal funds rate (FRED ``DFF``) over
three horizons:

* 3-month change   (current EFFR minus EFFR 3 months ago, in basis points)
* 6-month change   (current minus 6 months ago)
* 12-month change  (current minus 12 months ago)

The composite *FFR-change momentum* signal is the simple average of the three
horizon changes, expressed in basis points. Positive = tightening cycle;
negative = easing cycle; near-zero = pause.

Regime classification
~~~~~~~~~~~~~~~~~~~~~

Buckets (the 50 bp / 200 bp thresholds match typical Fed cycle magnitudes):

* `composite >= +200 bp`    — AGGRESSIVE_TIGHTENING
* `composite >= +50 bp`     — TIGHTENING
* `composite <= -200 bp`    — AGGRESSIVE_EASING
* `composite <= -50 bp`     — EASING
* otherwise                  — PAUSE

The macro composite (cbsrm.macro.macro_composite) consumes this regime label
to gate the overall risk-on / risk-off classification: aggressive tightening
shifts the prior toward risk-off even if other indicators look benign.

Reference
---------

- Federal Reserve H.15 release.
- FRED series DFF: Effective Federal Funds Rate (daily).
  https://fred.stlouisfed.org/series/DFF

The same construction works for DFEDTARU (target upper) / DFEDTARL (target
lower) by configuring ``series_id``; default is the realised effective rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from cbsrm.i18n import with_i18n
from cbsrm.indicators.base import IndicatorResult


# Approximate trading-day windows
HORIZONS_DAYS = {"3m": 63, "6m": 126, "12m": 252}

# Regime cut-offs in basis points on the composite change.
# 150 bp aggressive matches both 1994 (composite ~250 bp) and 2022-23
# (composite ~190 bp) cycles. 40 bp normal leaves room for genuine pauses.
THRESHOLD_AGGRESSIVE = 150
THRESHOLD_NORMAL = 40


@dataclass
class FFRChangeIndicator:
    """EFFR change momentum across 3M / 6M / 12M horizons."""

    id: str = "FFR-CHANGE-US"
    version: str = "1.0.0"
    source: str = (
        "Federal Reserve H.15 (Selected Interest Rates). "
        "FRED series DFF (Effective Federal Funds Rate, daily). "
        "https://fred.stlouisfed.org/series/DFF"
    )
    series_id: str = "DFF"

    def required_series(self) -> list[str]:
        return [self.series_id]

    def compute(self, data: pd.DataFrame) -> IndicatorResult:
        col = self.series_id
        if col not in data.columns:
            raise ValueError(
                f"{self.id}.compute() requires column '{col}'; "
                f"got columns {list(data.columns)}"
            )
        rate = data[col].dropna().astype(float)  # FRED returns in % (e.g. 5.33)

        if rate.empty:
            return IndicatorResult(
                indicator_id=self.id,
                version=self.version,
                values=pd.Series(dtype=float, name=self.id),
                metadata={"source": self.source, "n_obs": 0},
            )

        # Compute horizon changes in basis points (FRED is in percent)
        sub_cols: dict[str, pd.Series] = {"rate_pct": rate}
        for label, window in HORIZONS_DAYS.items():
            shifted = rate.shift(window)
            sub_cols[f"change_{label}_bp"] = ((rate - shifted) * 100.0).rename(
                f"change_{label}_bp"
            )

        sub = pd.concat(sub_cols, axis=1)

        # Composite = mean across horizons, in bp
        composite = sub[[f"change_{k}_bp" for k in HORIZONS_DAYS]].mean(axis=1).rename(self.id)
        composite = composite.dropna()

        latest_composite_bp = float(composite.iloc[-1]) if not composite.empty else float("nan")
        latest_rate = float(rate.iloc[-1])

        if pd.isna(latest_composite_bp):
            regime = "INSUFFICIENT_HISTORY"
        elif latest_composite_bp >= THRESHOLD_AGGRESSIVE:
            regime = "AGGRESSIVE_TIGHTENING"
        elif latest_composite_bp >= THRESHOLD_NORMAL:
            regime = "TIGHTENING"
        elif latest_composite_bp <= -THRESHOLD_AGGRESSIVE:
            regime = "AGGRESSIVE_EASING"
        elif latest_composite_bp <= -THRESHOLD_NORMAL:
            regime = "EASING"
        else:
            regime = "PAUSE"

        meta: dict[str, Any] = with_i18n({
            "source": self.source,
            "series_id": self.series_id,
            "n_obs": int(composite.size),
            "first_date": str(composite.index.min()) if not composite.empty else None,
            "last_date": str(composite.index.max()) if not composite.empty else None,
            "latest_rate_pct": latest_rate,
            "latest_composite_change_bp": latest_composite_bp,
            "regime": regime,
            "horizons": list(HORIZONS_DAYS.keys()),
            "thresholds_bp": {
                "aggressive": THRESHOLD_AGGRESSIVE,
                "normal": THRESHOLD_NORMAL,
            },
            "interpretation": (
                "Mean change in effective federal funds rate over 3M/6M/12M "
                "horizons, in basis points. Positive = tightening; negative = easing."
            ),
        }, "ffr_change.interpretation")
        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=composite,
            subindex_values=sub,
            metadata=meta,
        )
