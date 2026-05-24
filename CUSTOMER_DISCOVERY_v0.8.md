# CBSRM v0.8 — Customer discovery pack

> Discovery, not selling. The goal of every outreach below is a 30-minute conversation that teaches us something we do not already know. **Compliance position is fixed:** CBSRM is a research tool, not investment advice. Every template enforces that.

---

## 0. Compliance wording (use verbatim where appropriate)

- Inline: *"CBSRM is research analytics. It is not financial advice and not a regulated investment communication."*
- Email footer: *"CBSRM (Cross-Border Systemic Risk Monitor) is open-source research software (Apache 2.0). Outputs are research analytics, not financial advice, not a recommendation to buy or sell any security, and not a regulated investment communication. Operators wiring CBSRM outputs into live systems are responsible for their own risk controls."*

Apply the footer to every external email below. Apply the inline phrase the first time a CBSRM output is described in a conversation.

---

## 1. Ideal customer profiles (ICPs)

The three profiles below are listed in order of *evaluation likelihood*, not contract size. Start with the easiest conversation, not the largest budget.

### ICP-1 — "Research-led quant analyst inside a mid-sized hedge fund / prop shop"

- **Title:** Quant Researcher, Quantitative Analyst, Risk Analyst, Macro Strategist
- **Org shape:** $100M-$5B AUM, 5-30 person research team, in-house Python stack, no dedicated systemic-risk team
- **Why they care:** They already track CISS / SRISK / yield-curve / Sahm Rule manually from FRED or via paid Bloomberg pulls. CBSRM gives them a methodology-traceable Python stack with an audit chain — saves them ~2 weeks of in-house re-implementation per indicator.
- **First-call signal:** they immediately ask about the GJR-GARCH-DCC implementation choices and want to see the file.
- **Buying motion:** internal champion → 30-day pilot on a fund laptop → 1-year license / API contract.

### ICP-2 — "Financial-stability researcher at a central bank Innovation Hub / supervisory authority"

- **Title:** Senior Economist, Financial Stability Analyst, FinTech Lead, Innovation Hub Researcher
- **Org shape:** central bank, ECB / BIS / OFR / FSB satellite team, BIS Innovation Hub cohort, supervisory technology group
- **Why they care:** they cannot ship code into the formal supervisory pipeline without a methodology-first, auditable, vendor-neutral reference. CBSRM is exactly that.
- **First-call signal:** they ask about the cross-source replication harness and want the whitepaper.
- **Buying motion:** academic-style citation → invited talk / workshop → potential adoption as a reference implementation. Money is slow but legitimizing.

### ICP-3 — "Risk team at a regulated asset manager / insurer / family office"

- **Title:** Head of Risk, CRO, Risk Quant, Investment Risk Manager
- **Org shape:** $500M-$50B AUM, regulated (UCITS, AIFMD, FCA, SEC), compliance-oriented procurement
- **Why they care:** they need to *report* on systemic exposure for regulatory filings and internal risk committees. CBSRM produces auditable, reproducible numbers with a cryptographic chain — exactly what their compliance team wants to see when the regulator asks "where did this number come from?"
- **First-call signal:** they ask about the audit chain first, the methodology second, and the deployment posture third.
- **Buying motion:** Risk team trial → Compliance review → 6-12 month procurement → 3-year contract.

---

## 2. 20 target organization categories

Categories, not specific names. Operator picks ~5 named targets per category for the actual cold list.

1. **BIS Innovation Hub** (Basel, Singapore, Hong Kong, Frankfurt, London, Stockholm, Toronto, Eurosystem) — bridge to central banks
2. **ECB DG-Macroprudential Policy + Financial Stability**
3. **Federal Reserve Board — Office of Financial Research** (OFR)
4. **Bank of England — Financial Stability Strategy & Risk** (FSSR)
5. **Bank of Japan — Financial System Research Division**
6. **NYU Stern V-Lab** (the SRISK reference)
7. **University-affiliated systemic-risk groups** (Princeton Bendheim, MIT Sloan, LSE Financial Markets Group, Imperial Brevan Howard Centre)
8. **IMF Monetary and Capital Markets Department**
9. **FSB (Financial Stability Board) Secretariat**
10. **OECD Committee on Financial Markets**
11. **Top-tier macro hedge funds** (5-10 selected named funds — operator's discretion)
12. **Multi-strat hedge funds with internal macro books**
13. **Quant prop shops with macro overlay** (Jane Street, Two Sigma, DRW, Citadel-adjacent risk teams)
14. **Family offices with $1B+ AUM and a CIO who reads SSRN papers**
15. **Insurance investment teams** (AIG, Allianz, Munich Re — internal investment groups)
16. **Sovereign wealth funds** (GIC, Norges, ADIA, Temasek research teams)
17. **Pension fund risk teams** (CalPERS, CPPIB, OTPP)
18. **Asset managers with risk product lines** (BlackRock Aladdin, MSCI, S&P)
19. **Supervisory technology vendors** (Quantexa, Wolters Kluwer OneSumX, Vermeg)
20. **Risk-focused fintech research arms** (Kensho-style, AlphaSense-style, fintech-of-fintech)

Categories 1-6 = ICP-2; categories 11-13 = ICP-1; categories 15-19 = ICP-3.

---

## 3. 15 discovery questions

Use 4-6 per call. Always end on Q15.

1. *(framing)* "Walk me through the last time someone in your team asked 'where did this number come from?' for a systemic-risk or stress reading — what did the answer look like?"
2. *(data)* "What data sources are you currently pulling for stress / systemic-risk inputs, and what's the most painful part of that pipeline?"
3. *(methodology)* "Are you re-implementing canonical methodologies (CISS, SRISK, ΔCoVaR, MES) in-house, or are you consuming them from a vendor?"
4. *(reproducibility)* "If a regulator or board asked you to reproduce a stress index value from 18 months ago, how would you do it today?"
5. *(language)* "Is your team primarily Python, R, MATLAB, or vendor-tool? Where are the integration points?"
6. *(audit)* "What does your audit trail for an analytical computation look like today — file logs, sqlite, a vendor system, or 'we hope we still have the notebook'?"
7. *(coverage)* "Do you need cross-jurisdiction coverage (US, EA, UK, Japan) or are you US-only? What about emerging markets?"
8. *(format)* "When you share systemic-risk readings inside the firm, what format wins — PDF, Markdown, an internal dashboard, a notebook, a deck?"
9. *(cadence)* "Is your systemic-risk read a monthly / weekly / daily / event-driven thing?"
10. *(scope)* "Do you separate research analytics (this is interesting) from production risk monitoring (this drives action)? Where would CBSRM sit?"
11. *(buy vs build)* "If a methodology-first, auditable, open-source Python library covered 80% of what your in-house implementation does today, would you adopt it, fork it, or stay in-house? What would the deciding factor be?"
12. *(procurement)* "If you adopted CBSRM, would it be an open-source library used internally, a paid support contract, or a hosted API / report subscription? What does your procurement look like for each?"
13. *(integration)* "Walk me through how a new analytical library typically gets into your production pipeline — security review, ops review, dependency review?"
14. *(competition)* "When you've evaluated similar tools, what made you pass on them? Was it methodology, code quality, support, pricing, or something else?"
15. *(close)* "Is there anyone else in your network you think would benefit from seeing this work, even just to give feedback?"

---

## 4. Five cold-email variants

All ≤ 200 words. Operator-only send. **Preview-first.** Choose one per recipient based on which line of business the recipient is in.

### CE-1 — Methodology-first (ICP-1, ICP-2)

> Subject: Open-source SRISK / ΔCoVaR / DebtRank reimplementation in pure Python
>
> Dear <NAME>,
>
> Your work on <SPECIFIC PUBLISHED PAPER / SPECIFIC TALK> is one of the references I keep coming back to.
>
> I have just released CBSRM v0.8.0 — an open-source 7-layer Python platform that reproduces SRISK (Brownlees-Engle), ΔCoVaR (Adrian-Brunnermeier), MES (Acharya et al.), and a pure-numpy DebtRank engine (Battiston et al.) under one Protocol and one cryptographic audit chain. 555 tests, Apache 2.0.
>
> The cross-source replication harness validates CBSRM against ECB CISS + OFR-FSI for the US / EA / UK over 2010-2026, and the new v0.8 crisis-window dossier surface composes the six methodology stages end-to-end with bit-for-bit reproducibility.
>
> If you have 20 minutes, I would value your feedback on either the methodology choices or the audit-chain design. I am not selling anything; this is a request for technical critique from someone whose published work I have been learning from.
>
> Repo: https://github.com/pravo123/cbsrm
> v0.8 release notes: <RELEASE_URL>
>
> Best regards,
> Prabhawa Koirala
> WaverVanir International
>
> *CBSRM is research analytics, not financial advice.*

### CE-2 — Audit-chain-first (ICP-3, compliance/risk leads)

> Subject: Cryptographically auditable systemic-risk analytics — open source
>
> Dear <NAME>,
>
> Risk teams I talk to consistently raise one pain point about systemic-risk and stress analytics: "We can compute the number, but the lineage isn't there when the regulator asks."
>
> CBSRM v0.8.0 (Apache 2.0) addresses exactly this. Every fetch / computation / served value writes a sha256-linked lifecycle row to an append-only audit chain. The query "how did this number come to be?" has a one-SQL-statement answer.
>
> The methodology base is the canonical literature: SRISK, ΔCoVaR, MES, Holló-Kremer-Lo Duca CISS for US / EA / UK / Japan, the Sahm Rule, Diebold-Yilmaz spillover, plus a pure-numpy DebtRank engine. Five jurisdictions, five languages of interpretation labels, 555 tests.
>
> I would be interested in a 20-minute conversation about how risk teams in <SPECIFIC FIRM SECTOR> evaluate this kind of tooling — what the integration gates look like, what compliance asks for, what a procurement path looks like. No pitch.
>
> Repo: https://github.com/pravo123/cbsrm
>
> Best regards,
> Prabhawa Koirala
> WaverVanir International
>
> *CBSRM is research analytics, not financial advice.*

### CE-3 — Innovation-Hub framing (ICP-2)

> Subject: Methodology-first systemic-risk reference implementation (Apache 2.0)
>
> Dear <NAME>,
>
> I have been following the work of the BIS Innovation Hub <SPECIFIC CENTRE> on <SPECIFIC PROJECT / SPECIFIC SPEECH>.
>
> CBSRM v0.8.0 — an open-source Python implementation of the canonical systemic-risk methodology stack (SRISK, ΔCoVaR, MES, CISS, DebtRank, plus a six-stage crisis-window dossier flow) — is now live. The architecture maps cleanly to the Innovation Hub model: methodology-first, vendor-neutral, audit-chain-integrated, Apache 2.0.
>
> If the Hub or any affiliated central bank would benefit from a runnable reference implementation — or if you can point me to the right person to talk to about that — I would be grateful.
>
> Whitepaper draft: `whitepaper/cbsrm_methodology_v1.md` in the repo.
> Repo: https://github.com/pravo123/cbsrm
>
> Best regards,
> Prabhawa Koirala
> WaverVanir International
>
> *CBSRM is research analytics, not financial advice or a regulatory communication.*

### CE-4 — Crisis-dossier hook (any ICP)

> Subject: Reproducible 2008 / 2020 / 2023 systemic-stress dossiers — open source
>
> Dear <NAME>,
>
> CBSRM v0.8.0 (Apache 2.0) ships deterministic, fixture-backed crisis-window dossiers for 2008Q4 (Lehman aftermath), 2020Q1 (COVID volatility shock), and 2023Q1 (SVB / SBNY / FRC).
>
> Each dossier composes six methodology stages — macro-event surprise scoring, windowed replay, pure-numpy DebtRank, an Acemoglu-style phase classifier, fixture-backed dossier assembly, and a deterministic Markdown / JSON renderer — and is reproducible bit-for-bit across a CLI, a read-only FastAPI, and a Streamlit viewer.
>
> Useful for retrospective stress analysis, teaching, supervisory case studies, or as a methodology benchmark for in-house tooling.
>
> If a 20-minute walk-through would be useful for you or your team, I am happy to schedule.
>
> Repo: https://github.com/pravo123/cbsrm
> v0.8 release: <RELEASE_URL>
> Live demo: <STREAMLIT_VIEWER_URL>
>
> Best regards,
> Prabhawa Koirala
> WaverVanir International
>
> *CBSRM is research analytics, not financial advice.*

### CE-5 — Warm-network short form (existing contact / mutual intro)

> Subject: Shipped v0.8 of the systemic-risk thing
>
> Hi <NAME>,
>
> Quick update — CBSRM v0.8.0 is out. 555 tests, six new methodology stages (macro surprise scoring, replay, DebtRank, phase classifier, crisis dossiers, report renderer), three bit-for-bit-identical front-ends (CLI / FastAPI / Streamlit).
>
> If you have 15 minutes this <NEXT WEEK / MONTH>, I would value pushing it past you for a sanity check — particularly the audit-chain design and the v0.8 dossier composition.
>
> Repo: https://github.com/pravo123/cbsrm
> Release: <RELEASE_URL>
>
> Thanks,
> Prabhawa
>
> *CBSRM is research analytics, not financial advice.*

---

## 5. Five LinkedIn DM variants

LinkedIn enforces shorter messages. Each ≤ 80 words. Avoid pitch language; lead with the recipient's published work.

### DM-1 — Reference-the-paper

> Hi <NAME> — your work on <SPECIFIC PAPER> has shaped how I think about <SUBTOPIC>. I just shipped CBSRM v0.8.0, an open-source Python implementation of the SRISK / ΔCoVaR / MES / DebtRank stack with a cryptographic audit chain (Apache 2.0). If you have 20 minutes for technical feedback I would value it — not a sales pitch, a request for critique. Repo: github.com/pravo123/cbsrm

### DM-2 — Reference-the-talk

> Hi <NAME> — your <CONFERENCE / PODCAST> talk on <TOPIC> was excellent. I'd love to send you CBSRM v0.8.0, an open-source systemic-risk + crisis-dossier toolkit I just released. Methodology-first, 555 tests, Apache 2.0. Happy to walk you through it if useful, or just leave you the link. github.com/pravo123/cbsrm

### DM-3 — Mutual-network short

> Hi <NAME> — saw we're both connected to <MUTUAL>. Just shipped CBSRM v0.8.0 (open-source systemic-risk monitor, Apache 2.0, audit-chain integrated). Curious whether it'd be useful for what you're doing at <ORG>. Open to a quick chat. github.com/pravo123/cbsrm

### DM-4 — Direct ask (warmest contacts only)

> Hi <NAME> — would you be open to 15 minutes? I want to push CBSRM v0.8.0 past someone with your background to sanity-check the audit-chain + cross-jurisdiction design. Open-source, Apache 2.0, 555 tests. No pitch. github.com/pravo123/cbsrm

### DM-5 — Crisis-dossier hook

> Hi <NAME> — CBSRM v0.8 just shipped reproducible crisis dossiers for 2008Q4, 2020Q1, 2023Q1. Six-stage pipeline, three front-ends, bit-for-bit identical output. Useful if you ever want a vendor-neutral retrospective stress benchmark. Apache 2.0. github.com/pravo123/cbsrm

---

## 6. What counts as validation

A signal is "validating" only if it meets at least one of the four bars below. **One reply is not validation.** **A GitHub star is not validation.**

### V1 — Methodology engagement

A practitioner reads at least one of the methodology files and either: (a) opens a GitHub issue with a substantive critique, or (b) replies to email/DM with a specific question that could only come from reading the code. *Counts as: this work is technically interesting to the right people.*

### V2 — Adoption signal

Someone forks the repo and the fork shows at least one commit beyond the README change. Or: someone installs the package and runs `cbsrm` commands locally (visible via repo traffic + an inbound issue). *Counts as: this work clears the activation barrier.*

### V3 — Conversation signal

Two or more discovery calls scheduled in any 30-day window where the recipient is in ICP-1, ICP-2, or ICP-3 and asks at least one question from §3 unprompted. *Counts as: the framing resonates with the right audience.*

### V4 — Money signal

A user offers to pay for one of: (a) hosted API access, (b) a support contract, (c) a custom report build, (d) a paid pilot. *Counts as: there is a commercial product here.*

**Strong-validation bar (do not pivot before this):** at least one V4 OR three V3s OR five V1+V2 combined.

---

## 7. What counts as "pivot or refine"

Triggered if any of the following hold after 60 days of active outreach (≥ 30 cold sends, ≥ 5 conversations attempted):

### P1 — Wrong-audience signal

Replies are dominated by "interesting but we're not the buyer" (ICP misfit). *Refine:* test ICP-2 (central-bank) framing more aggressively; deprioritize ICP-1 or ICP-3 depending on which is misfiring.

### P2 — Methodology-too-niche signal

Conversations confirm interest in *one specific subset* (e.g., DebtRank only, or CISS only) and indifference to the rest. *Refine:* lead with the subset in outreach; demote the umbrella framing.

### P3 — Open-source-only signal

Every conversation lands at "we'll fork and self-host, won't pay." *Refine:* the SaaS thesis is wrong for this audience. Either find a different audience (regulated risk teams — ICP-3 — are most likely to pay) or pivot to a support / consulting model.

### P4 — Methodology-correctness signal

Multiple methodologically informed reviewers flag the same correctness concern. *Refine:* fix the methodology before any further outreach. Outreach is downstream of correctness.

### P5 — Compliance-blocker signal

Compliance reviews at multiple ICP-3 firms reject CBSRM for the same reason (e.g., "we can't use Apache 2.0 in this jurisdiction" or "missing SOC2"). *Refine:* address the most common blocker; consider a commercial license tier with the missing artifact.

---

## 8. Sent log

```
[YYYY-MM-DD] template=<CE-n|DM-n> recipient=<NAME, ORG> anchor=<RELEASE_URL|SSRN|other> response=<none|polite no|scheduled call|forwarded>
```

Append a row after each outreach. The log is the operator's working memory; review the last 20 rows before sending the next batch.

---

## 9. Standing constraints (do not violate)

- **Preview-first.** Every external send goes through operator review before it leaves the laptop.
- **No mass sends.** ≤ 5 outreaches per day, ≤ 20 per week.
- **No misrepresentation.** Do not claim hosted SaaS, billing, auth, PDF, live data, or live trading. Those are roadmap items, not shipped surfaces.
- **Compliance position is non-negotiable.** Every email and DM ends with the research-only disclaimer or its inline equivalent.
- **Reciprocity.** If a reviewer gives substantive feedback, credit them in the next CHANGELOG entry (with their permission). Builds the social-proof flywheel.
