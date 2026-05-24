"""Smoke tests for the Streamlit crisis-dossier viewer.

The Streamlit page itself is intentionally **not** launched here — driving a
live Streamlit process from pytest is brittle on Windows CI and would require
Streamlit at test time.  Instead we exercise the pure
:func:`build_viewer_artifacts` helper, which is the entire data surface of the
page; the Streamlit ``render()`` function is a thin presentation wrapper over
that helper.

The viewer module lives at ``dashboard/crisis_dossier_viewer.py``, but
``dashboard/`` is not a Python package (no ``__init__.py``) — so we load the
module by file path with ``importlib`` rather than touching the dashboard
directory layout.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from cbsrm.diagnostics import list_dossier_windows


# ─── Module loader ───────────────────────────────────────────────────


_VIEWER_PATH = (
    Path(__file__).resolve().parents[1]
    / "dashboard"
    / "crisis_dossier_viewer.py"
)


def _load_viewer_module():
    """Import ``dashboard/crisis_dossier_viewer.py`` by file path."""
    assert _VIEWER_PATH.is_file(), f"viewer not found at {_VIEWER_PATH}"
    spec = importlib.util.spec_from_file_location(
        "_cbsrm_crisis_dossier_viewer_under_test", _VIEWER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so any internal "from __main__" style lookups work;
    # under our pinned module name there is no conflict with the real package.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def viewer():
    return _load_viewer_module()


# ─── Pure-helper contract ────────────────────────────────────────────


def test_module_imports_without_streamlit(viewer):
    """Importing the viewer module must not require Streamlit — the
    helper is the testable surface and Streamlit is a lazy import inside
    :func:`render`."""
    assert hasattr(viewer, "build_viewer_artifacts")
    assert hasattr(viewer, "render")
    # render() defers its `import streamlit as st`, so the module itself
    # never lists streamlit in its top-level names.
    assert "streamlit" not in dir(viewer)


# Tests below this line exercise build_viewer_artifacts(), which now
# composes the v0.9 HTML renderer and therefore requires the optional
# `markdown` package (installed via `cbsrm[html]`).  Skip cleanly when
# the package is unavailable.  The streamlit-import-safety test above
# does not depend on markdown and continues to run unconditionally.
pytest.importorskip("markdown")


@pytest.mark.parametrize("window", list_dossier_windows())
def test_build_viewer_artifacts_for_each_window(viewer, window):
    artifacts = viewer.build_viewer_artifacts(window)

    # echoed input
    assert artifacts["window_id"] == window

    # raw dossier
    assert artifacts["dossier"]["window_id"] == window

    # markdown — H1 title + window ID + disclaimer
    md = artifacts["markdown"]
    assert md.startswith("# "), md[:80]
    assert window in md
    assert "Disclaimer" in md

    # JSON envelope — pinned shape from the report renderer contract
    payload = artifacts["payload"]
    assert set(payload.keys()) >= {"report", "dossier"}
    assert payload["report"]["kind"] == "crisis_window_dossier"
    assert payload["dossier"]["window_id"] == window

    # JSON string — round-trips and matches the structured payload
    parsed = json.loads(artifacts["payload_json"])
    assert parsed == payload

    # ensure_ascii=False keeps the literal composition arrow intact so
    # downloaded files render correctly in editors/browsers.
    assert "→" in artifacts["payload_json"]
    assert "\\u2192" not in artifacts["payload_json"]


def test_build_viewer_artifacts_rejects_unknown_window(viewer):
    with pytest.raises(ValueError):
        viewer.build_viewer_artifacts("1999Q9")


def test_repeated_calls_are_deterministic(viewer):
    a1 = viewer.build_viewer_artifacts("2008Q4")
    a2 = viewer.build_viewer_artifacts("2008Q4")
    assert a1["markdown"] == a2["markdown"]
    assert a1["payload_json"] == a2["payload_json"]
    assert a1["html"] == a2["html"]


# ─── HTML artifact (v0.9 addition) ──────────────────────────────────


@pytest.mark.parametrize("window", list_dossier_windows())
def test_build_viewer_artifacts_includes_html_for_each_window(
    viewer, window,
):
    artifacts = viewer.build_viewer_artifacts(window)
    assert "html" in artifacts
    html = artifacts["html"]
    assert isinstance(html, str)
    assert len(html) > 0
    # Full HTML document with DOCTYPE + <html> shell
    assert "<!DOCTYPE html>" in html
    assert "<html" in html


def test_build_viewer_artifacts_html_contains_window_id_and_disclaimer(
    viewer,
):
    artifacts = viewer.build_viewer_artifacts("2008Q4")
    html = artifacts["html"]
    assert "2008Q4" in html
    assert "Disclaimer" in html


def test_build_viewer_artifacts_html_is_deterministic(viewer):
    """Two calls with the same window must produce byte-identical HTML."""
    h1 = viewer.build_viewer_artifacts("2020Q1")["html"]
    h2 = viewer.build_viewer_artifacts("2020Q1")["html"]
    assert h1 == h2


# ─── Manifest artifact (v0.9 addition) ──────────────────────────────


def test_build_viewer_artifacts_includes_manifest_and_manifest_json(
    viewer,
):
    artifacts = viewer.build_viewer_artifacts("2008Q4")
    assert "manifest" in artifacts
    assert "manifest_json" in artifacts
    assert isinstance(artifacts["manifest"], dict)
    assert isinstance(artifacts["manifest_json"], str)
    # Required top-level shape from cbsrm.reporting.manifest.
    assert set(artifacts["manifest"].keys()) == {
        "manifest_version", "report_id", "window_id", "format",
        "source", "generated_at_utc", "versions", "hashes",
        "disclaimer_present",
    }


def test_manifest_records_source_streamlit(viewer):
    artifacts = viewer.build_viewer_artifacts("2008Q4")
    assert artifacts["manifest"]["source"] == "streamlit"


def test_manifest_format_is_markdown(viewer):
    """The Streamlit page displays the Markdown rendering inline, so
    the manifest describes the Markdown output."""
    artifacts = viewer.build_viewer_artifacts("2008Q4")
    assert artifacts["manifest"]["format"] == "markdown"


def test_manifest_output_sha256_matches_artifacts_markdown(viewer):
    import hashlib

    artifacts = viewer.build_viewer_artifacts("2008Q4")
    expected = hashlib.sha256(
        artifacts["markdown"].encode("utf-8"),
    ).hexdigest()
    assert (
        artifacts["manifest"]["hashes"]["output_sha256"] == expected
    )


def test_manifest_json_round_trips(viewer):
    """``manifest_json`` is a pretty-printed JSON serialisation of
    ``manifest``; ``json.loads`` must return the same dict."""
    artifacts = viewer.build_viewer_artifacts("2008Q4")
    assert json.loads(artifacts["manifest_json"]) == artifacts["manifest"]


def test_manifest_window_id_pinned(viewer):
    artifacts = viewer.build_viewer_artifacts("2023Q1")
    assert artifacts["manifest"]["window_id"] == "2023Q1"
    assert artifacts["manifest"]["report_id"] == "crisis-dossier"


def test_manifest_is_deterministic_across_calls(viewer):
    a1 = viewer.build_viewer_artifacts("2020Q1")
    a2 = viewer.build_viewer_artifacts("2020Q1")
    assert a1["manifest"] == a2["manifest"]
    assert a1["manifest_json"] == a2["manifest_json"]


# ─── resolve_audit_db_path (Streamlit-free, v0.9 addition) ──────────


def test_resolve_audit_db_path_uses_sidebar_override(viewer):
    """A non-blank sidebar override wins over the env var."""
    out = viewer.resolve_audit_db_path(
        sidebar_override="/sidebar/path.db",
        env={"CBSRM_AUDIT_DB": "/env/path.db"},
    )
    assert out == "/sidebar/path.db"


def test_resolve_audit_db_path_falls_back_to_env_var(viewer):
    out = viewer.resolve_audit_db_path(
        sidebar_override="",
        env={"CBSRM_AUDIT_DB": "/env/path.db"},
    )
    assert out == "/env/path.db"


def test_resolve_audit_db_path_returns_none_when_neither_set(viewer):
    out = viewer.resolve_audit_db_path(
        sidebar_override="",
        env={},
    )
    assert out is None


def test_resolve_audit_db_path_blank_sidebar_lets_env_win(viewer):
    """A whitespace-only sidebar input must be treated as unset, so
    the env var fallback wins."""
    out = viewer.resolve_audit_db_path(
        sidebar_override="   ",
        env={"CBSRM_AUDIT_DB": "/env/path.db"},
    )
    assert out == "/env/path.db"


def test_resolve_audit_db_path_strips_env_value(viewer):
    """Trailing whitespace in CBSRM_AUDIT_DB must not break the
    sqlite-open path; ``.strip()`` is applied before use."""
    out = viewer.resolve_audit_db_path(
        sidebar_override=None,
        env={"CBSRM_AUDIT_DB": "  /env/path.db  "},
    )
    assert out == "/env/path.db"


def test_resolve_audit_db_path_blank_env_returns_none(viewer):
    out = viewer.resolve_audit_db_path(
        sidebar_override=None,
        env={"CBSRM_AUDIT_DB": "   "},
    )
    assert out is None


def test_resolve_audit_db_path_none_sidebar_uses_env_default(viewer):
    """When sidebar_override is None (e.g. test injection), the env
    fallback is still consulted."""
    out = viewer.resolve_audit_db_path(
        sidebar_override=None,
        env={"CBSRM_AUDIT_DB": "/env/path.db"},
    )
    assert out == "/env/path.db"


# ─── Integration: viewer manifest -> audit-DB path ──────────────────


def test_viewer_manifest_stamps_through_db_path_helper(viewer, tmp_path):
    """End-to-end shape: build viewer artifacts, then stamp the
    manifest into a sqlite DB via the path-based helper. Asserts the
    subject and DB row, without touching Streamlit at all."""
    from cbsrm.reporting import stamp_manifest_to_db_path

    artifacts = viewer.build_viewer_artifacts("2008Q4")
    db_path = tmp_path / "viewer-audit.db"
    audit_row = stamp_manifest_to_db_path(
        artifacts["manifest"], str(db_path),
    )
    assert audit_row["subject"] == "report:crisis-dossier:2008Q4:markdown"
    assert audit_row["kind"] == "REPORT_EXPORTED"
    assert db_path.is_file()
