"""Tests for the FastAPI read-only crisis-dossier report endpoints.

The endpoints are a thin pass-through over
``cbsrm.diagnostics.build_crisis_dossier`` / ``list_dossier_windows`` and
the ``cbsrm.reporting`` payload + Markdown renderer.  These tests pin
the externally observable HTTP contract:

  * status codes (200 / 404)
  * response shapes (list / JSON envelope / Markdown body)
  * media types
  * error detail shape (no traceback, supported-windows list returned)
  * offline construction (``build_app()`` must work with no network)

Methodology / payload internals are covered by
``tests/test_crisis_dossiers.py`` and ``tests/test_report_renderer.py``;
this file deliberately does *not* re-validate those.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402  (after importorskip)

from cbsrm.api.routes import build_app
from cbsrm.diagnostics import list_dossier_windows


# ─── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app())


# ─── app construction ───────────────────────────────────────────────


def test_build_app_is_offline(monkeypatch):
    """``build_app()`` must construct with no external I/O — the FastAPI
    routes are lazy-bodied, so wiring them must never touch the network.
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
    # Routes registered on the app must include our new surfaces.
    paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert "/reports/crisis-dossiers" in paths
    assert "/reports/crisis-dossiers/{window_id}" in paths
    assert "/reports/crisis-dossiers/{window_id}/markdown" in paths


# ─── /reports/crisis-dossiers ───────────────────────────────────────


def test_list_endpoint_returns_all_supported_windows(client):
    r = client.get("/reports/crisis-dossiers")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"windows"}
    assert body["windows"] == list(list_dossier_windows())
    # The pinned canonical set is locked here to catch silent drift.
    assert body["windows"] == ["2008Q4", "2020Q1", "2023Q1"]


# ─── /reports/crisis-dossiers/{window_id} (JSON) ────────────────────


def test_json_endpoint_2008q4_returns_expected_envelope(client):
    r = client.get("/reports/crisis-dossiers/2008Q4")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert set(body.keys()) >= {"report", "dossier"}
    assert body["report"]["kind"] == "crisis_window_dossier"
    assert body["dossier"]["window_id"] == "2008Q4"


@pytest.mark.parametrize("window", list_dossier_windows())
def test_json_endpoint_serves_all_supported_windows(window, client):
    r = client.get(f"/reports/crisis-dossiers/{window}")
    assert r.status_code == 200
    body = r.json()
    assert body["dossier"]["window_id"] == window
    assert body["report"]["kind"] == "crisis_window_dossier"


def test_json_endpoint_404_for_unknown_window(client):
    r = client.get("/reports/crisis-dossiers/1999Q9")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["window_id"] == "1999Q9"
    assert "unknown crisis-dossier window" in detail["error"]
    # Supported windows must be returned in the error so callers can recover.
    assert detail["supported_windows"] == list(list_dossier_windows())
    # No traceback leaked into the response body.
    assert "Traceback" not in r.text


# ─── /reports/crisis-dossiers/{window_id}/markdown ──────────────────


def test_markdown_endpoint_2008q4_returns_text_report(client):
    r = client.get("/reports/crisis-dossiers/2008Q4/markdown")
    assert r.status_code == 200
    ct = r.headers["content-type"]
    # Spec allows text/markdown OR text/plain; check the actual choice
    # but tolerate either form so the test is not brittle if the media
    # type is downgraded in a hostile proxy environment.
    assert ct.startswith(("text/markdown", "text/plain")), ct
    assert "charset=utf-8" in ct
    assert r.text.startswith("# ")
    assert "2008Q4" in r.text
    # NFA / research-only disclaimer must be carried through.
    assert "Disclaimer" in r.text


@pytest.mark.parametrize("window", list_dossier_windows())
def test_markdown_endpoint_serves_all_supported_windows(window, client):
    r = client.get(f"/reports/crisis-dossiers/{window}/markdown")
    assert r.status_code == 200
    assert r.text.startswith("# ")
    assert window in r.text


def test_markdown_emits_utf8_arrow_intact(client):
    """The renderer's composition footer contains U+2192 (→). The
    response body must deliver it as UTF-8 bytes (this is one of the
    bugs the CLI's ``_write_stdout_utf8_safe`` helper guards against
    on Windows; the API path goes through Starlette's PlainTextResponse,
    which should already encode UTF-8 correctly — this test pins that)."""
    r = client.get("/reports/crisis-dossiers/2023Q1/markdown")
    assert r.status_code == 200
    assert "→" in r.text
    # Verify the underlying bytes are real UTF-8 (not double-encoded).
    assert "\u2192".encode("utf-8") in r.content


def test_markdown_endpoint_404_for_unknown_window(client):
    r = client.get("/reports/crisis-dossiers/BOGUS/markdown")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["window_id"] == "BOGUS"
    assert detail["supported_windows"] == list(list_dossier_windows())
    assert "Traceback" not in r.text


# ─── determinism (read-only contract) ───────────────────────────────


def test_repeated_json_calls_are_byte_identical(client):
    r1 = client.get("/reports/crisis-dossiers/2008Q4")
    r2 = client.get("/reports/crisis-dossiers/2008Q4")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.content == r2.content


def test_repeated_markdown_calls_are_byte_identical(client):
    r1 = client.get("/reports/crisis-dossiers/2020Q1/markdown")
    r2 = client.get("/reports/crisis-dossiers/2020Q1/markdown")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.content == r2.content
