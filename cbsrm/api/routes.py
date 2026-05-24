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


def build_app(audit_conn: sqlite3.Connection | None = None):
    """Construct the FastAPI app. Returns the app instance.

    Pass an audit_conn to share an audit chain across the service; if None
    an in-memory sqlite is used (audit chain non-persistent).
    """
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as e:
        raise RuntimeError(
            "FastAPI not installed. Install with: pip install cbsrm[api]"
        ) from e

    if audit_conn is None:
        audit_conn = sqlite3.connect(":memory:", check_same_thread=False)
    audit = AuditChain(audit_conn)

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
        rows = audit.query_subject(subject, limit=limit)
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
        ok, broken = audit.verify()
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
    def get_crisis_dossier(window_id: str) -> dict[str, Any]:
        """Return the JSON report payload for one crisis window.

        Shape: ``{"report": {...}, "dossier": {...}}`` — identical to
        ``cbsrm crisis-dossier WINDOW --format json``.
        """
        from cbsrm.reporting import build_report_payload

        dossier = _resolve_dossier_or_404(window_id)
        return build_report_payload(dossier)

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

    return app


# Module-level app for `uvicorn cbsrm.api.routes:app`
try:
    app = build_app()
except RuntimeError:
    # FastAPI not installed — that's fine, importer can call build_app later
    app = None
