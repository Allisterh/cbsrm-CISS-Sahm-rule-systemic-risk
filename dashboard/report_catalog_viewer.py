"""Offline Streamlit landing page for the CBSRM v0.9 report registry.

A minimal, fully offline Streamlit page that lists the reports available
through :func:`cbsrm.reporting.get_report_catalog`, surfaces each report's
metadata, and points users to the per-window detail viewer at
``dashboard/crisis_dossier_viewer.py``.

Run:

    pip install cbsrm streamlit
    streamlit run dashboard/report_catalog_viewer.py

Design notes
------------
* All data logic lives in :func:`build_catalog_view`, a pure function with
  no Streamlit dependency. This keeps the helper testable without
  launching Streamlit and without requiring Streamlit to be installed in
  the test environment.
* Streamlit is imported lazily inside :func:`render`, so importing this
  module — for tests or for offline introspection — does not require
  Streamlit.
* Metadata-only: this page **never** executes a report, never touches the
  network, never calls the API server, never writes to disk. Mirrors the
  ``cbsrm reports`` CLI command and the ``GET /reports`` HTTP endpoint
  over the same registry.
* No FRED key, no auth, no billing, no PDF generation, no persistence.
  Research only — NFA.
"""
from __future__ import annotations

from typing import Any, Mapping

from cbsrm.reporting import get_report_catalog


# Path string used to point users at the per-window detail viewer. Kept
# at module scope so tests can pin it without re-deriving the constant.
CRISIS_DOSSIER_VIEWER_PATH = "dashboard/crisis_dossier_viewer.py"


# ─── Pure helper (Streamlit-free) ────────────────────────────────────


def build_catalog_view(
    catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Shape the report registry catalog for display.

    Parameters
    ----------
    catalog
        Optional pre-fetched catalog. Pass ``None`` (the default) to read
        from :func:`cbsrm.reporting.get_report_catalog`. The injection
        seam exists so callers (tests, future composer layers) can drive
        the viewer with a synthetic catalog without monkeypatching the
        registry.

    Returns
    -------
    dict with keys:
        ``report_count``  — number of reports
        ``reports``       — list of report metadata dicts (deep copies)
        ``crisis_dossier_viewer_path`` — relative path string used to
                            link to the existing per-window detail viewer

    Notes
    -----
    Pure, deterministic, Streamlit-free. Never executes a report.
    """
    if catalog is None:
        catalog = get_report_catalog()
    # ``get_report_catalog`` already returns fresh deep copies. When the
    # caller supplies a custom catalog dict we trust them not to mutate
    # the input concurrently with our consumption — the helper still
    # returns a new top-level dict so downstream mutation is local.
    reports = list(catalog.get("reports", []))
    return {
        "report_count": len(reports),
        "reports": reports,
        "crisis_dossier_viewer_path": CRISIS_DOSSIER_VIEWER_PATH,
    }


# ─── Streamlit UI (lazy streamlit import) ────────────────────────────


def render() -> None:
    """Render the Streamlit page. Imports Streamlit lazily so this
    module stays import-safe in environments without Streamlit
    installed."""
    import streamlit as st

    st.set_page_config(
        page_title="CBSRM Report Catalog",
        layout="wide",
    )
    st.title("CBSRM Report Catalog")
    st.caption(
        "Deterministic registry of available v0.9 reports. "
        "Metadata only — no report is executed by this page. "
        "Research only — **not financial advice**."
    )

    view = build_catalog_view()

    if view["report_count"] == 0:
        st.info("No reports are currently registered.")
        return

    for entry in view["reports"]:
        st.header(entry["title"])
        st.caption(f"`{entry['id']}`")
        st.markdown(entry["description"])

        col_formats, col_windows = st.columns(2)
        with col_formats:
            st.markdown("**Supported formats**")
            for fmt in entry.get("formats", []):
                st.markdown(f"- `{fmt}`")
        with col_windows:
            st.markdown("**Supported windows**")
            windows = entry.get("windows", [])
            if windows:
                for window in windows:
                    st.markdown(f"- `{window}`")
            else:
                st.markdown("_(none)_")

        with st.expander("Available surfaces"):
            surfaces = entry.get("surfaces", {})
            cli = surfaces.get("cli")
            if cli:
                st.markdown("**CLI**")
                st.code(cli, language="bash")
            api_routes = surfaces.get("api", [])
            if api_routes:
                st.markdown("**HTTP API**")
                for route in api_routes:
                    st.code(route, language="text")
            streamlit_cmd = surfaces.get("streamlit")
            if streamlit_cmd:
                st.markdown("**Streamlit**")
                st.code(streamlit_cmd, language="bash")

        st.markdown("---")

    st.markdown(
        "Per-window detail for the crisis-dossier report is in the "
        f"companion viewer at `{view['crisis_dossier_viewer_path']}` — "
        "run `streamlit run dashboard/crisis_dossier_viewer.py`."
    )


if __name__ == "__main__":  # pragma: no cover - exercised by `streamlit run`
    render()
