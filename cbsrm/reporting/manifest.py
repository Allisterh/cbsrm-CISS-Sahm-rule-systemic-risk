"""
cbsrm.reporting.manifest — deterministic export-time manifests.

A manifest *describes* a report export: which report, which window,
which format, which package versions produced it, and the sha256 of
the output bytes.  It is metadata only — it does not embed the
output, and it never executes a report.

Design contract
~~~~~~~~~~~~~~~

* **Deterministic by default.** Same inputs produce byte-identical
  manifests.  No wall-clock anywhere.  ``generated_at_utc`` is an
  opt-in caller-supplied string; when omitted, the field is ``None``
  and repeated calls produce equal manifests.
* **Pure.** No network, no filesystem writes, no PDF lib, no
  Markdown / HTML rendering at manifest-build time.  The manifest
  hashes the output text the caller already produced.
* **JSON-serializable.** ``json.dumps(manifest)`` round-trips.
* **Compositional, not duplicative.** Reads version constants from
  :mod:`cbsrm`, :mod:`cbsrm.reporting.registry`,
  :mod:`cbsrm.reporting.report_renderer`,
  :mod:`cbsrm.reporting.html_renderer`.  Pulls ``dossier_version`` /
  ``fixture_version`` from the dossier's own ``spec`` block when a
  dossier is supplied — no re-implementation of dossier internals.

Public surface (v0.9 work in progress)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* :func:`build_report_manifest` — build a deterministic manifest dict.
* :func:`sha256_text` — hex-encoded sha256 of UTF-8 text.
* :func:`sha256_jsonable` — hex-encoded sha256 of a JSON-serializable
  object using sorted keys (key-order independent).
* :data:`MANIFEST_VERSION` — semantic version of the manifest spec
  (independent of the renderer / registry / dossier specs).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


MANIFEST_VERSION = "1.0.0"


_SUPPORTED_FORMATS = ("json", "markdown", "html")
_SUPPORTED_SOURCES = ("python", "cli", "api", "streamlit")


# ─── Hash helpers ───────────────────────────────────────────────────


def sha256_text(text: str) -> str:
    """Return hex-encoded SHA-256 of ``text`` encoded as UTF-8.

    Raises
    ------
    TypeError
        If ``text`` is not a :class:`str`.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"sha256_text expected str, got {type(text).__name__}"
        )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_jsonable(obj: Any) -> str:
    """Return hex-encoded SHA-256 of a JSON-serializable object.

    Serialises ``obj`` with sorted keys and a compact separator set so
    the hash is independent of dict key insertion order. UTF-8 is
    preserved (``ensure_ascii=False``) so non-ASCII characters like the
    composition arrow ``→`` hash identically whether they arrive as
    raw codepoints or post-decode strings.

    Raises
    ------
    TypeError
        If ``obj`` is not JSON-serializable.
    """
    canonical = json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ─── Internal: helpers ──────────────────────────────────────────────


def _extract_dossier_versions(
    dossier: Mapping[str, Any] | None,
) -> tuple[str | None, str | None]:
    """Return ``(dossier_version, fixture_version)`` from a dossier's
    ``spec`` block, or ``(None, None)`` if the dossier is absent or
    the keys are missing. Best-effort; never raises on missing fields.
    """
    if dossier is None:
        return (None, None)
    spec = dossier.get("spec") if isinstance(dossier, Mapping) else None
    if not isinstance(spec, Mapping):
        return (None, None)
    dv = spec.get("dossier_version")
    fv = spec.get("fixture_version")
    return (
        dv if isinstance(dv, str) else None,
        fv if isinstance(fv, str) else None,
    )


def _detect_disclaimer(output_text: str) -> bool:
    """Return True iff the output carries the canonical NFA disclaimer.

    Detection is a substring check against the literal ``Disclaimer``
    heading that :func:`cbsrm.reporting.render_dossier_markdown`
    appends to every Markdown report. HTML inherits the disclaimer
    via composition over Markdown. JSON envelopes produced by
    :func:`cbsrm.reporting.build_report_payload` also carry it under
    ``payload['report']['disclaimer']``, so the typical crisis-dossier
    JSON export will also return ``True`` here. The flag tracks the
    actual output bytes — a caller emitting a stripped-down output
    will honestly surface ``False``.
    """
    return "Disclaimer" in output_text


# ─── Public API ─────────────────────────────────────────────────────


def build_report_manifest(
    *,
    report_id: str,
    output_text: str,
    output_format: str,
    window_id: str | None = None,
    source: str = "python",
    dossier: Mapping[str, Any] | None = None,
    payload: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic manifest describing a report export.

    Parameters
    ----------
    report_id :
        Identifier of the report (e.g. ``"crisis-dossier"``). Must be
        a non-empty :class:`str`.
    output_text :
        The exact rendered output bytes-as-text (Markdown / HTML / JSON
        string). Hashed via :func:`sha256_text`; not interpreted.
    output_format :
        One of ``{"json", "markdown", "html"}``.
    window_id :
        Optional window identifier (e.g. ``"2008Q4"``) for
        window-keyed reports.
    source :
        One of ``{"python", "cli", "api", "streamlit"}``. Defaults to
        ``"python"``.
    dossier :
        Optional dossier dict. When supplied, ``versions.dossier`` and
        ``versions.fixture`` are extracted from ``dossier["spec"]``.
    payload :
        Optional JSON-serializable payload object. When supplied, its
        canonical-form sha256 is stored under ``hashes.payload_sha256``.
    generated_at_utc :
        Optional ISO-8601 UTC timestamp string. The manifest stores it
        verbatim; no parsing or normalisation. When omitted, the
        manifest is fully deterministic.

    Returns
    -------
    dict
        A JSON-serializable manifest dict. Same inputs produce equal
        manifests.

    Raises
    ------
    TypeError
        If ``output_text`` is not a :class:`str`, or if
        ``generated_at_utc`` is supplied but is not a :class:`str`.
    ValueError
        If ``report_id`` is empty, or if ``output_format`` /
        ``source`` is not one of the supported values.
    """
    # ── Validation ──
    if not isinstance(report_id, str) or not report_id:
        raise ValueError("report_id must be a non-empty str")
    if not isinstance(output_text, str):
        raise TypeError(
            f"output_text must be str, got {type(output_text).__name__}"
        )
    if output_format not in _SUPPORTED_FORMATS:
        raise ValueError(
            f"output_format must be one of {_SUPPORTED_FORMATS}, "
            f"got {output_format!r}"
        )
    if source not in _SUPPORTED_SOURCES:
        raise ValueError(
            f"source must be one of {_SUPPORTED_SOURCES}, got {source!r}"
        )
    if generated_at_utc is not None and not isinstance(
        generated_at_utc, str
    ):
        raise TypeError(
            f"generated_at_utc must be str or None, got "
            f"{type(generated_at_utc).__name__}"
        )

    # ── Lazy version reads (so the manifest module stays import-safe
    #    even if a downstream version constant is ever moved). ──
    from cbsrm import __version__ as cbsrm_version
    from cbsrm.reporting.html_renderer import HTML_RENDERER_VERSION
    from cbsrm.reporting.registry import REPORT_REGISTRY_VERSION
    from cbsrm.reporting.report_renderer import REPORT_RENDERER_VERSION

    dossier_version, fixture_version = _extract_dossier_versions(dossier)

    hashes: dict[str, Any] = {
        "output_sha256": sha256_text(output_text),
    }
    if payload is not None:
        hashes["payload_sha256"] = sha256_jsonable(payload)

    return {
        "manifest_version": MANIFEST_VERSION,
        "report_id": report_id,
        "window_id": window_id,
        "format": output_format,
        "source": source,
        "generated_at_utc": generated_at_utc,
        "versions": {
            "cbsrm": cbsrm_version,
            "registry": REPORT_REGISTRY_VERSION,
            "report_renderer": REPORT_RENDERER_VERSION,
            "html_renderer": HTML_RENDERER_VERSION,
            "dossier": dossier_version,
            "fixture": fixture_version,
        },
        "hashes": hashes,
        "disclaimer_present": _detect_disclaimer(output_text),
    }
