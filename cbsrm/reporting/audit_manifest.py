"""
cbsrm.reporting.audit_manifest — bridge from v0.9 report manifests
into the existing :mod:`cbsrm.audit.chain` tamper-evident log.

Design contract
~~~~~~~~~~~~~~~

* **Thin bridge, not a re-implementation.** This module never touches
  :mod:`cbsrm.audit.chain` internals — it only constructs an
  :class:`~cbsrm.audit.chain.AuditEvent` and calls the existing public
  ``AuditChain.append`` method.
* **Read-only on manifest dicts.** ``stamp_manifest_to_chain`` does
  not mutate the manifest; it copies it into the audit payload.
* **Raw-string kind.** Uses the string literal ``"REPORT_EXPORTED"``
  rather than extending the :class:`AuditEventKind` enum, so this
  slice can land without modifying ``cbsrm/audit/chain.py``.
  ``AuditChain.append`` already accepts a raw-string kind via the
  ``else str(event.kind)`` branch in its hashing pipeline. A future
  slice can promote the kind to a typed enum member with no behaviour
  change.

Public surface (v0.9 work in progress)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* :data:`AUDIT_EVENT_KIND` — the string ``"REPORT_EXPORTED"``.
* :func:`manifest_subject` — derive the audit-chain subject string
  from a manifest dict.
* :func:`stamp_manifest_to_chain` — append a manifest as one
  audit-chain row and return the row metadata.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping

from cbsrm.audit.chain import AuditChain, AuditEvent


AUDIT_EVENT_KIND = "REPORT_EXPORTED"


# ─── Subject derivation ─────────────────────────────────────────────


def manifest_subject(manifest: Mapping[str, Any]) -> str:
    """Build the audit-chain subject string from a report manifest.

    Pattern: ``"report:{report_id}:{window_id}:{format}"``. When
    ``window_id`` is None the placeholder ``"-"`` is used so the
    subject string remains queryable by the existing
    :meth:`AuditChain.query_subject` / ``GET /audit/{subject}``
    surface.

    The ``"report:"`` prefix disambiguates report-export subjects
    from indicator-compute subjects (``CISS-US``, ``SRISK``, etc.).

    Raises
    ------
    ValueError
        If ``manifest['report_id']`` or ``manifest['format']`` is
        missing or empty.
    """
    report_id = manifest.get("report_id")
    output_format = manifest.get("format")
    if not isinstance(report_id, str) or not report_id:
        raise ValueError(
            "manifest must have a non-empty 'report_id' str"
        )
    if not isinstance(output_format, str) or not output_format:
        raise ValueError(
            "manifest must have a non-empty 'format' str"
        )
    window_id = manifest.get("window_id")
    window_part = window_id if isinstance(window_id, str) and window_id else "-"
    return f"report:{report_id}:{window_part}:{output_format}"


# ─── Audit-chain append + row read-back ─────────────────────────────


def stamp_manifest_to_chain(
    chain: AuditChain, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Append a manifest as one row in the audit chain.

    Parameters
    ----------
    chain :
        An open :class:`AuditChain`.  Its ``conn`` attribute must be
        a live :class:`sqlite3.Connection`.
    manifest :
        A deterministic manifest dict produced by
        :func:`cbsrm.reporting.build_report_manifest`. Stored as the
        audit-event payload via ``dict(manifest)`` (shallow copy of
        the top-level mapping; nested values are not deep-copied).

    Returns
    -------
    dict with keys:
        ``row_id``    — auto-incremented row id (int)
        ``hash``      — sha256 of the chained event (hex str)
        ``prev_hash`` — previous row's hash, or ``None`` for row #1
        ``ts``        — chain-set UTC ISO-8601 timestamp str
        ``subject``   — :func:`manifest_subject` output
        ``kind``      — :data:`AUDIT_EVENT_KIND`

    Notes
    -----
    The chain row's ``ts`` is wall-clock UTC set by
    :meth:`AuditChain.append`.  The manifest's own
    ``generated_at_utc`` field is independent (deterministic-by-default).
    The two coexist intentionally: the manifest says *what was
    rendered*, the chain row says *when it was rendered*.
    """
    if not isinstance(chain, AuditChain):
        raise TypeError(
            f"chain must be an AuditChain, got {type(chain).__name__}"
        )

    subject = manifest_subject(manifest)
    event = AuditEvent(
        kind=AUDIT_EVENT_KIND,  # raw str; AuditChain.append handles
        subject=subject,
        payload=dict(manifest),
    )
    row_id = chain.append(event)

    # Read back the canonical chain row so we surface the exact ts /
    # hash / prev_hash that the chain assigned. We use the same
    # underlying sqlite3.Connection — no schema knowledge beyond the
    # public-by-convention column list that AuditChain itself reads.
    row = chain.conn.execute(
        """SELECT id, ts, kind, subject, payload_json, hash, prev_hash
             FROM cbsrm_audit_log WHERE id = ?""",
        (row_id,),
    ).fetchone()
    if row is None:  # pragma: no cover - defensive
        raise sqlite3.DatabaseError(
            f"audit row {row_id} not found immediately after append"
        )

    _, ts, kind, stored_subject, _, h, prev_h = row
    return {
        "row_id": int(row_id),
        "hash": h,
        "prev_hash": prev_h,
        "ts": ts,
        "subject": stored_subject,
        "kind": kind,
    }


# Convenience: not exported through cbsrm.reporting.__init__ — kept
# internal so tests that need to validate a payload round-trip can
# use the chain's own json.loads path without re-importing json.
def _decode_payload_json(payload_json: str) -> dict[str, Any]:
    return json.loads(payload_json)


# ─── Path-based wrapper ────────────────────────────────────────────


def stamp_manifest_to_db_path(
    manifest: Mapping[str, Any], db_path: str,
) -> dict[str, Any]:
    """Append a manifest as one audit-chain row in the sqlite DB at
    ``db_path``.

    Thin path-based wrapper over :func:`stamp_manifest_to_chain`:
    opens a :class:`sqlite3.Connection`, wraps it in
    :class:`AuditChain`, stamps the manifest, then closes the
    connection in a ``finally`` block (no lock left behind even if
    the chain helper raises). The file at ``db_path`` is created if
    it does not exist; :meth:`AuditChain._ensure_schema` is
    idempotent.

    Returns the same 6-key row-metadata dict as
    :func:`stamp_manifest_to_chain`.

    Raises
    ------
    ValueError
        If ``db_path`` is not a non-empty str.
    sqlite3.OperationalError
        Propagated from :func:`sqlite3.connect` when the path is
        unwritable (permissions, missing parent directory). Caller
        is expected to surface it as a user-facing error.
    """
    if not isinstance(db_path, str) or not db_path:
        raise ValueError("db_path must be a non-empty str")

    conn = sqlite3.connect(db_path)
    try:
        chain = AuditChain(conn)
        return stamp_manifest_to_chain(chain, manifest)
    finally:
        conn.close()
