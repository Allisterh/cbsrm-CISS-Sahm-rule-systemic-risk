"""
cbsrm.macro — macro-economic indicators and regime classifiers.

Each module is a self-contained IIndicator implementation that consumes one or
more FRED series and emits a stress-relevant macro signal. The macro layer
sits one level above the L2 stress indicators (cbsrm.indicators) — these are
slower-moving condition variables that gate / weight the stress signals.

v0.3 inventory
--------------
- YieldCurveIndicator      — T10Y3M / T10Y2Y inversion + Estrella-Mishkin
                              recession-probability probit (NY Fed)
- NFPMomentumIndicator     — non-farm payroll YoY-change z-score (rolling)
- FFRChangeIndicator       — federal funds rate 3M/6M/12M change momentum
- DXYRegimeIndicator       — broad trade-weighted USD index trend regime
- MacroCompositeIndicator  — 4-state aggregate regime
                              (risk-on / risk-off / transition-up / transition-down)

Planned (post-v0.3)
-------------------
- CPISurpriseIndicator     — CPI YoY vs trailing 3yr median
- FFRFuturesPath           — fed-funds-futures implied policy path (needs CME)
- OilMacroIndicator        — WTI term-structure + OVX + geopolitical premium
- CreditSpreadRegime       — HY / IG spread regime classifier

Design note
-----------
Macro indicators share the IIndicator protocol with stress indicators because
the audit chain, dossier renderer, replication harness, and CLI driver are
all written against that one interface. New macro modules slot into the same
infrastructure without touching the audit / API / diagnostics layers.
"""
from cbsrm.macro import macro_events
from cbsrm.macro.cpi_surprise import CPISurpriseIndicator
from cbsrm.macro.credit_spread_regime import CreditSpreadRegimeIndicator
from cbsrm.macro.dxy_regime import DXYRegimeIndicator
from cbsrm.macro.ffr_change import FFRChangeIndicator
from cbsrm.macro.jpy_regime import JPYRegimeIndicator
from cbsrm.macro.macro_composite import (
    MACRO_REGIMES,
    MacroCompositeIndicator,
    classify_regime,
)
from cbsrm.macro.nfp_momentum import NFPMomentumIndicator
from cbsrm.macro.oil_macro import OilMacroIndicator
from cbsrm.macro.phase_classifier import (
    DEFAULT_CONFIG as PHASE_DEFAULT_CONFIG,
    PHASE_LABELS,
    PhaseClassifierConfig,
    RISK_POSTURES,
    classify_phase,
)
from cbsrm.macro.sahm_rule import SahmRuleIndicator
from cbsrm.macro.yield_curve import (
    YieldCurveIndicator,
    estrella_mishkin_recession_prob,
)

__all__ = [
    "YieldCurveIndicator",
    "estrella_mishkin_recession_prob",
    "NFPMomentumIndicator",
    "FFRChangeIndicator",
    "DXYRegimeIndicator",
    "JPYRegimeIndicator",
    "CPISurpriseIndicator",
    "OilMacroIndicator",
    "CreditSpreadRegimeIndicator",
    "SahmRuleIndicator",
    "MacroCompositeIndicator",
    "MACRO_REGIMES",
    "classify_regime",
    "macro_events",
    "classify_phase",
    "PhaseClassifierConfig",
    "PHASE_DEFAULT_CONFIG",
    "PHASE_LABELS",
    "RISK_POSTURES",
]
