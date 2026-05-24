"""Tests for the content-addressed report artifact store.

The store is a sqlite-backed table keyed on the manifest
``output_sha256``. These tests pin:

  * schema creation + idempotence
  * INSERT-OR-IGNORE semantics on hash collision (first-stored wins)
  * hash-mismatch validation (caller-side ``(output, manifest)``
    drift is rejected)
  * content-type derivation from ``manifest['format']``
  * optional ``created_at_utc`` injection (deterministic-by-test)
  * byte-length accuracy on UTF-8 encoding
  * ``get`` / ``list`` round-trip including manifest decode
  * offline contract — no network during any operation
  * end-to-end with a real rendered crisis-dossier
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from cbsrm.diagnostics import build_crisis_dossier
from cbsrm.reporting import (
    REPORT_STORE_VERSION,
    build_report_manifest,
    build_report_payload,
    get_report_artifact,
    init_report_store,
    list_report_artifacts,
    render_dossier_markdown,
    store_report_artifact,
)


# ─── helpers ────────────────────────────────────────────────────────


def _md_pair(window: str = "2008Q4", *, source: str = "python"):
    """Return ``(output_text, manifest)`` for a real rendered Markdown
    crisis-dossier — a canonical, deterministic input pair."""
    dossier = build_crisis_dossier(window)
    md = render_dossier_markdown(dossier)
    manifest = build_report_manifest(
        report_id="crisis-dossier",
        output_text=md,
        output_format="markdown",
        window_id=window,
        source=source,
        dossier=dossier,
        payload=build_report_payload(dossier),
    )
    return md, manifest


# ─── REPORT_STORE_VERSION shape ─────────────────────────────────────


def test_store_version_is_semver_like():
    parts = REPORT_STORE_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts), REPORT_STORE_VERSION


# ─── init_report_store ──────────────────────────────────────────────


def test_init_creates_file_and_schema(tmp_path):
    db = tmp_path / "store.db"
    assert not db.exists()
    init_report_store(str(db))
    assert db.is_file()
    # The table must exist with the documented schema.
    conn = sqlite3.connect(str(db))
    try:
        cols = [
            r[1] for r in conn.execute(
                "PRAGMA table_info(cbsrm_report_artifacts)"
            ).fetchall()
        ]
    finally:
        conn.close()
    assert cols == [
        "output_sha256", "report_id", "window_id", "format", "source",
        "output_text", "manifest_json", "content_type", "byte_length",
        "created_at_utc",
    ]


def test_init_is_idempotent(tmp_path):
    db = tmp_path / "store.db"
    init_report_store(str(db))
    # A second call must not raise and must not drop or change the
    # schema.
    init_report_store(str(db))
    conn = sqlite3.connect(str(db))
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM cbsrm_report_artifacts"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_init_blank_db_path_raises_valueerror():
    with pytest.raises(ValueError):
        init_report_store("")
    with pytest.raises(ValueError):
        init_report_store(None)  # type: ignore[arg-type]


# ─── store_report_artifact — happy path ────────────────────────────


def test_store_inserts_row_and_returns_required_fields(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    row = store_report_artifact(
        db, output_text=md, manifest=manifest,
        created_at_utc="2026-05-24T00:00:00Z",
    )
    assert set(row.keys()) == {
        "output_sha256", "report_id", "window_id", "format", "source",
        "output_text", "manifest", "content_type", "byte_length",
        "created_at_utc", "was_existing",
    }
    assert row["was_existing"] is False
    assert row["report_id"] == "crisis-dossier"
    assert row["window_id"] == "2008Q4"
    assert row["format"] == "markdown"
    assert row["source"] == "python"
    assert row["output_text"] == md
    assert row["manifest"] == manifest
    assert row["content_type"] == "text/markdown; charset=utf-8"
    assert row["byte_length"] == len(md.encode("utf-8"))
    assert row["created_at_utc"] == "2026-05-24T00:00:00Z"
    assert row["output_sha256"] == manifest["hashes"]["output_sha256"]


def test_store_deterministic_with_injected_timestamp(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    # The store row is byte-identical when the same (output, manifest,
    # created_at_utc) triple is provided, even though created_at_utc
    # is normally wall-clock.
    r1 = store_report_artifact(
        db, output_text=md, manifest=manifest,
        created_at_utc="2026-05-24T00:00:00Z",
    )
    db2 = str(tmp_path / "store2.db")
    r2 = store_report_artifact(
        db2, output_text=md, manifest=manifest,
        created_at_utc="2026-05-24T00:00:00Z",
    )
    # Both rows must agree on every field except `was_existing`.
    keys = set(r1.keys()) - {"was_existing"}
    for k in keys:
        assert r1[k] == r2[k], k


# ─── INSERT-OR-IGNORE on duplicate hash ────────────────────────────


def test_duplicate_store_returns_was_existing_true_and_preserves_row(
    tmp_path,
):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    first_ts = "2026-05-24T00:00:00Z"
    second_ts = "2099-01-01T00:00:00Z"
    r1 = store_report_artifact(
        db, output_text=md, manifest=manifest,
        created_at_utc=first_ts,
    )
    r2 = store_report_artifact(
        db, output_text=md, manifest=manifest,
        created_at_utc=second_ts,
    )
    assert r1["was_existing"] is False
    assert r2["was_existing"] is True
    # The pre-existing created_at_utc must NOT be overwritten by the
    # later call's value.
    assert r2["created_at_utc"] == first_ts
    # And the table has exactly one row.
    conn = sqlite3.connect(db)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM cbsrm_report_artifacts"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 1


# ─── hash-mismatch validation ──────────────────────────────────────


def test_store_rejects_hash_mismatch(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    # Tamper with the declared hash so it no longer matches sha256(md).
    bad_manifest = json.loads(json.dumps(manifest))
    bad_manifest["hashes"]["output_sha256"] = "0" * 64
    with pytest.raises(ValueError) as exc:
        store_report_artifact(
            db, output_text=md, manifest=bad_manifest,
        )
    assert "does not match" in str(exc.value)


def test_store_rejects_modified_output_text(tmp_path):
    """A subtle case: legitimate manifest, but the output bytes were
    tampered with before the store call. The hash check catches it."""
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    tampered = md + "\n<!-- injected -->\n"
    with pytest.raises(ValueError):
        store_report_artifact(
            db, output_text=tampered, manifest=manifest,
        )


# ─── input-type validation ─────────────────────────────────────────


def test_store_rejects_non_str_output_text(tmp_path):
    db = str(tmp_path / "store.db")
    _, manifest = _md_pair("2008Q4")
    with pytest.raises(TypeError):
        store_report_artifact(
            db, output_text=b"bytes",  # type: ignore[arg-type]
            manifest=manifest,
        )


def test_store_rejects_non_mapping_manifest(tmp_path):
    db = str(tmp_path / "store.db")
    md, _ = _md_pair("2008Q4")
    with pytest.raises(ValueError):
        store_report_artifact(
            db, output_text=md, manifest="not a mapping",  # type: ignore[arg-type]
        )


def test_store_rejects_missing_required_manifest_fields(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    # Strip a required field at a time.
    for key in ("report_id", "format", "source"):
        bad = dict(manifest)
        bad[key] = ""
        with pytest.raises(ValueError):
            store_report_artifact(db, output_text=md, manifest=bad)


def test_store_rejects_blank_db_path(tmp_path):
    md, manifest = _md_pair("2008Q4")
    with pytest.raises(ValueError):
        store_report_artifact("", output_text=md, manifest=manifest)


# ─── content-type derivation ───────────────────────────────────────


@pytest.mark.parametrize(
    "fmt,expected",
    [
        ("json", "application/json"),
        ("markdown", "text/markdown; charset=utf-8"),
        ("html", "text/html; charset=utf-8"),
    ],
)
def test_store_derives_default_content_type(tmp_path, fmt, expected):
    """When content_type is None, the helper derives a sensible MIME
    from manifest['format']. Each of the three v0.9 formats has a
    pinned default."""
    if fmt == "html":
        pytest.importorskip("markdown")
        from cbsrm.reporting import render_dossier_html

        dossier = build_crisis_dossier("2008Q4")
        text = render_dossier_html(dossier)
        manifest = build_report_manifest(
            report_id="crisis-dossier",
            output_text=text,
            output_format="html",
            window_id="2008Q4",
            source="python",
            dossier=dossier,
        )
    elif fmt == "json":
        dossier = build_crisis_dossier("2008Q4")
        payload = build_report_payload(dossier)
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        manifest = build_report_manifest(
            report_id="crisis-dossier",
            output_text=text,
            output_format="json",
            window_id="2008Q4",
            source="python",
            dossier=dossier,
            payload=payload,
        )
    else:
        text, manifest = _md_pair("2008Q4")

    db = str(tmp_path / f"{fmt}.db")
    row = store_report_artifact(db, output_text=text, manifest=manifest)
    assert row["content_type"] == expected


def test_store_accepts_explicit_content_type_override(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    row = store_report_artifact(
        db, output_text=md, manifest=manifest,
        content_type="text/x-custom; charset=utf-8",
    )
    assert row["content_type"] == "text/x-custom; charset=utf-8"


# ─── created_at_utc behaviour ──────────────────────────────────────


def test_created_at_utc_default_is_iso_like_string(tmp_path):
    """When omitted, the helper sets a wall-clock UTC ISO-8601 str.
    Shape check only (not value)."""
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    row = store_report_artifact(db, output_text=md, manifest=manifest)
    assert isinstance(row["created_at_utc"], str)
    assert len(row["created_at_utc"]) > 0
    assert "T" in row["created_at_utc"]


def test_created_at_utc_injected_value_preserved(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    row = store_report_artifact(
        db, output_text=md, manifest=manifest,
        created_at_utc="2026-12-31T23:59:59Z",
    )
    assert row["created_at_utc"] == "2026-12-31T23:59:59Z"


def test_created_at_utc_blank_string_raises(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    with pytest.raises(ValueError):
        store_report_artifact(
            db, output_text=md, manifest=manifest, created_at_utc="",
        )


# ─── byte_length ────────────────────────────────────────────────────


def test_byte_length_matches_utf8_encoding(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    row = store_report_artifact(db, output_text=md, manifest=manifest)
    assert row["byte_length"] == len(md.encode("utf-8"))
    # Includes the renderer's unicode arrows / em-dashes correctly —
    # not a naive `len(str)`.
    assert row["byte_length"] != len(md)


# ─── get_report_artifact ──────────────────────────────────────────


def test_get_returns_stored_row(tmp_path):
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    stored = store_report_artifact(
        db, output_text=md, manifest=manifest,
        created_at_utc="2026-05-24T00:00:00Z",
    )
    fetched = get_report_artifact(db, stored["output_sha256"])
    assert fetched is not None
    # `was_existing` is store-only; not in get's return.
    assert "was_existing" not in fetched
    # Every other field round-trips.
    for k in (
        "output_sha256", "report_id", "window_id", "format", "source",
        "output_text", "manifest", "content_type", "byte_length",
        "created_at_utc",
    ):
        assert fetched[k] == stored[k], k


def test_get_returns_none_for_unknown_hash(tmp_path):
    db = str(tmp_path / "store.db")
    init_report_store(db)
    assert get_report_artifact(db, "0" * 64) is None


def test_get_rejects_blank_hash(tmp_path):
    db = str(tmp_path / "store.db")
    init_report_store(db)
    with pytest.raises(ValueError):
        get_report_artifact(db, "")


# ─── list_report_artifacts ─────────────────────────────────────────


def test_list_returns_rows_desc_by_created_at(tmp_path):
    db = str(tmp_path / "store.db")
    # Store three crisis-dossier windows with injected ascending
    # timestamps; list should return them in DESC order.
    md1, m1 = _md_pair("2008Q4")
    md2, m2 = _md_pair("2020Q1")
    md3, m3 = _md_pair("2023Q1")
    store_report_artifact(
        db, output_text=md1, manifest=m1,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    store_report_artifact(
        db, output_text=md2, manifest=m2,
        created_at_utc="2026-02-01T00:00:00Z",
    )
    store_report_artifact(
        db, output_text=md3, manifest=m3,
        created_at_utc="2026-03-01T00:00:00Z",
    )
    rows = list_report_artifacts(db)
    assert [r["created_at_utc"] for r in rows] == [
        "2026-03-01T00:00:00Z",
        "2026-02-01T00:00:00Z",
        "2026-01-01T00:00:00Z",
    ]
    assert [r["window_id"] for r in rows] == ["2023Q1", "2020Q1", "2008Q4"]


def test_list_limit_respected(tmp_path):
    db = str(tmp_path / "store.db")
    for i, w in enumerate(["2008Q4", "2020Q1", "2023Q1"], start=1):
        md, manifest = _md_pair(w)
        store_report_artifact(
            db, output_text=md, manifest=manifest,
            created_at_utc=f"2026-0{i}-01T00:00:00Z",
        )
    assert len(list_report_artifacts(db, limit=2)) == 2
    assert len(list_report_artifacts(db, limit=10)) == 3


def test_list_limit_rejects_non_positive(tmp_path):
    db = str(tmp_path / "store.db")
    init_report_store(db)
    with pytest.raises(ValueError):
        list_report_artifacts(db, limit=0)
    with pytest.raises(ValueError):
        list_report_artifacts(db, limit=-1)


# ─── manifest decode round-trip ────────────────────────────────────


def test_manifest_round_trips_through_storage(tmp_path):
    """The decoded manifest from the store equals the original
    manifest object (order-independent)."""
    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    store_report_artifact(db, output_text=md, manifest=manifest)
    rows = list_report_artifacts(db, limit=1)
    decoded = rows[0]["manifest"]
    assert decoded == manifest


# ─── offline contract ──────────────────────────────────────────────


def test_store_is_offline(monkeypatch, tmp_path):
    """Persistence must not touch the network."""
    import urllib.request

    def _no_urlopen(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError("persistence made a urllib network call")

    monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)

    try:
        import requests  # noqa: F401

        def _no_requests(self, *_a, **_kw):  # pragma: no cover
            raise AssertionError(
                "persistence made a requests network call"
            )

        monkeypatch.setattr("requests.Session.request", _no_requests)
    except ImportError:
        pass

    db = str(tmp_path / "store.db")
    md, manifest = _md_pair("2008Q4")
    row = store_report_artifact(db, output_text=md, manifest=manifest)
    assert row["was_existing"] is False
    assert get_report_artifact(db, row["output_sha256"]) is not None


# ─── end-to-end: real renderer + manifest + storage ───────────────


def test_end_to_end_crisis_dossier_round_trip(tmp_path):
    db = str(tmp_path / "store.db")

    dossier = build_crisis_dossier("2008Q4")
    md = render_dossier_markdown(dossier)
    manifest = build_report_manifest(
        report_id="crisis-dossier",
        output_text=md,
        output_format="markdown",
        window_id="2008Q4",
        source="cli",
        dossier=dossier,
        payload=build_report_payload(dossier),
    )
    stored = store_report_artifact(
        db, output_text=md, manifest=manifest,
        created_at_utc="2026-05-24T00:00:00Z",
    )
    # The stored row must round-trip byte-identically for both the
    # report text and the manifest.
    assert stored["output_text"] == md
    assert stored["manifest"] == manifest
    # And the output_sha256 column equals hashlib's own sha256.
    assert stored["output_sha256"] == (
        hashlib.sha256(md.encode("utf-8")).hexdigest()
    )


# ─── bad-path error handling ───────────────────────────────────────


def test_store_bad_path_raises_operational_error(tmp_path):
    bad = tmp_path / "missing_parent" / "store.db"
    md, manifest = _md_pair("2008Q4")
    with pytest.raises(sqlite3.OperationalError):
        store_report_artifact(str(bad), output_text=md, manifest=manifest)


def test_init_bad_path_raises_operational_error(tmp_path):
    bad = tmp_path / "missing_parent" / "store.db"
    with pytest.raises(sqlite3.OperationalError):
        init_report_store(str(bad))
