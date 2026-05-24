# CBSRM v0.8.0

> The v0.8 series chains six methodology stages into one offline research pipeline, exposed through three **bit-for-bit-identical** front-ends. Research analytics, Apache 2.0, no external dependencies added.

The tag `v0.8.0` points at commit `410e3ac9f3e2d3e79484571ef16fc92cd3099d10`. Body below is copy-paste ready for <https://github.com/pravo123/cbsrm/releases/new?tag=v0.8.0>.

---

## Highlights

- **One composition, three front-ends.** `score_event → replay_macro_events → debt_rank → classify_phase → build_crisis_dossier → render_dossier_markdown / build_report_payload` powers the CLI, the read-only FastAPI routes, and the Streamlit viewer — all return the same bytes for the same window.
- **555 tests passing** (up from 469 at v0.7.x).
- **No new runtime dependencies.** FastAPI optional under `cbsrm[api]`; Streamlit lazily imported inside the viewer.
- **Offline, deterministic, fixture-backed.** Explicit no-network-IO tests for the new modules.
- Pure-numpy systemic-network primitive ships with the package.

---

## What's new since v0.7

### Six new methodology stages

| Module | Reference |
|---|---|
| `cbsrm.macro.macro_events.score_event` — discrete-event surprise scorer for 12 prints (CPI / CORE_CPI / PCE / NFP / UNRATE / INITIAL_CLAIMS / GDP / RETAIL_SALES / ISM_MFG / ISM_SVCS / FOMC_RATE) | Andersen-Bollerslev-Diebold-Vega (2003) |
| `cbsrm.diagnostics.macro_replay.replay_macro_events` — windowed pre/post log-return surface around macro prints | Original |
| `cbsrm.networks.debt_rank` — pure-numpy DebtRank with U/D/I state-machine cascade | Battiston et al. (2012) |
| `cbsrm.macro.phase_classifier.classify_phase` — Acemoglu-style 8-phase deterministic labeller (`expansion`, `overheating`, `slowdown`, `contraction`, `disinflationary_recovery`, `stagflationary_stress`, `financial_stress`, `indeterminate`) | Acemoglu-Ozdaglar-Tahbaz-Salehi (2015) |
| `cbsrm.diagnostics.build_crisis_dossier` — deterministic fixture-backed bundles for `2008Q4` (Lehman aftermath), `2020Q1` (COVID), `2023Q1` (SVB / SBNY / FRC) | Original |
| `cbsrm.reporting.render_dossier_markdown` + `build_report_payload` — publication-ready Markdown + JSON-serializable export | Original |

### Three front-ends, one composition

```bash
# CLI
cbsrm crisis-dossier 2008Q4 --format markdown > lehman.md
cbsrm crisis-dossier 2020Q1 --format json | jq '.dossier.phase_label'

# HTTP API (read-only)
uvicorn cbsrm.api.routes:app
curl http://localhost:8000/reports/crisis-dossiers
curl http://localhost:8000/reports/crisis-dossiers/2020Q1
curl http://localhost:8000/reports/crisis-dossiers/2020Q1/markdown

# Streamlit (offline, no FRED key required)
pip install streamlit
streamlit run dashboard/crisis_dossier_viewer.py
```

All three return the same body for the same window. Pinned by tests.

### Quality + footprint

- **555 tests passing.** Targeted suites for the new modules monkeypatch `urllib.request.urlopen` and `requests.Session.request` to fail — proves offline determinism, not just asserts it.
- **No new runtime dependencies.** Numpy-only on the new methodology code path. FastAPI stays under the optional `cbsrm[api]` extra. Streamlit is a lazy import inside the viewer's `render()`, so the helper module is importable (and unit-testable) without Streamlit installed.
- **UTF-8-safe CLI output** on Windows cp1252 consoles — the renderer emits `→` and em-dashes; `cbsrm/cli.py` includes a `_write_stdout_utf8_safe` helper that bypasses the codepage via `sys.stdout.buffer.write(... .encode("utf-8"))`.
- **HTTP 404 contract** on the API: unknown `window_id` returns `{"detail": {"error": "...", "window_id": "...", "supported_windows": [...]}}` with no traceback leaked.

---

## Install / upgrade

```bash
# from PyPI (when published)
pip install --upgrade cbsrm
# with the API extra
pip install --upgrade "cbsrm[api]"
# with everything
pip install --upgrade "cbsrm[all]"

# from source (current path)
git clone https://github.com/pravo123/cbsrm
cd cbsrm
git checkout v0.8.0
pip install -e ".[all]"
```

Verify:

```bash
python -c "import cbsrm; print(cbsrm.__version__)"   # -> 0.8.0
pytest tests/                                        # -> 555 passed
cbsrm crisis-dossier 2008Q4 --format markdown | head
```

---

## Versions bumped

- `pyproject.toml` `version`: `0.1.0` → `0.8.0`
- `cbsrm/__init__.py` `__version__`: `0.7.0` → `0.8.0`

---

## Positioning

The v0.8 surface is **research analytics**: deterministic, offline, fixture-backed. Suitable for SSRN figures, dashboard tiles, and SaaS-tier report generation downstream.

**Not financial advice. No live broker / Telegram / credential / execution wiring exists in this repository.** Operators wiring the outputs into a live system must add their own risk controls.

---

## Deferred to v0.8.x / v0.9

- `arch`-backed GJR-GARCH-DCC fitter (end-to-end SRISK / MES from raw return histories)
- BIS LBS (locational banking statistics) + EER (effective exchange rates) adapters
- Composer layer — unified `PipelineRecord` shape across the v0.8 stages
- PDF generation + file-persistence + SaaS download surface on top of the v0.8 report renderer
- Hosted, auth-gated multi-tenant API

See `PRODUCT_ROADMAP_v0.9.md` in the repo for the prioritized slice list.

---

## RC sequence into this release

`v0.8.0-rc1` → `rc2` → `rc3` → `rc4` → `rc5` → `rc6` → **`v0.8.0`**

All RC tags remain on origin for retrospective auditing.

---

## Acknowledgements

CBSRM stands on a methodology base built by Acharya, Adrian, Battiston, Brunnermeier, Diebold, Engle, Holló, Kremer, Lo Duca, Pedersen, Pesaran, Philippon, Richardson, Shin, Yilmaz, and the BIS / OFR / ECB / FRED data teams whose public APIs make the entire stack possible.

Apache 2.0. See [`CHANGELOG.md`](CHANGELOG.md) for the per-slice log and [`docs/v0.8_research_flow.md`](docs/v0.8_research_flow.md) for the end-to-end research walkthrough.
