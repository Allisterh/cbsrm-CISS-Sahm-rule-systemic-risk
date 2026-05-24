"""Tests for the ``cbsrm macro-composite`` CLI command.

The command is a thin pass-through over
:func:`cbsrm.reporting.build_macro_composite_report` and
:func:`cbsrm.reporting.render_macro_composite_markdown`. These tests
pin the externally observable CLI contract:

  * default + explicit ``--format`` selection
  * deterministic byte-identical stdout on repeated invocation
  * argparse rejects unknown windows, invalid formats, and missing args
  * unknown-window defensive path (if it is ever reached) emits a clean
    error to stderr and exits 2 (no traceback)
  * no external network IO is performed
  * ``cbsrm macro-composite --help`` works

Methodology and report internals are covered by
``tests/test_macro_composite_report.py``; this file does not
re-validate them.
"""
from __future__ import annotations

import json

import pytest

from cbsrm.cli import main
from cbsrm.reporting import (
    NFA_DISCLAIMER,
    build_macro_composite_report,
    render_macro_composite_markdown,
)


_SUPPORTED_WINDOWS = ["2008Q4", "2020Q1", "2023Q1"]


# ─── helpers ─────────────────────────────────────────────────────────


def _run(argv, capsys):
    rc = main(argv)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


# ─── default + explicit format selection ────────────────────────────


def test_default_format_is_json(capsys):
    rc, out, err = _run(["macro-composite", "2008Q4"], capsys)
    assert rc == 0, err
    assert err == ""
    payload = json.loads(out)
    assert payload["report_id"] == "macro-composite"
    assert payload["window_id"] == "2008Q4"


def test_explicit_json_format(capsys):
    rc, out, err = _run(
        ["macro-composite", "2020Q1", "--format", "json"], capsys
    )
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["window_id"] == "2020Q1"


def test_json_emits_no_unicode_escape_sequences(capsys):
    """``ensure_ascii=False`` is required so any non-ASCII glyph
    (em-dash, →, etc.) renders as the literal character rather than a
    ``\\u`` escape — matches the formatting used by ``crisis-dossier
    --format json`` and ``reports``."""
    rc, out, _err = _run(["macro-composite", "2008Q4"], capsys)
    assert rc == 0
    assert "\\u" not in out


@pytest.mark.parametrize("window_id", _SUPPORTED_WINDOWS)
def test_all_supported_windows_render_json(window_id, capsys):
    rc, out, err = _run(["macro-composite", window_id], capsys)
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["window_id"] == window_id
    # And byte-identical to the in-process builder output.
    expected = build_macro_composite_report(window_id)
    assert payload == expected


def test_markdown_format_returns_text_report(capsys):
    rc, out, err = _run(
        ["macro-composite", "2008Q4", "--format", "markdown"], capsys
    )
    assert rc == 0, err
    # Markdown is not JSON.
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)
    assert "2008Q4" in out
    # Disclaimer heading is present (renderer contract).
    assert "## Disclaimer" in out
    assert NFA_DISCLAIMER.strip().splitlines()[0] in out


@pytest.mark.parametrize("window_id", _SUPPORTED_WINDOWS)
def test_all_supported_windows_render_markdown(window_id, capsys):
    rc, out, err = _run(
        ["macro-composite", window_id, "--format", "markdown"], capsys
    )
    assert rc == 0, err
    expected = render_macro_composite_markdown(
        build_macro_composite_report(window_id)
    )
    assert out == expected


# ─── argparse rejection paths ───────────────────────────────────────


def test_unknown_window_argparse_rejects(capsys):
    """``choices=list_macro_composite_windows()`` makes argparse reject
    unknown windows before the handler ever runs; argparse exits 2 and
    writes a usage line to stderr."""
    with pytest.raises(SystemExit) as exc:
        _run(["macro-composite", "9999Q9"], capsys)
    assert exc.value.code == 2


def test_invalid_format_choice_argparse_rejects(capsys):
    with pytest.raises(SystemExit) as exc:
        _run(
            ["macro-composite", "2008Q4", "--format", "yaml"], capsys
        )
    assert exc.value.code == 2


def test_missing_window_argparse_rejects(capsys):
    with pytest.raises(SystemExit) as exc:
        _run(["macro-composite"], capsys)
    assert exc.value.code == 2


# ─── defensive ValueError path in the handler ───────────────────────


def test_clean_error_no_traceback_on_unknown_window(capsys, monkeypatch):
    """The handler also defends against unknown windows from inside
    the builder (defense-in-depth in case ``choices=`` ever drifts
    from ``list_macro_composite_windows()``). When that defensive
    branch fires it must print a single clean error line to stderr,
    return exit code 2, and surface no Python traceback.
    """
    import cbsrm.cli as cli_mod

    def _raises(_window):
        raise ValueError("forced for defense-in-depth test")

    monkeypatch.setattr(cli_mod, "main", cli_mod.main)  # no-op, anchor
    # Patch the symbol the handler imports lazily.
    import cbsrm.reporting as rep_mod
    monkeypatch.setattr(
        rep_mod, "build_macro_composite_report", _raises
    )

    # Use a window argparse will accept so we reach the handler.
    rc, out, err = _run(["macro-composite", "2008Q4"], capsys)
    assert rc == 2
    assert out == ""
    assert "unknown macro-composite window '2008Q4'" in err
    assert "Supported windows:" in err
    assert "2008Q4" in err
    assert "Traceback" not in err


# ─── determinism (byte-identical stdout on repeat) ──────────────────


def test_repeated_json_invocation_is_byte_identical(capsys):
    rc1, out1, _ = _run(["macro-composite", "2023Q1"], capsys)
    rc2, out2, _ = _run(["macro-composite", "2023Q1"], capsys)
    assert rc1 == rc2 == 0
    assert out1 == out2


def test_repeated_markdown_invocation_is_byte_identical(capsys):
    rc1, out1, _ = _run(
        ["macro-composite", "2023Q1", "--format", "markdown"], capsys
    )
    rc2, out2, _ = _run(
        ["macro-composite", "2023Q1", "--format", "markdown"], capsys
    )
    assert rc1 == rc2 == 0
    assert out1 == out2


# ─── offline contract ───────────────────────────────────────────────


def test_no_external_network_io(monkeypatch, capsys):
    import urllib.request

    def _no_network(*_a, **_kw):  # pragma: no cover - defensive
        raise AssertionError(
            "cbsrm macro-composite CLI must not touch the network"
        )

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    try:
        import requests  # type: ignore
    except ImportError:
        requests = None
    if requests is not None:
        monkeypatch.setattr(requests.Session, "request", _no_network)

    for window_id in _SUPPORTED_WINDOWS:
        for fmt in ("json", "markdown"):
            rc, _out, err = _run(
                ["macro-composite", window_id, "--format", fmt], capsys
            )
            assert rc == 0, err


# ─── help surface ───────────────────────────────────────────────────


def test_macro_composite_subcommand_help(capsys):
    with pytest.raises(SystemExit) as exc:
        _run(["macro-composite", "--help"], capsys)
    assert exc.value.code == 0
    out = capsys.readouterr().out
    # Help text mentions the windows and the format flag.
    assert "macro-composite" in out
    assert "--format" in out
    assert "2008Q4" in out
