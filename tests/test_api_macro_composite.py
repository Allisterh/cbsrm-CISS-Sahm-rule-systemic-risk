"""Tests for the FastAPI read-only macro-composite report endpoints.

The endpoints are a thin pass-through over
:func:`cbsrm.reporting.build_macro_composite_report` and
:func:`cbsrm.reporting.render_macro_composite_markdown`. These tests
pin the externally observable HTTP contract:

  * status codes (200 / 404)
  * response shapes (list / JSON dict / Markdown body)
  * media types
  * 404 error-detail shape (no traceback, supported-windows list)
  * offline construction (``build_app()`` must work with no network)
  * byte-parity with the in-process builder / renderer
  * no accidental coupling to the crisis-dossier surface

Methodology / builder internals are covered by
``tests/test_macro_composite_report.py``; this file deliberately does
*not* re-validate them.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402  (after importorskip)

from cbsrm.api.routes import build_app
from cbsrm.reporting import (
    build_macro_composite_report,
    list_macro_composite_windows,
    render_macro_composite_markdown,
)


_SUPPORTED_WINDOWS = list_macro_composite_windows()


# ─── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app())


# ─── app construction / route registration ──────────────────────────


def test_build_app_is_offline_or_routes_registered(monkeypatch):
    """``build_app()`` must construct with no external I/O, and the
    three new macro-composite routes must be registered alongside the
    existing crisis-dossier surface.
    """
    import urllib.request

    def _no_urlopen(*_a, **_kw):
        raise AssertionError("build_app() made a urllib network call")

    monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)

    try:
        import requests  # noqa: F401

        def _no_requests(self, *_a, **_kw):  # pragma: no cover (defensive)
            raise AssertionError("build_app() made a requests network call")

        monkeypatch.setattr("requests.Session.request", _no_requests)
    except ImportError:
        pass

    app = build_app()
    assert app is not None
    paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert "/reports/macro-composite" in paths
    assert "/reports/macro-composite/{window_id}" in paths
    assert "/reports/macro-composite/{window_id}/markdown" in paths


# ─── /reports/macro-composite (list) ────────────────────────────────


def test_list_endpoint_returns_all_supported_windows(client):
    r = client.get("/reports/macro-composite")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"windows"}
    assert body["windows"] == list(_SUPPORTED_WINDOWS)
    # Pin the canonical set so silent drift fails this test loudly.
    assert body["windows"] == ["2008Q4", "2020Q1", "2023Q1"]


# ─── /reports/macro-composite/{window_id} (JSON) ────────────────────


def test_json_endpoint_2008q4_returns_expected_shape(client):
    r = client.get("/reports/macro-composite/2008Q4")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["report_id"] == "macro-composite"
    assert body["window_id"] == "2008Q4"
    # Top-level keys from the builder contract.
    assert {"phase_features", "phase_classification", "spec"}.issubset(
        body.keys()
    )


@pytest.mark.parametrize("window", _SUPPORTED_WINDOWS)
def test_json_endpoint_byte_parity_with_builder(window, client):
    r = client.get(f"/reports/macro-composite/{window}")
    assert r.status_code == 200
    assert r.json() == build_macro_composite_report(window)


@pytest.mark.parametrize("window", _SUPPORTED_WINDOWS)
def test_json_endpoint_serves_all_supported_windows(window, client):
    r = client.get(f"/reports/macro-composite/{window}")
    assert r.status_code == 200
    body = r.json()
    assert body["window_id"] == window
    assert body["report_id"] == "macro-composite"


def test_json_endpoint_404_for_unknown_window(client):
    r = client.get("/reports/macro-composite/1999Q9")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["window_id"] == "1999Q9"
    assert "unknown macro-composite window" in detail["error"]
    assert detail["supported_windows"] == list(_SUPPORTED_WINDOWS)
    # No traceback leaked into the response body.
    assert "Traceback" not in r.text


# ─── /reports/macro-composite/{window_id}/markdown ──────────────────


def test_markdown_endpoint_2008q4_returns_text_report(client):
    r = client.get("/reports/macro-composite/2008Q4/markdown")
    assert r.status_code == 200
    ct = r.headers["content-type"]
    # Spec allows text/markdown OR text/plain; tolerate either form.
    assert ct.startswith(("text/markdown", "text/plain")), ct
    assert "charset=utf-8" in ct
    assert "2008Q4" in r.text
    # NFA / research-only disclaimer must be carried through.
    assert "Disclaimer" in r.text


@pytest.mark.parametrize("window", _SUPPORTED_WINDOWS)
def test_markdown_endpoint_byte_parity_with_renderer(window, client):
    r = client.get(f"/reports/macro-composite/{window}/markdown")
    assert r.status_code == 200
    expected = render_macro_composite_markdown(
        build_macro_composite_report(window)
    )
    assert r.text == expected


@pytest.mark.parametrize("window", _SUPPORTED_WINDOWS)
def test_markdown_endpoint_serves_all_supported_windows(window, client):
    r = client.get(f"/reports/macro-composite/{window}/markdown")
    assert r.status_code == 200
    assert window in r.text


def test_markdown_endpoint_404_for_unknown_window(client):
    r = client.get("/reports/macro-composite/BOGUS/markdown")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["window_id"] == "BOGUS"
    assert detail["supported_windows"] == list(_SUPPORTED_WINDOWS)
    assert "Traceback" not in r.text


# ─── determinism (read-only contract) ───────────────────────────────


def test_repeated_json_calls_are_byte_identical(client):
    r1 = client.get("/reports/macro-composite/2008Q4")
    r2 = client.get("/reports/macro-composite/2008Q4")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.content == r2.content


def test_repeated_markdown_calls_are_byte_identical(client):
    r1 = client.get("/reports/macro-composite/2020Q1/markdown")
    r2 = client.get("/reports/macro-composite/2020Q1/markdown")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.content == r2.content


# ─── sibling-not-parent: must not call build_crisis_dossier ─────────


def test_json_endpoint_does_not_call_build_crisis_dossier(monkeypatch):
    """The macro-composite report is a sibling of crisis-dossier, not
    a parent/child. The JSON route must satisfy its response without
    ever calling ``build_crisis_dossier`` (which would imply silent
    coupling).
    """
    import cbsrm.diagnostics.crisis_dossiers as diag_mod

    def _no_dossier(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "macro-composite JSON route must not call build_crisis_dossier"
        )

    monkeypatch.setattr(diag_mod, "build_crisis_dossier", _no_dossier)

    with TestClient(build_app()) as c:
        r = c.get("/reports/macro-composite/2008Q4")
        assert r.status_code == 200
        assert r.json()["window_id"] == "2008Q4"


def test_markdown_endpoint_does_not_call_build_crisis_dossier(monkeypatch):
    import cbsrm.diagnostics.crisis_dossiers as diag_mod

    def _no_dossier(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "macro-composite Markdown route must not call build_crisis_dossier"
        )

    monkeypatch.setattr(diag_mod, "build_crisis_dossier", _no_dossier)

    with TestClient(build_app()) as c:
        r = c.get("/reports/macro-composite/2008Q4/markdown")
        assert r.status_code == 200
        assert "2008Q4" in r.text


# ─── no manifest/audit/store wiring this slice ──────────────────────


def test_no_manifest_audit_store_query_params_silently_accepted(client):
    """FastAPI silently ignores unknown query parameters. Pin that the
    macro-composite JSON route was NOT wired to manifest/audit/store
    flags (that exposure is deferred). Sending the flags must produce
    the exact same response as the bare endpoint.
    """
    r_bare = client.get("/reports/macro-composite/2008Q4")
    r_flags = client.get(
        "/reports/macro-composite/2008Q4"
        "?manifest=true&audit=true&store=true"
    )
    assert r_bare.status_code == 200
    assert r_flags.status_code == 200
    assert r_bare.content == r_flags.content
    # And the response must NOT carry any manifest/audit/store keys.
    body = r_flags.json()
    assert "manifest" not in body
    assert "audit" not in body
    assert "stored" not in body


# ─── existing surfaces must remain unchanged ────────────────────────


def test_crisis_dossier_routes_unchanged_after_macro_composite_added():
    """Adding macro-composite routes must not perturb the existing
    crisis-dossier surface — all four paths must still be registered.
    """
    app = build_app()
    paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert "/reports/crisis-dossiers" in paths
    assert "/reports/crisis-dossiers/{window_id}" in paths
    assert "/reports/crisis-dossiers/{window_id}/markdown" in paths
    assert "/reports/crisis-dossiers/{window_id}/html" in paths


def test_reports_catalog_endpoint_advertises_macro_composite_api_routes(client):
    """The /reports catalog endpoint must surface the three
    macro-composite sibling routes in ``surfaces.api`` after the v0.9
    one-shot surfaces flip (all three front-ends — CLI, API,
    Streamlit — now exist on ``main``). Pins the catalog-honesty
    contract from the API slice's side.
    """
    r = client.get("/reports")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"reports"}
    ids = [entry["id"] for entry in body["reports"]]
    # Both entries still present and unchanged in order/shape.
    assert "crisis-dossier" in ids
    assert "macro-composite" in ids
    # macro-composite surfaces.api now advertises the three sibling routes.
    mc_entry = next(e for e in body["reports"] if e["id"] == "macro-composite")
    assert mc_entry["surfaces"]["api"] == [
        "GET /reports/macro-composite",
        "GET /reports/macro-composite/{window_id}",
        "GET /reports/macro-composite/{window_id}/markdown",
    ]
