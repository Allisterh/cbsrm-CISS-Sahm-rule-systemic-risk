"""Tests for the ``cbsrm crisis-dossier`` CLI export command.

The command is a thin composition layer over
``cbsrm.diagnostics.build_crisis_dossier`` and the ``cbsrm.reporting``
renderer.  These tests pin the externally observable CLI contract:

  * exit codes
  * JSON / Markdown output shape
  * UTF-8 safety (the report renderer emits "→" and em-dashes which would
    crash a naive ``sys.stdout.write`` on Windows cp1252 consoles)
  * deterministic output (same args → byte-identical output)
  * graceful failure on unknown windows
  * no external I/O (offline / fixture-backed)

The tests deliberately do **not** re-validate the dossier or renderer
internals — those are covered by ``tests/test_crisis_dossiers.py`` and
``tests/test_report_renderer.py``.
"""
from __future__ import annotations

import json

import pytest

from cbsrm.cli import main
from cbsrm.diagnostics import list_dossier_windows


# ─── helpers ─────────────────────────────────────────────────────────


def _run(argv, capsys):
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


# ─── JSON format ─────────────────────────────────────────────────────


def test_default_format_is_json(capsys):
    rc, out, err = _run(["crisis-dossier", "2008Q4"], capsys)
    assert rc == 0, err
    assert err == ""
    payload = json.loads(out)
    assert set(payload.keys()) >= {"report", "dossier"}
    assert payload["report"]["kind"] == "crisis_window_dossier"
    assert payload["dossier"]["window_id"] == "2008Q4"


def test_explicit_json_format(capsys):
    rc, out, _err = _run(
        ["crisis-dossier", "2020Q1", "--format", "json"], capsys,
    )
    assert rc == 0
    payload = json.loads(out)
    assert payload["dossier"]["window_id"] == "2020Q1"
    # round-trip serialization sanity (the payload claims to be JSON-clean)
    json.dumps(payload)


def test_json_emits_unicode_via_ensure_ascii_false(capsys):
    """The renderer/payload uses U+2192 (→) in the composition spec — the
    CLI must emit it as a literal UTF-8 character, not as ``\\u2192``."""
    rc, out, _err = _run(["crisis-dossier", "2008Q4"], capsys)
    assert rc == 0
    # If we ever regressed to ensure_ascii=True the literal arrow would be
    # absent and an escape sequence would appear instead.
    assert "→" in out
    assert "\\u2192" not in out


@pytest.mark.parametrize("window", list_dossier_windows())
def test_all_supported_windows_render_json(window, capsys):
    rc, out, err = _run(["crisis-dossier", window, "--format", "json"], capsys)
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["dossier"]["window_id"] == window


# ─── Markdown format ─────────────────────────────────────────────────


def test_markdown_format_returns_text_report(capsys):
    rc, out, err = _run(
        ["crisis-dossier", "2008Q4", "--format", "markdown"], capsys,
    )
    assert rc == 0, err
    assert err == ""
    # The renderer guarantees a top-level "# " title.
    assert out.startswith("# "), out[:80]
    # Required H2 sections from the renderer contract. (Section names
    # are pinned by tests/test_report_renderer.py — we re-check here only
    # to confirm the CLI pipeline delivers them unchanged.)
    for marker in (
        "## Shock summary",
        "## Phase classification",
        "## Macro event scores",
        "## Replay summary",
        "## Network stress summary",
        "## Research notes",
        "## Spec",
    ):
        assert marker in out, f"missing section: {marker}"
    # NFA / research-only disclaimer must be carried through.
    assert "Disclaimer" in out, "disclaimer missing from markdown export"


def test_markdown_title_prefix_is_applied(capsys):
    prefix = "DRAFT — "
    rc, out, _err = _run(
        [
            "crisis-dossier", "2020Q1",
            "--format", "markdown",
            "--title-prefix", prefix,
        ],
        capsys,
    )
    assert rc == 0
    first_line = out.splitlines()[0]
    assert first_line.startswith(f"# {prefix}"), first_line


def test_markdown_emits_unicode_arrow(capsys):
    """The composition footer contains U+2192; the UTF-8-safe writer must
    deliver it intact even on Windows cp1252 (this would have crashed
    before the ``_write_stdout_utf8_safe`` helper landed)."""
    rc, out, _err = _run(
        ["crisis-dossier", "2023Q1", "--format", "markdown"], capsys,
    )
    assert rc == 0
    assert "→" in out


@pytest.mark.parametrize("window", list_dossier_windows())
def test_all_supported_windows_render_markdown(window, capsys):
    rc, out, err = _run(
        ["crisis-dossier", window, "--format", "markdown"], capsys,
    )
    assert rc == 0, err
    assert window in out


# ─── Error handling ──────────────────────────────────────────────────


def test_unknown_window_exits_two_with_clean_stderr(capsys):
    rc, out, err = _run(["crisis-dossier", "1999Q9"], capsys)
    assert rc == 2
    assert out == ""
    assert "unknown crisis-dossier window" in err
    assert "1999Q9" in err
    # Hint must list the supported set so operators can self-recover.
    for window in list_dossier_windows():
        assert window in err
    # Clean error path — no traceback leak.
    assert "Traceback" not in err


def test_invalid_format_choice_argparse_rejects(capsys):
    """argparse should reject unknown ``--format`` values with SystemExit
    rather than reaching the handler."""
    with pytest.raises(SystemExit) as excinfo:
        main(["crisis-dossier", "2008Q4", "--format", "pdf"])
    assert excinfo.value.code != 0


def test_missing_window_argparse_rejects(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["crisis-dossier"])
    assert excinfo.value.code != 0


# ─── Determinism + isolation ─────────────────────────────────────────


def test_repeated_invocation_is_byte_identical(capsys):
    rc1, out1, _err1 = _run(
        ["crisis-dossier", "2008Q4", "--format", "json"], capsys,
    )
    rc2, out2, _err2 = _run(
        ["crisis-dossier", "2008Q4", "--format", "json"], capsys,
    )
    assert rc1 == 0 and rc2 == 0
    assert out1 == out2, "JSON export must be deterministic"


def test_repeated_markdown_is_byte_identical(capsys):
    rc1, out1, _ = _run(
        ["crisis-dossier", "2020Q1", "--format", "markdown"], capsys,
    )
    rc2, out2, _ = _run(
        ["crisis-dossier", "2020Q1", "--format", "markdown"], capsys,
    )
    assert rc1 == 0 and rc2 == 0
    assert out1 == out2, "Markdown export must be deterministic"


def test_no_external_network_io(monkeypatch, capsys):
    """The dossier path must be 100% offline.  We monkeypatch the two
    HTTP entry points the CBSRM stack uses (``urllib.request.urlopen``
    and ``requests.Session.request``) to raise immediately if touched."""
    import urllib.request

    def _no_urlopen(*_a, **_kw):
        raise AssertionError("crisis-dossier CLI made a urllib network call")

    monkeypatch.setattr(urllib.request, "urlopen", _no_urlopen)

    try:
        import requests  # noqa: F401

        def _no_requests(self, *_a, **_kw):  # pragma: no cover (defensive)
            raise AssertionError(
                "crisis-dossier CLI made a requests network call"
            )

        monkeypatch.setattr("requests.Session.request", _no_requests)
    except ImportError:
        pass

    for window in list_dossier_windows():
        rc, _out, err = _run(
            ["crisis-dossier", window, "--format", "json"], capsys,
        )
        assert rc == 0, err
        rc, _out, err = _run(
            ["crisis-dossier", window, "--format", "markdown"], capsys,
        )
        assert rc == 0, err


# ─── HTML format (v0.9 addition) ────────────────────────────────────


def test_html_format_2008q4_returns_doctype_html(capsys):
    """`--format html` must produce a full HTML document starting with
    the DOCTYPE declaration."""
    pytest.importorskip("markdown")
    rc, out, err = _run(
        ["crisis-dossier", "2008Q4", "--format", "html"], capsys,
    )
    assert rc == 0, err
    assert out.startswith("<!DOCTYPE html>")
    assert "<html" in out
    assert "</html>" in out


@pytest.mark.parametrize("window", list_dossier_windows())
def test_html_format_serves_all_supported_windows(window, capsys):
    pytest.importorskip("markdown")
    rc, out, err = _run(
        ["crisis-dossier", window, "--format", "html"], capsys,
    )
    assert rc == 0, err
    assert "<!DOCTYPE html>" in out
    assert window in out


def test_html_format_contains_disclaimer(capsys):
    pytest.importorskip("markdown")
    rc, out, _err = _run(
        ["crisis-dossier", "2008Q4", "--format", "html"], capsys,
    )
    assert rc == 0
    assert "Disclaimer" in out


def test_html_format_title_prefix_applies(capsys):
    pytest.importorskip("markdown")
    rc, out, _err = _run(
        ["crisis-dossier", "2008Q4",
         "--format", "html",
         "--title-prefix", "WAVERVANIR"],
        capsys,
    )
    assert rc == 0
    assert "WAVERVANIR" in out
    # And it must appear inside the <title> element so the saved-PDF
    # default filename in browsers is meaningful.
    assert "WAVERVANIR" in out.split("</title>")[0]


def test_html_format_is_byte_identical_across_runs(capsys):
    pytest.importorskip("markdown")
    rc1, out1, _ = _run(
        ["crisis-dossier", "2020Q1", "--format", "html"], capsys,
    )
    rc2, out2, _ = _run(
        ["crisis-dossier", "2020Q1", "--format", "html"], capsys,
    )
    assert rc1 == 0 and rc2 == 0
    assert out1 == out2


def test_argparse_accepts_html_in_format_choices(capsys):
    """argparse must reject other formats; html must be accepted as a
    first-class choice alongside json and markdown."""
    # html is accepted (smoke check via successful parse path)
    rc, _out, _err = _run(
        ["crisis-dossier", "2008Q4", "--format", "html"], capsys,
    )
    assert rc == 0
    # Sanity: a bogus format value still fails cleanly (no traceback,
    # non-zero exit). argparse exits via SystemExit on this path.
    with pytest.raises(SystemExit) as excinfo:
        main(["crisis-dossier", "2008Q4", "--format", "yaml"])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert err
    assert "Traceback" not in err


# ─── Manifest flag (v0.9 addition) ──────────────────────────────────


def _read_manifest(path):
    import json as _json
    return _json.loads(path.read_text(encoding="utf-8"))


def test_manifest_flag_writes_sibling_file(tmp_path, capsys):
    """`--manifest PATH` writes a deterministic manifest JSON file."""
    out_path = tmp_path / "m.json"
    rc, out, err = _run(
        ["crisis-dossier", "2008Q4",
         "--format", "json", "--manifest", str(out_path)],
        capsys,
    )
    assert rc == 0, err
    assert out_path.is_file()
    manifest = _read_manifest(out_path)
    # Required top-level shape from cbsrm.reporting.manifest.
    assert set(manifest.keys()) == {
        "manifest_version", "report_id", "window_id", "format",
        "source", "generated_at_utc", "versions", "hashes",
        "disclaimer_present",
    }


def test_manifest_records_source_cli(tmp_path, capsys):
    out_path = tmp_path / "m.json"
    rc, _out, _err = _run(
        ["crisis-dossier", "2008Q4",
         "--format", "markdown", "--manifest", str(out_path)],
        capsys,
    )
    assert rc == 0
    manifest = _read_manifest(out_path)
    assert manifest["source"] == "cli"


@pytest.mark.parametrize("fmt", ["json", "markdown", "html"])
def test_manifest_format_matches_cli_format(fmt, tmp_path, capsys):
    if fmt == "html":
        pytest.importorskip("markdown")
    out_path = tmp_path / "m.json"
    rc, _out, _err = _run(
        ["crisis-dossier", "2020Q1",
         "--format", fmt, "--manifest", str(out_path)],
        capsys,
    )
    assert rc == 0
    manifest = _read_manifest(out_path)
    assert manifest["format"] == fmt


def test_manifest_output_sha256_matches_stdout(tmp_path, capsys):
    """The hash in the manifest must equal sha256 of the bytes the
    user saw on stdout."""
    import hashlib

    out_path = tmp_path / "m.json"
    rc, stdout, _err = _run(
        ["crisis-dossier", "2008Q4",
         "--format", "markdown", "--manifest", str(out_path)],
        capsys,
    )
    assert rc == 0
    manifest = _read_manifest(out_path)
    expected = hashlib.sha256(stdout.encode("utf-8")).hexdigest()
    assert manifest["hashes"]["output_sha256"] == expected


def test_manifest_window_id_pinned(tmp_path, capsys):
    out_path = tmp_path / "m.json"
    rc, _out, _err = _run(
        ["crisis-dossier", "2023Q1",
         "--format", "json", "--manifest", str(out_path)],
        capsys,
    )
    assert rc == 0
    manifest = _read_manifest(out_path)
    assert manifest["window_id"] == "2023Q1"
    assert manifest["report_id"] == "crisis-dossier"


def test_no_file_written_when_manifest_flag_omitted(tmp_path, capsys):
    """Without `--manifest`, no file in tmp_path. Stdout report is
    still emitted as before."""
    rc, out, _err = _run(
        ["crisis-dossier", "2008Q4", "--format", "json"], capsys,
    )
    assert rc == 0
    assert out  # report still on stdout
    assert list(tmp_path.iterdir()) == []  # no side-effect file


def test_stdout_byte_identical_with_and_without_manifest_flag(
    tmp_path, capsys,
):
    """The manifest flag must be purely additive: stdout report
    bytes are byte-identical with or without `--manifest`."""
    rc1, out_without, _ = _run(
        ["crisis-dossier", "2008Q4", "--format", "json"], capsys,
    )
    out_path = tmp_path / "m.json"
    rc2, out_with, _ = _run(
        ["crisis-dossier", "2008Q4",
         "--format", "json", "--manifest", str(out_path)],
        capsys,
    )
    assert rc1 == 0 and rc2 == 0
    assert out_without == out_with
