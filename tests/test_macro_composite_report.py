"""Tests for the v0.9 executable macro-composite report builder.

Pins the contract of the phase-classifier-only first cut:

* deterministic, JSON-serializable, fresh-copy-per-call
* fixture-backed and offline (no network)
* drift-guarded against the diagnostics-side ``_CrisisFixture``
* does NOT call ``build_crisis_dossier``
* does NOT call ``classify_regime`` (deferred to a later slice)
* narrow markdown renderer with stable, reproducible output
"""
from __future__ import annotations

import json

import pytest

from cbsrm.reporting import (
    MACRO_COMPOSITE_REPORT_VERSION,
    MACRO_COMPOSITE_WINDOWS,
    NFA_DISCLAIMER,
    build_macro_composite_report,
    list_macro_composite_windows,
    render_macro_composite_markdown,
)


# ─── version / windows shape ────────────────────────────────────────


def test_report_version_is_semver_like():
    parts = MACRO_COMPOSITE_REPORT_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts), MACRO_COMPOSITE_REPORT_VERSION


def test_windows_constant_is_canonical_three_tuple():
    assert MACRO_COMPOSITE_WINDOWS == ("2008Q4", "2020Q1", "2023Q1")


def test_list_windows_returns_list_with_pinned_order():
    out = list_macro_composite_windows()
    assert isinstance(out, list)
    assert out == ["2008Q4", "2020Q1", "2023Q1"]


def test_list_windows_is_deterministic_and_returns_fresh_list():
    a = list_macro_composite_windows()
    b = list_macro_composite_windows()
    assert a == b
    assert a is not b  # fresh list per call
    a.append("MUTATION")
    assert "MUTATION" not in list_macro_composite_windows()


# ─── unknown-window error contract ──────────────────────────────────


def test_unknown_window_raises_valueerror_with_supported_list():
    with pytest.raises(ValueError) as exc:
        build_macro_composite_report("9999Q9")
    msg = str(exc.value)
    assert "9999Q9" in msg
    assert "2008Q4" in msg  # supported list rendered into message


# ─── builder shape / determinism / JSON ─────────────────────────────


_REQUIRED_TOP_LEVEL_KEYS = {
    "report_id", "window_id", "title", "phase_features",
    "phase_classification", "research_notes", "disclaimer", "spec",
}


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_builder_has_required_top_level_keys(window_id):
    report = build_macro_composite_report(window_id)
    assert _REQUIRED_TOP_LEVEL_KEYS.issubset(report.keys())
    assert report["report_id"] == "macro-composite"
    assert report["window_id"] == window_id
    assert window_id in report["title"]


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_builder_is_deterministic(window_id):
    a = build_macro_composite_report(window_id)
    b = build_macro_composite_report(window_id)
    # Equal as Python objects.
    assert a == b
    # And byte-identical under sorted-key JSON serialisation.
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_builder_output_is_json_serializable(window_id):
    report = build_macro_composite_report(window_id)
    encoded = json.dumps(report)
    decoded = json.loads(encoded)
    assert decoded == report


def test_builder_returns_fresh_copy_per_call():
    a = build_macro_composite_report("2008Q4")
    a["title"] = "MUTATED"
    a["phase_features"]["growth_z"] = 99.0
    a["research_notes"].append("MUTATION")
    a["phase_classification"]["phase"] = "MUTATED"
    a["spec"]["windows"].append("MUTATED")
    b = build_macro_composite_report("2008Q4")
    assert b["title"] != "MUTATED"
    assert b["phase_features"]["growth_z"] != 99.0
    assert "MUTATION" not in b["research_notes"]
    assert b["phase_classification"]["phase"] != "MUTATED"
    assert "MUTATED" not in b["spec"]["windows"]


# ─── spec block ─────────────────────────────────────────────────────


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_spec_block_pins_versions_and_windows(window_id):
    report = build_macro_composite_report(window_id)
    spec = report["spec"]
    assert spec["report_id"] == "macro-composite"
    assert spec["report_version"] == MACRO_COMPOSITE_REPORT_VERSION
    assert spec["phase_classifier_rule_version"] == "1.0.0"
    assert spec["windows"] == ["2008Q4", "2020Q1", "2023Q1"]


# ─── phase_classification contract ──────────────────────────────────


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_phase_classification_rule_version_pinned(window_id):
    report = build_macro_composite_report(window_id)
    assert report["phase_classification"]["rule_version"] == "1.0.0"


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_phase_classification_carries_drivers_and_risk_posture(window_id):
    report = build_macro_composite_report(window_id)
    pc = report["phase_classification"]
    assert "dominant_drivers" in pc
    assert isinstance(pc["dominant_drivers"], list)
    assert "risk_posture" in pc
    assert isinstance(pc["risk_posture"], str)
    assert pc["risk_posture"]  # non-empty


# ─── drift guard against diagnostics fixture ────────────────────────


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_phase_features_match_diagnostics_fixture(window_id):
    """If the diagnostics-side ``_CrisisFixture.phase_features`` ever
    shifts for one of the shared windows, this test fires loudly and
    the operator must update both sides together. Accessed via the
    public ``get_fixture_snapshot`` seam — no private import needed."""
    from cbsrm.diagnostics.crisis_dossiers import get_fixture_snapshot

    diag = get_fixture_snapshot(window_id)["phase_features"]
    report = build_macro_composite_report(window_id)
    assert report["phase_features"] == diag


# ─── disclaimer ─────────────────────────────────────────────────────


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_disclaimer_equals_canonical_nfa(window_id):
    report = build_macro_composite_report(window_id)
    assert report["disclaimer"] == NFA_DISCLAIMER


# ─── offline contract ──────────────────────────────────────────────


def test_builder_is_offline_no_urllib_or_requests(monkeypatch):
    import urllib.request

    def _no_network(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError("macro-composite report must be offline")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    try:
        import requests  # type: ignore
    except ImportError:
        requests = None
    if requests is not None:
        monkeypatch.setattr(requests, "get", _no_network)
        monkeypatch.setattr(requests, "post", _no_network)

    # All three windows must build without touching the network.
    for window_id in ("2008Q4", "2020Q1", "2023Q1"):
        report = build_macro_composite_report(window_id)
        assert report["window_id"] == window_id


def test_builder_does_not_call_build_crisis_dossier(monkeypatch):
    """Pin that the macro-composite report does not piggy-back on the
    crisis-dossier builder. The two reports are siblings, not parent
    /child."""
    import cbsrm.diagnostics.crisis_dossiers as diag_mod

    def _no_dossier(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "macro-composite report must not call build_crisis_dossier"
        )

    monkeypatch.setattr(diag_mod, "build_crisis_dossier", _no_dossier)
    report = build_macro_composite_report("2008Q4")
    assert report["window_id"] == "2008Q4"


def test_builder_does_not_call_classify_regime(monkeypatch):
    """First-cut slice pins phase-classifier-only. Integration with
    ``classify_regime`` is deferred and must not silently start
    happening."""
    import cbsrm.macro.macro_composite as mc_mod

    def _no_regime(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "macro-composite report first cut must not call "
            "classify_regime"
        )

    monkeypatch.setattr(mc_mod, "classify_regime", _no_regime)
    report = build_macro_composite_report("2020Q1")
    assert report["window_id"] == "2020Q1"


# ─── markdown renderer ─────────────────────────────────────────────


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_render_markdown_returns_str(window_id):
    report = build_macro_composite_report(window_id)
    md = render_macro_composite_markdown(report)
    assert isinstance(md, str)
    assert md  # non-empty


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_render_markdown_contains_title_and_window(window_id):
    report = build_macro_composite_report(window_id)
    md = render_macro_composite_markdown(report)
    assert report["title"] in md
    assert window_id in md


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_render_markdown_carries_disclaimer_heading(window_id):
    report = build_macro_composite_report(window_id)
    md = render_macro_composite_markdown(report)
    assert "## Disclaimer" in md
    # Body of the disclaimer (or at least a recognisable substring of
    # the NFA boilerplate) is present.
    assert NFA_DISCLAIMER.strip().splitlines()[0] in md


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_render_markdown_ends_with_single_newline(window_id):
    report = build_macro_composite_report(window_id)
    md = render_macro_composite_markdown(report)
    assert md.endswith("\n")
    assert not md.endswith("\n\n\n")


@pytest.mark.parametrize("window_id", ["2008Q4", "2020Q1", "2023Q1"])
def test_render_markdown_is_deterministic(window_id):
    report = build_macro_composite_report(window_id)
    a = render_macro_composite_markdown(report)
    b = render_macro_composite_markdown(report)
    assert a == b


def test_render_markdown_rejects_non_mapping():
    with pytest.raises(ValueError):
        render_macro_composite_markdown("not a dict")  # type: ignore[arg-type]


def test_render_markdown_rejects_missing_keys():
    incomplete = {"report_id": "macro-composite", "window_id": "2008Q4"}
    with pytest.raises(ValueError) as exc:
        render_macro_composite_markdown(incomplete)
    msg = str(exc.value)
    assert "missing required keys" in msg
