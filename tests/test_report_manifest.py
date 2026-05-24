"""Tests for the deterministic export-time report manifest.

The manifest is pure metadata over a rendered report. These tests pin
the externally observable contract:

  * deterministic-by-default (no wall-clock)
  * JSON-serializable
  * version-aware (cbsrm + registry + renderer + html-renderer +
    dossier spec versions all surfaced)
  * Unicode-safe hashing
  * key-order-independent JSON hashing
  * disclaimer detection on Markdown/HTML, false on raw JSON envelopes
  * input validation: bad ``output_format``, bad ``source``, empty
    ``report_id``, non-str ``output_text`` / ``generated_at_utc``
  * no network IO during manifest build
"""
from __future__ import annotations

import hashlib
import json

import pytest

from cbsrm import __version__ as CBSRM_VERSION
from cbsrm.diagnostics import build_crisis_dossier
from cbsrm.reporting import (
    HTML_RENDERER_VERSION,
    MANIFEST_VERSION,
    REPORT_REGISTRY_VERSION,
    REPORT_RENDERER_VERSION,
    build_report_manifest,
    build_report_payload,
    render_dossier_markdown,
    sha256_jsonable,
    sha256_text,
)


# ─── MANIFEST_VERSION shape ─────────────────────────────────────────


def test_manifest_version_is_semver_like():
    parts = MANIFEST_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts), MANIFEST_VERSION


# ─── sha256_text ────────────────────────────────────────────────────


def test_sha256_text_matches_hashlib():
    for s in ["", "hello", "report → footer", "élan"]:
        assert (
            sha256_text(s)
            == hashlib.sha256(s.encode("utf-8")).hexdigest()
        )


def test_sha256_text_is_deterministic():
    assert sha256_text("abc") == sha256_text("abc")


def test_sha256_text_is_unicode_safe():
    # The composition arrow → (U+2192) and em-dash — (U+2014) are part
    # of the renderer's output; their UTF-8 bytes must hash identically.
    arrow = sha256_text("a → b")
    expected = hashlib.sha256("a → b".encode("utf-8")).hexdigest()
    assert arrow == expected


def test_sha256_text_rejects_non_str():
    with pytest.raises(TypeError):
        sha256_text(b"bytes are not str")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        sha256_text(123)  # type: ignore[arg-type]


# ─── sha256_jsonable ────────────────────────────────────────────────


def test_sha256_jsonable_independent_of_key_order():
    a = {"x": 1, "y": [2, 3], "z": {"inner": True}}
    b = {"z": {"inner": True}, "y": [2, 3], "x": 1}
    assert sha256_jsonable(a) == sha256_jsonable(b)


def test_sha256_jsonable_changes_on_value_change():
    base = sha256_jsonable({"x": 1})
    assert sha256_jsonable({"x": 2}) != base
    assert sha256_jsonable({"x": 1, "y": None}) != base


def test_sha256_jsonable_unicode_safe():
    s = sha256_jsonable({"msg": "report → footer"})
    # Round-trip the canonical encoding to confirm no escape drift.
    canonical = json.dumps(
        {"msg": "report → footer"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    assert s == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ─── build_report_manifest — happy path ────────────────────────────


def _crisis_md_manifest(window: str = "2008Q4") -> dict:
    """Helper: build a manifest for a real rendered Markdown crisis
    dossier with no caller-supplied timestamp."""
    dossier = build_crisis_dossier(window)
    md = render_dossier_markdown(dossier)
    return build_report_manifest(
        report_id="crisis-dossier",
        output_text=md,
        output_format="markdown",
        window_id=window,
        dossier=dossier,
    )


def test_manifest_required_top_level_shape():
    m = _crisis_md_manifest()
    assert set(m.keys()) == {
        "manifest_version", "report_id", "window_id",
        "format", "source", "generated_at_utc",
        "versions", "hashes", "disclaimer_present",
    }


def test_manifest_pins_known_constants():
    m = _crisis_md_manifest()
    assert m["manifest_version"] == MANIFEST_VERSION
    assert m["report_id"] == "crisis-dossier"
    assert m["window_id"] == "2008Q4"
    assert m["format"] == "markdown"
    # default source is "python"
    assert m["source"] == "python"


def test_manifest_versions_populated_from_packages():
    m = _crisis_md_manifest()
    versions = m["versions"]
    assert versions["cbsrm"] == CBSRM_VERSION
    assert versions["registry"] == REPORT_REGISTRY_VERSION
    assert versions["report_renderer"] == REPORT_RENDERER_VERSION
    assert versions["html_renderer"] == HTML_RENDERER_VERSION


def test_manifest_extracts_dossier_and_fixture_versions():
    dossier = build_crisis_dossier("2008Q4")
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text=render_dossier_markdown(dossier),
        output_format="markdown",
        window_id="2008Q4",
        dossier=dossier,
    )
    versions = m["versions"]
    # Both keys are present and either str or None; happy-path: str.
    assert versions["dossier"] is not None
    assert versions["fixture"] is not None
    assert isinstance(versions["dossier"], str)
    assert isinstance(versions["fixture"], str)


def test_manifest_dossier_omitted_yields_none_spec_versions():
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text="# heading",
        output_format="markdown",
    )
    assert m["versions"]["dossier"] is None
    assert m["versions"]["fixture"] is None


# ─── Determinism ────────────────────────────────────────────────────


def test_manifest_has_no_timestamp_by_default():
    m = _crisis_md_manifest()
    assert m["generated_at_utc"] is None


def test_manifest_is_deterministic_without_timestamp():
    m1 = _crisis_md_manifest()
    m2 = _crisis_md_manifest()
    assert m1 == m2
    # Byte-identical canonical JSON too — stronger contract.
    assert json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True)


def test_manifest_injected_timestamp_preserved_verbatim():
    dossier = build_crisis_dossier("2008Q4")
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text=render_dossier_markdown(dossier),
        output_format="markdown",
        window_id="2008Q4",
        dossier=dossier,
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    assert m["generated_at_utc"] == "2026-01-01T00:00:00Z"


# ─── Hashes ────────────────────────────────────────────────────────


def test_manifest_output_hash_matches_rendered_markdown():
    dossier = build_crisis_dossier("2008Q4")
    md = render_dossier_markdown(dossier)
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text=md,
        output_format="markdown",
        window_id="2008Q4",
        dossier=dossier,
    )
    assert m["hashes"]["output_sha256"] == sha256_text(md)


def test_manifest_output_hash_matches_rendered_html():
    pytest.importorskip("markdown")
    from cbsrm.reporting import render_dossier_html

    dossier = build_crisis_dossier("2008Q4")
    html = render_dossier_html(dossier)
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text=html,
        output_format="html",
        window_id="2008Q4",
        dossier=dossier,
    )
    assert m["hashes"]["output_sha256"] == sha256_text(html)


def test_manifest_payload_hash_present_only_when_payload_supplied():
    dossier = build_crisis_dossier("2020Q1")
    md = render_dossier_markdown(dossier)

    # Without payload: only output_sha256 in hashes.
    m_no = build_report_manifest(
        report_id="crisis-dossier",
        output_text=md,
        output_format="markdown",
        window_id="2020Q1",
        dossier=dossier,
    )
    assert "payload_sha256" not in m_no["hashes"]

    # With payload: payload_sha256 present and equal to sha256_jsonable.
    payload = build_report_payload(dossier)
    m_with = build_report_manifest(
        report_id="crisis-dossier",
        output_text=md,
        output_format="markdown",
        window_id="2020Q1",
        dossier=dossier,
        payload=payload,
    )
    assert "payload_sha256" in m_with["hashes"]
    assert m_with["hashes"]["payload_sha256"] == sha256_jsonable(payload)


# ─── Disclaimer detection ──────────────────────────────────────────


def test_manifest_disclaimer_true_for_markdown_crisis_report():
    m = _crisis_md_manifest()
    assert m["disclaimer_present"] is True


def test_manifest_disclaimer_true_for_html_crisis_report():
    pytest.importorskip("markdown")
    from cbsrm.reporting import render_dossier_html

    dossier = build_crisis_dossier("2023Q1")
    html = render_dossier_html(dossier)
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text=html,
        output_format="html",
        window_id="2023Q1",
        dossier=dossier,
    )
    assert m["disclaimer_present"] is True


def test_manifest_disclaimer_true_for_json_envelope():
    """The JSON envelope carries the NFA disclaimer too — it lives in
    ``payload['report']['disclaimer']`` (see
    :func:`cbsrm.reporting.build_report_payload`). The manifest's
    substring detection picks this up, so every supported format
    consistently reports ``disclaimer_present=True`` on crisis-dossier
    exports. This consistency is intentional hygiene; if a caller
    ever produced an output without the disclaimer text, the manifest
    would honestly report ``False``."""
    dossier = build_crisis_dossier("2008Q4")
    payload = build_report_payload(dossier)
    json_text = json.dumps(payload)
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text=json_text,
        output_format="json",
        window_id="2008Q4",
        dossier=dossier,
        payload=payload,
    )
    assert m["disclaimer_present"] is True


def test_manifest_disclaimer_false_when_output_lacks_disclaimer():
    """The detection is a substring check — a synthetic output with
    no ``Disclaimer`` heading must surface as ``disclaimer_present
    is False``. This is the load-bearing contract: the flag tracks
    the actual output, not a hardcoded assumption about format."""
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text="# Just a heading, no footer\n\nbody text",
        output_format="markdown",
    )
    assert m["disclaimer_present"] is False


# ─── JSON-serializability ──────────────────────────────────────────


def test_manifest_is_json_serializable():
    m = _crisis_md_manifest()
    encoded = json.dumps(m)
    assert json.loads(encoded) == m


def test_manifest_with_injected_timestamp_round_trips_through_json():
    dossier = build_crisis_dossier("2020Q1")
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text=render_dossier_markdown(dossier),
        output_format="markdown",
        window_id="2020Q1",
        dossier=dossier,
        generated_at_utc="2026-05-24T18:00:00Z",
    )
    assert json.loads(json.dumps(m)) == m


# ─── Validation: each invalid arg fails cleanly ────────────────────


def test_invalid_report_id_empty_raises_valueerror():
    with pytest.raises(ValueError):
        build_report_manifest(
            report_id="",
            output_text="x",
            output_format="markdown",
        )


def test_invalid_report_id_non_str_raises_valueerror():
    with pytest.raises(ValueError):
        build_report_manifest(
            report_id=123,  # type: ignore[arg-type]
            output_text="x",
            output_format="markdown",
        )


def test_invalid_output_text_raises_typeerror():
    with pytest.raises(TypeError):
        build_report_manifest(
            report_id="crisis-dossier",
            output_text=123,  # type: ignore[arg-type]
            output_format="markdown",
        )


def test_invalid_output_format_raises_valueerror():
    with pytest.raises(ValueError):
        build_report_manifest(
            report_id="crisis-dossier",
            output_text="x",
            output_format="yaml",
        )


def test_invalid_source_raises_valueerror():
    with pytest.raises(ValueError):
        build_report_manifest(
            report_id="crisis-dossier",
            output_text="x",
            output_format="markdown",
            source="rogue-runner",
        )


def test_invalid_timestamp_type_raises_typeerror():
    with pytest.raises(TypeError):
        build_report_manifest(
            report_id="crisis-dossier",
            output_text="x",
            output_format="markdown",
            generated_at_utc=1700000000,  # type: ignore[arg-type]
        )


# ─── Source enumeration ────────────────────────────────────────────


@pytest.mark.parametrize("src", ["python", "cli", "api", "streamlit"])
def test_each_supported_source_is_accepted(src):
    m = build_report_manifest(
        report_id="crisis-dossier",
        output_text="x",
        output_format="markdown",
        source=src,
    )
    assert m["source"] == src


# ─── Offline / no-network contract ─────────────────────────────────


def test_manifest_build_is_offline(monkeypatch):
    """Manifest construction must not touch the network. We
    monkeypatch the two common HTTP entry points to raise, then
    build a manifest end-to-end."""
    import urllib.request

    def _no_urlopen(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "manifest build made a urllib network call"
        )

    monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)

    try:
        import requests  # noqa: F401

        def _no_requests(self, *_a, **_kw):  # pragma: no cover
            raise AssertionError(
                "manifest build made a requests network call"
            )

        monkeypatch.setattr("requests.Session.request", _no_requests)
    except ImportError:
        pass

    m = _crisis_md_manifest()
    assert m["report_id"] == "crisis-dossier"
