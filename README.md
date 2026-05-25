# CBSRM — Cross-Border Systemic Risk Monitor

> A 7-layer, methodology-first, open-source platform for cross-jurisdiction financial-stability monitoring and systemic-risk pricing.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-944_passing-brightgreen.svg)](#tests)
[![Version](https://img.shields.io/badge/version-0.8.0-blueviolet.svg)](CHANGELOG.md)
[![Whitepaper](https://img.shields.io/badge/whitepaper-12_sections-orange.svg)](whitepaper/cbsrm_methodology_v1.md)

CBSRM reproduces, in modern typed Python, the canonical systemic-risk and financial-stability measures used by central banks, supervisory authorities, and the academic literature — under one Protocol, one audit chain, and one reproducibility guarantee. Apache 2.0.

```
┌──────────────────────────────────────────────────────────────────────┐
│  L7  Public surface       — whitepaper, dashboards, SSRN paper       │
│  L6  Truth ledger         — sha256-linked audit chain                │
│  L5  Execution            — (private companion only)                 │
│  L4  Risk                 — (private companion only)                 │
│  L3  Composer             — (private companion only)                 │
│  L2  Indicators           — stress (CISS, OFR-FSI, STLFSI) +         │
│                             macro (yield curve, NFP, FFR, DXY, JPY, │
│                             CPI, oil, credit spread, composite)      │
│      Risk-pricing         — SRISK, LRMES, ΔCoVaR, MES                │
│  L1  Data adapters        — FRED, OFR, ECB SDMX                      │
└──────────────────────────────────────────────────────────────────────┘
```

## What's inside (v0.8.0)

| Layer | Modules | Reference |
|-------|---------|-----------|
| **Stress indicators** | CISS-US, ECB CISS (EA / US / UK), STLFSI4, OFR-FSI | Holló-Kremer-Lo Duca (2012) |
| **Macro engine** | Yield curve + recession probit, NFP momentum, FFR change, broad-USD regime, USD/JPY regime, CPI surprise, oil macro, credit-spread regime, Sahm Rule, 4-state composite | Estrella-Mishkin (1996), Bruno-Shin (2015), Hamilton (2003), Gilchrist-Zakrajsek (2012), Sahm (2019) |
| **Risk pricing** | SRISK + LRMES, ΔCoVaR, MES | Brownlees-Engle (2017), Adrian-Brunnermeier (2016), Acharya et al. (2017) |
| **Cross-border (v0.6)** | BIS Stats SDMX adapter, OTC derivatives notional, consolidated banking statistics | BIS Statistics |
| **Connectedness (v0.7)** | Diebold-Yilmaz spillover index (Pesaran-Shin GFEVD) | Diebold-Yilmaz (2012) |
| **Macro events (v0.8)** | `score_event` discrete-event surprise scorer (12 prints: CPI / CORE_CPI / PCE / NFP / UNRATE / INITIAL_CLAIMS / GDP / RETAIL_SALES / ISM_MFG / ISM_SVCS / FOMC_RATE) | Andersen-Bollerslev-Diebold-Vega (2003) |
| **Replay (v0.8)** | `replay_macro_events` windowed pre/post log-return surface around macro prints | Original |
| **Network systemic risk (v0.8)** | `debt_rank` pure-numpy DebtRank engine + U/D/I state-machine cascade | Battiston et al. (2012) |
| **Phase classifier (v0.8)** | `classify_phase` Acemoglu-style 8-phase deterministic labeller | Acemoglu-Ozdaglar-Tahbaz-Salehi (2015) |
| **Crisis dossiers (v0.8)** | `build_crisis_dossier` deterministic fixture-backed bundles for 2008Q4 / 2020Q1 / 2023Q1 | Original |
| **Report renderer (v0.8)** | `render_dossier_markdown` + `build_report_payload` Markdown + JSON-serializable export surface | Original |
| **CLI export (v0.8)** | `cbsrm crisis-dossier WINDOW [--format json\|markdown] [--title-prefix TEXT]` (UTF-8-safe, offline) | Original |
| **HTTP API (v0.8)** | `GET /reports/crisis-dossiers`, `GET /reports/crisis-dossiers/{id}`, `GET /reports/crisis-dossiers/{id}/markdown` (read-only, no auth, lazy FastAPI import) | Original |
| **Streamlit viewer (v0.8)** | `dashboard/crisis_dossier_viewer.py` standalone offline page — selectbox + inline Markdown + `.md`/`.json` downloads | Original |
| **Audit + diagnostics** | sha256-linked lifecycle ledger, cross-source replication harness, crisis-window replay | Original |
| **Five jurisdictions** | US / Euro-Area / UK / Japan / broad-USD | — |
| **Five languages** | EN / JA / ES / FR / DE | Reviewed translations |

## Quick start

```bash
git clone https://github.com/pravo123/cbsrm
cd cbsrm
pip install -e ".[all]"
export FRED_API_KEY=your_free_fred_key  # https://fred.stlouisfed.org/docs/api/api_key.html

cbsrm info
cbsrm latest STLFSI4
cbsrm ciss-us --start 2020-01-01
cbsrm yield-curve --start 2010-01-01
cbsrm macro-regime --start 2020-01-01
cbsrm srisk --input panel.json
cbsrm delta-covar --input firm.json
cbsrm mes --input firm.json
```

End-to-end example walkthrough: [`examples/quickstart.py`](examples/quickstart.py).

## Live readings (2026-05-20)

| Indicator | Value | Status |
|---|---:|---|
| ECB-CISS-US | 0.00817 | Very low |
| ECB-CISS-EA | 0.00261 | Very low |
| ECB-CISS-UK | 0.05322 | Low–moderate |
| STLFSI4 | -0.7404 | Below-average stress |
| T10Y3M | +0.92 pp | Not inverted |
| P(recession 12mo) | 13.8% | Low |
| FFR composite | -25 bp | PAUSE (EFFR 3.62%) |
| USD/JPY z | +1.19 | USD_MILD_BULL_JPY |
| Macro composite | TRANSITION_UP | — |

Two independent US methodologies (STLFSI4 and ECB-CISS-US) cross-validate the read. All reproducible from any FRED key.

## Why CBSRM exists

Existing open-source systemic-risk implementations are fragmented: academic code lives in R, Stata, MATLAB; commercial systems are black-box; reference numbers come from different vendors that don't agree. CBSRM is methodology-first — every number is reproducible, every lifecycle event is in the audit chain, every source is cited inline. The same Python Protocol covers both stress indicators and risk-pricing measures, so adding a new module is one file plus one registration line.

The target consumers are: hedge-fund and prop-shop risk teams, central-bank financial-stability researchers, supervisory-technology vendors, family offices, and academic researchers. The same code runs on a researcher's laptop and behind a production FastAPI service.

## Architecture

CBSRM is the public half of a paired system. The private companion (VolanX) applies the same data / indicators / audit primitives to a multi-broker derivatives execution platform — same 7-layer architecture, additional layers L3-L5 covering risk, composer, and execution. See [`ARCHITECTURE.md`](../ARCHITECTURE.md) in the parent worktree for the full north-star (note: the private layers are referenced for completeness but not part of the public package).

## Tests

```bash
pytest tests/ -v
# 944 passing on current main in <25s; all HTTP mocked; Monte Carlo seeded for determinism.
```

## Whitepaper

[`whitepaper/cbsrm_methodology_v1.md`](whitepaper/cbsrm_methodology_v1.md) — twelve sections, ~11,000 words:

1. Motivation + architectural intent
2. Related work (open + commercial systemic-risk systems)
3. CISS methodology (Holló-Kremer-Lo Duca)
4. Audit chain primitive
5. Replication strategy
6. BIS Innovation Hub alignment
7. Cross-source replication thresholds
8. Live validation results (2026-05)
9. Macro Engine (v0.3 — 5 jurisdictions, 5 languages)
10. SRISK risk-pricing layer (v0.4)
11. ΔCoVaR (v0.5)
12. MES (v0.5)

## Citation

If CBSRM informs research or supervisory work, please cite:

```bibtex
@misc{cbsrm2026,
  author       = {Koirala, Prabhawa},
  title        = {CBSRM: Cross-Border Systemic Risk Monitor},
  year         = {2026},
  publisher    = {GitHub / WaverVanir International},
  url          = {https://github.com/pravo123/cbsrm},
  note         = {Apache 2.0; version 0.8.0}
}
```

SSRN abstract + JEL codes: see [`SSRN_SUBMISSION.md`](SSRN_SUBMISSION.md).

## Roadmap

**Shipped through v0.8.0:**
- v0.6 — BIS Stats SDMX adapter (OTC derivatives, consolidated banking statistics) + Streamlit dashboard
- v0.7 — Sahm Rule + Diebold-Yilmaz spillover index
- v0.8 — macro event surprise scorer, windowed macro replay, pure-numpy DebtRank, Acemoglu-style phase classifier, deterministic crisis-window dossiers, Markdown + JSON report renderer, plus three front-ends sharing the same composition: CLI (`cbsrm crisis-dossier`), read-only HTTP API (`/reports/crisis-dossiers`), and standalone offline Streamlit viewer (`dashboard/crisis_dossier_viewer.py`)

**Deferred from v0.8.0 (carried into v0.9):**
- `arch`-backed GJR-GARCH-DCC fitter (end-to-end SRISK / MES from raw return histories)
- BIS LBS (locational banking statistics) + EER (effective exchange rates) adapters

**v0.9+ (planned):**
- Composer layer — unified `PipelineRecord` shape, uniform date convention, uniform identifier/version contract across the v0.8 stages
- Cross-jurisdiction integrator (EUR / GBP / JPY events propagating into USD-asset connectedness)
- PDF generation (binary byte stream) + SaaS download surface on top of the v0.8 report renderer (note: HTML print-to-PDF foundation and SQLite content-addressed file persistence keyed on `output_sha256` have both shipped on `main` already; see the v0.8 launch section below)

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Issue templates and a methodology-review checklist are in `.github/`.

## Inbound

This work compounds when applied. Substantive conversations with quant research teams, prop shops, central-bank innovation hubs, and supervisory-technology groups welcomed via the repository or LinkedIn (Prabhawa Koirala / WaverVanir International).

## License

Apache 2.0 — see [`LICENSE`](LICENSE).

## v0.8 launch (released as `v0.8.0`; v0.9 work in progress on `main`)

The v0.8 research flow shipped at tag `v0.8.0` and is on `main`, with
three front-ends sharing one composition. Additive v0.9 work has since
landed on `main` on top of the `v0.8.0` tag — a deterministic report
registry/catalog (`cbsrm.reporting.get_report_catalog`, `cbsrm reports`,
`GET /reports`, `dashboard/report_catalog_viewer.py`), an HTML export
foundation (`cbsrm.reporting.render_dossier_html`) with CLI/API/Streamlit
parity (`--format html`, `/reports/crisis-dossiers/{window_id}/html`,
HTML download button in the existing crisis-dossier viewer),
deterministic export-time manifests
(`cbsrm.reporting.build_report_manifest`, surfaced via
`cbsrm crisis-dossier --manifest PATH`, `?manifest=true` on the JSON
API, and a Streamlit manifest download button), opt-in audit-chain
stamping for exports across all three front-ends
(`cbsrm.reporting.stamp_manifest_to_chain` /
`stamp_manifest_to_db_path`, surfaced via `cbsrm crisis-dossier
--audit-db PATH`, `?audit=true` on the JSON API, and a Streamlit
sidebar "Stamp manifest to audit chain" button driven by
`CBSRM_AUDIT_DB`), and SQLite-backed content-addressed report
persistence keyed on the manifest's `output_sha256`
(`cbsrm.reporting.persistence` — `init_report_store`,
`store_report_artifact`, `get_report_artifact`, `list_report_artifacts`
— surfaced via `cbsrm crisis-dossier --store-db PATH`, `?store=true`
on the JSON API plus a `GET /reports/stored/{output_sha256}` lookup
endpoint, and a Streamlit sidebar "Persist report to store" button
driven by `CBSRM_REPORT_STORE`). The persistence layer is intentionally
**not** coupled to the audit chain in code; the two surfaces share the
manifest's `output_sha256` as a natural join key, and either can be
used standalone. The catalog's second entry, `macro-composite`, is now
fully exposed across all three executable front-ends — a dedicated
CLI subcommand
(`cbsrm macro-composite WINDOW --format json|markdown`), three
read-only HTTP API routes (`GET /reports/macro-composite`,
`…/{window_id}`, `…/{window_id}/markdown`), and a standalone
Streamlit viewer (`streamlit run dashboard/macro_composite_viewer.py`)
— all backed by `cbsrm.reporting.build_macro_composite_report(window_id)`
and `cbsrm.reporting.render_macro_composite_markdown(report)`. It is a
phase-classifier-only first cut, deterministic and fixture-backed,
returning JSON + Markdown for the same canonical windows
(`2008Q4` / `2020Q1` / `2023Q1`); export wiring (manifest / audit /
persistence) and `classify_regime` integration for the macro-composite
report remain deferred to follow-up slices. These v0.9 surfaces are
**not** in the `v0.8.0` tag — they live on `main` only.

**macro shock (`score_event`) → crisis replay (`replay_macro_events`) →
cross-asset connectedness (`DYSpilloverIndicator`) → systemic DebtRank
(`debt_rank`) → phase classifier (`classify_phase`) → crisis dossier
(`build_crisis_dossier`) → report renderer
(`render_dossier_markdown` + `build_report_payload` + `render_dossier_html`)**

…served identically through:

| Front-end | Command |
|---|---|
| **CLI**       | `cbsrm crisis-dossier WINDOW --format json\|markdown\|html [--title-prefix TEXT] [--manifest PATH] [--audit-db PATH] [--store-db PATH]` · `cbsrm macro-composite WINDOW --format json\|markdown` · `cbsrm reports` |
| **HTTP API**  | `GET /reports`, `…/crisis-dossiers`, `…/{window_id}[?manifest=true][&audit=true][&store=true]`, `…/{window_id}/markdown`, `…/{window_id}/html`, `…/stored/{output_sha256}`, `…/macro-composite`, `…/macro-composite/{window_id}`, `…/macro-composite/{window_id}/markdown` |
| **Streamlit** | `streamlit run dashboard/crisis_dossier_viewer.py` (Markdown/JSON/HTML/Manifest downloads + opt-in "Report store" sidebar driven by `CBSRM_REPORT_STORE`) · `streamlit run dashboard/macro_composite_viewer.py` · `streamlit run dashboard/report_catalog_viewer.py` |

All three are deterministic, fixture-backed, offline (no FRED key, no
network), and return bit-for-bit identical reports for the same window.

End-to-end walkthrough, runnable code blocks for every stage, and the
current API-consistency gap list (pre-flagged for the planned v0.9
composer layer) are in
[`docs/v0.8_research_flow.md`](docs/v0.8_research_flow.md).

**Positioning.** The v0.8 surface is **research analytics**:
deterministic / offline / fixture-backed, with explicit no-I/O
regression tests on the new modules. Suitable for SSRN figures,
dashboard tiles, and SaaS-tier report generation. **Not financial
advice; no live broker / Telegram / credential / execution wiring** —
operators wiring the outputs into a live system must add their own
risk controls.
