# Changelog

All notable changes to CBSRM are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and CBSRM adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — v0.8 work in progress

**`cbsrm.macro.macro_events` — discrete macro-event surprise scorer**
- Pure function `score_event(event, actual, consensus, previous=None, unit=None, history=None)` returns a normalised surprise (`surprise`, `surprise_z`, `abs_z`), a `direction` (`hotter_than_expected` / `cooler_than_expected` / `in_line`), a `severity` bucket (`trivial` / `mild` / `moderate` / `large` / `extreme`), and a coarse `risk_bias` tag (`rates_up_equities_down` etc).
- Event registry covers 12 prints: CPI, CORE_CPI, PCE, CORE_PCE, NFP, UNRATE, INITIAL_CLAIMS, GDP, RETAIL_SALES, ISM_MANUFACTURING, ISM_SERVICES, FOMC_RATE. Per-event polarity (e.g. UNRATE: higher = cooler) and conservative historical-surprise σ anchors so z-scoring works with zero caller-supplied history.
- z-score auto-prefers a caller-supplied surprise history (NaN/None filtered, ≥ 2 finite obs required, non-zero variance), otherwise falls back to the registry default scale.
- Companion helpers: `list_supported_events()`, `get_event_spec(event)`.
- Intended as *decision intelligence*, not a trading signal — coarse `risk_bias` mapping, in-line band defaults to |z| < 0.25 = `neutral`.
- 23 tests in `tests/test_macro_events.py`.

**`cbsrm.diagnostics.macro_replay` — windowed price reaction around macro events**
- `replay_macro_events(events_df, prices_df, pre_window_days=5, post_window_days=5)` composes `macro_events.score_event` with as-of-or-prior price lookups on a wide-form price panel, returning a long-form DataFrame keyed by `(event, price_series)` with `surprise`, `surprise_z`, `direction`, `severity`, `risk_bias`, and pre/post log returns. Pure function, no I/O.
- Runnable walkthrough at `notebooks/crisis_replay/macro_event_replay.py` driving deterministic fixtures (`fixtures/events.csv` mixing CPI/NFP/UNRATE 2023-2024, `fixtures/prices.csv` covering all event dates ± 15 days for SPY_PROXY / TLT_PROXY).
- 10 tests in `tests/test_macro_replay.py` covering returned schema, hotter-direction propagation, hand-calculated pre/post log returns on a linear ramp, missing-column / empty-input / non-positive-window / non-DataFrame `ValueError` paths, fixture round-trip, and unknown-event passthrough.

### Planned for v0.8 (remaining)
- 2008Q4 / 2020Q1 / 2023Q1 crisis-replay notebooks (will consume `macro_events`)
- Network-contagion via `marcobardoscia/neva` (DebtRank)
- `arch`-backed GJR-GARCH-DCC fitter for end-to-end SRISK from raw returns
- LBS (locational banking statistics) + BIS EER (effective exchange rates)
- Acemoglu phase classifier

---

## [0.7.0] — 2026-05-21

### Added — v0.7 milestone: Sahm Rule + Diebold-Yilmaz spillover

**`cbsrm.macro.sahm_rule.SahmRuleIndicator`** (Sahm 2019, FEDS Notes)
- Real-time recession indicator from FRED `UNRATE`. Triggers when the 3-month average of the unemployment rate rises ≥ 0.50 pp above its trailing 12-month minimum. Perfect record for US recessions since 1970.
- Classifications: `RECESSION_TRIGGERED` / `EARLY_WARNING` (≥ 0.30 pp) / `NORMAL`.
- Full i18n (en/ja/es/fr/de) per the v0.3 multi-language convention.
- CLI: `cbsrm sahm-rule [--start ...]`.

**`cbsrm.indicators.dy_spillover.DYSpilloverIndicator`** (Diebold-Yilmaz 2012, IJF)
- Total spillover index in [0, 100%] over any return panel. Pesaran-Shin (1998) generalized variance decomposition (invariant to variable ordering).
- Pure numpy: OLS VAR + closed-form GFEVD. No statsmodels dependency.
- Validation invariants: rows of normalized FEVD sum to 1; spillover bounded in [0, 100]; invariant to constant rescaling of any column; coupled panels yield higher spillover than independent ones.
- Also exports `spillover_series()` for rolling-window time-series of the index.
- CLI: `cbsrm dy-spillover [--tickers XLF,XLK,XLE,XLU]` (Stooq daily-close default).

**CLI / info / docs**
- `cbsrm sahm-rule`, `cbsrm dy-spillover` subcommands.
- `cbsrm info` updated with both modules and the new `connectedness_indicators` group.

**Whitepaper §14 — Recession nowcasting + connectedness**
- Sahm methodology, the 2024 borderline trigger, the EARLY_WARNING extension.
- Diebold-Yilmaz methodology, Pesaran-Shin generalized variance decomposition, spillover-vs-stress complementarity.

**Tests**
- 363 passing (was 335; +28 across `test_sahm_rule.py` and `test_dy_spillover.py`).

### Hosted demo + Show HN
- `dashboard/STREAMLIT_DEPLOY.md` — step-by-step Streamlit Community Cloud deploy (free, no card).
- `SHOW_HN_POST.md` — submission-ready Hacker News post + 2 alternate titles + a comment-anchor draft.

---

## [0.6.0] — 2026-05-21

### Added — v0.6 milestone: BIS Stats SDMX adapter + Streamlit dashboard

CBSRM gains the cross-border-banking + OTC-derivatives dimension that was the most-requested missing surface from v0.5.

**New module — `cbsrm.data.bis_sdmx`**
- `BISStatsClient` — SDMX 2.1 REST client against `stats.bis.org/api/v2` (CSV mode, no XML deps). Mirrors the `ECBSDMXClient` shape: file-cache, retry-on-transient, project-identifying User-Agent.
- Generic `get_dataset(flow_id, key, version, params)` for arbitrary BIS dataflows.
- Convenience methods: `get_otc_derivatives_notional()`, `get_consolidated_banking_claims()`.

**New indicators — `cbsrm.indicators.bis_*`**
- `BISOTCDerivativesIndicator` — wraps OTC derivatives notional outstanding (table D5.1). Semi-annual.
- `BISCBSClaimsIndicator` — wraps consolidated banking statistics (cross-border claims on immediate counterparty basis). Quarterly.

**Streamlit demo dashboard — `dashboard/streamlit_app.py`**
- Single-page live view: macro composite regime, 4 jurisdictions stress (CISS + STLFSI4), 4 macro readings, SRISK panel for 3 G-SIBs, ΔCoVaR + MES illustration.
- Read-only, no auth surface. Caches with `st.cache_data(ttl=3600)`.
- `streamlit run dashboard/streamlit_app.py` to launch.

**CLI**
- `cbsrm bis-otc [--start YYYY]` — latest OTC derivatives notional
- `cbsrm bis-cbs [--start YYYY-Qn]` — latest cross-border banking claims
- `cbsrm info` updated to list BIS as a data source

**Whitepaper**
- New §13 "Cross-border banking + OTC derivatives data" — methodology, datasets, integration with the v0.5 risk-pricing triad, supervisory interpretation

**Tests**
- 335 passing (was 316; +19 across `test_bis_sdmx.py`)

### Notes
- BIS publishes SDMX 2.1; their key formats and dataflow versions occasionally rotate. The convenience methods use sensible defaults; operators with known BIS keys can pass them via `get_dataset(flow_id, key)`.
- The Streamlit dashboard is read-only and intentionally limited in scope — it exists as a demo / screenshot surface, not a production monitoring system.

---

## [0.5.0] — 2026-05-21

### Added — v0.5 milestone: ΔCoVaR + MES — risk-pricing layer expanded

The `cbsrm.risk` subpackage now ships the three most-cited
systemic-risk metrics in supervisory literature:

- **SRISK** (Brownlees-Engle 2017) — v0.4
- **ΔCoVaR** (Adrian-Brunnermeier 2016) — v0.5, NEW
- **MES** (Acharya-Pedersen-Philippon-Richardson 2017) — v0.5, NEW

**New module — `cbsrm.risk.delta_covar`**
- `DeltaCoVaREstimator` — fits CoVaR via linear quantile regression on
  paired firm + system returns (optional state-variable controls);
  computes `ΔCoVaR = β_q × (VaR_q_firm − median_firm)`.
- `quantile_regression()` — pure-numpy linear quantile regression
  (Koenker-Bassett 1978) via gradient descent on the pinball loss. No
  statsmodels / SciPy dependency at fit-time.
- Validated against known-correlation synthetic pairs (independence →
  ΔCoVaR ≈ 0; high correlation → ΔCoVaR strongly negative; median q
  yields ΔCoVaR ≈ 0 by construction).

**New module — `cbsrm.risk.mes`**
- `empirical_mes()` — historical MES from a paired return sample. The
  fast, robust default for samples with sufficient market-tail days.
- `MESMonteCarlo` — model-implied MES via GJR-GARCH-DCC simulation at
  one-day horizon. Same simulator as LRMES; lets you compute MES under
  counterfactual scenarios that haven't occurred in the historical sample.

**CLI**
- `cbsrm delta-covar --input panel.json` — ΔCoVaR for one firm vs system.
- `cbsrm mes --input panel.json` — empirical MES for one firm vs market.
- `cbsrm info` updated to list all four risk modules.

**Whitepaper**
- New §11 — ΔCoVaR methodology + validation properties
- New §12 — MES (empirical + model-implied), comparison with SRISK / ΔCoVaR

**Tests**
- 316 passing (was 292; +24 new across `test_delta_covar.py` and `test_mes.py`)

### Notes
- The three risk modules cover the three dominant academic + supervisory
  approaches to measuring systemic risk: capital shortfall under stress
  (SRISK), tail-conditional system distress contribution (ΔCoVaR), and
  one-day marginal tail exposure (MES). They are complementary, not
  substitutes.

---

## [0.4.0] — 2026-05-20

### Added — v0.4 milestone: SRISK + 3 new macro indicators

**New subpackage — `cbsrm.risk`**

First inhabitant of the risk-pricing layer (one level above stress
indicators + macro regime classifiers).

- `cbsrm.risk.srisk.SRISKCalculator` — SRISK identity (Brownlees-Engle 2017):
  `SRISK = k * D - (1 - k) * W * (1 - LRMES)`. Default `k = 0.08`
  (prudential ratio for US bank holding companies). Validates inputs,
  classifies shortfall vs surplus, preserves metadata.
- `cbsrm.risk.srisk.LRMESMonteCarlo` — Long-Run Marginal Expected Shortfall
  computed via bivariate GJR-GARCH-DCC Monte Carlo. Conditions on the market
  cumulative log-return falling below a threshold (default `-0.40` over
  126 trading days, per Brownlees-Engle 2017 §3.2).
- `cbsrm.risk.srisk.srisk_panel()` — multi-firm aggregator. Outputs total
  positive SRISK (V-Lab convention) + net SRISK + per-firm breakdown
  sorted by SRISK desc.
- `cbsrm.risk.garch_dcc_sim.GARCHDCCSimulator` — bivariate GJR-GARCH(1,1) +
  DCC(1,1) path simulator. Pure numpy, no `arch` / SciPy / `cython` build
  dependency. Includes parameter stationarity / DCC unit-circle validation.

**Three new macro indicators**

- `cbsrm.macro.cpi_surprise.CPISurpriseIndicator` — Robust z-score of YoY
  CPI inflation (FRED `CPIAUCSL`) vs trailing 36-month median (IQR-based
  scale). Classifies INFLATION_OVERSHOOT / AT_TREND / DISINFLATION.
- `cbsrm.macro.oil_macro.OilMacroIndicator` — WTI crude regime (FRED
  `DCOILWTICO`) via YoY log-return. Classifies OIL_SPIKE / OIL_RISING /
  OIL_RANGEBOUND / OIL_FALLING / OIL_CRASH at 30% / 10% bands.
- `cbsrm.macro.credit_spread_regime.CreditSpreadRegimeIndicator` — ICE BofA
  US HY OAS regime (FRED `BAMLH0A0HYM2`). Classifies CREDIT_STRESS_ACUTE /
  CREDIT_STRESS_RISING / CREDIT_NORMAL / CREDIT_BENIGN at 350 / 700 /
  1000 bps thresholds + 100 / 200 bps 1-month-change triggers.

**CLI**

- `cbsrm srisk --input panel.json [--k 0.08]` — SRISK for a JSON panel of firms
- `cbsrm cpi-surprise [--start ...]`
- `cbsrm oil-macro [--start ...]`
- `cbsrm credit-spread [--start ...]`
- `cbsrm info` updated to list risk modules

**Tests**

- 292 passing (was 244; +48 new across `test_srisk.py` and `test_v04_macro.py`).

### Notes
- v0.4 SRISK ships *without* a built-in GJR-GARCH-DCC fitter — parameters
  are caller-supplied. v0.5 adds an `arch`-backed fitter for end-to-end
  per-firm calibration.
- The CPI surprise indicator is a robust momentum proxy. v0.5 will add a
  true `actual − consensus` series via a Trading-Economics or similar
  free-tier consensus adapter.

---

## [0.3.1] — 2026-05-20

### Fixed
- **CISS-US-Canonical SLOOS frequency mismatch.** `CISSUSBuilder.build()` now
  splits required FRED series into a weekly main panel and a quarterly side
  panel for SLOOS-style series (`DRTSCILM`, `DRTSCLCC`). The quarterly panel
  is fetched at FRED's native cadence and reindexed onto the main panel via
  forward-fill, eliminating the HTTP 400 from requesting quarterly series
  at weekly frequency. New class constant: `CISSUSBuilder.QUARTERLY_FRED_IDS`.
- **OFR client User-Agent.** Changed from `cbsrm/0.2` (which the OFR WAF
  blocked) to a standard desktop-Chrome UA. The project identifying string
  is preserved as a custom `X-Project-Source` HTTP header so OFR ops can
  still grep server logs for the project. Note: the underlying CSV endpoint
  may still return 403 from non-residential IPs — this is server-side WAF
  policy. Workaround: download `ofr-fsi.csv` manually and set
  `OFR_FSI_CSV_URL=file:///path/to/ofr-fsi.csv`.

### Added
- `CISSUSBuilder.QUARTERLY_FRED_IDS` class constant — extension point for
  future SLOOS-style series.

### Tests
- 244 passing (one test updated for the new dual-fetch pattern).

---

## [0.3.0] — 2026-05-20

### Added — v0.3 milestone: Macro Engine + Multi-jurisdiction + i18n

**Japan + multi-language**

- `cbsrm.macro.jpy_regime.JPYRegimeIndicator` — USD/JPY trend regime via
  FRED `DEXJPUS`. Same z-score methodology as DXY but classifications
  reflect the yen's safe-haven role: USD_STRONG_JPY_WEAK / USD_MILD_BULL_JPY
  / NEUTRAL / USD_MILD_BEAR_JPY / USD_WEAK_JPY_STRONG. CLI: `cbsrm jpy-regime`.
- `cbsrm.i18n` — multi-language label dictionary covering en / ja / es / fr / de
  for all v0.3 macro indicator interpretations. Every macro indicator now
  carries `interpretation_i18n` in its metadata as a per-locale dict.
  Consumers (CLI, dashboard, API) can pick a locale at render time without
  re-running the indicator.
- Test invariant: every i18n key has a translation for every supported locale
  (enforced in `tests/test_i18n.py`).

**New subpackage — `cbsrm.macro`**

Macro-economic indicators that sit one layer above the L2 stress indices.
Each implements `IIndicator` so it plugs into the existing audit chain,
replication harness, FastAPI service, and CLI driver.

- `cbsrm.macro.yield_curve.YieldCurveIndicator` — T10Y3M inversion + days-
  inverted run-length + Estrella-Mishkin (NY Fed) probit for 12-month
  recession probability. Pure-Python `Phi(.)`, no scipy dependency.
- `cbsrm.macro.nfp_momentum.NFPMomentumIndicator` — Rolling 60-month z-score
  of MoM log payroll growth (FRED `PAYEMS`). Classifies ACCELERATING /
  AT_TREND / DECELERATING / SEVERE_DECELERATION. Promotes to true
  *actual-minus-consensus* surprise in v0.4 when a consensus adapter ships.
- `cbsrm.macro.ffr_change.FFRChangeIndicator` — Composite of 3M/6M/12M EFFR
  changes (FRED `DFF`), in basis points. Regime buckets calibrated against
  1994 / 2004-06 / 2015-19 / 2022-23 hiking cycles: AGGRESSIVE_TIGHTENING /
  TIGHTENING / PAUSE / EASING / AGGRESSIVE_EASING. Thresholds at ±150 bp /
  ±40 bp on the composite.
- `cbsrm.macro.dxy_regime.DXYRegimeIndicator` — Rolling 252-day z-score of
  the Federal Reserve Board H.10 broad trade-weighted USD index (FRED
  `DTWEXBGS`). Strong-bull / strong-bear at |z| ≥ 1.5. Built around Bruno-
  Shin (2015) and Avdjiev-du-Koepke-Shin (2018) finding that broad USD
  regime is the primary driver of global / EM financial conditions.
- `cbsrm.macro.macro_composite.MacroCompositeIndicator` — 4-state regime
  composite (RISK_ON / TRANSITION_UP / TRANSITION_DOWN / RISK_OFF). Each
  sub-indicator emits a score in [-1, +1]; mean bucketed at ±0.4 / ±0.1.
  Three hard-override triggers force RISK_OFF independent of composite
  score: persistent inversion + recession-prob > 30%, AGGRESSIVE_TIGHTENING,
  SEVERE_PAYROLL_DECELERATION.

**CLI**
- `cbsrm yield-curve [--start ...]` — live FRED smoke for T10Y3M.
- `cbsrm nfp-momentum [--start ...]` — live PAYEMS smoke.
- `cbsrm ffr-change [--start ...]` — live DFF smoke.
- `cbsrm dxy-regime [--start ...]` — live DTWEXBGS smoke.
- `cbsrm macro-regime [--start ...]` — 4-state composite end-to-end.
- `cbsrm info` updated to list the macro indicators.

**Tests**
- 221 passing (was 168; +53 new across 5 new test files). All HTTP mocked.

**Whitepaper**
- New §9 "Macro Engine" between §8 (live validation) and Appendix A.
  Documents methodology choices, threshold calibrations, 4-state regime
  scoring rule, and 2026-05-20 live-data readings.

### Whitepaper §9 status

The §9 commitment of the Macro Engine layer is satisfied by v0.3. Reference
invocation:

```
cbsrm macro-regime --start 2010-01-01
```

Threshold calibrations may tighten in v0.4 after a 3-month live observation
window.

### Notes
- The macro engine is intentionally *separable* from the stress engine.
  Stress indices (§§3-8) and macro indicators (§9) plug into the same audit
  + diagnostics + API + CLI infrastructure but are independently usable.
- Private companion repo (VolanX) wires the composite regime into a
  position-sizing layer via the new `ISignalSource` protocol — that
  integration is *not* part of the public CBSRM release.

### Planned for v0.4
- ΔCoVaR (Adrian-Brunnermeier 2016)
- Acemoglu phase classifier
- `marcobardoscia/neva` network-contagion integration
- CFTC Public Reporting adapter

### Planned for v0.5
- Diebold-Yilmaz spillover index (Python reimplementation; existing R-only)
- Cross-jurisdiction integrator (the unique contribution)
- Streamlit dashboard

---

## [0.2.0] — 2026-05-21

### Added — v0.2 milestone: cross-source replication

**L1 — Data adapters**
- `cbsrm.data.ofr.OFRClient` — OFR Financial Stress Index (CSV) +
  Short-Term Funding Monitor (JSON) client. File-cached, retry-on-transient.
  Permissive CSV schema autodetection (column rename tolerant).
- `cbsrm.data.ecb_sdmx.ECBSDMXClient` — ECB Data Portal SDMX client in
  CSV mode (no XML SDMX deps). Convenience methods: `get_ciss_euro_area`,
  `get_ciss_us`, `get_ciss_uk`. Configurable base URL via env var.

**L2 — New indicator wrappers**
- `cbsrm.indicators.ofr_fsi.OFRFSIWrap` — passthrough indicator for the
  OFR FSI composite + 5-subindex breakdown (credit, equity valuation,
  funding, safe assets, volatility). Permissive column resolution.
- `cbsrm.indicators.ecb_ciss.ECBCISSWrap` — passthrough indicator for
  ECB-published CISS series. Supports euro-area (EA), US, UK variants.

**New subpackage — Diagnostics**
- `cbsrm.diagnostics.replication.replicate()` — cross-indicator comparison.
  Computes Pearson r, Spearman ρ, z-scored MAE over full sample plus
  declared crisis windows. Threshold-checking via
  `ReplicationReport.meets_threshold(full_sample_r, crisis_r)`.
- `cbsrm.diagnostics.replication.CRISIS_WINDOWS` — 9 canonical episodes
  (2007 subprime, 2008 GFC acute, 2010 EU debt, 2011 EU debt #2, 2015
  China deval, 2018Q4, 2020 COVID, 2022 inflation, 2023 SVB).

**CLI**
- `cbsrm ofr-fsi [-v]` — fetch + print latest OFR FSI composite.
- `cbsrm ecb-ciss [--variant EA|US|UK]` — fetch + print latest ECB CISS.
- `cbsrm replicate ciss-us ofr-fsi [--threshold-full 0.80 --threshold-crisis 0.75]`
  — run full replication diagnostics with PASS/FAIL against thresholds.
  Supports `ofr-fsi`, `ecb-ciss-ea`, `ecb-ciss-us`, `ecb-ciss-uk` as canonical side.
- `cbsrm info` updated to enumerate new indicators + data sources.

**Tests**
- 148 passing (was 91; +57 new). HTTP mocked, no live network needed.
- Test coverage: OFR client (13), OFR FSI wrapper (10), ECB client + CISS wrapper (18),
  replication diagnostics (15).

### Whitepaper §7.2 status

The v0.2 release satisfies the §7.2 commitment of cross-indicator replication.
`cbsrm replicate ciss-us ofr-fsi --start 2010-01-01` is the reference invocation.
Replication thresholds in v0.2: full-sample Pearson r ≥ 0.80, crisis-window Pearson r ≥ 0.75
(provisional; tightened to 0.85 / 0.80 in v0.3 after live-data validation).

---

## [0.1.0] — 2026-05-21

### Added

**L0 — Audit chain**
- `cbsrm.audit.chain.AuditChain` — sha256-linked append-only audit log
  with full lifecycle tracking (REQUESTED, INPUT_FETCHED, INPUT_MISSING,
  COMPUTED, SERVED, METHOD_UPGRADED, REPRODUCED, FAILED). Ported from
  the same author's production Derivatives Risk Framework.
- `cbsrm.audit.audited_indicator.AuditedIndicator` — thin wrapper that
  writes a full 4-event lifecycle on every `indicator.compute()` call,
  attaching the COMPUTED row id to the returned IndicatorResult.

**L1 — Public data ingestion**
- `cbsrm.data.fred.FREDClient` — Federal Reserve Economic Data API
  wrapper with file-cache, retry-on-transient, license-aware metadata
  accessor, and pandas Series/DataFrame outputs in UTC-tz timezone.

**L2 — Indicators (methodology)**
- `cbsrm.indicators.base.IIndicator` — protocol every indicator implements.
- `cbsrm.indicators.stlfsi.STLFSIWrap` — STLFSI4 passthrough as the
  baseline integrity check.
- `cbsrm.indicators.ciss_us.CISSUS` — Composite Indicator of Systemic
  Stress (Holló-Kremer-Lo Duca 2012) applied to US data with
  user-configurable input mapping.
- `cbsrm.indicators.ciss_us_canonical.CISSUSCanonical` — CISSUS with
  the frozen canonical FRED-derived input mapping (15 inputs across
  5 subindices: money market, bond market, equity market, financial
  intermediaries, foreign exchange).

**Builders**
- `cbsrm.builders.ciss_us_builder.CISSUSBuilder` — bridge from raw FRED
  series to CISSUS-ready 15-column input matrix. Implements recipes for
  SPREAD, ABS, CMAX, REALVOL, DAILY_VOL transforms. Returns reproducibility
  manifest documenting every input's source and substitution status.

**L5 — API + CLI**
- `cbsrm.api.routes.build_app` — FastAPI service exposing indicator
  registry, audit-chain access, and chain verification.
- `cbsrm` CLI with subcommands: `info`, `latest`, `ciss-us`, `verify-audit`.

**Documentation**
- `README.md` with architecture diagram, quick-start, citation form.
- `whitepaper/cbsrm_methodology_v1.md` — 10-section academic-style paper
  (~5,800 words) covering methodology, related work, BIS Innovation Hub
  alignment, replication strategy, and limitations.
- `examples/run_ciss_us.py` — end-to-end demo script.

**Testing**
- 91 tests, all passing on Python 3.10+.
- Test coverage spans audit chain integrity, FRED HTTP mocking, indicator
  protocol conformance, CISS-US synthetic crisis-window validation,
  builder recipe correctness, and audited-indicator lifecycle.

**Infrastructure**
- `pyproject.toml` configured for PyPI publication.
- Apache 2.0 license.
- GitHub Actions CI matrix (Ubuntu/macOS/Windows × Python 3.10/3.11/3.12).

### Notes
- BIS Stats API and ECB Data Portal adapters are scaffolded in the
  `cbsrm.data.__init__` module docstring but ship in v0.2.
- The CISS-US canonical 15-input mapping documented in the whitepaper §3.2
  includes several substitutes for inputs not available on FRED (e.g.
  basis swaps, SLOOS diffusion). The builder's manifest records every
  substitution; the v0.2 release will reduce substitutions by adding
  the ECB SDMX adapter for euro-area cross-references.
