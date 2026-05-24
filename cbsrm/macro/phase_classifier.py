"""
Acemoglu-style macro/market phase classifier.

A *deterministic, offline, feature-driven* classifier that labels a snapshot
of pre-computed macro and market features into one of eight interpretable
phases. Intended as a **research classification layer** — not a live signal,
not a trading rule, not an execution gate.

Where ``macro_composite.classify_regime`` produces a 4-state risk-on / risk-off
regime from raw sub-indicator metadata, this module produces a richer 8-phase
taxonomy from caller-supplied normalised features. The two are complementary:
the composite answers "what is the current risk-tone of the market?"; the
phase classifier answers "what macro-economic regime are we currently in?"

Naming
~~~~~~

"Acemoglu-style" is shorthand for the Acemoglu-Ozdaglar-Tahbaz-Salehi (2015)
network-resilience framework as adapted to macro phase labelling: phases
distinguish regimes where shocks are likely to be *distributed* (expansion,
disinflationary_recovery) from regimes where they are likely to be *amplified*
(overheating, stagflationary_stress, financial_stress). This module does NOT
implement the original network propagation paper — for that see
``cbsrm.networks.debt_rank``. It implements a phase taxonomy that ladders into
the same risk-amplification narrative.

Inputs
~~~~~~

Caller supplies a feature dict (or a ``pandas.Series`` / ``pandas.DataFrame``)
with z-scored macro/market readings. All inputs are optional except that
the classifier needs *some* features to produce a non-indeterminate label.
Supported features:

* ``growth_z``           — GDP / NFP / activity momentum z-score (+ve = expanding)
* ``inflation_z``        — CPI / PCE z-score (+ve = hotter than trend)
* ``unemployment_z``     — UNRATE z-score (+ve = labour weakening)
* ``rates_z``            — policy-tightness z-score (+ve = tightening)
* ``credit_spread_z``    — HY / IG spread z-score (+ve = widening = stress)
* ``volatility_z``       — VIX / MOVE z-score (+ve = stress)
* ``liquidity_z``        — broad FCI / dollar / repo z-score (+ve = looser)
* ``systemic_risk_z``    — DebtRank or systemic-stress z-score (+ve = elevated)

Either ``unemployment_z`` or ``labor_slack_z`` is accepted (treated as
synonyms; ``labor_slack_z`` wins if both are supplied).

Outputs
~~~~~~~

For single-row input → a dict with::

    {
      "phase": str,                       # one of PHASE_LABELS
      "score": float,                     # confidence in [0, 1]
      "dominant_drivers": list[str],      # features with |z| >= 1, magnitude-sorted
      "risk_posture": str,                # one of RISK_POSTURES
      "input_features_used": list[str],   # the canonical feature names actually consumed
      "rule_version": str,                # spec version of the rule book
      "spec": dict,                       # the human-readable rule descriptions
    }

For DataFrame batch input → a ``pandas.DataFrame`` with one row per input
row and columns ``phase / score / dominant_drivers / risk_posture /
n_features_used``. The index is preserved.

Validation
~~~~~~~~~~

* Non-finite values (NaN/inf) anywhere in the supplied features raise
  ``ValueError``.
* Empty DataFrame raises ``ValueError``.
* Unsupported feature keys (typos like ``inflaton_z``) raise ``ValueError``
  to surface caller mistakes early.
* Missing fields are handled gracefully — the classifier degrades to
  ``indeterminate`` if too few features are present to support a rule.

Determinism
~~~~~~~~~~~

The classifier is a pure function. Same input → same output. No random
state, no I/O, no clock, no environment lookups. Safe to call from tests,
notebooks, and audited replay pipelines.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd


# ─── Public constants ──────────────────────────────────────────────


PHASE_LABELS: tuple[str, ...] = (
    "expansion",
    "overheating",
    "slowdown",
    "contraction",
    "disinflationary_recovery",
    "stagflationary_stress",
    "financial_stress",
    "indeterminate",
)


RISK_POSTURES: tuple[str, ...] = (
    "risk_on",
    "balanced",
    "defensive",
    "risk_off",
    "stress_mitigation",
)


SUPPORTED_FEATURES: tuple[str, ...] = (
    "growth_z",
    "inflation_z",
    "unemployment_z",
    "labor_slack_z",   # synonym of unemployment_z
    "rates_z",
    "credit_spread_z",
    "volatility_z",
    "liquidity_z",
    "systemic_risk_z",
)


RULE_VERSION = "1.0.0"


# ─── Config ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PhaseClassifierConfig:
    """Threshold knobs for the deterministic phase rules.

    All thresholds are in z-score units (so ``inflation_hot=1.0`` means
    ``inflation_z >= 1.0`` is considered "hot"). Defaults are conservative
    and were chosen to produce a balanced phase distribution on a roughly
    standardised feature panel.
    """

    growth_hot: float = 0.5
    growth_cool: float = -0.5
    growth_cold: float = -1.0
    inflation_hot: float = 1.0
    inflation_cool: float = -0.5
    unemployment_rising: float = 1.0
    unemployment_falling: float = -0.5
    credit_spread_stress: float = 1.5
    credit_spread_widening: float = 0.5
    credit_spread_tightening: float = -0.5
    volatility_stress: float = 1.5
    systemic_stress: float = 1.5
    rates_tight: float = 0.0   # +ve rates_z already means tightening
    driver_threshold: float = 1.0   # |z| >= this → counted as a dominant driver

    # Minimum number of non-missing features required to produce a
    # non-indeterminate label.
    min_features_for_classification: int = 3


DEFAULT_CONFIG = PhaseClassifierConfig()


# ─── Helpers ────────────────────────────────────────────────────────


def _canonicalise_features(raw: Mapping[str, Any]) -> dict[str, float]:
    """Validate keys + values, normalise synonyms, return canonical floats.

    - Unknown keys raise ValueError.
    - Non-finite values raise ValueError.
    - Returns only the canonical 8-feature key set (no synonyms in output).
    - ``labor_slack_z`` is folded into ``unemployment_z`` (label wins if both
      supplied; the latter would be unusual, but explicit is better than
      surprising).
    """
    out: dict[str, float] = {}
    unknown = [k for k in raw if k not in SUPPORTED_FEATURES]
    if unknown:
        raise ValueError(
            f"phase_classifier: unsupported feature key(s) {unknown!r}; "
            f"supported = {list(SUPPORTED_FEATURES)}"
        )

    for k, v in raw.items():
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"phase_classifier: feature {k!r} must be a finite number, "
                f"got {v!r}"
            ) from exc
        if not math.isfinite(f):
            raise ValueError(
                f"phase_classifier: feature {k!r} is non-finite ({f!r}); "
                "drop the feature or impute before calling."
            )
        # Fold labor_slack_z → unemployment_z if explicit unemployment_z
        # is absent. If both supplied, labor_slack_z wins (clarified above).
        if k == "labor_slack_z":
            out["unemployment_z"] = f
        else:
            out[k] = f
    return out


def _dominant_drivers(
    features: Mapping[str, float], threshold: float
) -> list[str]:
    items = [(k, abs(v)) for k, v in features.items() if abs(v) >= threshold]
    items.sort(key=lambda kv: kv[1], reverse=True)
    return [k for k, _ in items]


def _phase_for(
    features: dict[str, float], cfg: PhaseClassifierConfig
) -> tuple[str, float, str, list[str]]:
    """Return (phase, score, risk_posture, fired_rules).

    Rule priority (highest first):
        1. financial_stress override
        2. stagflationary_stress
        3. overheating
        4. contraction
        5. slowdown
        6. expansion
        7. disinflationary_recovery
        8. indeterminate fallback
    """
    g = features.get("growth_z")
    inf = features.get("inflation_z")
    u = features.get("unemployment_z")
    cs = features.get("credit_spread_z")
    vol = features.get("volatility_z")
    sys = features.get("systemic_risk_z")
    r = features.get("rates_z")

    n_features = len(features)
    if n_features < cfg.min_features_for_classification:
        return ("indeterminate", 0.0, "balanced",
                ["INSUFFICIENT_FEATURES"])

    fired: list[str] = []

    # 1) financial_stress — any single stress channel screams loudly.
    stress_signals = []
    if cs is not None and cs >= cfg.credit_spread_stress:
        stress_signals.append(("credit_spread_z", cs / cfg.credit_spread_stress))
    if vol is not None and vol >= cfg.volatility_stress:
        stress_signals.append(("volatility_z", vol / cfg.volatility_stress))
    if sys is not None and sys >= cfg.systemic_stress:
        stress_signals.append(("systemic_risk_z", sys / cfg.systemic_stress))
    if stress_signals:
        magnitude = max(m for _, m in stress_signals)
        score = min(1.0, magnitude / 2.0)   # 2x threshold = full confidence
        fired = [f"STRESS:{name}" for name, _ in stress_signals]
        return ("financial_stress", score, "stress_mitigation", fired)

    # 2) stagflationary_stress — high inflation + weak growth.
    if (inf is not None and inf >= cfg.inflation_hot
            and g is not None and g <= cfg.growth_cool):
        score = min(1.0, 0.5 * (
            (inf / cfg.inflation_hot) + (abs(g) / abs(cfg.growth_cool))
        ) / 2.0 + 0.5)
        fired = ["STAG:inflation_z_hot", "STAG:growth_z_cool"]
        return ("stagflationary_stress", score, "defensive", fired)

    # 3) overheating — hot growth + hot inflation (optional tightening).
    if (g is not None and g >= cfg.growth_hot
            and inf is not None and inf >= cfg.inflation_hot):
        score = min(1.0, 0.5 + 0.25 * (g / cfg.growth_hot)
                    + 0.25 * (inf / cfg.inflation_hot))
        fired = ["OVERHEAT:growth_z_hot", "OVERHEAT:inflation_z_hot"]
        if r is not None and r > cfg.rates_tight:
            fired.append("OVERHEAT:rates_z_tightening")
        return ("overheating", min(1.0, score), "defensive", fired)

    # 4) contraction — collapsing growth + labour weakening + credit widening.
    contraction_hits = 0
    contraction_fired = []
    if g is not None and g <= cfg.growth_cold:
        contraction_hits += 1
        contraction_fired.append("CONTRACT:growth_z_cold")
    if u is not None and u >= cfg.unemployment_rising:
        contraction_hits += 1
        contraction_fired.append("CONTRACT:unemployment_z_rising")
    if cs is not None and cs >= cfg.credit_spread_widening:
        contraction_hits += 1
        contraction_fired.append("CONTRACT:credit_spread_z_widening")
    if contraction_hits >= 2:
        score = min(1.0, 0.5 + 0.15 * contraction_hits)
        return ("contraction", score, "risk_off", contraction_fired)

    # 5) slowdown — softening growth without acute stress.
    if (g is not None and cfg.growth_cold < g <= cfg.growth_cool
            and (cs is None or cs <= cfg.credit_spread_widening)):
        score = min(1.0, 0.4 + 0.3 * (abs(g) / abs(cfg.growth_cool)))
        fired = ["SLOWDOWN:growth_z_cool"]
        if cs is not None and cs > 0:
            fired.append("SLOWDOWN:credit_spread_z_drifting")
        return ("slowdown", score, "defensive", fired)

    # 6) expansion — solid growth + inflation in band + credit tightening.
    if (g is not None and g >= cfg.growth_hot
            and (inf is None or cfg.inflation_cool <= inf < cfg.inflation_hot)
            and (cs is None or cs <= cfg.credit_spread_tightening)):
        score = min(1.0, 0.5 + 0.3 * (g / cfg.growth_hot))
        fired = ["EXPAND:growth_z_hot"]
        if cs is not None:
            fired.append("EXPAND:credit_spread_z_tightening")
        return ("expansion", score, "risk_on", fired)

    # 7) disinflationary_recovery — growth recovering + inflation cooling
    #    + labour normalising.
    if (g is not None and g >= 0.0
            and inf is not None and inf <= cfg.inflation_cool
            and (u is None or u <= cfg.unemployment_falling)):
        score = min(1.0, 0.4 + 0.3 * abs(inf / cfg.inflation_cool)
                    + 0.2 * (g / max(cfg.growth_hot, 1e-9)))
        fired = ["DISINFL:inflation_z_cool", "DISINFL:growth_z_positive"]
        if u is not None:
            fired.append("DISINFL:unemployment_z_falling")
        return ("disinflationary_recovery", min(1.0, score), "risk_on", fired)

    # 8) indeterminate fallback
    return ("indeterminate", 0.0, "balanced", ["NO_RULE_FIRED"])


# ─── Public API ────────────────────────────────────────────────────


def classify_phase(
    features: Mapping[str, Any] | pd.Series | pd.DataFrame,
    *,
    config: PhaseClassifierConfig | None = None,
) -> dict[str, Any] | pd.DataFrame:
    """Classify a macro/market-feature snapshot into an Acemoglu-style phase.

    Parameters
    ----------
    features :
        Either a single-row input (``dict`` / ``pandas.Series``) or a batch
        input (``pandas.DataFrame`` with feature names as columns).
    config :
        Optional :class:`PhaseClassifierConfig`. Defaults to :data:`DEFAULT_CONFIG`.

    Returns
    -------
    dict | pandas.DataFrame
        - For single-row input: a dict with keys ``phase``, ``score``,
          ``dominant_drivers``, ``risk_posture``, ``input_features_used``,
          ``rule_version``, ``spec``.
        - For DataFrame input: a DataFrame with columns ``phase``, ``score``,
          ``dominant_drivers``, ``risk_posture``, ``n_features_used``.
          Input index is preserved.
    """
    cfg = config or DEFAULT_CONFIG

    if isinstance(features, pd.DataFrame):
        if features.empty:
            raise ValueError(
                "phase_classifier: input DataFrame is empty; "
                "supply at least one row of features."
            )
        # Validate columns up-front so a typo fails fast on the whole batch.
        unknown_cols = [c for c in features.columns if c not in SUPPORTED_FEATURES]
        if unknown_cols:
            raise ValueError(
                f"phase_classifier: unsupported column(s) {unknown_cols!r}; "
                f"supported = {list(SUPPORTED_FEATURES)}"
            )
        rows: list[dict[str, Any]] = []
        for _, raw in features.iterrows():
            d = {k: v for k, v in raw.items() if pd.notna(v)}
            canon = _canonicalise_features(d)
            phase, score, posture, fired = _phase_for(canon, cfg)
            rows.append({
                "phase": phase,
                "score": score,
                "dominant_drivers": _dominant_drivers(canon, cfg.driver_threshold),
                "risk_posture": posture,
                "n_features_used": len(canon),
            })
        return pd.DataFrame(rows, index=features.index)

    if isinstance(features, pd.Series):
        raw_dict = {k: v for k, v in features.items() if pd.notna(v)}
    elif isinstance(features, Mapping):
        raw_dict = dict(features)
    else:
        raise ValueError(
            "phase_classifier: features must be a dict, pandas.Series, or "
            f"pandas.DataFrame; got {type(features).__name__}"
        )

    canon = _canonicalise_features(raw_dict)
    phase, score, posture, fired = _phase_for(canon, cfg)
    return {
        "phase": phase,
        "score": score,
        "dominant_drivers": _dominant_drivers(canon, cfg.driver_threshold),
        "risk_posture": posture,
        "input_features_used": sorted(canon.keys()),
        "rule_version": RULE_VERSION,
        "spec": {
            "rules_fired": fired,
            "phase_labels": list(PHASE_LABELS),
            "risk_postures": list(RISK_POSTURES),
            "config": {
                "growth_hot": cfg.growth_hot,
                "growth_cool": cfg.growth_cool,
                "growth_cold": cfg.growth_cold,
                "inflation_hot": cfg.inflation_hot,
                "inflation_cool": cfg.inflation_cool,
                "unemployment_rising": cfg.unemployment_rising,
                "unemployment_falling": cfg.unemployment_falling,
                "credit_spread_stress": cfg.credit_spread_stress,
                "credit_spread_widening": cfg.credit_spread_widening,
                "credit_spread_tightening": cfg.credit_spread_tightening,
                "volatility_stress": cfg.volatility_stress,
                "systemic_stress": cfg.systemic_stress,
                "rates_tight": cfg.rates_tight,
                "driver_threshold": cfg.driver_threshold,
                "min_features_for_classification":
                    cfg.min_features_for_classification,
            },
            "interpretation": (
                "Deterministic feature-driven phase label. Research / "
                "decision-intelligence layer; not a trading signal. "
                "Pair with cbsrm.macro.macro_composite.classify_regime for "
                "the 4-state risk-tone overlay."
            ),
        },
    }


__all__ = [
    "classify_phase",
    "PhaseClassifierConfig",
    "DEFAULT_CONFIG",
    "PHASE_LABELS",
    "RISK_POSTURES",
    "SUPPORTED_FEATURES",
    "RULE_VERSION",
]
