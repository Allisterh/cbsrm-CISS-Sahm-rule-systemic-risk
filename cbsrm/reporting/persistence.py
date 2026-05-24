"""
cbsrm.reporting.persistence — content-addressed report artifact store.

A sqlite-backed store keyed on the manifest ``output_sha256``. The store
holds rendered report text + the deterministic manifest dict; later
slices (CLI / API / Streamlit consumers, "Recent reports" surface, PDF
export, audit-chain join) can read by hash without re-rendering.

Design contract
~~~~~~~~~~~~~~~

* **Content-addressed.** Primary key is ``output_sha256`` from the
  manifest. Same content -> same key -> ``INSERT OR IGNORE`` keeps
  the first-stored row; subsequent stores of the same hash return the
  pre-existing row metadata with ``was_existing=True``.
* **Single-operator scope.** No multi-tenant logic, no auth, no
  encryption. A v0.9 sqlite-on-disk store, not a SaaS database.
* **Stdlib only.** ``sqlite3`` + ``json`` + ``hashlib``. No new
  dependencies.
* **Optional determinism.** ``created_at_utc`` is opt-in caller-
  supplied. When omitted, the helper uses wall-clock UTC ISO-8601
  (same pattern as :class:`AuditChain.append`). Tests inject a fixed
  string to keep storage rows byte-identical across runs.
* **Audit-chain independence.** This module never writes to or reads
  from :mod:`cbsrm.audit.chain`. The two surfaces converge naturally
  on ``output_sha256`` as the shared join key, but each does its own
  thing.

Public surface (v0.9 work in progress)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* :func:`init_report_store` — create / ensure the schema. Idempotent.
* :func:`store_report_artifact` — INSERT-OR-IGNORE one artifact.
  Returns row metadata + ``was_existing: bool``.
* :func:`get_report_artifact` — lookup by ``output_sha256``.
* :func:`list_report_artifacts` — most-recent N rows, DESC by
  ``created_at_utc``.
* :data:`REPORT_STORE_VERSION` — semantic version of the store spec.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping


REPORT_STORE_VERSION = "1.0.0"


_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS cbsrm_report_artifacts (
    output_sha256   TEXT PRIMARY KEY,
    report_id       TEXT NOT NULL,
    window_id       TEXT,
    format          TEXT NOT NULL,
    source          TEXT NOT NULL,
    output_text     TEXT NOT NULL,
    manifest_json   TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    byte_length     INTEGER NOT NULL,
    created_at_utc  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cra_report_id  ON cbsrm_report_artifacts(report_id);
CREATE INDEX IF NOT EXISTS idx_cra_window_id  ON cbsrm_report_artifacts(window_id);
CREATE INDEX IF NOT EXISTS idx_cra_format     ON cbsrm_report_artifacts(format);
CREATE INDEX IF NOT EXISTS idx_cra_created    ON cbsrm_report_artifacts(created_at_utc DESC);
"""


_DEFAULT_CONTENT_TYPES = {
    "json":     "application/json",
    "markdown": "text/markdown; charset=utf-8",
    "html":     "text/html; charset=utf-8",
}


# ─── Path / connection helpers ──────────────────────────────────────


def _validate_db_path(db_path: Any) -> str:
    if not isinstance(db_path, str) or not db_path:
        raise ValueError("db_path must be a non-empty str")
    return db_path


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


def _row_to_dict(row: tuple) -> dict[str, Any]:
    """Map a SELECT row from cbsrm_report_artifacts to the public-shape
    dict. Manifest JSON is decoded back to a dict."""
    (
        output_sha256, report_id, window_id, fmt, source,
        output_text, manifest_json, content_type, byte_length,
        created_at_utc,
    ) = row
    return {
        "output_sha256": output_sha256,
        "report_id": report_id,
        "window_id": window_id,
        "format": fmt,
        "source": source,
        "output_text": output_text,
        "manifest": json.loads(manifest_json),
        "content_type": content_type,
        "byte_length": int(byte_length),
        "created_at_utc": created_at_utc,
    }


_SELECT_ALL_COLUMNS = (
    "output_sha256, report_id, window_id, format, source, "
    "output_text, manifest_json, content_type, byte_length, "
    "created_at_utc"
)


# ─── Public API ─────────────────────────────────────────────────────


def init_report_store(db_path: str) -> None:
    """Open the sqlite DB at ``db_path``, ensure the schema, close.

    Idempotent — calling on an existing store re-runs the
    ``CREATE TABLE IF NOT EXISTS`` and ``CREATE INDEX IF NOT EXISTS``
    statements without dropping anything.

    Raises
    ------
    ValueError
        If ``db_path`` is empty or not a str.
    sqlite3.OperationalError
        Propagated from :func:`sqlite3.connect` if the path is
        unwritable.
    """
    path = _validate_db_path(db_path)
    conn = sqlite3.connect(path)
    try:
        _ensure_schema(conn)
    finally:
        conn.close()


def store_report_artifact(
    db_path: str,
    *,
    output_text: str,
    manifest: Mapping[str, Any],
    content_type: str | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Append (or no-op on collision) one report artifact to the store.

    The primary key is ``manifest['hashes']['output_sha256']``; the
    helper verifies that this matches :func:`sha256_text` of
    ``output_text`` — caller-side hash drift is rejected with
    :class:`ValueError`.

    When a row with the same ``output_sha256`` already exists the
    SQL is ``INSERT OR IGNORE``: the *existing* row's bytes,
    metadata, and ``created_at_utc`` are preserved, and the
    returned dict carries ``was_existing=True``.

    ``content_type`` defaults to a sensible MIME for the
    ``manifest['format']`` (``json`` -> ``application/json``,
    ``markdown`` -> ``text/markdown; charset=utf-8``, ``html`` ->
    ``text/html; charset=utf-8``).

    ``created_at_utc`` defaults to ``datetime.now(timezone.utc)
    .isoformat()``. Callers (and tests) can inject a fixed string
    for deterministic storage rows.

    Returns
    -------
    dict
        Row metadata including ``was_existing: bool``. On collision,
        ``output_text`` / ``manifest`` / ``content_type`` /
        ``created_at_utc`` / ``byte_length`` reflect the *pre-existing*
        row, not the (ignored) supplied inputs.

    Raises
    ------
    ValueError
        If ``db_path`` is empty, or if ``output_text`` /
        ``manifest`` validation fails (including hash mismatch).
    TypeError
        If ``output_text`` is not a :class:`str`.
    sqlite3.OperationalError
        Propagated from :func:`sqlite3.connect`.
    """
    path = _validate_db_path(db_path)

    # Validate inputs explicitly so the storage layer never silently
    # round-trips junk. Tests pin every error path.
    if not isinstance(output_text, str):
        raise TypeError(
            f"output_text must be str, got {type(output_text).__name__}"
        )
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be a Mapping")

    report_id = manifest.get("report_id")
    fmt = manifest.get("format")
    source = manifest.get("source")
    hashes = manifest.get("hashes")
    if not isinstance(report_id, str) or not report_id:
        raise ValueError("manifest['report_id'] must be a non-empty str")
    if not isinstance(fmt, str) or not fmt:
        raise ValueError("manifest['format'] must be a non-empty str")
    if not isinstance(source, str) or not source:
        raise ValueError("manifest['source'] must be a non-empty str")
    if not isinstance(hashes, Mapping):
        raise ValueError("manifest['hashes'] must be a Mapping")
    declared_hash = hashes.get("output_sha256")
    if not isinstance(declared_hash, str) or not declared_hash:
        raise ValueError(
            "manifest['hashes']['output_sha256'] must be a non-empty str"
        )

    # Defensive hash-match check — catches caller-side mismatches
    # between the rendered bytes and the manifest's claimed hash.
    from cbsrm.reporting.manifest import sha256_text

    expected_hash = sha256_text(output_text)
    if expected_hash != declared_hash:
        raise ValueError(
            "manifest['hashes']['output_sha256'] does not match "
            "sha256_text(output_text); caller passed mismatched "
            "(output, manifest) pair."
        )

    window_id = manifest.get("window_id")  # may be None
    if window_id is not None and not isinstance(window_id, str):
        raise ValueError(
            "manifest['window_id'] must be str or None"
        )

    if content_type is None:
        derived = _DEFAULT_CONTENT_TYPES.get(fmt)
        if derived is None:
            raise ValueError(
                f"cannot derive default content_type for format "
                f"{fmt!r}; pass content_type explicitly"
            )
        content_type = derived
    elif not isinstance(content_type, str) or not content_type:
        raise ValueError(
            "content_type must be a non-empty str when supplied"
        )

    if created_at_utc is None:
        created_at_utc = datetime.now(timezone.utc).isoformat()
    elif not isinstance(created_at_utc, str) or not created_at_utc:
        raise ValueError(
            "created_at_utc must be a non-empty str when supplied"
        )

    manifest_json = json.dumps(
        dict(manifest), sort_keys=True, ensure_ascii=False,
    )
    byte_length = len(output_text.encode("utf-8"))

    conn = sqlite3.connect(path)
    try:
        _ensure_schema(conn)
        cur = conn.execute(
            """INSERT OR IGNORE INTO cbsrm_report_artifacts
               (output_sha256, report_id, window_id, format, source,
                output_text, manifest_json, content_type, byte_length,
                created_at_utc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                declared_hash, report_id, window_id, fmt, source,
                output_text, manifest_json, content_type, byte_length,
                created_at_utc,
            ),
        )
        was_existing = cur.rowcount == 0
        conn.commit()

        # Read back the canonical row — either the freshly inserted
        # one or the pre-existing one if INSERT was IGNORE'd.
        row = conn.execute(
            f"SELECT {_SELECT_ALL_COLUMNS} "
            "FROM cbsrm_report_artifacts WHERE output_sha256 = ?",
            (declared_hash,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:  # pragma: no cover - defensive
        raise sqlite3.DatabaseError(
            f"artifact {declared_hash!r} not found immediately "
            f"after INSERT OR IGNORE"
        )

    out = _row_to_dict(row)
    out["was_existing"] = was_existing
    return out


def get_report_artifact(
    db_path: str, output_sha256: str,
) -> dict[str, Any] | None:
    """Return the artifact row for ``output_sha256`` as a dict, or
    ``None`` if the hash is not in the store.

    Raises
    ------
    ValueError
        If ``db_path`` is empty.
    """
    path = _validate_db_path(db_path)
    if not isinstance(output_sha256, str) or not output_sha256:
        raise ValueError("output_sha256 must be a non-empty str")

    conn = sqlite3.connect(path)
    try:
        _ensure_schema(conn)
        row = conn.execute(
            f"SELECT {_SELECT_ALL_COLUMNS} "
            "FROM cbsrm_report_artifacts WHERE output_sha256 = ?",
            (output_sha256,),
        ).fetchone()
    finally:
        conn.close()

    return _row_to_dict(row) if row is not None else None


def list_report_artifacts(
    db_path: str, *, limit: int = 100,
) -> list[dict[str, Any]]:
    """Return the most-recent ``limit`` artifacts, ordered DESC by
    ``created_at_utc``.

    Raises
    ------
    ValueError
        If ``db_path`` is empty or ``limit`` is not a positive int.
    """
    path = _validate_db_path(db_path)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive int")

    conn = sqlite3.connect(path)
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            f"SELECT {_SELECT_ALL_COLUMNS} "
            "FROM cbsrm_report_artifacts "
            "ORDER BY created_at_utc DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_dict(r) for r in rows]
