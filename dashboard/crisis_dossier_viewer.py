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
import os
import sqlite3
from typing import Any, Mapping

from cbsrm.diagnostics import build_crisis_dossier, list_dossier_windows
from cbsrm.reporting import (
    build_report_manifest,
    build_report_payload,
    render_dossier_html,
    render_dossier_markdown,
    stamp_manifest_to_db_path,
)


# ─── Audit-DB path resolution (Streamlit-free, fully testable) ────


def resolve_audit_db_path(
    *,
    sidebar_override: str | None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Decide which audit-chain DB path the Streamlit page should use.

    Precedence:

    1. ``sidebar_override`` (non-blank after ``.strip()``) — wins.
    2. ``env["CBSRM_AUDIT_DB"]`` (non-blank after ``.strip()``) — fallback.
    3. Otherwise ``None``.

    ``env`` defaults to :data:`os.environ`. Whitespace-only strings
    are treated as unset on either side.
    """
    if sidebar_override is not None:
        candidate = sidebar_override.strip()
        if candidate:
            return candidate
    env_map = env if env is not None else os.environ
    candidate = (env_map.get("CBSRM_AUDIT_DB") or "").strip()
    return candidate or None


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
        ``window_id``     — the input, echoed for caller convenience
        ``dossier``       — raw dossier dict from ``build_crisis_dossier``
        ``markdown``      — deterministic Markdown report (str)
        ``html``          — deterministic HTML report (str), suitable for
                            browser print-to-PDF (via
                            :func:`cbsrm.reporting.render_dossier_html`)
        ``payload``       — ``{"report": {...}, "dossier": {...}}`` envelope
        ``payload_json``  — UTF-8-safe pretty-printed JSON serialisation of
                            ``payload`` (``ensure_ascii=False`` so the
                            composition arrow ``→`` round-trips intact)
        ``manifest``      — deterministic export-time manifest dict
                            describing the displayed Markdown rendering;
                            stamped with ``source="streamlit"``,
                            ``format="markdown"`` and the sha256 of the
                            Markdown text. No wall-clock.
        ``manifest_json`` — pretty-printed JSON serialisation of
                            ``manifest`` (UTF-8-safe)

    Raises
    ------
    ValueError
        If ``window_id`` is not in the supported set.
    RuntimeError
        If the optional ``markdown`` package required by the HTML
        renderer is not installed (``pip install cbsrm[html]``).
    """
    dossier = build_crisis_dossier(window_id)
    payload = build_report_payload(dossier)
    markdown_text = render_dossier_markdown(dossier)
    manifest = build_report_manifest(
        report_id="crisis-dossier",
        output_text=markdown_text,
        output_format="markdown",
        window_id=window_id,
        source="streamlit",
        dossier=dossier,
        payload=payload,
    )
    return {
        "window_id": window_id,
        "dossier": dossier,
        "markdown": markdown_text,
        "html": render_dossier_html(dossier),
        "payload": payload,
        "payload_json": json.dumps(payload, indent=2, ensure_ascii=False),
        "manifest": manifest,
        "manifest_json": json.dumps(
            manifest, indent=2, ensure_ascii=False,
        ),
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

    col_md, col_json, col_html, col_manifest = st.columns(4)
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
    with col_html:
        st.download_button(
            label="Download HTML (.html)",
            data=artifacts["html"].encode("utf-8"),
            file_name=f"cbsrm_crisis_dossier_{window_id}.html",
            mime="text/html",
        )
    with col_manifest:
        st.download_button(
            label="Download Manifest (.manifest.json)",
            data=artifacts["manifest_json"].encode("utf-8"),
            file_name=(
                f"cbsrm_crisis_dossier_{window_id}.manifest.json"
            ),
            mime="application/json",
        )

    # ─── Sidebar: opt-in audit-chain stamping ──────────────────────
    with st.sidebar:
        st.markdown("### Audit chain (opt-in)")
        sidebar_override = st.text_input(
            "Audit DB path (overrides CBSRM_AUDIT_DB)", value="",
        )
        db_path = resolve_audit_db_path(sidebar_override=sidebar_override)
        if db_path:
            st.caption(f"Configured: `{db_path}`")
        else:
            st.caption(
                "Not configured. Set `CBSRM_AUDIT_DB` or enter a path above."
            )
        do_stamp = st.button(
            "Stamp manifest to audit chain",
            disabled=(db_path is None),
        )

    if do_stamp and db_path:
        try:
            audit_row = stamp_manifest_to_db_path(
                artifacts["manifest"], db_path,
            )
            st.sidebar.success(
                f"Stamped row #{audit_row['row_id']}\n\n"
                f"subject: `{audit_row['subject']}`\n\n"
                f"hash: `{audit_row['hash']}`\n\n"
                f"ts: `{audit_row['ts']}`"
            )
        except sqlite3.OperationalError as exc:
            st.sidebar.error(
                f"Cannot open audit DB '{db_path}': {exc}"
            )

    st.markdown("---")
    st.markdown(artifacts["markdown"])


if __name__ == "__main__":  # pragma: no cover - exercised by `streamlit run`
    render()
