"""Tests for the deterministic report-catalog registry.

The registry is a *read-only* directory of available reports. It must:

  * Contain the v0.8 ``crisis-dossier`` report.
  * Be deterministic — every call returns equal data, in the same
    order, with the same JSON-serializable shape.
  * Stay in sync with :func:`cbsrm.diagnostics.list_dossier_windows`
    (composition, not duplication).
  * Never execute a report. The crisis-dossier builder relies on
    fixtures, so a "did we accidentally build a dossier?" check is
    encoded via a monkeypatch on ``build_crisis_dossier``.
  * Be defensive about caller mutation — returned dicts must be fresh.
  * Surface unknown ids with a ``ValueError`` listing supported ids.
"""
from __future__ import annotations

import copy
import json

import pytest

from cbsrm.diagnostics import list_dossier_windows
from cbsrm.reporting import (
    REPORT_REGISTRY_VERSION,
    get_report_catalog,
    get_report_metadata,
    list_report_ids,
)


# ─── version / shape ────────────────────────────────────────────────


def test_registry_version_is_semver_like():
    parts = REPORT_REGISTRY_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts), REPORT_REGISTRY_VERSION


def test_catalog_top_level_shape():
    catalog = get_report_catalog()
    assert isinstance(catalog, dict)
    assert set(catalog.keys()) == {"reports"}
    assert isinstance(catalog["reports"], list)
    assert len(catalog["reports"]) >= 1


def test_each_entry_has_required_keys():
    required = {"id", "title", "description", "formats", "windows", "surfaces"}
    catalog = get_report_catalog()
    for entry in catalog["reports"]:
        assert isinstance(entry, dict)
        assert required.issubset(set(entry.keys())), entry


def test_each_entry_surfaces_has_required_keys():
    required = {"cli", "api", "streamlit"}
    catalog = get_report_catalog()
    for entry in catalog["reports"]:
        surfaces = entry["surfaces"]
        assert isinstance(surfaces, dict)
        assert required.issubset(set(surfaces.keys())), surfaces
        assert isinstance(surfaces["cli"], str)
        assert isinstance(surfaces["api"], list)
        assert isinstance(surfaces["streamlit"], str)
        assert all(isinstance(r, str) for r in surfaces["api"])


# ─── crisis-dossier specifics ──────────────────────────────────────


def test_catalog_contains_crisis_dossier():
    assert "crisis-dossier" in list_report_ids()


def test_crisis_dossier_metadata_is_complete():
    meta = get_report_metadata("crisis-dossier")
    assert meta["id"] == "crisis-dossier"
    assert meta["title"]  # non-empty
    assert meta["description"]
    assert set(meta["formats"]) == {"json", "markdown"}
    assert meta["windows"] == list(list_dossier_windows())
    # Canonical set pinned here to catch silent drift even if the
    # diagnostics fixtures shift.
    assert meta["windows"] == ["2008Q4", "2020Q1", "2023Q1"]
    assert "crisis-dossier" in meta["surfaces"]["cli"]
    assert any("/reports/crisis-dossiers" in r for r in meta["surfaces"]["api"])
    assert "crisis_dossier_viewer.py" in meta["surfaces"]["streamlit"]


# ─── determinism ────────────────────────────────────────────────────


def test_list_report_ids_is_sorted_and_deterministic():
    ids1 = list_report_ids()
    ids2 = list_report_ids()
    assert ids1 == ids2
    assert ids1 == sorted(ids1)


def test_catalog_is_byte_identical_across_calls():
    c1 = get_report_catalog()
    c2 = get_report_catalog()
    # Equal as Python objects.
    assert c1 == c2
    # And the JSON encoding is byte-identical (a stronger contract
    # because dict iteration order matters here).
    assert json.dumps(c1, sort_keys=False) == json.dumps(c2, sort_keys=False)


def test_get_report_metadata_is_deterministic():
    m1 = get_report_metadata("crisis-dossier")
    m2 = get_report_metadata("crisis-dossier")
    assert m1 == m2
    assert json.dumps(m1, sort_keys=False) == json.dumps(m2, sort_keys=False)


# ─── JSON-serializability ──────────────────────────────────────────


def test_catalog_is_json_serializable():
    catalog = get_report_catalog()
    encoded = json.dumps(catalog)  # no ensure_ascii needed; no unicode
    decoded = json.loads(encoded)
    assert decoded == catalog


def test_metadata_is_json_serializable():
    meta = get_report_metadata("crisis-dossier")
    assert json.loads(json.dumps(meta)) == meta


# ─── defensive copying ─────────────────────────────────────────────


def test_catalog_returns_fresh_copy_per_call():
    c1 = get_report_catalog()
    c1["reports"].append({"id": "MUTATION-PROBE"})
    c1["reports"][0]["title"] = "MUTATED"
    c2 = get_report_catalog()
    ids = [e["id"] for e in c2["reports"]]
    assert "MUTATION-PROBE" not in ids
    assert c2["reports"][0]["title"] != "MUTATED"


def test_metadata_returns_fresh_copy_per_call():
    m1 = get_report_metadata("crisis-dossier")
    m1["title"] = "MUTATED"
    m1["windows"].append("9999Q9")
    m1["surfaces"]["api"].append("MUTATED")
    m2 = get_report_metadata("crisis-dossier")
    assert m2["title"] != "MUTATED"
    assert "9999Q9" not in m2["windows"]
    assert "MUTATED" not in m2["surfaces"]["api"]


# ─── unknown id ────────────────────────────────────────────────────


def test_unknown_report_id_raises_valueerror_with_supported_list():
    with pytest.raises(ValueError) as exc:
        get_report_metadata("NOT-A-REPORT")
    msg = str(exc.value)
    assert "NOT-A-REPORT" in msg
    assert "crisis-dossier" in msg  # supported list rendered into message


# ─── no execution side effects ─────────────────────────────────────


def test_catalog_does_not_execute_any_report(monkeypatch):
    """Catalog assembly must NOT call ``build_crisis_dossier`` — the
    registry is metadata-only. We trap the call here to pin that
    contract; if anything in registry.py ever invokes the dossier
    builder, the test fails loudly.
    """
    import cbsrm.diagnostics as diagnostics_pkg

    def _no_build(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "registry must not execute build_crisis_dossier"
        )

    monkeypatch.setattr(
        diagnostics_pkg, "build_crisis_dossier", _no_build
    )

    catalog = get_report_catalog()
    ids = get_report_metadata("crisis-dossier")
    assert "crisis-dossier" in [e["id"] for e in catalog["reports"]]
    assert ids["id"] == "crisis-dossier"


# ─── composition with list_dossier_windows ─────────────────────────


def test_windows_stay_in_sync_with_list_dossier_windows(monkeypatch):
    """Registry must source windows from list_dossier_windows() so it
    cannot drift if new dossier fixtures land. We simulate an extra
    window and verify the registry surfaces it."""
    import cbsrm.reporting.registry as registry_mod

    def _fake_windows():
        return ["2008Q4", "2020Q1", "2023Q1", "2099Q9"]

    monkeypatch.setattr(
        "cbsrm.diagnostics.list_dossier_windows", _fake_windows
    )
    # cbsrm.diagnostics re-exports the symbol — also patch the
    # binding the registry's lazy import will resolve to.
    monkeypatch.setattr(
        "cbsrm.diagnostics.crisis_dossiers.list_dossier_windows",
        _fake_windows,
        raising=False,
    )
    # Confirm the registry deepcopy doesn't cache stale data.
    meta = registry_mod.get_report_metadata("crisis-dossier")
    assert "2099Q9" in meta["windows"]


# ─── shared snapshot integrity ─────────────────────────────────────


def test_returned_objects_are_deepcopies_not_shared_refs():
    """Two calls must return distinct objects all the way down so
    mutating one cannot affect the other."""
    c1 = get_report_catalog()
    c2 = get_report_catalog()
    assert c1 is not c2
    assert c1["reports"] is not c2["reports"]
    assert c1["reports"][0] is not c2["reports"][0]
    assert c1["reports"][0]["windows"] is not c2["reports"][0]["windows"]
    # And the deep equality contract still holds.
    assert copy.deepcopy(c1) == c1 == c2
