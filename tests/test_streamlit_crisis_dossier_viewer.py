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
