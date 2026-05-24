"""Smoke tests for the Streamlit report-catalog landing page.

The Streamlit page itself is intentionally **not** launched here — driving
a live Streamlit process from pytest is brittle on Windows CI and would
require Streamlit at test time. Instead we exercise the pure
:func:`build_catalog_view` helper, which is the entire data surface of
the page; the Streamlit ``render()`` function is a thin presentation
wrapper over that helper.

The viewer module lives at ``dashboard/report_catalog_viewer.py``, but
``dashboard/`` is not a Python package (no ``__init__.py``) — so we load
the module by file path with ``importlib`` rather than touching the
dashboard directory layout.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from cbsrm.reporting import get_report_catalog


# ─── Module loader ───────────────────────────────────────────────────


_VIEWER_PATH = (
    Path(__file__).resolve().parents[1]
    / "dashboard"
    / "report_catalog_viewer.py"
)


def _load_viewer_module():
    """Import ``dashboard/report_catalog_viewer.py`` by file path."""
    assert _VIEWER_PATH.is_file(), f"viewer not found at {_VIEWER_PATH}"
    spec = importlib.util.spec_from_file_location(
        "_cbsrm_report_catalog_viewer_under_test", _VIEWER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def viewer():
    return _load_viewer_module()


# ─── Module-shape / lazy-streamlit contract ─────────────────────────


def test_module_imports_without_streamlit(viewer):
    """Importing the viewer module must not require Streamlit — the
    helper is the testable surface and Streamlit is a lazy import
    inside :func:`render`."""
    assert hasattr(viewer, "build_catalog_view")
    assert hasattr(viewer, "render")
    # render() defers its `import streamlit as st`, so the module
    # itself never lists streamlit in its top-level names.
    assert "streamlit" not in dir(viewer)


# ─── build_catalog_view contract ────────────────────────────────────


def test_build_catalog_view_default_uses_registry(viewer):
    view = viewer.build_catalog_view()
    assert isinstance(view, dict)
    assert set(view.keys()) >= {
        "report_count", "reports", "crisis_dossier_viewer_path",
    }
    assert view["report_count"] >= 1
    ids = [r["id"] for r in view["reports"]]
    assert "crisis-dossier" in ids
    assert view["crisis_dossier_viewer_path"] == (
        "dashboard/crisis_dossier_viewer.py"
    )


def test_build_catalog_view_matches_registry_catalog(viewer):
    """Default-call path must be a pure pass-through over the registry —
    the reports list equals what the registry returns."""
    view = viewer.build_catalog_view()
    catalog = get_report_catalog()
    assert view["reports"] == catalog["reports"]
    assert view["report_count"] == len(catalog["reports"])


def test_build_catalog_view_is_json_serializable(viewer):
    """Default-call output must round-trip through json.dumps."""
    view = viewer.build_catalog_view()
    encoded = json.dumps(view)
    assert json.loads(encoded) == view


def test_build_catalog_view_accepts_injected_catalog(viewer):
    """Test-injection seam — caller-supplied catalog is honoured
    without falling back to the live registry."""
    synthetic = {
        "reports": [
            {
                "id": "synth",
                "title": "Synthetic",
                "description": "test only",
                "formats": ["json"],
                "windows": [],
                "surfaces": {
                    "cli": "synthetic-cli",
                    "api": ["GET /synthetic"],
                    "streamlit": "synthetic-streamlit",
                },
            },
        ],
    }
    view = viewer.build_catalog_view(synthetic)
    assert view["report_count"] == 1
    assert view["reports"][0]["id"] == "synth"
    # crisis-dossier should NOT appear when an alternate catalog is
    # injected — confirms the live registry was not consulted.
    ids = [r["id"] for r in view["reports"]]
    assert "crisis-dossier" not in ids


def test_build_catalog_view_does_not_execute_reports(viewer, monkeypatch):
    """Hitting the viewer must NOT invoke ``build_crisis_dossier``.
    The catalog is metadata-only; this is the load-bearing contract
    that distinguishes the landing page from the per-window viewer."""
    import cbsrm.diagnostics as diagnostics_pkg

    def _no_build(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "report catalog viewer must not call build_crisis_dossier"
        )

    monkeypatch.setattr(
        diagnostics_pkg, "build_crisis_dossier", _no_build
    )

    view = viewer.build_catalog_view()
    ids = [r["id"] for r in view["reports"]]
    assert "crisis-dossier" in ids


def test_build_catalog_view_pins_crisis_dossier_metadata(viewer):
    """Pin the canonical metadata for the v0.8 crisis-dossier entry so
    drift here is caught here, not only in the registry tests."""
    view = viewer.build_catalog_view()
    crisis = next(r for r in view["reports"] if r["id"] == "crisis-dossier")
    assert set(crisis["formats"]) == {"json", "markdown"}
    assert crisis["windows"] == ["2008Q4", "2020Q1", "2023Q1"]
    surfaces = crisis["surfaces"]
    assert surfaces["cli"].startswith("cbsrm crisis-dossier")
    assert any("/reports/crisis-dossiers" in r for r in surfaces["api"])
    assert "crisis_dossier_viewer.py" in surfaces["streamlit"]


def test_build_catalog_view_is_deterministic(viewer):
    """Two default-call invocations must return equal data."""
    v1 = viewer.build_catalog_view()
    v2 = viewer.build_catalog_view()
    assert v1 == v2
    assert json.dumps(v1) == json.dumps(v2)


def test_build_catalog_view_returns_fresh_copies(viewer):
    """Mutating output of one call must not affect a subsequent call —
    confirms the registry's deep-copy contract propagates through the
    viewer helper."""
    v1 = viewer.build_catalog_view()
    v1["reports"].append({"id": "MUTATION-PROBE"})
    if v1["reports"] and "title" in v1["reports"][0]:
        v1["reports"][0]["title"] = "MUTATED"
    v2 = viewer.build_catalog_view()
    ids = [r["id"] for r in v2["reports"]]
    assert "MUTATION-PROBE" not in ids
    if v2["reports"]:
        assert v2["reports"][0].get("title") != "MUTATED"
    # And the deep-equal contract still holds for re-reads.
    assert copy.deepcopy(v2) == v2
