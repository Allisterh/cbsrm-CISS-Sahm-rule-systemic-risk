"""Smoke tests for the Streamlit macro-composite viewer.

The Streamlit page itself is intentionally **not** launched here — driving
a live Streamlit process from pytest is brittle on Windows CI and would
require Streamlit at test time. Instead we exercise the pure
:func:`build_viewer_artifacts` helper, which is the entire data surface
of the page; the Streamlit ``render()`` function is a thin presentation
wrapper over that helper.

The viewer module lives at ``dashboard/macro_composite_viewer.py``, but
``dashboard/`` is not a Python package (no ``__init__.py``) — so we load
the module by file path with ``importlib`` rather than touching the
dashboard directory layout.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from cbsrm.reporting import (
    build_macro_composite_report,
    get_report_catalog,
    list_macro_composite_windows,
)


# ─── Module loader ───────────────────────────────────────────────────


_VIEWER_PATH = (
    Path(__file__).resolve().parents[1]
    / "dashboard"
    / "macro_composite_viewer.py"
)


def _load_viewer_module():
    """Import ``dashboard/macro_composite_viewer.py`` by file path."""
    assert _VIEWER_PATH.is_file(), f"viewer not found at {_VIEWER_PATH}"
    spec = importlib.util.spec_from_file_location(
        "_cbsrm_macro_composite_viewer_under_test", _VIEWER_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def viewer():
    return _load_viewer_module()


_WINDOWS = list(list_macro_composite_windows())


# ─── Module-shape / lazy-streamlit contract ─────────────────────────


def test_module_imports_without_streamlit(viewer):
    """Importing the viewer module must not require Streamlit — the
    helper is the testable surface and Streamlit is a lazy import
    inside :func:`render`."""
    assert hasattr(viewer, "build_viewer_artifacts")
    assert hasattr(viewer, "render")
    # render() defers its `import streamlit as st`, so the module
    # itself never lists streamlit in its top-level names.
    assert "streamlit" not in dir(viewer)


# ─── build_viewer_artifacts contract ────────────────────────────────


_REQUIRED_ARTIFACT_KEYS = {
    "window_id",
    "report",
    "markdown",
    "json_text",
    "markdown_filename",
    "json_filename",
}


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_returns_required_keys(viewer, window_id):
    artifacts = viewer.build_viewer_artifacts(window_id)
    assert isinstance(artifacts, dict)
    assert set(artifacts.keys()) == _REQUIRED_ARTIFACT_KEYS


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_report_id_pinned(viewer, window_id):
    artifacts = viewer.build_viewer_artifacts(window_id)
    assert artifacts["report"]["report_id"] == "macro-composite"


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_window_id_echoes(viewer, window_id):
    artifacts = viewer.build_viewer_artifacts(window_id)
    assert artifacts["window_id"] == window_id
    assert artifacts["report"]["window_id"] == window_id


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_markdown_shape(viewer, window_id):
    artifacts = viewer.build_viewer_artifacts(window_id)
    md = artifacts["markdown"]
    assert isinstance(md, str)
    # Title line from build_macro_composite_report is
    #   "Macro Composite Snapshot — <window>"
    # rendered as "# Macro Composite Snapshot — <window>".
    assert "# Macro Composite Snapshot" in md
    assert window_id in md
    assert "## Disclaimer" in md
    # Markdown renderer terminates with a single trailing newline.
    assert md.endswith("\n")


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_json_text_parses_to_report(viewer, window_id):
    artifacts = viewer.build_viewer_artifacts(window_id)
    parsed = json.loads(artifacts["json_text"])
    assert parsed == artifacts["report"]


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_json_text_is_canonical(viewer, window_id):
    """Pins ``indent=2`` + ``ensure_ascii=False`` + single trailing
    newline. The report title contains an em-dash ``—`` which must
    round-trip as the literal Unicode character, not as a ``\\u2014``
    escape — that is a functional requirement, not a defensive
    convention."""
    artifacts = viewer.build_viewer_artifacts(window_id)
    expected = (
        json.dumps(artifacts["report"], indent=2, ensure_ascii=False)
        + "\n"
    )
    assert artifacts["json_text"] == expected
    assert artifacts["json_text"].endswith("\n")
    # Indent=2 produces 2-space leading indentation on object members.
    assert '\n  "report_id"' in artifacts["json_text"]
    # ensure_ascii=False keeps the em-dash literal.
    assert "—" in artifacts["json_text"]
    assert "\\u2014" not in artifacts["json_text"]


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_filenames(viewer, window_id):
    artifacts = viewer.build_viewer_artifacts(window_id)
    assert (
        artifacts["markdown_filename"]
        == f"cbsrm_macro_composite_{window_id}.md"
    )
    assert (
        artifacts["json_filename"]
        == f"cbsrm_macro_composite_{window_id}.json"
    )


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_is_deterministic(viewer, window_id):
    a = viewer.build_viewer_artifacts(window_id)
    b = viewer.build_viewer_artifacts(window_id)
    assert a["markdown"] == b["markdown"]
    assert a["json_text"] == b["json_text"]
    assert a["report"] == b["report"]
    assert a["markdown_filename"] == b["markdown_filename"]
    assert a["json_filename"] == b["json_filename"]


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_returns_fresh_objects(viewer, window_id):
    """The viewer must not cache: mutating one call's report dict must
    not affect a subsequent call. Inherited from the builder's
    fresh-copy-per-call contract."""
    a = viewer.build_viewer_artifacts(window_id)
    a["report"]["title"] = "MUTATED"
    a["report"]["phase_features"]["growth_z"] = 999.0
    b = viewer.build_viewer_artifacts(window_id)
    assert b["report"]["title"] != "MUTATED"
    assert b["report"]["phase_features"]["growth_z"] != 999.0


def test_build_viewer_artifacts_all_windows_succeed(viewer):
    for window_id in _WINDOWS:
        artifacts = viewer.build_viewer_artifacts(window_id)
        assert artifacts["report"]["window_id"] == window_id


def test_build_viewer_artifacts_rejects_unknown_window(viewer):
    """Propagates :class:`ValueError` verbatim from
    :func:`cbsrm.reporting.build_macro_composite_report`."""
    with pytest.raises(ValueError) as exc:
        viewer.build_viewer_artifacts("9999Q9")
    assert "9999Q9" in str(exc.value)


def test_build_viewer_artifacts_is_offline(viewer, monkeypatch):
    """Monkeypatch the standard outbound-IO hooks to fire on any
    accidental network call, then build every supported window. Mirrors
    the offline-contract test in
    ``tests/test_macro_composite_report.py``."""
    import urllib.request

    def _explode(*_args, **_kwargs):
        raise AssertionError("network call is forbidden")

    monkeypatch.setattr(urllib.request, "urlopen", _explode)
    try:
        import requests  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - requests is optional
        requests = None
    if requests is not None:
        monkeypatch.setattr(requests.Session, "request", _explode)

    for window_id in _WINDOWS:
        artifacts = viewer.build_viewer_artifacts(window_id)
        assert artifacts["report"]["window_id"] == window_id


@pytest.mark.parametrize("window_id", _WINDOWS)
def test_build_viewer_artifacts_matches_in_process_builder(viewer, window_id):
    """Pin that the viewer is a pure pass-through over
    :func:`build_macro_composite_report` — no transformation, no
    enrichment, no field reshaping."""
    artifacts = viewer.build_viewer_artifacts(window_id)
    expected = build_macro_composite_report(window_id)
    assert artifacts["report"] == expected


# ─── Catalog-honesty drift guard ────────────────────────────────────


def test_registry_macro_composite_surfaces_advertise_all_front_ends():
    """The registry catalog entry for ``macro-composite`` now advertises
    all three executable front-ends shipped on ``main``: the dedicated
    CLI subcommand, the three read-only HTTP API routes, and this new
    standalone Streamlit viewer. Pins the one-shot catalog-honesty
    flip — if this test fails after a future slice, either the
    advertised surface no longer exists (broken catalog honesty) or
    the surfaces dict was mutated."""
    catalog = get_report_catalog()
    macro = next(
        entry for entry in catalog["reports"]
        if entry["id"] == "macro-composite"
    )
    surfaces = macro["surfaces"]
    # CLI: dedicated ``cbsrm macro-composite`` subcommand.
    assert surfaces["cli"] == (
        "cbsrm macro-composite WINDOW --format json|markdown"
    )
    # API: the three sibling routes.
    assert surfaces["api"] == [
        "GET /reports/macro-composite",
        "GET /reports/macro-composite/{window_id}",
        "GET /reports/macro-composite/{window_id}/markdown",
    ]
    # Streamlit: this viewer page (not the catalog landing page).
    assert surfaces["streamlit"] == (
        "streamlit run dashboard/macro_composite_viewer.py"
    )
    assert "macro_composite_viewer.py" in surfaces["streamlit"]
