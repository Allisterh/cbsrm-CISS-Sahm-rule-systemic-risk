"""Tests for the read-only ``GET /reports`` catalog endpoint.

This is a thin pass-through over :func:`cbsrm.reporting.get_report_catalog`.
The deeper registry contract is exercised by ``tests/test_report_registry.py``;
this file only pins the HTTP surface:

  * 200 status
  * JSON shape (``{"reports": [...]}``)
  * crisis-dossier is present
  * determinism (byte-identical across repeated calls)
  * the new route is registered on the FastAPI app
  * no report is executed as a side effect of hitting the catalog
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402  (after importorskip)

from cbsrm.api.routes import build_app
from cbsrm.reporting import get_report_catalog


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app())


# ─── route registration ────────────────────────────────────────────


def test_reports_catalog_route_is_registered():
    app = build_app()
    paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert "/reports" in paths
    # And we must not have broken the existing crisis-dossier routes.
    assert "/reports/crisis-dossiers" in paths
    assert "/reports/crisis-dossiers/{window_id}" in paths
    assert "/reports/crisis-dossiers/{window_id}/markdown" in paths


# ─── 200 + shape ───────────────────────────────────────────────────


def test_reports_catalog_returns_200_and_json(client):
    r = client.get("/reports")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")


def test_reports_catalog_response_shape(client):
    body = client.get("/reports").json()
    assert set(body.keys()) == {"reports"}
    assert isinstance(body["reports"], list)
    assert len(body["reports"]) >= 1


def test_reports_catalog_contains_crisis_dossier(client):
    body = client.get("/reports").json()
    ids = [entry["id"] for entry in body["reports"]]
    assert "crisis-dossier" in ids


def test_reports_catalog_matches_registry(client):
    """The endpoint must be a pure pass-through over the registry —
    the JSON body equals the python-level catalog."""
    body = client.get("/reports").json()
    assert body == get_report_catalog()


# ─── determinism ────────────────────────────────────────────────────


def test_reports_catalog_is_byte_identical_across_calls(client):
    r1 = client.get("/reports")
    r2 = client.get("/reports")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.content == r2.content


# ─── no execution side effects ─────────────────────────────────────


def test_reports_catalog_includes_macro_composite(client):
    """The catalog endpoint must surface every registered report. After
    the v0.9 second-report slice, the response must include both
    crisis-dossier and macro-composite."""
    body = client.get("/reports").json()
    ids = [entry["id"] for entry in body["reports"]]
    assert "crisis-dossier" in ids
    assert "macro-composite" in ids


def test_reports_catalog_macro_composite_surfaces_advertise_all_front_ends(
    client,
):
    """After the one-shot surfaces flip, ``GET /reports`` must advertise
    the three macro-composite executable front-ends now on ``main``:
    the dedicated CLI subcommand, the three sibling HTTP API routes,
    and the standalone Streamlit viewer. Pins the catalog-honesty
    contract from the HTTP surface."""
    body = client.get("/reports").json()
    macro = next(
        entry for entry in body["reports"]
        if entry["id"] == "macro-composite"
    )
    surfaces = macro["surfaces"]
    assert surfaces["cli"] == (
        "cbsrm macro-composite WINDOW --format json|markdown"
    )
    assert surfaces["api"] == [
        "GET /reports/macro-composite",
        "GET /reports/macro-composite/{window_id}",
        "GET /reports/macro-composite/{window_id}/markdown",
    ]
    assert surfaces["streamlit"] == (
        "streamlit run dashboard/macro_composite_viewer.py"
    )


def test_reports_catalog_does_not_build_a_dossier(monkeypatch):
    """Hitting ``GET /reports`` must NOT invoke the dossier builder.
    The catalog is metadata-only; this is the load-bearing contract
    that separates the catalog endpoint from the per-window endpoints."""
    import cbsrm.diagnostics as diagnostics_pkg

    def _no_build(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "GET /reports must not call build_crisis_dossier"
        )

    monkeypatch.setattr(
        diagnostics_pkg, "build_crisis_dossier", _no_build
    )

    client = TestClient(build_app())
    r = client.get("/reports")
    assert r.status_code == 200
    assert "crisis-dossier" in [e["id"] for e in r.json()["reports"]]
