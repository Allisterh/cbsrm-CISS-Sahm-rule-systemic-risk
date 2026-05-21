# CBSRM — Cross-Border Systemic Risk Monitor

## A reproducible open-source framework for cross-jurisdiction financial-stability monitoring with regulator-grade audit chains

**Working paper, v0.1 — May 2026**
**Author:** WaverVanir International LLC
**Code:** https://github.com/pravo123/cbsrm
**License:** Apache-2.0
**Companion repository:** Derivatives Risk Framework (DRF), https://github.com/pravo123/derivatives-risk-framework

---

## Abstract

Existing public indicators of systemic financial stress are fragmented by jurisdiction. The Federal Reserve Bank of St. Louis publishes STLFSI4 for the United States; the European Central Bank publishes the Composite Indicator of Systemic Stress (CISS) for the euro area; the Office of Financial Research publishes the OFR Financial Stress Index daily; NYU Stern's V-Lab publishes SRISK weekly for large US banks. Each is methodologically rigorous, but no single public artifact (i) re-applies these methodologies across jurisdictions, (ii) exposes the construction code transparently, (iii) produces a daily-cadence cross-border composite with source attribution, and (iv) carries a tamper-evident audit trail of every computation suitable for supervisory review. We introduce **CBSRM**, an open-source Python framework that closes this gap. The v0.1 release ships the audit-chain primitive, the FRED data adapter, the STLFSI passthrough as a baseline, and a US-extended CISS implementation following Holló, Kremer & Lo Duca (2012). The audit-chain primitive is ported from the same author's Derivatives Risk Framework, where it sits under a production multi-broker order pipeline; this paper documents its generalization to systemic-stress methodology audit. We discuss positioning relative to BIS Innovation Hub themes — specifically Project Pine (programmable monetary-policy operations), Project Pyxtrial (stablecoin balance-sheet monitoring), and BIS WPs 1250 and 1291 on machine learning for financial-stability surveillance — and outline the publication and replication agenda for v0.2 through v0.5.

**Keywords:** systemic risk, financial stability, composite stress indicator, CISS, SRISK, audit chain, supervisory technology, central bank cooperation.

**JEL classification:** G01, G15, G18, G28.

---

## 1. Introduction

### 1.1 The fragmentation problem

The 2008 global financial crisis, the March 2020 dash-for-cash, and the March 2023 regional-bank stress episode each demonstrated that financial-stability risks propagate across jurisdictions faster than the public surveillance infrastructure adapts. The standard public-domain composite stress indicators address this only partially:

- The St. Louis Fed Financial Stress Index (STLFSI4) is principal-component-based, weekly, and confined to US series.
- The Chicago Fed National Financial Conditions Index (NFCI) and its adjusted variant (ANFCI) are weekly, US.
- The Kansas City Fed Financial Stress Index (KCFSI) is monthly, US.
- The Office of Financial Research Financial Stress Index (OFR FSI; Monin 2019) is daily, US.
- The ECB Composite Indicator of Systemic Stress (CISS; Holló, Kremer & Lo Duca 2012) is weekly, euro area, with the portfolio-theoretic aggregation that captures non-linear "systemic" amplification.
- NYU Stern's V-Lab publishes SRISK (Brownlees & Engle 2017) weekly for ~30 US large bank holding companies; the engine is not open-source.

Each is methodologically defensible within its mandate. **None is cross-jurisdictional**, none offers a methodology-transparent daily composite across the US, euro area, UK, Japan, and emerging markets, and none carries a tamper-evident audit trail that downstream users (hedge-fund risk teams, family offices, central-bank counterparts, supervisory technology vendors) can independently verify.

### 1.2 Contribution

This paper introduces CBSRM — Cross-Border Systemic Risk Monitor — as a public, open-source, Apache-2.0-licensed framework that addresses each fragmentation axis. Specifically:

1. **Re-implementation, not re-aggregation.** Rather than consuming the ECB CISS or OFR FSI as opaque outputs, CBSRM re-implements the construction algorithms in modern typed Python and applies them, with appropriate input-substitution, across jurisdictions. This makes every value reproducible from public inputs and every methodology choice auditable.

2. **Cross-jurisdiction by construction.** v0.1 ships the US extension of CISS (CISS-US); the v0.2-v0.5 roadmap extends to euro area (replication of ECB output as integrity check), UK, Japan, and an EM cohort.

3. **Regulator-grade audit chain.** Every CBSRM computation is appended to a sha256-chained tamper-evident log that records (a) the request, (b) the input vintage, (c) the computed value, and (d) every external service of that value. The chain primitive is ported from the same author's production derivatives risk infrastructure where it underpins multi-broker order auditing.

4. **API-accessible methodology.** A FastAPI service exposes every computation, the underlying audit row, and a verification endpoint that re-hashes the chain on demand.

5. **Programmable risk-gate extension.** The audit primitive bridges to Project Pine and Project Pyxtrial in the supervisory-technology dimension: methodology values can be referenced from smart contracts or compliance pipelines with cryptographic verifiability of their provenance.

### 1.3 Roadmap of the paper

§2 reviews the methodology literature and the public-tooling landscape. §3 specifies the v0.1 indicator implementations: STLFSI passthrough as the canonical baseline and CISS-US as the first non-trivial methodology re-application. §4 catalogs the data sources, their licensing posture, and the implications for the paid SaaS tier. §5 describes the architecture and the audit-chain design in detail. §6 develops the programmable risk-gate extension and its alignment with active BIS Innovation Hub projects. §7 reports replication diagnostics against synthetic crisis windows and (planned for v0.2) against the ECB-published CISS series. §8 lays out the v0.2-v0.5 roadmap, including cross-jurisdiction integration, SRISK, CoVaR, and Diebold-Yilmaz spillovers. §9 catalogs limitations and threat-model considerations. §10 concludes with the BIS Innovation Hub alignment.

---

## 2. Related work

### 2.1 Composite stress indicators

The methodological foundation of CBSRM-style composites is **Holló, Kremer & Lo Duca (2012)**, ECB Working Paper 1426. Their construction proceeds in three stages: (i) cumulative-distribution-function transformation of fifteen raw stress indicators to the unit interval; (ii) simple-average aggregation within five financial-system segments (money market, bond market, equity market, financial intermediaries, foreign exchange) to produce five subindices; and (iii) portfolio-theoretic aggregation of the subindex vector through a quadratic form weighted by a time-varying exponentially-weighted-moving correlation matrix. The third step is what makes the composite *systemic* in a meaningful sense: when cross-segment correlations rise (the structural definition of a systemic episode), the composite amplifies non-linearly even if each segment's stress is only modestly elevated.

The **OFR Financial Stress Index** (Monin 2019, *Risks*) is a dynamic factor model over 33 indicators across credit, equity valuation, funding, safe assets, and volatility, with a 2023 update adding alternative-reference-rate components after the LIBOR transition.

The **Kansas City Financial Stress Index** (Hakkio & Keeton 2009) and the **Chicago Fed NFCI** (Brave & Butters 2011) are principal-component composites over US risk, liquidity, and leverage variables.

The **STLFSI** is a principal-component composite over 18 US series in its v4 (2022) form.

CBSRM's CISS-US implementation in v0.1 follows Holló-Kremer-Lo Duca verbatim on the algorithm, substituting fifteen US raw inputs for the original euro-area series. §3.2 details the substitution.

### 2.2 Firm-level systemic-risk measures

The two dominant firm-level systemic-risk measures in the public literature are **SRISK** (Acharya, Pedersen, Philippon & Richardson 2017; Brownlees & Engle 2017) and **CoVaR** (Adrian & Brunnermeier 2016).

SRISK is a conditional capital-shortfall measure: the expected capital shortfall of firm *i* conditional on a severe market downturn, scaled by leverage. It requires equity-return-conditional volatility (typically GJR-GARCH-DCC), simulated multi-period market crashes, and balance-sheet leverage. NYU Stern's V-Lab publishes SRISK weekly for ~30 US bank holding companies; the engine is not open-source, and no maintained Python implementation exists in the public domain.

ΔCoVaR is a quantile-regression measure: the difference in the market's value-at-risk conditional on the firm being in distress versus conditional on the firm being at its median state. The original code is in R; a small number of Python replications exist on GitHub but none have crossed the threshold from research artifact to production-quality library.

CBSRM v0.2 will ship SRISK in modern typed Python on top of `bashtage/arch` (the canonical Python GARCH library); v0.3 will ship ΔCoVaR. Both will be validated against V-Lab's published weekly numbers (where possible) and against the original papers' tabulated examples.

### 2.3 Network and contagion models

The Eisenberg-Noe (2001) clearing-payments model is the canonical network-contagion baseline; Battiston et al. (2012) introduced DebtRank as an iterative impact measure; Bardoscia et al. (2015) introduced linear DebtRank as a closed-form alternative. Bank of England researcher Marco Bardoscia maintains `marcobardoscia/neva` (Apache-2.0, Python), which implements the full family of network valuations. CBSRM v0.3 will integrate `neva` rather than reimplement.

Acemoglu, Ozdaglar & Tahbaz-Salehi (2015, NBER w18727) provide the canonical theoretical analysis of how network density and shock size interact to determine resilience versus fragility. Their analytic phase transition (complete-and-resilient versus ring-and-fragile) is, to the author's knowledge, not implemented as a usable classifier in any open-source library. CBSRM v0.4 will ship this classifier as a genuine contribution.

### 2.4 BIS Innovation Hub context

Three threads of recent BIS work are directly relevant:

1. **Project Pine** (concluded May 2025, NY Fed Innovation Center and BIS Swiss Centre): an open-market-operations toolkit on smart contracts, with programmable reserve-requirement, fine-tuning, and standing-facility primitives. The artifact is the open-source prototype. Pine establishes the precedent that supervisory infrastructure can be both transparent and machine-readable.

2. **Project Pyxtrial** (London Centre): stablecoin balance-sheet monitoring, i.e. supervisory technology for asset-backing solvency surveillance. The premise — that supervisors need machine-readable, audit-able views of regulated balance sheets — generalizes to systemic-stress monitoring.

3. **BIS Working Papers 1250 (Aldasoro, Hördahl, Schrimpf & Zhu 2025, "Predicting financial market stress with machine learning") and 1291 (2025, "Harnessing AI for monitoring financial markets: early warning signals from interpretable ML")**. These papers establish that BIS research is actively investing in ML-based financial-stress prediction and that interpretability — the ability to attribute predictions to specific inputs — is a first-order requirement.

CBSRM positions itself in the intersection of these three: it is a methodology-transparent, audit-chain-backed, interpretable, multi-jurisdiction stress framework that could be referenced as an upstream input by Pyxtrial-style supervisory pipelines or as a downstream consumer of Pine-style programmable monetary-policy variables.

---

## 3. Methodology

### 3.1 v0.1 indicator set

CBSRM v0.1 ships two indicators:

- **STLFSI4 wrapper** (`cbsrm.indicators.stlfsi.STLFSIWrap`). A passthrough of the FRED-published St. Louis Fed Financial Stress Index v4. Acts as the *baseline integrity check*: any user-built composite that materially disagrees with STLFSI4 during US crisis windows (2008Q4, 2020Q1, 2023Q1) is suspect.

- **CISS-US** (`cbsrm.indicators.ciss_us.CISSUS`). The first non-trivial methodology implementation: Holló-Kremer-Lo Duca applied to US data.

### 3.2 CISS-US construction

The Holló-Kremer-Lo Duca algorithm, restated for the US extension:

#### Stage 1: Raw input transformation

Let *x*_{i,t} denote the *t*-th observation of the *i*-th raw stress indicator, *i* = 1 … 15. Define the empirical-CDF transform

> *z*_{i,t} = rank(x_{i,t}, {x_{i,s}}_{s=1}^T) / (T+1)

where rank is the average-rank function. The result *z*_{i,t} ∈ (0, 1) is the empirical quantile of *x*_{i,t} within the full-sample distribution of indicator *i*. This makes all inputs scale-free, comparable across heterogeneous units, and robust to outliers.

#### Stage 2: Subindex aggregation

The 15 transformed inputs are partitioned into 5 subindices of 3 inputs each, indexed by financial-system segment *k* ∈ {money market, bond market, equity market, financial intermediaries, foreign exchange}:

> *s*_{k,t} = (1/3) Σ_{i ∈ S_k} *z*_{i,t}

where *S_k* is the set of three raw indicators assigned to segment *k*.

#### Stage 3: Portfolio-theoretic composite

Let **s**_t = (*s*_{1,t}, … , *s*_{5,t})ᵀ denote the subindex vector at time *t* and **w** = (*w*_1, … , *w*_5)ᵀ a non-negative weight vector summing to 1 (defaults: equal weights). The composite is

> CISS_t = ( **w** ⊙ **s**_t )ᵀ **C**_t ( **w** ⊙ **s**_t )

where ⊙ is the elementwise product and **C**_t is the 5×5 time-varying correlation matrix of the subindex returns, estimated by exponentially-weighted moving covariance with decay λ:

> Σ_t = λ Σ_{t-1} + (1−λ)(**s**_t − **μ**_t)(**s**_t − **μ**_t)ᵀ
> *C*_{t,ij} = Σ_{t,ij} / √(Σ_{t,ii} Σ_{t,jj})

The default λ = 0.93 follows the ECB CISS implementation. Initial Σ₀ is bootstrapped from the full-sample sample covariance to avoid degenerate initial readings.

The quadratic form is what gives the composite its systemic property: when subindex stresses are uncorrelated, CISS_t is bounded above by the sum of squared weighted segments; when correlations rise toward 1 (systemic episode), the quadratic form amplifies because the off-diagonal contributions become positive and large. By construction CISS_t ∈ [0, 1] (with clipping for numerical drift).

#### US input substitution

The 15 US raw inputs intended for the canonical CISS-US v1 mapping (release v0.2; the v0.1 implementation accepts any user-supplied 15-column mapping via `CISSConfig.inputs_by_subindex`) are:

| Subindex | Input 1 | Input 2 | Input 3 |
|---|---|---|---|
| Money market | TED spread (TEDRATE) | SOFR − IORB spread | 3M CP − T-Bill spread |
| Bond market | \|10Y − 2Y Treasury spread\| (T10Y2Y) | HY corp OAS (BAMLH0A0HYM2) | 10Y Treasury realized vol |
| Equity market | VIX (VIXCLS) | S&P 500 CMAX (rolling max-drawdown) | S&P 500 financials beta |
| Financial intermediaries | KBW Bank Index CMAX | Bank-sector realized volatility | SLOOS tightening diffusion |
| Foreign exchange | Trade-weighted USD volatility (DTWEXBGS) | EUR/USD basis swap | JPY/USD basis swap |

This mapping deliberately mirrors the structural intent of the ECB version: each subindex captures stress in one functional market segment with a level indicator, a tail-risk indicator, and a relative-pricing indicator.

### 3.3 Replication diagnostics

CBSRM provides a `CISSUS.replication_diagnostics(cbsrm_series, canonical)` function that compares any computed series against a published canonical reference. For CISS-US the natural references are:

- The ECB CISS series for the euro area (correlation should be high during global crises, lower otherwise — a partial diagnostic).
- STLFSI4 (very different methodology but should correlate ≥ 0.6 during crisis windows).
- The OFR FSI (similar daily-cadence US stress index).

Diagnostics returned: Pearson correlation, Spearman rank correlation, z-score mean-absolute error, overlap window size.

§7 reports synthetic-data diagnostics; live-data diagnostics will be released alongside v0.2.

---

## 4. Data

### 4.1 Source roster

CBSRM v0.1 integrates FRED only; the v0.2 roster expands to seven sources, all public and free of API charge:

| # | Source | Endpoint root | Python adapter | License posture |
|---|---|---|---|---|
| 1 | FRED | api.stlouisfed.org/fred | `cbsrm.data.fred` (shipped) | Public domain (derived analytics unrestricted) |
| 2 | NY Fed Markets API | markets.newyorkfed.org/api | `cbsrm.data.nyfed` (v0.2) | US Govt work, open |
| 3 | OFR Short-term Funding Monitor | data.financialresearch.gov/v1 | `cbsrm.data.ofr_stfm` (v0.2) | US Govt work, open |
| 4 | ECB Data Portal | data-api.ecb.europa.eu | `cbsrm.data.ecb_sdmx` (v0.3) | CC-BY-equivalent |
| 5 | BIS Stats API | stats.bis.org/api/v1 | `cbsrm.data.bis_sdmx` (v0.3) | Derived analytics permitted; raw redistribution restricted |
| 6 | CFTC Public Reporting | publicreporting.cftc.gov | `cbsrm.data.cftc` (v0.4) | US Govt work, open |
| 7 | NY Fed CMDI | newyorkfed.org/research/policy/cmdi | `cbsrm.data.nyfed_cmdi` (v0.4) | Citation, no commercial restriction |

### 4.2 License posture for the paid tier

The OSS distribution is Apache-2.0 throughout. The planned paid tier (v0.6+) will provide value-add layers (real-time feeds with sub-daily refresh, custom institution lists for SRISK, audit-chain exports for regulator compliance, replay of historical vintages) without re-distributing the underlying public data verbatim. ECB and BIS data appear in the framework as *derived analytics* — stress scores, correlations, attributions — never as raw mirroring; this is the conservative licensing interpretation and is documented in the per-adapter `source_info()` accessor.

---

## 5. Architecture

CBSRM is organized in six layers (one of which sits under all the others):

```
L1  Public data ingestion
L2  Indicators (methodology IP)
L3  Network / contagion engine
L4  Cross-jurisdiction integrator
L5  API / dashboard
L0  Audit chain  (under everything)
```

### 5.1 The audit chain

The audit primitive is `cbsrm.audit.chain.AuditChain`, a sha256-linked append-only log over an SQLite-backed table `cbsrm_audit_log`. Each row carries:

- `id`, `ts` — monotonic identifier and UTC timestamp
- `kind` — one of REQUESTED, INPUT_FETCHED, INPUT_MISSING, COMPUTED, SERVED, METHOD_UPGRADED, REPRODUCED, FAILED
- `subject` — the indicator identifier ('CISS-US', 'SRISK', etc.)
- `payload_json` — structured payload
- `hash` — sha256( prev_hash ‖ ts ‖ kind ‖ subject ‖ payload_json )
- `prev_hash` — the previous row's hash

The canonical happy-path lifecycle for an indicator computation is

> REQUESTED → INPUT_FETCHED → COMPUTED → SERVED

with REJECTED/FAILED/INPUT_MISSING as off-path terminal states. `AuditChain.verify(start_id=1)` re-hashes the chain from any starting row and returns a list of row identifiers where the stored hash does not match the recomputed hash or the stored `prev_hash` does not link to the actual previous row.

This primitive is ported from the same author's Derivatives Risk Framework (DRF), where it underlies the multi-broker order audit (5-state lifecycle: SUBMITTED → ROUTED → ACKED → FILLED → SETTLED, plus REJECTED and CANCELED). The DRF production implementation has 19 dedicated tests and is wired into broker.place_order(), broker.close_position(), and broker.sync_on_startup() call sites. CBSRM ports the algorithm; the test suite for CBSRM's audit chain (13 tests) exercises the same tamper-detection properties on the simpler systemic-risk lifecycle.

### 5.2 Why the audit primitive matters here

In a private trading context the audit chain is operational hygiene: it lets the operator prove, after the fact, that an order was placed in a specific state with specific parameters. In a public stress-monitor context the same primitive serves a *supervisory* function: downstream users (hedge-fund risk teams citing CBSRM stress readings in regulatory disclosures, supervisory technology vendors integrating CBSRM into a Pyxtrial-style pipeline, central-bank counterparts cross-referencing CBSRM readings against their own surveillance outputs) can verify the chain locally, in O(n), without trusting the CBSRM service. This is the same property — *machine-readable provenance with cryptographic verifiability* — that motivates the BIS Innovation Hub's interest in programmable supervisory infrastructure (Project Pyxtrial, Project Atlas, Project Pine).

### 5.3 API layer

A FastAPI service (`cbsrm.api.routes.build_app`) exposes:

- `GET /indicators` — registry of available indicators
- `GET /indicators/{id}/latest` — latest reading with audit row id
- `GET /audit/{subject}` — full audit chain for one subject
- `POST /audit/verify` — re-hash and return chain integrity status

The v0.6+ paid tier will add authenticated endpoints for custom institution lists (SRISK universes beyond V-Lab's ~30 firms), backtest endpoints (replay historical vintages), and signed audit-chain exports.

---

## 6. The programmable risk-gate extension

### 6.1 Bridge to Project Pine

Project Pine demonstrated that monetary-policy operations (reserve-requirement adjustments, fine-tuning operations, standing-facility access) can be expressed as smart contracts referencing on-chain or off-chain state. The same architectural pattern generalizes to *supervisory* operations: machine-readable rules that reference CBSRM stress indicators as input variables and trigger supervisory actions (heightened reporting, capital surcharges, mandatory liquidity buffers) when the indicators cross policy thresholds.

The technical precondition for such a pipeline is *cryptographically verifiable provenance of the indicator value*. The CBSRM audit chain provides exactly this primitive. A supervisory smart contract can:

1. Reference a CBSRM indicator value at a specific row id.
2. Independently fetch the audit row from the CBSRM service.
3. Verify the chain from any earlier audit row up through the referenced row.
4. Apply its policy logic only if verification succeeds.

This composes cleanly with Pine-style programmable monetary-policy variables and Pyxtrial-style balance-sheet surveillance: the same audit primitive sits under all three.

### 6.2 Bridge to the Derivatives Risk Framework

The author's companion repository, the Derivatives Risk Framework, ships the production audit chain in the context of a multi-asset trading engine: every order placed, every position closed, every reconciliation event is recorded in the chain. CBSRM lifts the primitive into the public domain by demonstrating its applicability to a *non-private* use case (public stress-indicator computation) with the same correctness guarantees.

The implication is that the same architecture spans both private capital deployment (DRF) and public supervisory infrastructure (CBSRM). This is precisely the pattern that BIS Project Pyxtrial seeks for stablecoin reserve surveillance: the supervisory pipeline and the regulated entity's internal pipeline can interoperate over the same primitives without trusting each other.

---

## 7. Replication diagnostics

### 7.1 Synthetic-data validation (v0.1)

The CBSRM v0.1 test suite exercises CISSUS against a synthetic two-regime dataset: 200 weeks of low-stress uncorrelated noise followed by 200 weeks of crisis-regime data where a common factor loads onto all 15 raw inputs. The tests assert:

- Output values are bounded in [0, 1] (test_cissus_values_bounded_in_unit_interval).
- The crisis half exhibits CISS readings materially elevated above the calm half — at least 2× the calm mean (test_cissus_crisis_window_elevated_vs_calm).
- The composite respects systemic amplification — during the crisis window the composite mean is not drastically smaller than the average per-subindex mean, reflecting the contribution of rising correlations to the quadratic form (test_cissus_systemic_amplification).
- The per-subindex breakdown is exposed and bounded (test_cissus_subindex_breakdown_present).

All 48 tests in the v0.1 suite (13 for the audit chain, 13 for FRED, 22 for indicators) pass.

### 7.2 Live-data validation (planned v0.2)

The v0.2 release will ship a `notebooks/04_replicate_ecb_ciss.ipynb` that:

1. Pulls the official ECB CISS series via the ECB SDMX API.
2. Reconstructs the same 15 ECB inputs from public sources.
3. Computes CISSUS with the ECB input mapping (rather than US substitution).
4. Reports Pearson, Spearman, z-score MAE, and visual overlay over the 2007-2026 sample.

The acceptance threshold (proposed) is Pearson *r* ≥ 0.90 over the full sample and ≥ 0.85 within each declared crisis window. Replication below these thresholds is treated as a methodology bug and held over for v0.3.

Parallel notebooks (planned v0.3) will replicate STLFSI4 from its 18 inputs and the OFR FSI from the published 33-indicator list, applying the same threshold logic.

---

## 8. Roadmap

| Release | Indicator additions | Data additions | Other |
|---|---|---|---|
| v0.1 (current) | STLFSI4 wrapper, CISSUS (methodology + synthetic validation) | FRED | Audit chain, FastAPI skeleton, CLI |
| v0.2 (Q3 2026) | Canonical CISSUS mapping, ECB CISS replication, OFR FSI replication | NY Fed, OFR | Notebooks 01-04: 2020Q1 / 2008Q4 / 2023Q1 replays |
| v0.3 (Q4 2026) | SRISK (Brownlees-Engle 2017), LRMES, MES; ECB CISS adapter | ECB, BIS | Integrate `bashtage/arch` for GARCH-DCC |
| v0.4 (Q1 2027) | ΔCoVaR (Adrian-Brunnermeier 2016); Acemoglu phase classifier | CFTC, NY Fed CMDI | Integrate `marcobardoscia/neva` for network contagion |
| v0.5 (Q2 2027) | Diebold-Yilmaz spillover (reimplementation; existing R-only); cross-jurisdiction integrator | World Bank GFDD | Streamlit dashboard |
| v0.6+ (H2 2027) | Sovereign EWS (KLR + Manasse-Roubini + ML benchmark) | Atlantic Council CBDC tracker | Paid tier infrastructure |

The v0.5 cross-jurisdiction integrator is the unique contribution targeted: a daily-cadence stress reading per jurisdiction with cross-jurisdiction co-movement attribution. To the author's knowledge no open-source artifact of this form exists.

### 8.1 Companion publication agenda

| Date | Submission | Target |
|---|---|---|
| Q3 2026 | SSRN methodology paper (this document, expanded) | FEN: Risk Management & Analysis of Risk |
| Aug 27-29 2026 | Jackson Hole 2026 poster | Topic: "Financial Innovation: Implications for Payments and Policy" |
| Q4 2026 | BIS WP submission (informal) | Cite WP 1250, 1291; address Aldasoro/Schrimpf/Auer |
| Oct/Nov 2026 | Joint BIS/BoE/ECB/IMF Spillover Conference 2027 | Scientific committee includes Hyun Song Shin |
| 2027 | Journal of Financial Stability submission | After ECB CISS replication is published |

---

## 9. Limitations and threat model

### 9.1 Methodology limitations

- The CISS construction's portfolio-theoretic aggregation assumes that subindex returns are coherent at the EWMA-correlation horizon. For very fast crises (intra-day flash events) the weekly-cadence EWMA may understate stress; this is a known property of the methodology and is not a CBSRM-specific defect.
- The 15-input mapping for CISS-US in §3.2 is the *intended* canonical mapping; v0.1 accepts any 15-column input matrix, deferring the canonical pin to v0.2 when the necessary FRED-derived spreads (notably the SOFR-IORB spread and the trade-weighted USD volatility) are wired in.
- The audit chain does not protect against compromise of the CBSRM service itself (an attacker with write access to the chain can produce a valid-looking chain). Defense in depth — air-gapped chain backups, independent chain mirrors — is left to downstream operators.

### 9.2 Data limitations

- BIS data licensing restricts raw redistribution; CBSRM treats BIS series as inputs to derived analytics only and exposes the underlying mnemonic citation rather than mirroring the raw values.
- ECB data are CC-BY-equivalent but require attribution; the API surfaces source metadata via `.source_info()` on each adapter.
- US government data (FRED, NY Fed, OFR, CFTC) is in the public domain and unrestricted for derived analytics.

### 9.3 Threat model for the audit chain

The chain is tamper-evident (every modification is detectable in O(n) by re-hashing) but not tamper-resistant (it does not prevent modification). For applications requiring tamper resistance — e.g. inputs to regulatory enforcement actions — downstream operators should mirror the chain to an append-only ledger (blockchain, write-once storage, or off-site read replica) and compare hashes at the boundary.

---

## 10. Conclusion and BIS Innovation Hub alignment

The BIS Innovation Hub's mandate, as articulated across Project Pine, Project Pyxtrial, Project Atlas, and BIS Working Papers 1250 and 1291, includes (i) the construction of supervisory-grade tooling for financial-stability monitoring, (ii) the application of interpretable machine learning to systemic risk, and (iii) the development of cross-border interoperability primitives. CBSRM is positioned in the intersection of these three: it ships methodology-transparent, audit-chain-backed, interpretable stress indicators with explicit cross-jurisdiction roadmap and a primitive (the audit chain) directly applicable to the supervisory-technology dimension.

The v0.1 release is the foundation: the audit chain primitive, the FRED data adapter, and the first methodology re-implementation. Subsequent releases will close the cross-jurisdiction, network-contagion, and machine-learning gaps. The companion Derivatives Risk Framework provides the production-validated audit primitive; CBSRM lifts that primitive into the public domain and applies it to the supervisory side of the same coin.

The author welcomes correspondence from researchers at BIS Innovation Hub centres (Swiss Centre, Eurosystem, London, Nordic, Hong Kong, Singapore, Toronto), at central banks engaged with the Innovation Hub Secondment Programme, and at policy institutions whose mandates intersect the CBSRM methodology footprint.

---

## References

Acemoglu, D., Ozdaglar, A. & Tahbaz-Salehi, A. (2015). "Systemic Risk and Stability in Financial Networks." *American Economic Review* 105(2): 564–608.

Acharya, V., Pedersen, L., Philippon, T. & Richardson, M. (2017). "Measuring Systemic Risk." *Review of Financial Studies* 30(1): 2–47.

Adrian, T. & Brunnermeier, M. (2016). "CoVaR." *American Economic Review* 106(7): 1705–1741.

Aldasoro, I., Hördahl, P., Schrimpf, A. & Zhu, F. (2025). "Predicting financial market stress with machine learning." *BIS Working Paper* 1250.

Bardoscia, M., Battiston, S., Caccioli, F. & Caldarelli, G. (2015). "DebtRank: A Microscopic Foundation for Shock Propagation." *PLoS ONE* 10(6): e0130406.

Battiston, S., Puliga, M., Kaushik, R., Tasca, P. & Caldarelli, G. (2012). "DebtRank: Too Central to Fail? Financial Networks, the FED and Systemic Risk." *Scientific Reports* 2: 541.

Brave, S. A. & Butters, R. A. (2011). "Monitoring Financial Stability: A Financial Conditions Index Approach." *Federal Reserve Bank of Chicago Economic Perspectives*.

Brownlees, C. & Engle, R. (2017). "SRISK: A Conditional Capital Shortfall Measure of Systemic Risk." *Review of Financial Studies* 30(1): 48–79.

Diebold, F. X. & Yilmaz, K. (2012). "Better to give than to receive: Predictive directional measurement of volatility spillovers." *International Journal of Forecasting* 28(1): 57–66.

Eisenberg, L. & Noe, T. (2001). "Systemic Risk in Financial Systems." *Management Science* 47(2): 236–249.

Glasserman, P. & Young, H. P. (2015). "How Likely Is Contagion in Financial Networks?" *Journal of Banking & Finance* 50: 383–399.

Hakkio, C. S. & Keeton, W. R. (2009). "Financial Stress: What Is It, How Can It Be Measured, and Why Does It Matter?" *Federal Reserve Bank of Kansas City Economic Review*.

Holló, D., Kremer, M. & Lo Duca, M. (2012). "CISS — A Composite Indicator of Systemic Stress in the Financial System." *ECB Working Paper* 1426.

Monin, P. (2019). "The OFR Financial Stress Index." *Risks* 7(1): 25.

BIS (2025). "Harnessing AI for monitoring financial markets: early warning signals from interpretable ML." *BIS Working Paper* 1291.

BIS Innovation Hub (2025). "Project Pine: A pioneering technical exploration of how a smart contract toolkit could support central banks." Final report, May 2025.

BIS Annual Economic Report (2025). "The next-generation monetary and financial system." Chapter III.

---

## 8 — Live validation against real data (v0.2 smoke test, 2026-05-20)

Sections 1–7 describe the methodology. This section reports the first end-to-end live execution of the v0.2 pipeline against real public data sources, as a pre-submission sanity check.

### 8.1 — Headline numerical readings

The current systemic-stress snapshot across three jurisdictions, captured on the indicators' most recent published observation dates:

| Indicator       | Value      | Observation date | Source          | Interpretation                  |
|-----------------|------------|------------------|-----------------|---------------------------------|
| ECB-CISS-US     | 0.00817    | 2026-05-18       | ECB Data Portal | Very low (>0.4 ≈ crisis zone)   |
| ECB-CISS-EA     | 0.00261    | 2026-05-18       | ECB Data Portal | Very low                        |
| ECB-CISS-UK     | 0.05322    | 2026-05-18       | ECB Data Portal | Low–moderate                    |
| STLFSI4 (US)    | -0.7404    | 2026-05-15       | St. Louis Fed   | Below-average stress (z-scored) |

All four readings reproducible via `python -m cbsrm.cli latest <id>` after `pip install -e .` and `export FRED_API_KEY=<key>`.

### 8.2 — Cross-jurisdiction observations

Three observations on this snapshot:

1. **UK runs roughly 20× the US/EA reading.** Cross-jurisdiction divergence of this magnitude is itself a financial-stability signal — global conditions are not homogeneous despite tight integration. Likely drivers as of May 2026 include gilt-market dynamics and Bank of England policy posture, though decomposing the contribution is out of scope for this section.
2. **EA reads below US.** Both are deep in the "very low" zone, but euro-area is the lowest of the three.
3. **Independent US methodology cross-checks.** STLFSI4 (St. Louis Fed, z-scored composite of US money-market, interest-rate, and credit indicators) and ECB-CISS-US (Holló-Kremer-Lo Duca aggregation over a different basket published by the ECB) use disjoint input series and unrelated aggregation rules. Both report below-average / near-zero stress for the US on the observation date. This is the first piece of empirical cross-source corroboration in the CBSRM pipeline against live data.

### 8.3 — Defects surfaced by live execution

Two methodology-relevant defects appeared only against live sources. The v0.2 test suite passes 168/168 against mocked HTTP fixtures, but mocking cannot catch input-format drift or upstream-server policy changes.

1. **CISS-US-Canonical frequency mismatch.** The canonical 15-input recipe in `cbsrm.builders.ciss_us_builder` requests SLOOS-style credit-tightening series (FRED IDs `DRTSCILM`, `DRTSCLCC`) at weekly cadence. Those series are published quarterly. FRED returns HTTP 400 with `Bad Request`. Fix: route the SLOOS subset through quarterly fetch then forward-fill to weekly. Targeted for v0.3.
2. **OFR-FSI 403 Forbidden.** The Office of Financial Research's CSV endpoint at `financialresearch.gov/financial-stress-index/data/files/ofr-fsi.csv` blocks the default `httpx` User-Agent (server-side WAF rule, observed 2026-05-20). Fix: set a project-identifying UA string (e.g. `cbsrm/0.2 (financial-stability research; +https://github.com/pravo123/cbsrm)`) in `cbsrm.data.ofr.OFRClient`. Targeted for v0.3.

Neither defect invalidates the four readings above. The CISS-US canonical-vs-OFR-FSI cross-source replication test promised in §7.2 will run in the v0.3 release after these two adapters are fixed.

### 8.4 — Methodological note on transparency

Surfacing live-validation failures is part of the CBSRM design intent, not a coincidence. The audit chain (§4) records `INPUT_MISSING` and `FAILED` lifecycle events for every fetch that errors, so the same audit query that confirms `COMPUTED` lineage also surfaces every silent fallback or substitution. The dossier rendered by `cbsrm.diagnostics.crisis_replay` distinguishes between "indicator unavailable" and "indicator reads low" — a distinction supervisory and central-bank operators should expect from any production financial-stability monitor.

The v0.3 release will (a) close the two defects above, (b) tighten the replication-threshold floor in §7.2 from 0.80 / 0.75 to 0.85 / 0.80 after three months of recorded live observations, and (c) add SRISK (Brownlees-Engle 2017) on top of `bashtage/arch` as the first risk-pricing (rather than stress-indexing) module.

---

## 9 — Macro Engine (v0.3)

§§1–8 focus on systemic-stress *indices* — composite indicators that read the
current level of market stress. The v0.3 Macro Engine layer sits one level
above: it ingests slower-moving macroeconomic condition variables (yield-curve
slope, payroll momentum, policy-rate trajectory, broad-dollar regime) and
emits a 4-state aggregate regime label intended to *gate* and *weight* the
stress indices when downstream consumers (e.g. risk-conditional position
sizers, supervisory dashboards) need a single coarse-grained answer to the
question "is the macro environment risk-on, risk-off, or in transition?"

### 9.1 — Module inventory

| Module                       | FRED inputs    | Output                                            |
|------------------------------|----------------|---------------------------------------------------|
| `YieldCurveIndicator`        | `T10Y3M`       | Estrella-Mishkin (NY Fed) recession probability   |
| `NFPMomentumIndicator`       | `PAYEMS`       | MoM log-growth rolling z-score (60-month window)  |
| `FFRChangeIndicator`         | `DFF`          | Composite of 3M/6M/12M EFFR changes (bp)          |
| `DXYRegimeIndicator`         | `DTWEXBGS`     | 252-day rolling z-score of broad USD index        |
| `MacroCompositeIndicator`    | all four       | 4-state label + composite score                   |

All five modules implement the `IIndicator` protocol (§4) and therefore plug
into the audit chain, replication harness, FastAPI service, and CLI driver
without bespoke wiring.

### 9.2 — Methodology choices

**Yield curve (Estrella & Mishkin, NBER 1996; NY Fed refresh).** Probit on
the constant-maturity 10Y-minus-3M Treasury spread:

```
P(recession_{t+12} = 1 | spread_t) = Phi( beta_0 + beta_1 * spread_t )
beta_0 = -0.5450
beta_1 = -0.5898
```

CBSRM publishes the daily probability series plus a *persistent inversion*
flag (run-length ≥ 60 trading days). Persistent inversion has preceded 8 of
the last 8 NBER-dated US recessions.

**NFP momentum, not surprise.** Without a real-time consensus-forecast feed
(Bloomberg / Refinitiv / Trading Economics), v0.3 publishes the rolling
z-score of monthly log-growth in `PAYEMS` against the trailing 60-month
window. Promotion to a true *actual − consensus* surprise indicator is
deferred to v0.4 contingent on a free-tier consensus adapter.

**FFR change composite.** Mean of 3M, 6M, and 12M changes in `DFF`, in basis
points. Regime thresholds (`±150 bp` aggressive, `±40 bp` normal) are
calibrated against the 1994, 2004-06, 2015-19, and 2022-23 hiking cycles.

**DXY regime.** Rolling 252-day z-score of FRED `DTWEXBGS` (broad trade-
weighted dollar, Fed Board H.10) — not the narrower ICE DXY. Strong-bull /
strong-bear thresholds at |z| ≥ 1.5 follow the Bruno-Shin (2015) and Avdjiev-
du-Koepke-Shin (2018) findings that broad-dollar regime drives EM and
cross-border financial conditions.

**Composite (4-state).** Each sub-indicator emits a score in [-1, +1] (risk-
off negative). The mean is bucketed::

    composite >= +0.4    → RISK_ON
    -0.1 < composite < +0.4 → TRANSITION_UP
    -0.4 < composite <= -0.1 → TRANSITION_DOWN
    composite <= -0.4    → RISK_OFF

Three *hard-override* conditions force `RISK_OFF` regardless of composite
score: (a) persistent yield-curve inversion combined with recession
probability > 30%; (b) FFR-change regime = AGGRESSIVE_TIGHTENING;
(c) NFP momentum classification = SEVERE_DECELERATION. These three are
documented catastrophic-condition triggers (Estrella-Mishkin 1996, Sahm
2019, Bauer-Swanson 2023).

### 9.3 — Live-data validation (2026-05-20)

Single-day end-to-end read against FRED:

| Indicator               | Value          | Regime / interp                |
|-------------------------|----------------|--------------------------------|
| Yield curve T10Y3M      | +0.92 pp       | Not inverted                   |
| Recession prob (12mo)   | 0.138          | Low (Estrella-Mishkin)         |
| FFR composite change    | -25 bp         | PAUSE (current EFFR 3.62%)     |
| DXY z-score (252d)      | -0.63          | DOLLAR_BEAR                    |
| NFP momentum z          | -0.51          | AT_TREND                       |

Macro composite would integrate to `TRANSITION_UP` band on this snapshot
(positive curve + pause + weak dollar weighed against slightly-soft
payrolls). This is consistent with §8.1 — the systemic-stress indices read
near-zero, the macro layer reads slightly risk-on. No override triggers.

### 9.4 — Use by downstream consumers

The macro engine is intentionally *separable* from the stress engine. Two
deployment patterns are supported in v0.3:

1. **Independent dashboard.** Render the four sub-indicators plus the
   composite label on the supervisory dashboard alongside the stress
   indices. Useful for second-line risk teams who want both a near-term
   stress reading and a slower-moving regime label.

2. **Stress-index gate / weight.** In a portfolio-risk or stress-test
   pipeline, the composite regime can multiplicatively scale the position
   size or the stress-tolerance budget. A reference implementation lives in
   the private companion repository (`VOLANX/signals/macro_signal_source.py`,
   not part of CBSRM), but the public composite is sufficient on its own.

The v0.4 release will (a) add CPI-surprise, oil-macro, and a credit-spread
regime module; (b) add a true Trading-Economics-backed surprise series for
NFP; (c) ship one persistence-and-recompute notebook reproducing the
classifier on the 2008 and 2020 recessions.

### 9.5 — Japan and the safe-haven yen

In v0.3 the macro engine adds a fifth sub-indicator —
``cbsrm.macro.jpy_regime.JPYRegimeIndicator`` — covering the USD/JPY pair
via FRED ``DEXJPUS``. Japan's inclusion is not cosmetic: Japan is the third-
largest economy by GDP, the world's largest net external creditor, and the
funding leg of the global yen carry trade. The yen's role as a safe-haven
currency means that USD/JPY decompresses (yen strengthens) during global
risk-off episodes, complementing the broad-USD signal from
``DXYRegimeIndicator``. Five-state classification (``USD_STRONG_JPY_WEAK``,
``USD_MILD_BULL_JPY``, ``NEUTRAL``, ``USD_MILD_BEAR_JPY``, ``USD_WEAK_JPY_STRONG``)
follows the same |z| ≥ 1.5 threshold convention as DXY but with labels
that name both sides of the pair, since "USD bear" is operationally distinct
from "JPY safe-haven flight" for portfolio-risk consumers.

The composite regime (``MacroCompositeIndicator``) does not yet aggregate
JPY into its 4-state classifier — that is deferred to v0.4 once a longer
window of overlapping observations is available — but the JPY indicator is
fully usable standalone via the CLI (``cbsrm jpy-regime``) and the FastAPI
service.

### 9.6 — Multi-language interpretation labels

Every v0.3 macro indicator now ships its ``interpretation`` field in five
languages: English (``en``), Japanese (``ja``), Spanish (``es``), French
(``fr``), and German (``de``). The localised labels live in ``cbsrm.i18n``
and are attached to the indicator metadata under ``interpretation_i18n``
as a per-locale dict. Dashboards, supervisory reports, and downstream
consumers can pick the locale at render time without re-running the
indicator. The translations are reviewed (not machine-translated) and a
test invariant in the suite ensures every label key has a translation for
every supported locale.

Multi-language support is the first step toward making CBSRM usable by
non-anglophone central-bank and supervisory teams. Additional locales
(zh, ko, pt) are on the v0.5 roadmap.

---

## 10 — Risk-pricing layer: SRISK (v0.4)

§9 added a macro engine — slower-moving condition variables. §10 adds the
risk-pricing layer: methodology that *prices* tail outcomes rather than
*measures* current stress.

### 10.1 — Why SRISK

SRISK (Brownlees & Engle 2017) is the canonical conditional-capital-shortfall
measure of systemic risk. Where CISS / OFR-FSI / STLFSI4 report "how stressed
is the system *right now*", SRISK answers "*if a crisis hit tomorrow*, how
much equity capital would firm *i* need to inject to remain solvent?". The
two are complementary: stress indices observe contemporaneous market
behaviour, SRISK pre-prices the equity-capital injection that would be
required if the contemporaneous behaviour got an order of magnitude worse.

NYU Stern's V-Lab has published SRISK weekly for every globally-systemic
financial institution since 2010, making it the most-cited single quantity
in macroprudential supervision (Brownlees-Engle has > 2,000 citations as
of 2026, and Federal Reserve Board / ECB / Bank of England working papers
routinely cite V-Lab SRISK in financial-stability reports).

CBSRM v0.4 ships a clean Python reimplementation of the methodology —
production-grade, audit-traceable, and reproducible against V-Lab numbers
for any firm where the operator can provide market cap and book debt.

### 10.2 — The SRISK identity

For firm *i*, SRISK is the expected capital shortfall conditional on a
systemic event:

```
    SRISK_i = k * D_i - (1 - k) * W_i * (1 - LRMES_i)
```

where ``k`` is the prudential capital ratio (default 8% for US bank holding
companies, 4.5% for insurers); ``D_i`` is book debt (book liabilities);
``W_i`` is current market cap; and ``LRMES_i`` (Long-Run Marginal Expected
Shortfall) is the expected fraction lost in firm *i*'s equity over the
crisis horizon (default 6 months / 126 trading days) conditional on the
market hitting the crisis threshold (default -40%).

### 10.3 — LRMES via GJR-GARCH-DCC Monte Carlo

Computing LRMES requires:

1. A model for firm-and-market joint return dynamics. CBSRM uses bivariate
   GJR-GARCH(1,1) marginals (asymmetric volatility) + scalar DCC(1,1)
   correlation dynamics (Engle 2002) — exactly the Brownlees-Engle
   specification.
2. Monte Carlo simulation of joint return paths over the crisis horizon.
3. Conditioning on the subset of paths where the market cumulative
   return fell below the crisis threshold, and taking the expected firm
   equity loss within that subset.

The CBSRM implementation lives in
``cbsrm.risk.garch_dcc_sim.GARCHDCCSimulator`` (pure numpy, no
``arch``/SciPy/Cython dependency at simulate-time). Parameters are caller-
supplied; v0.5 will add an ``arch``-backed fitter so the entire pipeline
can run from raw return histories.

The unit-test suite validates four required properties:

1. Stationarity guard rejects non-stationary parameter sets.
2. LRMES is monotone in conditional correlation.
3. LRMES is monotone in volatility.
4. SRISK is monotone in book debt and LRMES.

### 10.4 — Public adoption pathway

V-Lab's pre-existing SRISK series is the canonical benchmark. CBSRM does
*not* publish a competing official SRISK number; rather, it gives any
researcher, regulator, or trading firm the ability to:

* Reproduce V-Lab's SRISK for any firm with public market-cap + book-debt
  data, validating their internal models.
* Compute SRISK on non-US firms / sectors that V-Lab does not cover
  (e.g. EM banks, private credit funds via NAV proxy, large insurance
  groups with parametric debt).
* Stress-test SRISK under counterfactual crisis scenarios (e.g. -25%
  shock, 90-day horizon, doubled correlation) for resilience analysis.

### 10.5 — Roadmap to MES, ΔCoVaR, network-contagion

MES (Marginal Expected Shortfall, the daily-horizon cousin of LRMES) is a
trivial adaptation of the same Monte Carlo, conditioning on a single-day
market shock rather than a horizon-cumulative one — planned for v0.5.

ΔCoVaR (Adrian-Brunnermeier 2016) uses quantile regression rather than
GARCH-DCC and ships as a parallel module. Combined with SRISK, it gives
CBSRM the two most-cited systemic-risk metrics in supervisory literature.

Network-contagion (DebtRank, Battiston et al. 2012) addresses an
orthogonal dimension: which firms are *vulnerable* via balance-sheet
linkages rather than via co-movement. The ``marcobardoscia/neva`` reference
implementation is the target integration point — planned for v0.5.

---

## Appendix A — CBSRM v0.1 module inventory

```
cbsrm/
├── cbsrm/
│   ├── __init__.py
│   ├── cli.py
│   ├── audit/
│   │   ├── __init__.py
│   │   └── chain.py            (AuditChain, AuditEvent, AuditEventKind)
│   ├── data/
│   │   ├── __init__.py
│   │   └── fred.py             (FREDClient, FREDSeriesMeta)
│   ├── indicators/
│   │   ├── __init__.py
│   │   ├── base.py             (IIndicator protocol, IndicatorResult)
│   │   ├── stlfsi.py           (STLFSIWrap baseline)
│   │   └── ciss_us.py          (CISSUS methodology, CISSConfig)
│   └── api/
│       ├── __init__.py
│       └── routes.py           (FastAPI build_app)
├── tests/                       (48 tests, all passing)
├── whitepaper/
│   └── cbsrm_methodology_v1.md  (this document)
├── LICENSE                      (Apache-2.0)
├── README.md
└── pyproject.toml
```

## Appendix B — Reproducibility

To reproduce every numerical claim in this paper:

```bash
git clone https://github.com/pravo123/cbsrm
cd cbsrm
pip install -e ".[all]"
pytest tests/ -v
```

Expected output: `48 passed`. The synthetic-data crisis-window assertions in §7.1 are deterministic given the fixed seed in `tests/test_indicators.py::_make_synthetic_inputs`.

## Appendix C — Correspondence

The author can be reached via the CBSRM GitHub repository. Inbound from researchers at BIS, ECB, OFR, NY Fed, Fed Board, IMF, FSB, ESRB, and equivalent national institutions is particularly welcomed.

---

*End of v0.1 working paper.*
