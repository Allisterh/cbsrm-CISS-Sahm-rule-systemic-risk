# Launch posts — CBSRM v0.8.0

> **Preview-first.** Nothing in this file posts on its own. Every block below is a draft for operator review. Substitute every `<…>` placeholder before posting.

Anchors needed before posting (collect these first):

- `<RELEASE_URL>` — GitHub Release URL for `v0.8.0` (created in `LAUNCH_COMMAND_CENTER.md` §3)
- `<STREAMLIT_VIEWER_URL>` — live URL of `dashboard/crisis_dossier_viewer.py` (see §4) **or** omit those lines if not deployed
- `<SCREENSHOT_PATH_OR_URL>` — the v0.8-viewer screenshot from §5 (drag-and-drop into LinkedIn or upload to HN as a comment with the image-host link)
- `<SSRN_ABSTRACT_URL>` — only if the paper is live; otherwise omit

---

## 1. LinkedIn — professional version (recommended for first launch post)

Audience: quant researchers, risk officers, supervisory teams, central-bank Innovation Hub folks, fintech CTOs. Tone: peer-to-peer, methodology-first, no hype.

> CBSRM v0.8.0 is out.
>
> CBSRM (Cross-Border Systemic Risk Monitor) is an open-source, 7-layer Python platform that reproduces the canonical systemic-risk and financial-stability methodology stack — SRISK (Brownlees-Engle 2017), ΔCoVaR (Adrian-Brunnermeier 2016), MES (Acharya et al. 2017), Holló-Kremer-Lo Duca CISS for US / EA / UK / Japan, the Sahm Rule, Diebold-Yilmaz spillover index — under one Protocol and one cryptographic audit chain.
>
> v0.8 adds:
> • a discrete-event macro surprise scorer (CPI / NFP / FOMC / ISM / …)
> • windowed crisis replay
> • a pure-numpy DebtRank engine (Battiston et al. 2012)
> • an Acemoglu-style 8-phase macro classifier
> • deterministic fixture-backed crisis-window dossiers for 2008Q4, 2020Q1, 2023Q1
> • a Markdown + JSON report renderer
>
> The dossier surface ships three bit-for-bit-identical front-ends sharing one composition:
> • CLI: `cbsrm crisis-dossier 2008Q4 --format markdown`
> • HTTP: `GET /reports/crisis-dossiers/2020Q1/markdown`
> • Streamlit: `streamlit run dashboard/crisis_dossier_viewer.py`
>
> 555 tests passing. No new runtime dependencies. Pure numpy at compute time on the new code path. Offline-deterministic — explicit no-network-IO tests for the new modules.
>
> Repo (Apache 2.0): https://github.com/pravo123/cbsrm
> v0.8.0 release notes: <RELEASE_URL>
> Live demo: <STREAMLIT_VIEWER_URL>
>
> Research analytics, not financial advice.
>
> Built solo. Open to feedback on the methodology choices and the audit-chain design.
>
> #SystemicRisk #FinancialStability #OpenSource #QuantitativeFinance #Python

---

## 2. LinkedIn — visionary WaverVanir version (alternate)

Audience: same as #1 plus founders / investors / policy folks who care about narrative. Tone: longer arc, still grounded, still "research only."

> Two years ago I started working on the question: *what does it take to build the canonical systemic-risk toolkit in modern, typed, auditable Python — at the level a central-bank Innovation Hub or a supervisory team could actually adopt?*
>
> Today I shipped v0.8.0 of CBSRM (Cross-Border Systemic Risk Monitor), the open-source half of that work, under the WaverVanir International banner.
>
> What's in the box:
> • The canonical systemic-risk triad: SRISK, ΔCoVaR, MES — under one Protocol, one audit chain
> • Five-jurisdiction stress and macro coverage (US / EA / UK / Japan / broad USD) with interpretation labels in five languages
> • A pure-numpy DebtRank engine for systemic-network propagation
> • Discrete-event macro surprise scoring + windowed replay
> • An Acemoglu-style 8-phase deterministic macro classifier
> • Three deterministic fixture-backed crisis dossiers (2008Q4 Lehman, 2020Q1 COVID, 2023Q1 SVB)
> • A Markdown + JSON report renderer
> • Three bit-for-bit-identical front-ends — CLI, read-only FastAPI, offline Streamlit
> • 555 tests passing
>
> Design choices that aren't obvious from the README:
> 1. *Methodology, not infrastructure, is the differentiator.* Every fetch / compute / served value writes to a sha256-linked audit chain. The query "how did this number come to be?" has a one-SQL-statement answer.
> 2. *Pure-Python posture is on purpose.* Supervisory environments are dependency-hostile; ~600 lines of dependency-free code is easier to audit than wrapping a black-box library.
> 3. *Public ships the methodology; the engine ships separately.* CBSRM is Apache 2.0. The private companion (VolanX) applies the same data and audit primitives to a multi-broker derivatives execution platform — that work is intentionally not in this repo.
>
> The thesis behind WaverVanir: financial-stability tooling should look like modern open-source software, and the credibility surface for serious quant work is *runnable, reproducible methodology* — not slides.
>
> Repo: https://github.com/pravo123/cbsrm
> Release: <RELEASE_URL>
> Live demo: <STREAMLIT_VIEWER_URL>
>
> Research analytics, not financial advice.
>
> #FinancialStability #SystemicRisk #OpenSource #QuantFinance #CentralBanking #Python

---

## 3. Stocktwits — short post (with stoic emoji)

Audience: retail-quant adjacent crowd, market-structure curious. Tone: short, factual, no ticker spam, no recommendations. Stoic emoji per operator preference: 🜞 (alchemical "vinegar of philosophers") — or fall back to a column / scale glyph if the platform mangles it.

> 🜞 CBSRM v0.8.0 — open-source systemic risk + crisis dossier reports in pure Python.
>
> Six-stage research pipeline: macro surprise → replay → DebtRank → phase classifier → dossier → Markdown/JSON.
>
> CLI, read-only API, and Streamlit viewer share one composition (bit-for-bit). 555 tests. Apache 2.0.
>
> Research only. Not advice.
>
> Repo: https://github.com/pravo123/cbsrm
> Release: <RELEASE_URL>

Fallback glyph if 🜞 mis-renders: ⚖️ or ♟.

---

## 4. Show HN — title options

Existing recommended block lives in `SHOW_HN_POST.md`. For convenience, the current titles ranked from `docs/v08-launch-copy-refresh`:

1. **Recommended:** `Show HN: CBSRM – open-source SRISK / CoVaR / DebtRank in pure Python` (69 chars)
2. **Alternate (if live demo URL is ready):** `Show HN: CBSRM v0.8 – systemic risk + crisis dossier reports (Apache 2.0)` (74 chars)
3. **Architecture-first alternate:** `Show HN: A 7-layer cross-border systemic risk monitor (Apache 2.0)` (67 chars)

Full body + URL field + posting-window mechanics: `SHOW_HN_POST.md`.

---

## 5. First HN comment (full)

Lives in `SHOW_HN_POST.md` (refreshed on `docs/v08-launch-copy-refresh`). Summary: 4 numbered design-choice bullets ending with "one composition, three front-ends" and the public/private split. Paste it within 60 seconds of submission.

---

## 6. Five short reply templates (for HN / LinkedIn comments)

Use verbatim or as starting points. Each ≤ 100 words.

### R1 — "Why not just use [R package X]?"

> Two reasons. (a) Activation cost: a Python implementation removes the R-to-Python serialization layer that costs ~3 weeks to maintain in a real workflow. (b) Audit-chain coupling: every CBSRM computation persists a sha256-linked lifecycle row. That works inside a NumPy stack and would require non-trivial glue to reach from inside an R session. Happy to walk through the SRISK / MES code path side-by-side with the R reference if it's useful — the file is `cbsrm/risk/srisk.py`.

### R2 — "How does this compare to V-Lab / SRISK numbers?"

> V-Lab is the canonical reference for SRISK. CBSRM publishes its own numbers but isn't trying to displace V-Lab — the cross-source replication harness in v0.2 already validates against ECB CISS + OFR-FSI for stress indices, and the SRISK / MES implementations are validated against published analytical properties in the whitepaper §§10-12. Treat V-Lab as the benchmark; treat CBSRM as a code path you can audit and run on your own data.

### R3 — "Is this production-ready for a regulator / fund / shop?"

> CBSRM v0.8 is research analytics — deterministic, offline, fixture-backed for the new dossier surface. It is import-and-run safe and has 555 tests. What it does **not** ship out of the box: hosted multi-tenant API, auth, billing, persistence, PDF export, or live broker wiring. Those are explicitly on the v0.9 roadmap. So: "ready to evaluate, ready to integrate into a private pipeline, not ready as a turnkey SaaS." Happy to talk through the gap for your specific use case.

### R4 — "What does the audit chain actually protect against?"

> Three failure modes most academic implementations miss: (a) silent data revisions (FRED + ECB + OFR re-publish history; CBSRM ledger lets you trace which vintage produced each served value), (b) silent code drift across releases (the chain records the indicator class + version, so a hash change tells you the methodology moved), and (c) silent caller substitution (the audit row encodes the subject + payload, so you can replay any served number from the chain alone).

### R5 — "Can I contribute / extend it?"

> Yes. The Protocol design means a new indicator is one file + one registration line. `CONTRIBUTING.md` has the methodology-review checklist; issue templates are in `.github/`. If you have a candidate indicator or jurisdiction you'd like to see covered, drop an issue with the citation — I'd rather discuss methodology first and code second.

---

## 7. Three "what NOT to say" cautions

1. **Do not claim live trading, execution, or signal-generation.** CBSRM is research analytics. The trading work is in a private companion repository and is intentionally not in scope. Anyone wiring CBSRM outputs into a live system must add their own risk controls. If asked, point at this exact line: *"CBSRM is research analytics; the trading and execution work is in a private companion repository (VolanX) and is intentionally out of scope for the public release."*

2. **Do not claim PDF export, hosted multi-tenant API, accounts, billing, or any SaaS that does not exist.** The repo has a CLI, a single-process read-only FastAPI, and a standalone Streamlit page. Saying "hosted SaaS" implies infrastructure that this commit does not contain. If pressed, defer to the v0.9 roadmap (`PRODUCT_ROADMAP_v0.9.md`) and offer to talk privately about timing.

3. **Do not respond defensively to "isn't this just X?" or "this is just a wrapper around Y" comments.** They are HN/LinkedIn weather, not signal. Reply with R1 above, or with a one-line link to the specific file the commenter would learn the most from. If the commenter has a substantive critique, ask one clarifying question instead of arguing — every minute spent in a defensive thread is a minute not engaging with someone who actually wants to use the work.

---

## 8. Post-launch capture template

After each post goes up, append a line here so the launch debrief in `LAUNCH_COMMAND_CENTER.md` §11 step 15 is one copy-paste:

```
[YYYY-MM-DD HH:MM ET] surface=linkedin|stocktwits|hackernews url=<post URL> initial-reach=<karma|comments|reactions> first-hour-cold-inbound=<n>
```
