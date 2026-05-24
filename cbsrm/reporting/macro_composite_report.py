"""
cbsrm.reporting.macro_composite_report — executable macro-composite report.

A deterministic, offline, fixture-backed builder that produces a
phase-classifier snapshot for one of the canonical crisis windows
(``2008Q4`` / ``2020Q1`` / ``2023Q1``). This is the v0.9 first cut of
the registry's ``macro-composite`` entry — phase-classifier-only.
Integration with :func:`cbsrm.macro.classify_regime` (which needs
sub-indicator metadata dicts not yet pinned per window) is deferred to
a follow-up slice.

Design contract
~~~~~~~~~~~~~~~

* **Pure.** No I/O, no network, no filesystem, no Streamlit, no
  wall-clock. Same ``window_id`` → byte-identical dict under
  ``json.dumps(..., sort_keys=True)``.
* **Offline.** No live data adapters. Phase z-scores are pinned in
  this module and drift-guarded against
  ``cbsrm.diagnostics.crisis_dossiers.get_fixture_snapshot``.
* **Compositional, not duplicative.** Consumes only
  :func:`cbsrm.macro.classify_phase`. Does NOT call
  ``build_crisis_dossier`` or ``classify_regime`` — those belong to
  the crisis-dossier report and to a deferred regime-snapshot slice
  respectively.
* **Builder-only.** No CLI / API / Streamlit / manifest / audit /
  persistence wiring in this slice. Downstream surfaces can layer over
  this builder via the existing generic
  :func:`cbsrm.reporting.build_report_manifest` /
  :func:`cbsrm.reporting.store_report_artifact` without modifying this
  module.

Public surface
~~~~~~~~~~~~~~

* :data:`MACRO_COMPOSITE_REPORT_VERSION` — semver of this report spec.
* :data:`MACRO_COMPOSITE_WINDOWS` — canonical 3-tuple of supported
  window IDs.
* :func:`list_macro_composite_windows` — return the supported window
  IDs as a fresh ``list[str]``.
* :func:`build_macro_composite_report` — return a deterministic
  JSON-serializable report dict for one window.
* :func:`render_macro_composite_markdown` — render a report dict as a
  deterministic Markdown string.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping


MACRO_COMPOSITE_REPORT_VERSION = "1.0.0"

MACRO_COMPOSITE_WINDOWS: tuple[str, ...] = ("2008Q4", "2020Q1", "2023Q1")


# Phase z-scores pinned per window. Drift-guarded by a test that
# asserts equality against
# ``cbsrm.diagnostics.crisis_dossiers.get_fixture_snapshot(window_id)
# ["phase_features"]`` — if the diagnostics fixture ever shifts, the
# test fires loudly and the operator must update both sides together.
_MACRO_PHASE_FEATURES: dict[str, dict[str, float]] = {
    "2008Q4": {
        "growth_z":         -2.0,
        "inflation_z":      -0.5,
        "unemployment_z":    1.4,
        "credit_spread_z":   2.6,
        "volatility_z":      2.8,
        "liquidity_z":      -1.5,
        "systemic_risk_z":   2.2,
        "rates_z":          -1.0,
    },
    "2020Q1": {
        "growth_z":         -3.0,
        "inflation_z":      -0.2,
        "unemployment_z":    1.0,
        "credit_spread_z":   1.8,
        "volatility_z":      3.5,
        "liquidity_z":      -2.5,
        "systemic_risk_z":   1.7,
        "rates_z":          -2.0,
    },
    "2023Q1": {
        "growth_z":          0.2,
        "inflation_z":       1.1,
        "unemployment_z":   -0.2,
        "credit_spread_z":   1.0,
        "volatility_z":      0.8,
        "liquidity_z":      -0.6,
        "systemic_risk_z":   1.1,
        "rates_z":           1.2,
    },
}


# Pinned research notes — two deterministic strings per window. They
# describe what the report is, NOT what to trade. The disclaimer field
# carries the canonical NFA boilerplate.
_RESEARCH_NOTES: tuple[str, ...] = (
    "Phase classifier applied to fixture z-scores; deterministic offline.",
    "Companion to the crisis-dossier report for the same window.",
)


# ─── Public API ─────────────────────────────────────────────────────


def list_macro_composite_windows() -> list[str]:
    """Return the supported window IDs as a fresh ``list[str]``.

    The order mirrors :data:`MACRO_COMPOSITE_WINDOWS` (chronological).
    """
    return list(MACRO_COMPOSITE_WINDOWS)


def build_macro_composite_report(window_id: str) -> dict[str, Any]:
    """Build a deterministic macro-composite report dict for one window.

    Parameters
    ----------
    window_id
        One of :data:`MACRO_COMPOSITE_WINDOWS`.

    Returns
    -------
    dict
        JSON-serializable report dict with keys ``report_id``,
        ``window_id``, ``title``, ``phase_features``,
        ``phase_classification``, ``research_notes``, ``disclaimer``,
        ``spec``. A fresh object is returned per call — callers may
        mutate it without affecting subsequent calls.

    Raises
    ------
    ValueError
        If ``window_id`` is not in :data:`MACRO_COMPOSITE_WINDOWS`.
    """
    if window_id not in _MACRO_PHASE_FEATURES:
        raise ValueError(
            f"unknown macro-composite window id {window_id!r}. "
            f"supported = {list_macro_composite_windows()}"
        )

    # Lazy imports keep this module import-safe in any environment
    # where macro / reporting submodules may be unavailable at boot.
    from cbsrm.macro import classify_phase
    from cbsrm.reporting.report_renderer import NFA_DISCLAIMER

    features = dict(_MACRO_PHASE_FEATURES[window_id])
    phase_verdict = classify_phase(features)

    return {
        "report_id": "macro-composite",
        "window_id": window_id,
        "title": f"Macro Composite Snapshot — {window_id}",
        "phase_features": dict(features),
        "phase_classification": copy.deepcopy(phase_verdict),
        "research_notes": list(_RESEARCH_NOTES),
        "disclaimer": NFA_DISCLAIMER,
        "spec": {
            "report_id": "macro-composite",
            "report_version": MACRO_COMPOSITE_REPORT_VERSION,
            "phase_classifier_rule_version": "1.0.0",
            "windows": list(MACRO_COMPOSITE_WINDOWS),
        },
    }


# ─── Markdown renderer ──────────────────────────────────────────────


_REQUIRED_REPORT_KEYS: tuple[str, ...] = (
    "report_id", "window_id", "title", "phase_features",
    "phase_classification", "research_notes", "disclaimer", "spec",
)


def render_macro_composite_markdown(report: Mapping[str, Any]) -> str:
    """Render a macro-composite report dict as deterministic Markdown.

    Parameters
    ----------
    report
        A dict shaped like the output of
        :func:`build_macro_composite_report`.

    Returns
    -------
    str
        Markdown text terminated with a single trailing newline.
        Same input → byte-identical output.

    Raises
    ------
    ValueError
        If ``report`` is missing any required top-level key.
    """
    if not isinstance(report, Mapping):
        raise ValueError(
            "report must be a Mapping shaped like "
            "build_macro_composite_report output"
        )
    missing = [k for k in _REQUIRED_REPORT_KEYS if k not in report]
    if missing:
        raise ValueError(
            f"macro-composite report is missing required keys: {missing}"
        )

    window_id = report["window_id"]
    title = report["title"]
    phase = report["phase_classification"]
    phase_label = phase.get("phase", "indeterminate")
    score = phase.get("score", 0.0)
    risk_posture = phase.get("risk_posture", "unspecified")
    drivers = phase.get("dominant_drivers", []) or []
    features = report["phase_features"]

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Window: `{window_id}`")
    lines.append("")
    lines.append(
        f"Phase: **{phase_label}** "
        f"(score={float(score):.3f}, risk_posture={risk_posture})"
    )
    lines.append("")

    lines.append("## Dominant drivers")
    if drivers:
        for d in drivers:
            lines.append(f"- `{d}`")
    else:
        lines.append("_(none)_")
    lines.append("")

    lines.append("## Phase features")
    lines.append("")
    lines.append("| Feature | z-score |")
    lines.append("|---|---:|")
    # Sort feature keys for byte-identical determinism regardless of
    # the input dict's key insertion order.
    for key in sorted(features.keys()):
        val = float(features[key])
        lines.append(f"| `{key}` | {val:+.3f} |")
    lines.append("")

    lines.append("## Research notes")
    for note in report["research_notes"]:
        lines.append(f"- {note}")
    lines.append("")

    lines.append("## Disclaimer")
    lines.append("")
    lines.append(report["disclaimer"])
    lines.append("")

    return "\n".join(lines) + "\n"
