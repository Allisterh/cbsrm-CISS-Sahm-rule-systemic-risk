"""
cbsrm.reporting.registry — deterministic catalog of available reports.

This module is a *read-only* directory of the reports that the cbsrm
package can produce. It is the bridge between the v0.8 hardcoded
crisis-dossier surface and a future SaaS-style report catalog.

Design contract
~~~~~~~~~~~~~~~

* **Pure metadata.** Functions in this module never execute a report,
  never touch the network, and never write to disk.
* **Deterministic.** Given the same diagnostics fixtures, every call to
  :func:`get_report_catalog` returns equal data — same ids, same
  ordering, same JSON-serializable shape.
* **Composition over duplication.** ``windows`` for the crisis-dossier
  report are pulled live from
  :func:`cbsrm.diagnostics.list_dossier_windows`, so the registry
  cannot drift if new dossier fixtures are added.
* **Defensive ownership.** All return values are *fresh* copies; the
  caller may mutate them without affecting subsequent calls.

Public surface (v0.9 work in progress)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* :func:`get_report_catalog` — return the full ``{"reports": [...]}``
  catalog as a JSON-serializable dict.
* :func:`list_report_ids` — return the alphabetical list of report ids.
* :func:`get_report_metadata` — return the metadata dict for one
  report; raise :class:`ValueError` if the id is unknown.
* :data:`REPORT_REGISTRY_VERSION` — semantic version of the registry
  spec, independent of the report-renderer and dossier specs.
"""
from __future__ import annotations

import copy
from typing import Any


REPORT_REGISTRY_VERSION = "1.0.0"


# ─── Internal: report metadata builders ─────────────────────────────


def _crisis_dossier_entry() -> dict[str, Any]:
    """Build the crisis-dossier registry entry.

    ``windows`` is sourced live from
    :func:`cbsrm.diagnostics.list_dossier_windows` so the registry
    cannot fall out of sync as new dossier fixtures land. All other
    metadata is intentionally pinned in-source — this is the catalog
    contract, not the runtime contract.
    """
    # Lazy import keeps cbsrm.reporting import-safe in any environment
    # where diagnostics may not yet be wired (defensive — diagnostics
    # is part of the core package today).
    from cbsrm.diagnostics import list_dossier_windows

    return {
        "id": "crisis-dossier",
        "title": "Crisis Dossier",
        "description": (
            "Historical crisis-window research dossier composed from "
            "macro events, replay surfaces, DebtRank network stress, "
            "and Acemoglu-style phase classification. Deterministic, "
            "fixture-backed, offline."
        ),
        "formats": ["json", "markdown"],
        "windows": list(list_dossier_windows()),
        "surfaces": {
            "cli": "cbsrm crisis-dossier WINDOW --format json|markdown",
            "api": [
                "GET /reports/crisis-dossiers",
                "GET /reports/crisis-dossiers/{window_id}",
                "GET /reports/crisis-dossiers/{window_id}/markdown",
            ],
            "streamlit": (
                "streamlit run dashboard/crisis_dossier_viewer.py"
            ),
        },
    }


def _macro_composite_entry() -> dict[str, Any]:
    """Build the macro-composite registry entry.

    Python-executable through
    :func:`cbsrm.reporting.build_macro_composite_report`, with three
    dedicated front-ends now on ``main``: a CLI subcommand
    (``cbsrm macro-composite WINDOW --format json|markdown``), three
    read-only HTTP API routes
    (``GET /reports/macro-composite[/{window_id}[/markdown]]``), and a
    standalone Streamlit viewer
    (``streamlit run dashboard/macro_composite_viewer.py``). The
    ``surfaces`` field below now advertises all three. The v0.9 first
    cut is phase-classifier-only — it composes
    :func:`cbsrm.macro.classify_phase` over pinned per-window
    z-scores. Integration with :func:`cbsrm.macro.classify_regime`
    (which needs sub-indicator metadata dicts not yet pinned per
    window), plus manifest / audit / persistence wiring for this
    report, are deferred to follow-up slices.
    """
    # Lazy import keeps cbsrm.reporting.registry import-safe in any
    # environment where the macro-composite report module may not yet
    # be wired (defensive — both modules ship together today).
    from cbsrm.reporting.macro_composite_report import (
        list_macro_composite_windows,
    )

    return {
        "id": "macro-composite",
        "title": "Macro Composite Snapshot",
        "description": (
            "Deterministic, fixture-backed macro-composite snapshot. "
            "Python-executable through "
            "cbsrm.reporting.build_macro_composite_report(window_id), "
            "with dedicated CLI / API / Streamlit front-ends on main. "
            "The v0.9 first cut is phase-classifier-only: it composes "
            "cbsrm.macro.classify_phase over pinned per-window z-scores "
            "for the same canonical windows as the crisis-dossier "
            "report (2008Q4 / 2020Q1 / 2023Q1). Integration with "
            "cbsrm.macro.classify_regime, plus manifest / audit / "
            "persistence wiring for this report, are deferred to "
            "follow-up slices."
        ),
        "formats": ["json", "markdown"],
        "windows": list(list_macro_composite_windows()),
        "surfaces": {
            "cli": "cbsrm macro-composite WINDOW --format json|markdown",
            "api": [
                "GET /reports/macro-composite",
                "GET /reports/macro-composite/{window_id}",
                "GET /reports/macro-composite/{window_id}/markdown",
            ],
            "streamlit": (
                "streamlit run dashboard/macro_composite_viewer.py"
            ),
        },
    }


# Ordered tuple of metadata builders. New reports are appended here;
# `get_report_catalog` deep-copies their output on every call. Catalog
# insertion order is deterministic and pinned by
# ``test_catalog_lists_both_reports_in_deterministic_order``.
_REPORT_BUILDERS: tuple = (
    _crisis_dossier_entry,
    _macro_composite_entry,
)


# ─── Public API ─────────────────────────────────────────────────────


def get_report_catalog() -> dict[str, Any]:
    """Return the full report catalog as a JSON-serializable dict.

    Shape::

        {
            "reports": [
                {"id": ..., "title": ..., "description": ...,
                 "formats": [...], "windows": [...],
                 "surfaces": {"cli": ..., "api": [...], "streamlit": ...}},
                ...
            ]
        }

    The returned object is a fresh deep copy — callers may freely
    mutate it without affecting subsequent calls.
    """
    return {
        "reports": [copy.deepcopy(builder()) for builder in _REPORT_BUILDERS],
    }


def list_report_ids() -> list[str]:
    """Return the alphabetical list of registered report ids."""
    return sorted(entry["id"] for entry in (b() for b in _REPORT_BUILDERS))


def get_report_metadata(report_id: str) -> dict[str, Any]:
    """Return the metadata dict for ``report_id``.

    Raises
    ------
    ValueError
        If ``report_id`` is not a registered report. The supported
        ids are listed in the message so callers can recover.
    """
    for builder in _REPORT_BUILDERS:
        entry = builder()
        if entry["id"] == report_id:
            return copy.deepcopy(entry)
    raise ValueError(
        f"unknown report id {report_id!r}. "
        f"supported = {list_report_ids()}"
    )
