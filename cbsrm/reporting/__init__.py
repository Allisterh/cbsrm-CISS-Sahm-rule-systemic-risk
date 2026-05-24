"""
cbsrm.reporting — deterministic rendering and export of research outputs.

This subpackage turns the v0.8 research artifacts (today: crisis-window
dossiers from :mod:`cbsrm.diagnostics.crisis_dossiers`) into clean,
SaaS-ready surfaces — Markdown reports for human review, JSON payloads
for storage / API responses / downstream tooling.

Design contract
~~~~~~~~~~~~~~~

* **Offline.** No live API calls, no file writes, no network, no
  filesystem access, no PDF generation, no web app, no auth, no
  billing — pure in-memory transformations.
* **Deterministic.** Same dossier in → same Markdown / JSON out. Safe
  for snapshot tests, audited replay, and stable demo screenshots.
* **Compositional, not duplicative.** Consumes the
  :func:`cbsrm.diagnostics.crisis_dossiers.build_crisis_dossier` output;
  does not re-implement any of the v0.8 surfaces (`score_event`,
  `replay_macro_events`, `debt_rank`, `classify_phase`).

Public surface (v0.8)
~~~~~~~~~~~~~~~~~~~~~

* :func:`render_dossier_markdown` — render a crisis-window dossier as a
  publication-ready Markdown report.
* :func:`build_report_payload` — produce a JSON-serializable dict
  payload suitable for storage or a future SaaS report-download API.
* :data:`REPORT_RENDERER_VERSION` — semantic version of the renderer
  spec (independent of the dossier spec).
* :data:`NFA_DISCLAIMER` — canonical "not financial advice" boilerplate
  appended to every Markdown report.

Public surface (v0.9 work in progress)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* :func:`get_report_catalog` — return the full JSON-serializable
  catalog of available reports.
* :func:`list_report_ids` — alphabetical list of registered report ids.
* :func:`get_report_metadata` — metadata for one report; raises
  :class:`ValueError` for unknown ids.
* :data:`REPORT_REGISTRY_VERSION` — semantic version of the registry
  spec (independent of the renderer and dossier specs).
* :func:`render_dossier_html` — render a crisis-window dossier as
  deterministic HTML suitable for browser print-to-PDF. Requires the
  optional ``markdown`` package (``pip install cbsrm[html]``).
* :data:`HTML_RENDERER_VERSION` — semantic version of the HTML
  renderer spec.
* :func:`build_report_manifest` — build a deterministic export-time
  manifest describing a rendered report (report id, window, format,
  versions, output sha256). Pure / offline / no wall-clock by default.
* :func:`sha256_text`, :func:`sha256_jsonable` — hash helpers used by
  the manifest layer; safe to use stand-alone.
* :data:`MANIFEST_VERSION` — semantic version of the manifest spec.
"""
from cbsrm.reporting.html_renderer import (
    HTML_RENDERER_VERSION,
    render_dossier_html,
)
from cbsrm.reporting.manifest import (
    MANIFEST_VERSION,
    build_report_manifest,
    sha256_jsonable,
    sha256_text,
)
from cbsrm.reporting.registry import (
    REPORT_REGISTRY_VERSION,
    get_report_catalog,
    get_report_metadata,
    list_report_ids,
)
from cbsrm.reporting.report_renderer import (
    NFA_DISCLAIMER,
    REPORT_RENDERER_VERSION,
    build_report_payload,
    render_dossier_markdown,
)

__all__ = [
    "render_dossier_markdown",
    "build_report_payload",
    "REPORT_RENDERER_VERSION",
    "NFA_DISCLAIMER",
    "get_report_catalog",
    "list_report_ids",
    "get_report_metadata",
    "REPORT_REGISTRY_VERSION",
    "render_dossier_html",
    "HTML_RENDERER_VERSION",
    "build_report_manifest",
    "sha256_text",
    "sha256_jsonable",
    "MANIFEST_VERSION",
]
