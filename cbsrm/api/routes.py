"""
FastAPI service exposing CBSRM indicators.

Run with:
    pip install cbsrm[api]
    uvicorn cbsrm.api.routes:app --reload

Endpoints (v0.1):
    GET  /                      — service info
    GET  /health                — healthz
    GET  /indicators            — list registered indicators
    GET  /indicators/{id}/latest
    GET  /indicators/{id}/series?start=YYYY-MM-DD&end=YYYY-MM-DD
    GET  /audit/{subject}       — audit chain for one subject
    POST /audit/verify          — verify chain integrity

This module intentionally imports FastAPI lazily so that the core
indicator + audit code remains importable in environments without
fastapi installed (e.g. notebooks).
"""
from __future__ import annotations

import sqlite3
from typing import Any

from cbsrm import __version__
from cbsrm.audit.chain import AuditChain


def build_app(
    audit_conn: sqlite3.Connection | None = None,
    report_store_db_path: str | None = None,
):
    """Construct the FastAPI app. Returns the app instance.

    Pass an audit_conn to share an audit chain across the service; if None
    an in-memory sqlite is used (audit chain non-persistent).

    Pass ``report_store_db_path`` to enable the v0.9 sqlite report-artifact
    store. When set, the store's schema is initialised at app-construction
    time (`init_report_store(...)`), and the JSON crisis-dossier endpoint
    accepts ``?store=true`` plus a new ``GET /reports/stored/{output_sha256}``
    lookup endpoint becomes meaningful. When **None** (default), both
    surfaces return ``HTTP 400`` with a clear hint instead of writing to
    any path. The route layer never reads a filesystem path from the
    request — operator-config only, to keep the attack surface flat.
    """
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as e:
        raise RuntimeError(
            "FastAPI not installed. Install with: pip install cbsrm[api]"
        ) from e

    if audit_conn is None:
        audit_conn = sqlite3.connect(":memory:", check_same_thread=False)
    # Closure variable is renamed from ``audit`` to ``audit_chain`` so
    # the v0.9 JSON crisis-dossier endpoint can expose an ``audit:
    # bool`` query parameter without a name collision.
    audit_chain = AuditChain(audit_conn)

    # Initialise the report-artifact store schema once, at
    # app-construction time. Fails fast on unwritable paths
    # (sqlite3.OperationalError) so the operator sees the misconfig
    # before any request lands.
    if report_store_db_path is not None:
        from cbsrm.reporting import init_report_store

        init_report_store(report_store_db_path)

    app = FastAPI(
        title="CBSRM — Cross-Border Systemic Risk Monitor",
        version=__version__,
        description=(
            "Open-source quantitative framework for cross-jurisdiction "
            "systemic-stress monitoring. Apache-2.0 licensed. "
            "See https://github.com/pravo123/cbsrm for the whitepaper "
            "and methodology details."
        ),
    )

    @app.get("/", tags=["meta"])
    def root() -> dict[str, Any]:
        return {
            "service": "cbsrm",
            "version": __version__,
            "tier": "public",
            "docs": "/docs",
            "whitepaper": "whitepaper/cbsrm_methodology_v1.md",
            "license": "Apache-2.0",
        }

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/indicators", tags=["indicators"])
    def list_indicators() -> dict[str, Any]:
        from cbsrm.indicators import CISSUS, STLFSIWrap

        registry = [
            {
                "id": STLFSIWrap.id,
                "version": STLFSIWrap.version,
                "source": STLFSIWrap.source,
                "requires": STLFSIWrap().required_series(),
            },
            {
                "id": CISSUS.id,
                "version": CISSUS.version,
                "source": CISSUS.source,
                "requires": CISSUS().required_series(),
            },
        ]
        return {"indicators": registry}

    @app.get("/audit/{subject}", tags=["audit"])
    def get_audit(subject: str, limit: int = 100) -> dict[str, Any]:
        rows = audit_chain.query_subject(subject, limit=limit)
        return {
            "subject": subject,
            "n_rows": len(rows),
            "rows": [
                {
                    "id": r.id, "ts": r.ts, "kind": r.kind,
                    "subject": r.subject, "payload": r.payload,
                    "hash": r.hash, "prev_hash": r.prev_hash,
                }
                for r in rows
            ],
        }

    @app.post("/audit/verify", tags=["audit"])
    def verify_audit() -> dict[str, Any]:
        ok, broken = audit_chain.verify()
        if not ok:
            raise HTTPException(
                status_code=409,
                detail={"chain_ok": False, "broken_row_ids": broken},
            )
        return {"chain_ok": True, "broken_row_ids": []}

    # ─── Report catalog (read-only) ─────────────────────────────────
    #
    # Thin pass-through over `cbsrm.reporting.get_report_catalog()`.
    # Returns a deterministic JSON catalog of available reports —
    # metadata only, no report is executed. The catalog itself is
    # versioned independently by `REPORT_REGISTRY_VERSION`.

    @app.get("/reports", tags=["reports"])
    def list_reports() -> dict[str, Any]:
        """Return the deterministic catalog of available reports.

        Shape: ``{"reports": [{"id": ..., "title": ..., "description":
        ..., "formats": [...], "windows": [...], "surfaces": {...}}]}``.
        Calling this endpoint never executes a report.
        """
        from cbsrm.reporting import get_report_catalog

        return get_report_catalog()

    # ─── v0.8 crisis-window reports (read-only) ─────────────────────
    #
    # Thin mirror of the CLI `crisis-dossier` surface. Pure composition
    # of `cbsrm.diagnostics.build_crisis_dossier` with the
    # `cbsrm.reporting` payload/renderer. No methodology added here.
    #
    # Lazy imports keep the FastAPI module importable in environments
    # without the optional reporting stack ready at boot.

    def _resolve_dossier_or_404(window_id: str):
        """Build a dossier for ``window_id`` or raise a 404 with the
        supported-window list. Centralised so JSON and Markdown routes
        share the same error contract."""
        from cbsrm.diagnostics import (
            build_crisis_dossier,
            list_dossier_windows,
        )

        supported = list_dossier_windows()
        if window_id not in supported:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"unknown crisis-dossier window '{window_id}'",
                    "window_id": window_id,
                    "supported_windows": list(supported),
                },
            )
        try:
            return build_crisis_dossier(window_id)
        except ValueError as exc:
            # Defence in depth — the membership check above should make
            # this unreachable, but if the registry shape ever drifts
            # the API still fails clean (no traceback leak).
            raise HTTPException(
                status_code=404,
                detail={
                    "error": str(exc),
                    "window_id": window_id,
                    "supported_windows": list(supported),
                },
            ) from None

    @app.get("/reports/crisis-dossiers", tags=["reports"])
    def list_crisis_dossiers() -> dict[str, Any]:
        """List the supported crisis-dossier window IDs."""
        from cbsrm.diagnostics import list_dossier_windows

        return {"windows": list(list_dossier_windows())}

    @app.get("/reports/crisis-dossiers/{window_id}", tags=["reports"])
    def get_crisis_dossier(
        window_id: str,
        manifest: bool = False,
        audit: bool = False,
        store: bool = False,
    ) -> dict[str, Any]:
        """Return the JSON report payload for one crisis window.

        Shape (matrix of the two query flags):

        +----------+-------+-------------------------------------------+
        | manifest | audit | response keys                             |
        +==========+=======+===========================================+
        | false    | false | ``report``, ``dossier`` (v0.8 unchanged)  |
        | true     | false | ``report``, ``dossier``, ``manifest``     |
        | false    | true  | ``report``, ``dossier``, ``manifest``,    |
        |          |       | ``audit`` (manifest auto-built)           |
        | true     | true  | ``report``, ``dossier``, ``manifest``,    |
        |          |       | ``audit``                                 |
        +----------+-------+-------------------------------------------+

        When ``?audit=true`` the manifest is appended to the app's
        :class:`AuditChain` as one ``REPORT_EXPORTED`` row, and the
        response ``audit`` key carries the row metadata
        (``row_id``, ``hash``, ``prev_hash``, ``ts``, ``subject``,
        ``kind``). The chain row's ``ts`` is wall-clock UTC set inside
        :meth:`AuditChain.append`; the manifest's own
        ``generated_at_utc`` field is independent
        (deterministic-by-default).

        The manifest's ``output_sha256`` hashes the *core* canonical
        payload JSON text (matching the CLI ``--format json`` output
        byte-for-byte), not the self-referential response envelope
        that includes the manifest. This keeps CLI ↔ API hash parity
        for the same window across all four matrix rows.
        """
        import json as _json

        from cbsrm.reporting import build_report_payload

        # Fail-fast before any rendering: ?store=true on an
        # unconfigured app is a misconfiguration, not a 5xx.
        if store and report_store_db_path is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "report store is not configured",
                    "hint": (
                        "Configure build_app(report_store_db_path=...) "
                        "before using ?store=true."
                    ),
                },
            )

        dossier = _resolve_dossier_or_404(window_id)
        payload = build_report_payload(dossier)
        if not manifest and not audit and not store:
            return payload

        from cbsrm.reporting import (
            build_report_manifest,
            stamp_manifest_to_chain,
        )

        canonical = (
            _json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        )
        manifest_dict = build_report_manifest(
            report_id="crisis-dossier",
            output_text=canonical,
            output_format="json",
            window_id=window_id,
            source="api",
            dossier=dossier,
            payload=payload,
        )

        response: dict[str, Any] = {**payload, "manifest": manifest_dict}
        if audit:
            audit_row = stamp_manifest_to_chain(audit_chain, manifest_dict)
            response["audit"] = audit_row
        if store:
            from cbsrm.reporting import store_report_artifact

            stored = store_report_artifact(
                report_store_db_path,  # type: ignore[arg-type]
                output_text=canonical,
                manifest=manifest_dict,
            )
            # Narrow projection: don't duplicate output_text /
            # manifest already present in the envelope.
            response["stored"] = {
                "output_sha256":  stored["output_sha256"],
                "was_existing":   stored["was_existing"],
                "byte_length":    stored["byte_length"],
                "content_type":   stored["content_type"],
                "created_at_utc": stored["created_at_utc"],
            }
        return response

    @app.get(
        "/reports/crisis-dossiers/{window_id}/markdown",
        tags=["reports"],
        response_class=None,  # set per-call below
    )
    def get_crisis_dossier_markdown(window_id: str):
        """Return the Markdown report for one crisis window.

        Media type: ``text/markdown; charset=utf-8``. Body is identical
        to ``cbsrm crisis-dossier WINDOW --format markdown``.
        """
        from fastapi.responses import PlainTextResponse
        from cbsrm.reporting import render_dossier_markdown

        dossier = _resolve_dossier_or_404(window_id)
        return PlainTextResponse(
            content=render_dossier_markdown(dossier),
            media_type="text/markdown; charset=utf-8",
        )

    @app.get(
        "/reports/crisis-dossiers/{window_id}/html",
        tags=["reports"],
        response_class=None,  # set per-call below
    )
    def get_crisis_dossier_html(window_id: str):
        """Return the HTML report for one crisis window.

        Media type: ``text/html; charset=utf-8``. Body is identical to
        ``cbsrm crisis-dossier WINDOW --format html`` and suitable for
        browser print-to-PDF. Requires the optional ``cbsrm[html]``
        extra (``markdown`` package) on the server.
        """
        from fastapi.responses import HTMLResponse
        from cbsrm.reporting import render_dossier_html

        dossier = _resolve_dossier_or_404(window_id)
        return HTMLResponse(
            content=render_dossier_html(dossier),
            media_type="text/html; charset=utf-8",
        )

    # ─── v0.9 macro-composite report (read-only, first cut) ─────────
    #
    # Sibling of the crisis-dossier surface: three routes mirroring
    # `/reports/crisis-dossiers*` shape — list endpoint, JSON detail
    # endpoint, and Markdown detail endpoint. Pure pass-through over
    # `cbsrm.reporting.build_macro_composite_report` and
    # `cbsrm.reporting.render_macro_composite_markdown`. No
    # manifest/audit/store query params in this slice — those stay
    # deferred behind the existing generic helpers and can layer in
    # later without changing these route signatures.

    def _resolve_macro_composite_or_404(window_id: str) -> dict[str, Any]:
        """Build a macro-composite report for ``window_id`` or raise
        a 404 with the supported-window list. Centralised so JSON and
        Markdown routes share the same error contract."""
        from cbsrm.reporting import (
            build_macro_composite_report,
            list_macro_composite_windows,
        )

        supported = list_macro_composite_windows()
        if window_id not in supported:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"unknown macro-composite window '{window_id}'",
                    "window_id": window_id,
                    "supported_windows": list(supported),
                },
            )
        try:
            return build_macro_composite_report(window_id)
        except ValueError as exc:
            # Defence in depth — the membership check above should make
            # this unreachable, but if the builder shape ever drifts the
            # API still fails clean (no traceback leak).
            raise HTTPException(
                status_code=404,
                detail={
                    "error": str(exc),
                    "window_id": window_id,
                    "supported_windows": list(supported),
                },
            ) from None

    @app.get("/reports/macro-composite", tags=["reports"])
    def list_macro_composite() -> dict[str, Any]:
        """List the supported macro-composite window IDs."""
        from cbsrm.reporting import list_macro_composite_windows

        return {"windows": list_macro_composite_windows()}

    @app.get(
        "/reports/macro-composite/{window_id}", tags=["reports"],
    )
    def get_macro_composite(window_id: str) -> dict[str, Any]:
        """Return the deterministic macro-composite JSON report for
        one canonical window. Body is byte-identical to
        ``cbsrm macro-composite WINDOW`` (default ``--format json``).
        """
        return _resolve_macro_composite_or_404(window_id)

    @app.get(
        "/reports/macro-composite/{window_id}/markdown",
        tags=["reports"],
        response_class=None,  # set per-call below
    )
    def get_macro_composite_markdown(window_id: str):
        """Return the Markdown macro-composite report for one window.

        Media type: ``text/markdown; charset=utf-8``. Body is identical
        to ``cbsrm macro-composite WINDOW --format markdown``.
        """
        from fastapi.responses import PlainTextResponse
        from cbsrm.reporting import render_macro_composite_markdown

        report = _resolve_macro_composite_or_404(window_id)
        return PlainTextResponse(
            content=render_macro_composite_markdown(report),
            media_type="text/markdown; charset=utf-8",
        )

    # ─── Report-artifact store lookup (v0.9) ────────────────────────
    #
    # Read-only fetch by ``output_sha256`` from the operator-configured
    # sqlite store. Returns 400 when the app was not built with a
    # ``report_store_db_path``, mirroring the JSON endpoint's
    # ``?store=true`` behaviour — clients can detect "feature wired
    # but unconfigured" vs "artifact absent" by status code.
    #
    # No filesystem path is ever read from the request; the only path
    # in scope is the operator-supplied ``report_store_db_path``
    # captured in this closure.

    @app.get(
        "/reports/stored/{output_sha256}", tags=["reports"],
    )
    def get_stored_artifact(output_sha256: str) -> dict[str, Any]:
        """Return the full stored report artifact for a sha256 key."""
        if report_store_db_path is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "report store is not configured",
                    "hint": (
                        "Configure build_app(report_store_db_path=...) "
                        "to enable /reports/stored/{output_sha256}."
                    ),
                },
            )
        from cbsrm.reporting import get_report_artifact

        row = get_report_artifact(report_store_db_path, output_sha256)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "artifact not found",
                    "output_sha256": output_sha256,
                },
            )
        return row

    return app


# Module-level app for `uvicorn cbsrm.api.routes:app`
try:
    app = build_app()
except RuntimeError:
    # FastAPI not installed — that's fine, importer can call build_app later
    app = None
