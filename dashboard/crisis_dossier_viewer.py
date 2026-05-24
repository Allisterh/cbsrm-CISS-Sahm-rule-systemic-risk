"""Offline Streamlit viewer for CBSRM v0.8 crisis-window dossiers.

A minimal, fully offline Streamlit page that lets a user pick one of the
canonical crisis windows (2008Q4 / 2020Q1 / 2023Q1), renders the deterministic
Markdown report, and offers Markdown / JSON downloads of the same report
payload the CLI and HTTP API expose.

Run:

    pip install cbsrm streamlit
    streamlit run dashboard/crisis_dossier_viewer.py

Design notes
------------
* All data logic lives in :func:`build_viewer_artifacts`, a pure function with
  no Streamlit dependency.  This keeps the helper testable without launching
  Streamlit (and without requiring Streamlit to be installed in the test
  environment).
* Streamlit is imported lazily inside :func:`render`, so simply importing this
  module — for tests or for offline introspection — does not require Streamlit.
* No FRED key, no network calls, no API server dependency, no auth, no
  billing, no PDF generation, no persistence.  Research only — NFA.
"""
from __future__ import annotations

import json
from typing import Any

from cbsrm.diagnostics import build_crisis_dossier, list_dossier_windows
from cbsrm.reporting import build_report_payload, render_dossier_markdown


# ─── Pure helper (Streamlit-free) ────────────────────────────────────


def build_viewer_artifacts(window_id: str) -> dict[str, Any]:
    """Compose dossier + Markdown + JSON-payload artifacts for one window.

    Parameters
    ----------
    window_id
        One of the canonical window IDs returned by
        :func:`cbsrm.diagnostics.list_dossier_windows`.

    Returns
    -------
    dict with keys:
        ``window_id``    — the input, echoed for caller convenience
        ``dossier``      — raw dossier dict from ``build_crisis_dossier``
        ``markdown``     — deterministic Markdown report (str)
        ``payload``      — ``{"report": {...}, "dossier": {...}}`` envelope
        ``payload_json`` — UTF-8-safe pretty-printed JSON serialisation of
                           ``payload`` (``ensure_ascii=False`` so the
                           composition arrow ``→`` round-trips intact)

    Raises
    ------
    ValueError
        If ``window_id`` is not in the supported set.
    """
    dossier = build_crisis_dossier(window_id)
    payload = build_report_payload(dossier)
    return {
        "window_id": window_id,
        "dossier": dossier,
        "markdown": render_dossier_markdown(dossier),
        "payload": payload,
        "payload_json": json.dumps(payload, indent=2, ensure_ascii=False),
    }


# ─── Streamlit UI (lazy streamlit import) ────────────────────────────


def render() -> None:
    """Render the Streamlit page.  Imports Streamlit lazily so this module
    stays import-safe in environments without Streamlit installed."""
    import streamlit as st

    st.set_page_config(
        page_title="CBSRM Crisis Dossier Reports",
        layout="wide",
    )
    st.title("CBSRM Crisis Dossier Reports")
    st.caption(
        "Deterministic, offline, fixture-backed v0.8 crisis-window dossiers "
        "rendered through the canonical report renderer. "
        "No live data, no network calls, no API server required. "
        "Research only — **not financial advice**."
    )

    windows = list(list_dossier_windows())
    window_id = st.selectbox("Select crisis window", windows)

    artifacts = build_viewer_artifacts(window_id)

    col_md, col_json = st.columns(2)
    with col_md:
        st.download_button(
            label="Download Markdown (.md)",
            data=artifacts["markdown"].encode("utf-8"),
            file_name=f"crisis_dossier_{window_id}.md",
            mime="text/markdown",
        )
    with col_json:
        st.download_button(
            label="Download JSON (.json)",
            data=artifacts["payload_json"].encode("utf-8"),
            file_name=f"crisis_dossier_{window_id}.json",
            mime="application/json",
        )

    st.markdown("---")
    st.markdown(artifacts["markdown"])


if __name__ == "__main__":  # pragma: no cover - exercised by `streamlit run`
    render()
