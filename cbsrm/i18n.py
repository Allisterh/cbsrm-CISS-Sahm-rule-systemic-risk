"""
Multi-language label dictionary for indicator interpretations.

Supported locales (v0.3): ``en``, ``ja``, ``es``, ``fr``, ``de``.

Usage
-----

Indicators embed the localised label set in their metadata via
``with_i18n(metadata, key)``. Consumers (CLI, dashboard, API) can pick a
locale at render time::

    meta = result.metadata
    interp = meta["interpretation_i18n"]["ja"]   # Japanese
    # or
    interp = meta["interpretation_i18n"].get(locale, meta["interpretation_i18n"]["en"])

Design notes
------------

* English is the canonical source. All other locales are reviewed translations.
* Locale codes are lowercase ISO-639-1 (``en``, ``ja``, ``es``, ``fr``, ``de``).
* Indicators that need new labels register them in ``LABELS`` keyed by an
  internal label-key (e.g. ``"yield_curve.interpretation"``).
* Missing translations fall back to English at lookup time, with a warning.

This module is dependency-free (no Babel, no gettext) for portability — the
goal is a research artefact, not a production i18n stack.
"""
from __future__ import annotations

from typing import Any

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "ja", "es", "fr", "de")
FALLBACK_LOCALE: str = "en"


# ─── Translation table ──────────────────────────────────────────────


LABELS: dict[str, dict[str, str]] = {
    # ── Yield curve ────────────────────────────────────────────────
    "yield_curve.interpretation": {
        "en": (
            "Recession probability 12 months out, conditional on current "
            "10Y-3M Treasury spread, via Estrella-Mishkin probit. "
            "Persistent inversion = run-length above the threshold trading days."
        ),
        "ja": (
            "10年-3か月の米国債スプレッドに基づくEstrella-Mishkinプロビット・モデル"
            "による、12か月先の景気後退確率。継続的な逆イールド = "
            "閾値営業日数を上回る連続日数。"
        ),
        "es": (
            "Probabilidad de recesión a 12 meses, condicional al diferencial "
            "actual del Tesoro a 10A-3M, mediante el probit de Estrella-Mishkin. "
            "Inversión persistente = racha mayor al umbral de días de mercado."
        ),
        "fr": (
            "Probabilité de récession à 12 mois, conditionnelle à l'écart "
            "actuel des bons du Trésor 10Y-3M, via le probit d'Estrella-Mishkin. "
            "Inversion persistante = série supérieure au seuil de jours ouvrés."
        ),
        "de": (
            "Rezessionswahrscheinlichkeit über 12 Monate, bedingt durch den "
            "aktuellen US-Treasury-Spread 10J-3M, via Estrella-Mishkin-Probit. "
            "Anhaltende Inversion = Lauflänge über dem Schwellen-Handelstageswert."
        ),
    },

    # ── NFP momentum ───────────────────────────────────────────────
    "nfp_momentum.interpretation": {
        "en": (
            "Rolling z-score of MoM log payroll growth vs trailing window. "
            "z>=+1 ACCELERATING, z<=-1 DECELERATING, z<=-2 SEVERE_DECELERATION."
        ),
        "ja": (
            "前月比対数雇用者数成長率の、過去ウィンドウに対するローリング"
            "z-スコア。z>=+1 加速、z<=-1 減速、z<=-2 深刻な減速。"
        ),
        "es": (
            "z-score móvil del crecimiento logarítmico mensual de la nómina "
            "frente a la ventana retrospectiva. z>=+1 ACELERANDO, "
            "z<=-1 DESACELERANDO, z<=-2 DESACELERACIÓN_GRAVE."
        ),
        "fr": (
            "z-score glissant de la croissance log mensuelle de l'emploi par "
            "rapport à la fenêtre rétrospective. z>=+1 ACCÉLÉRATION, "
            "z<=-1 DÉCÉLÉRATION, z<=-2 DÉCÉLÉRATION_GRAVE."
        ),
        "de": (
            "Gleitender z-Score des MoM-Log-Wachstums der Beschäftigtenzahl "
            "vs. zurückliegendes Fenster. z>=+1 BESCHLEUNIGUNG, "
            "z<=-1 VERLANGSAMUNG, z<=-2 SCHWERE_VERLANGSAMUNG."
        ),
    },

    # ── FFR change ─────────────────────────────────────────────────
    "ffr_change.interpretation": {
        "en": (
            "Mean change in effective federal funds rate over 3M/6M/12M "
            "horizons, in basis points. Positive = tightening; negative = easing."
        ),
        "ja": (
            "実効フェデラルファンド金利の3か月・6か月・12か月変化の平均"
            "（ベーシスポイント）。正 = 引き締め、負 = 緩和。"
        ),
        "es": (
            "Cambio medio de la tasa efectiva de fondos federales en horizontes "
            "de 3M/6M/12M, en puntos básicos. Positivo = endurecimiento; negativo = relajación."
        ),
        "fr": (
            "Variation moyenne du taux effectif des fonds fédéraux sur 3M/6M/12M, "
            "en points de base. Positif = resserrement ; négatif = assouplissement."
        ),
        "de": (
            "Mittlere Änderung des effektiven Federal Funds Rate über 3M/6M/12M "
            "in Basispunkten. Positiv = Straffung; negativ = Lockerung."
        ),
    },

    # ── DXY regime ─────────────────────────────────────────────────
    "dxy_regime.interpretation": {
        "en": (
            "Rolling z-score of the broad trade-weighted USD index over the "
            "trailing 252-day window. |z|>=1.5 is a strong-regime classification."
        ),
        "ja": (
            "広範な貿易加重ドル指数の、過去252営業日ウィンドウに対する"
            "ローリングz-スコア。|z|>=1.5は強気/弱気レジームの分類基準。"
        ),
        "es": (
            "z-score móvil del índice amplio del USD ponderado por comercio "
            "sobre la ventana retrospectiva de 252 días. |z|>=1.5 indica régimen fuerte."
        ),
        "fr": (
            "z-score glissant de l'indice large du dollar pondéré par les "
            "échanges sur 252 jours. |z|>=1.5 indique un régime fort."
        ),
        "de": (
            "Gleitender z-Score des breiten handelsgewichteten USD-Index über "
            "die zurückliegenden 252 Tage. |z|>=1.5 ist eine starke Regimeklassifikation."
        ),
    },

    # ── JPY regime ─────────────────────────────────────────────────
    "jpy_regime.interpretation": {
        "en": (
            "Rolling z-score of USD/JPY over the trailing 252-day window. "
            "|z|>=1.5 is a strong-regime classification. Positive z = USD strong "
            "vs JPY; negative z = JPY strong vs USD."
        ),
        "ja": (
            "ドル円の過去252営業日ウィンドウに対するローリングz-スコア。"
            "|z|>=1.5は強気/弱気レジーム。正のz = ドル高/円安、"
            "負のz = ドル安/円高。"
        ),
        "es": (
            "z-score móvil del USD/JPY sobre la ventana retrospectiva de 252 días. "
            "|z|>=1.5 indica régimen fuerte. z positivo = USD fuerte; z negativo = JPY fuerte."
        ),
        "fr": (
            "z-score glissant de l'USD/JPY sur 252 jours. |z|>=1.5 indique un "
            "régime fort. z positif = USD fort ; z négatif = JPY fort."
        ),
        "de": (
            "Gleitender z-Score des USD/JPY über die zurückliegenden 252 Tage. "
            "|z|>=1.5 ist eine starke Regimeklassifikation. Positiver z = USD stark; "
            "negativer z = JPY stark."
        ),
    },

    # ── Macro composite ────────────────────────────────────────────
    "macro_composite.interpretation": {
        "en": (
            "4-state aggregate regime over yield curve, payroll momentum, "
            "Fed funds change, and broad-USD regime. RISK_ON: macro tailwinds; "
            "TRANSITION_UP/DOWN: in flux; RISK_OFF: recession signal or aggressive tightening."
        ),
        "ja": (
            "イールドカーブ、雇用モメンタム、FF金利変化、広範なドルレジームに対する"
            "4状態の集約レジーム。RISK_ON: 追い風、TRANSITION_UP/DOWN: 変動中、"
            "RISK_OFF: 景気後退シグナルまたは積極的引き締め。"
        ),
        "es": (
            "Régimen agregado de 4 estados sobre curva de rendimientos, "
            "momentum de nómina, cambio en tasa Fed y régimen del USD. "
            "RISK_ON: vientos de cola; TRANSITION_UP/DOWN: en flujo; "
            "RISK_OFF: señal de recesión o endurecimiento agresivo."
        ),
        "fr": (
            "Régime agrégé à 4 états sur courbe des taux, momentum de l'emploi, "
            "variation du Fed funds et régime du dollar. RISK_ON: vents porteurs ; "
            "TRANSITION_UP/DOWN: en transition ; RISK_OFF: signal de récession ou "
            "resserrement agressif."
        ),
        "de": (
            "4-Zustands-Aggregatregime über Zinskurve, Lohn-Momentum, Fed-Funds-"
            "Änderung und breites USD-Regime. RISK_ON: makroökonomischer Rückenwind; "
            "TRANSITION_UP/DOWN: im Übergang; RISK_OFF: Rezessionssignal oder "
            "aggressive Straffung."
        ),
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────


def lookup(key: str, *, locale: str = "en") -> str:
    """Return the label for ``key`` in ``locale``. Falls back to English.

    Raises KeyError if ``key`` is not registered at all.
    """
    if key not in LABELS:
        raise KeyError(f"i18n key '{key}' is not registered. "
                       f"Known: {sorted(LABELS)}")
    by_locale = LABELS[key]
    if locale in by_locale:
        return by_locale[locale]
    # Fallback chain: requested → en → first available
    if FALLBACK_LOCALE in by_locale:
        return by_locale[FALLBACK_LOCALE]
    # Last resort: any available locale
    return next(iter(by_locale.values()))


def all_locales_for(key: str) -> dict[str, str]:
    """Return the full per-locale label set for ``key``."""
    if key not in LABELS:
        raise KeyError(f"i18n key '{key}' is not registered. "
                       f"Known: {sorted(LABELS)}")
    return dict(LABELS[key])


def with_i18n(meta: dict[str, Any], key: str) -> dict[str, Any]:
    """Add ``interpretation_i18n`` (full per-locale dict) to a metadata dict.

    Pure-additive: returns a new dict, does not mutate the input.
    """
    out = dict(meta)
    out["interpretation_i18n"] = all_locales_for(key)
    return out
