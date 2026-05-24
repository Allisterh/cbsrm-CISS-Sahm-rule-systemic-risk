# CBSRM — Cross-Border Systemic Risk Monitor

> A 7-layer, methodology-first, open-source platform for cross-jurisdiction financial-stability monitoring and systemic-risk pricing.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-316_passing-brightgreen.svg)](#tests)
[![Version](https://img.shields.io/badge/version-0.5.0-blueviolet.svg)](CHANGELOG.md)
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

## What's inside (v0.5.0)

| Layer | Modules | Reference |
|-------|---------|-----------|
| **Stress indicators** | CISS-US, ECB CISS (EA / US / UK), STLFSI4, OFR-FSI | Holló-Kremer-Lo Duca (2012) |
| **Macro engine** | Yield curve + recession probit, NFP momentum, FFR change, broad-USD regime, USD/JPY regime, CPI surprise, oil macro, credit-spread regime, 4-state composite | Estrella-Mishkin (1996), Bruno-Shin (2015), Hamilton (2003), Gilchrist-Zakrajsek (2012) |
| **Risk pricing** | SRISK + LRMES, ΔCoVaR, MES | Brownlees-Engle (2017), Adrian-Brunnermeier (2016), Acharya et al. (2017) |
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
# 316 passing in <5s; all HTTP mocked; Monte Carlo seeded for determinism.
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
  note         = {Apache 2.0; version 0.5.0}
}
```

SSRN abstract + JEL codes: see [`SSRN_SUBMISSION.md`](SSRN_SUBMISSION.md).

## Roadmap

**v0.6** (next):
- BIS Stats API adapter (cross-border banking, derivatives notional, FX turnover)
- Network-contagion via DebtRank ([`marcobardoscia/neva`](https://github.com/marcobardoscia/neva))
- `arch`-backed GJR-GARCH-DCC fitter (end-to-end SRISK / MES from raw return histories)
- Crisis-replay notebooks (2008Q4, 2020Q1, 2023Q1)

**v0.7+:**
- Diebold-Yilmaz spillover index
- Acemoglu phase classifier
- Streamlit dashboard
- Cross-jurisdiction integrator

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Issue templates and a methodology-review checklist are in `.github/`.

## Inbound

This work compounds when applied. Substantive conversations with quant research teams, prop shops, central-bank innovation hubs, and supervisory-technology groups welcomed via the repository or LinkedIn (Prabhawa Koirala / WaverVanir International).

## License

Apache 2.0 — see [`LICENSE`](LICENSE).

## v0.8 research flow (work in progress)

The v0.8 series chains four modules into a single narrative —
**macro shock (`score_event`) → crisis replay (`replay_macro_events`) →
cross-asset connectedness (`DYSpilloverIndicator`) → systemic DebtRank
(`debt_rank`)**. End-to-end walkthrough, runnable code blocks, and the
current API-consistency gap list are in
[`docs/v0.8_research_flow.md`](docs/v0.8_research_flow.md). Stages 2 and 4
land on `main` from parallel branches before the v0.8 tag.
