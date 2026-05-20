"""Tests for cbsrm.i18n."""
from __future__ import annotations

import pytest

from cbsrm.i18n import (
    FALLBACK_LOCALE,
    LABELS,
    SUPPORTED_LOCALES,
    all_locales_for,
    lookup,
    with_i18n,
)


# ─── Structural ─────────────────────────────────────────────────────


def test_supported_locales_complete():
    assert "en" in SUPPORTED_LOCALES
    assert "ja" in SUPPORTED_LOCALES
    assert "es" in SUPPORTED_LOCALES
    assert "fr" in SUPPORTED_LOCALES
    assert "de" in SUPPORTED_LOCALES


def test_fallback_is_english():
    assert FALLBACK_LOCALE == "en"


def test_every_label_has_all_supported_locales():
    """Every key in LABELS must have a translation for every supported locale."""
    for key, by_locale in LABELS.items():
        for loc in SUPPORTED_LOCALES:
            assert loc in by_locale, (
                f"label '{key}' is missing translation for locale '{loc}'"
            )
            assert by_locale[loc], f"label '{key}' has empty {loc} translation"


def test_macro_indicator_keys_registered():
    """All v0.3 macro indicators must have interpretation keys registered."""
    required = {
        "yield_curve.interpretation",
        "nfp_momentum.interpretation",
        "ffr_change.interpretation",
        "dxy_regime.interpretation",
        "jpy_regime.interpretation",
        "macro_composite.interpretation",
    }
    missing = required - set(LABELS.keys())
    assert not missing, f"missing label keys: {missing}"


# ─── lookup / all_locales_for ──────────────────────────────────────


def test_lookup_returns_correct_locale():
    en = lookup("yield_curve.interpretation", locale="en")
    ja = lookup("yield_curve.interpretation", locale="ja")
    assert en != ja
    assert "Estrella-Mishkin" in en
    # Japanese version mentions the model name in Latin script
    assert "Estrella-Mishkin" in ja


def test_lookup_unknown_locale_falls_back_to_english():
    en = lookup("yield_curve.interpretation", locale="en")
    fallback = lookup("yield_curve.interpretation", locale="xx")
    assert fallback == en


def test_lookup_unknown_key_raises():
    with pytest.raises(KeyError):
        lookup("nope.key", locale="en")


def test_all_locales_returns_complete_dict():
    out = all_locales_for("jpy_regime.interpretation")
    for loc in SUPPORTED_LOCALES:
        assert loc in out


def test_all_locales_unknown_key_raises():
    with pytest.raises(KeyError):
        all_locales_for("nope.key")


def test_all_locales_returns_copy_not_internal_dict():
    out = all_locales_for("jpy_regime.interpretation")
    out["fr"] = "MUTATED"
    fresh = all_locales_for("jpy_regime.interpretation")
    assert fresh["fr"] != "MUTATED"


# ─── with_i18n helper ───────────────────────────────────────────────


def test_with_i18n_adds_locale_dict():
    meta = {"source": "x", "n_obs": 5}
    out = with_i18n(meta, "yield_curve.interpretation")
    assert "interpretation_i18n" in out
    assert "en" in out["interpretation_i18n"]
    assert "ja" in out["interpretation_i18n"]


def test_with_i18n_returns_new_dict_no_mutation():
    meta = {"source": "x"}
    out = with_i18n(meta, "yield_curve.interpretation")
    assert "interpretation_i18n" not in meta
    assert out is not meta


def test_with_i18n_preserves_existing_keys():
    meta = {"source": "x", "n_obs": 5, "custom": True}
    out = with_i18n(meta, "ffr_change.interpretation")
    assert out["source"] == "x"
    assert out["n_obs"] == 5
    assert out["custom"] is True
