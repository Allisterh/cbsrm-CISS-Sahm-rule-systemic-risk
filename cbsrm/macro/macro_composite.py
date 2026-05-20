"""
Macro-regime composite indicator (4-state).

Aggregates the four CBSRM macro sub-indicators (yield curve, NFP momentum,
FFR change, DXY regime) into one labelled 4-state regime variable used by
downstream consumers (notably VolanX's regime-conditional position sizer).

States
------

The output state space is::

    RISK_ON              — macro tailwinds aligned, no recession signal
    TRANSITION_DOWN      — deteriorating, but no acute stress yet
    TRANSITION_UP        — bottoming, early recovery signs
    RISK_OFF             — recession signal present OR aggressive tightening
                           OR severe payroll deceleration OR persistent inversion

A fifth bucket — ``INSUFFICIENT_HISTORY`` — applies when any sub-indicator
has fewer observations than its minimum for classification.

Scoring rule (deterministic, audit-traceable)
---------------------------------------------

Each sub-indicator contributes a real-valued score in [-1, +1] with negative
meaning risk-off pressure and positive meaning risk-on:

* **yield_curve**     ``+1`` if recession_prob < 10%, linearly interpolated
                       to ``-1`` if recession_prob >= 50% (NY-Fed published
                       50% threshold). Persistent inversion subtracts a
                       further 0.5.

* **nfp_momentum**    ``z`` clipped to ``[-2, +2]`` then divided by 2.
                       Severe-deceleration regime adds a further -0.25.

* **ffr_change**      ``+1`` for EASING / AGGRESSIVE_EASING (rate cuts are
                       risk-on); ``0`` for PAUSE; ``-0.5`` for TIGHTENING;
                       ``-1`` for AGGRESSIVE_TIGHTENING.

* **dxy_regime**      ``+0.5`` for DOLLAR_BEAR, ``+1`` for STRONG_DOLLAR_BEAR
                       (weaker dollar = looser global FCI); symmetric for
                       bull regimes.

Composite ``S`` = simple mean of the four scores (range [-1, +1]).

State mapping::

    S >= +0.4    → RISK_ON
    -0.1 < S < +0.4 → TRANSITION_UP
    -0.4 < S <= -0.1 → TRANSITION_DOWN
    S <= -0.4    → RISK_OFF

Hard overrides (independent of S) that force RISK_OFF:

* yield_curve persistent inversion AND recession_prob > 30%
* ffr_change regime = AGGRESSIVE_TIGHTENING
* nfp_momentum classification = SEVERE_DECELERATION

These three are catastrophic-condition triggers documented in Estrella-Mishkin
(1996), Sahm (2019), and operative Fed-Funds-cycle empirics (Bauer-Swanson 2023).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from cbsrm.i18n import with_i18n
from cbsrm.indicators.base import IndicatorResult
from cbsrm.macro.dxy_regime import DXYRegimeIndicator
from cbsrm.macro.ffr_change import FFRChangeIndicator
from cbsrm.macro.nfp_momentum import NFPMomentumIndicator
from cbsrm.macro.yield_curve import YieldCurveIndicator


MACRO_REGIMES = (
    "RISK_ON",
    "TRANSITION_UP",
    "TRANSITION_DOWN",
    "RISK_OFF",
    "INSUFFICIENT_HISTORY",
)


def _yield_score(yc: dict[str, Any]) -> float:
    p = yc.get("latest_recession_prob_12mo")
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return 0.0
    # +1 at p=0.10, 0 at p=0.30, -1 at p=0.50
    if p <= 0.10:
        s = 1.0
    elif p >= 0.50:
        s = -1.0
    elif p <= 0.30:
        s = 1.0 - (p - 0.10) / 0.20
    else:
        s = 0.0 - (p - 0.30) / 0.20
    if yc.get("latest_days_inverted_run", 0) >= yc.get(
        "persistent_inversion_days_threshold", 60
    ):
        s -= 0.5
    return max(-1.5, min(1.0, s))


def _nfp_score(nfp: dict[str, Any]) -> float:
    z = nfp.get("latest_z")
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return 0.0
    s = max(-2.0, min(2.0, z)) / 2.0
    if nfp.get("classification") == "SEVERE_DECELERATION":
        s -= 0.25
    return max(-1.25, min(1.0, s))


def _ffr_score(ffr: dict[str, Any]) -> float:
    regime = ffr.get("regime", "INSUFFICIENT_HISTORY")
    return {
        "AGGRESSIVE_EASING": 1.0,
        "EASING": 0.5,
        "PAUSE": 0.0,
        "TIGHTENING": -0.5,
        "AGGRESSIVE_TIGHTENING": -1.0,
        "INSUFFICIENT_HISTORY": 0.0,
    }.get(regime, 0.0)


def _dxy_score(dxy: dict[str, Any]) -> float:
    regime = dxy.get("regime", "INSUFFICIENT_HISTORY")
    return {
        "STRONG_DOLLAR_BEAR": 1.0,
        "DOLLAR_BEAR": 0.5,
        "NEUTRAL": 0.0,
        "DOLLAR_BULL": -0.5,
        "STRONG_DOLLAR_BULL": -1.0,
        "INSUFFICIENT_HISTORY": 0.0,
    }.get(regime, 0.0)


def _check_overrides(
    yc: dict[str, Any], nfp: dict[str, Any], ffr: dict[str, Any]
) -> list[str]:
    """Return list of hard-override reasons that force RISK_OFF."""
    triggers: list[str] = []
    p = yc.get("latest_recession_prob_12mo")
    inv_run = yc.get("latest_days_inverted_run", 0)
    thresh = yc.get("persistent_inversion_days_threshold", 60)
    if p is not None and not math.isnan(p) and p > 0.30 and inv_run >= thresh:
        triggers.append("PERSISTENT_INVERSION_WITH_HIGH_RECESSION_PROB")
    if ffr.get("regime") == "AGGRESSIVE_TIGHTENING":
        triggers.append("AGGRESSIVE_TIGHTENING")
    if nfp.get("classification") == "SEVERE_DECELERATION":
        triggers.append("SEVERE_PAYROLL_DECELERATION")
    return triggers


def classify_regime(
    yield_meta: dict[str, Any],
    nfp_meta: dict[str, Any],
    ffr_meta: dict[str, Any],
    dxy_meta: dict[str, Any],
) -> dict[str, Any]:
    """Pure function: 4 sub-indicator metadata dicts → composite verdict.

    Exposed for testing and for callers that have already computed sub-indicators
    (so the composite can be re-run without re-fetching data).
    """
    if any(
        (m.get("n_obs", 0) == 0) or (m.get("regime") == "INSUFFICIENT_HISTORY")
        or (m.get("classification") == "INSUFFICIENT_HISTORY")
        for m in (yield_meta, nfp_meta, ffr_meta, dxy_meta)
    ):
        return {
            "regime": "INSUFFICIENT_HISTORY",
            "composite_score": float("nan"),
            "sub_scores": {},
            "override_triggers": [],
        }

    sub_scores = {
        "yield_curve": _yield_score(yield_meta),
        "nfp_momentum": _nfp_score(nfp_meta),
        "ffr_change": _ffr_score(ffr_meta),
        "dxy_regime": _dxy_score(dxy_meta),
    }
    composite = sum(sub_scores.values()) / 4.0

    overrides = _check_overrides(yield_meta, nfp_meta, ffr_meta)
    if overrides:
        regime = "RISK_OFF"
    elif composite >= 0.4:
        regime = "RISK_ON"
    elif composite > -0.1:
        regime = "TRANSITION_UP"
    elif composite > -0.4:
        regime = "TRANSITION_DOWN"
    else:
        regime = "RISK_OFF"

    return {
        "regime": regime,
        "composite_score": composite,
        "sub_scores": sub_scores,
        "override_triggers": overrides,
    }


@dataclass
class MacroCompositeIndicator:
    """4-state macro regime composite.

    Unlike the individual macro indicators, this one expects ALL underlying
    FRED series in the ``data`` DataFrame (T10Y3M, PAYEMS, DFF, DTWEXBGS) and
    runs the four sub-indicators internally.
    """

    id: str = "MACRO-COMPOSITE-US"
    version: str = "1.0.0"
    source: str = (
        "Composite of: NY-Fed Estrella-Mishkin recession probit (FRED T10Y3M); "
        "BLS payroll momentum z-score (FRED PAYEMS); "
        "Federal Reserve H.15 effective fed funds change (FRED DFF); "
        "Federal Reserve Board H.10 broad USD trend (FRED DTWEXBGS)."
    )

    def required_series(self) -> list[str]:
        return ["T10Y3M", "PAYEMS", "DFF", "DTWEXBGS"]

    def compute(self, data: pd.DataFrame) -> IndicatorResult:
        missing = [c for c in self.required_series() if c not in data.columns]
        if missing:
            raise ValueError(
                f"{self.id}.compute() missing columns: {missing}; "
                f"got {list(data.columns)}"
            )

        yc_res = YieldCurveIndicator().compute(data[["T10Y3M"]])
        nfp_res = NFPMomentumIndicator().compute(data[["PAYEMS"]])
        ffr_res = FFRChangeIndicator().compute(data[["DFF"]])
        dxy_res = DXYRegimeIndicator().compute(data[["DTWEXBGS"]])

        verdict = classify_regime(
            yc_res.metadata, nfp_res.metadata, ffr_res.metadata, dxy_res.metadata
        )

        # Composite series — daily; computed as running mean of the four
        # standardised sub-scores aligned at the latest available date.
        # For the historical series, we recompute the composite at each date
        # the four sub-indicators all have values.
        sub_series: list[pd.Series] = []

        # Yield-curve score over time
        yc_vals = yc_res.values  # recession prob in [0, 1]
        yc_score = yc_vals.apply(
            lambda p: 1.0 if p <= 0.10 else (-1.0 if p >= 0.50 else (1.0 - (p - 0.10) / 0.20 if p <= 0.30 else 0.0 - (p - 0.30) / 0.20))
        ).rename("yc_score")
        sub_series.append(yc_score)

        # NFP score over time (z clipped /2)
        nfp_vals = nfp_res.values
        nfp_score = nfp_vals.clip(-2.0, 2.0).div(2.0).rename("nfp_score")
        sub_series.append(nfp_score)

        # FFR composite-change is in bp; -1 at -200bp, +1 at +200bp (clipped)
        ffr_vals = ffr_res.values  # mean change in bp
        ffr_score = (-ffr_vals / 200.0).clip(-1.0, 1.0).rename("ffr_score")
        sub_series.append(ffr_score)

        # DXY z is in [-3, +3] typically; -z / 1.5 clipped to [-1, +1]
        dxy_vals = dxy_res.values
        dxy_score = (-dxy_vals / 1.5).clip(-1.0, 1.0).rename("dxy_score")
        sub_series.append(dxy_score)

        # Align (outer join) then forward-fill within reason (max 30 days) so
        # monthly NFP doesn't blow away the daily score.
        sub_df = pd.concat(sub_series, axis=1).sort_index()
        # Forward-fill NFP and macro-monthly cadence indicators
        sub_df["nfp_score"] = sub_df["nfp_score"].ffill(limit=45)
        sub_df = sub_df.dropna()
        composite = sub_df.mean(axis=1).rename(self.id)

        meta: dict[str, Any] = with_i18n({
            "source": self.source,
            "n_obs": int(composite.size),
            "first_date": str(composite.index.min()) if not composite.empty else None,
            "last_date": str(composite.index.max()) if not composite.empty else None,
            "latest_regime": verdict["regime"],
            "latest_composite_score": verdict["composite_score"],
            "latest_sub_scores": verdict["sub_scores"],
            "latest_override_triggers": verdict["override_triggers"],
            "sub_indicators": {
                "yield_curve": yc_res.metadata,
                "nfp_momentum": nfp_res.metadata,
                "ffr_change": ffr_res.metadata,
                "dxy_regime": dxy_res.metadata,
            },
            "regime_definitions": {
                "RISK_ON": "composite >= +0.4 and no hard overrides",
                "TRANSITION_UP": "-0.1 < composite < +0.4",
                "TRANSITION_DOWN": "-0.4 < composite <= -0.1",
                "RISK_OFF": "composite <= -0.4 OR hard override triggered",
                "INSUFFICIENT_HISTORY": "any sub-indicator below min obs",
            },
        }, "macro_composite.interpretation")
        return IndicatorResult(
            indicator_id=self.id,
            version=self.version,
            values=composite,
            subindex_values=sub_df,
            metadata=meta,
        )
