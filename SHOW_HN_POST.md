# Show HN submission package — CBSRM

**Status:** ready to submit. Operator chooses one of the three titles below, pastes the body, posts the first comment immediately (timing matters for HN ranking).

**Best time to submit:** weekday 7:00-9:00 AM ET. Avoid weekends (HN traffic is lower; harder to reach front page).

---

## Title — pick one

Three options, ranked. HN title best practice: factual, specific, ≤ 80 chars, no clickbait, no "I built".

1. **Recommended:** `Show HN: CBSRM – open-source SRISK / CoVaR / Sahm Rule in pure Python`
   *(70 chars; cites three named methodologies that quant readers recognize instantly; "open-source" + "pure Python" are HN-friendly signals)*

2. **Alternate:** `Show HN: A 7-layer cross-border systemic risk monitor (Apache 2.0)`
   *(67 chars; emphasizes architecture + license; weaker than #1 because it doesn't name a specific methodology)*

3. **Alternate:** `Show HN: Reimplementing the supervisory systemic-risk toolkit in NumPy`
   *(67 chars; sells the methodological-rigor angle; risky because "supervisory" is jargony for general HN)*

---

## URL field

`https://github.com/pravo123/cbsrm`

(NOT the Streamlit URL. HN convention is: repo URL in the link, demo URL in the body. Putting the demo URL in the field flags as marketing.)

---

## Body (200 words, paste verbatim)

> Hi HN. CBSRM is an open-source 7-layer financial-stability + systemic-risk
> platform. Pure-Python reimplementations of the canonical methodology stack
> central banks and supervisory teams use: SRISK (Brownlees-Engle 2017), ΔCoVaR
> (Adrian-Brunnermeier 2016), MES (Acharya et al 2017), Holló-Kremer-Lo Duca
> CISS for US / EA / UK / Japan, the Sahm Rule, Diebold-Yilmaz spillover index,
> 10 macro indicators across 5 jurisdictions (US / EA / UK / Japan / broad USD),
> interpretation labels in 5 languages, and a sha256-linked audit chain that
> tracks every fetch / computation / served value.
>
> Built solo in ~7 weeks. 363 tests passing. Whitepaper has 14 methodology
> sections (~14k words). No SciPy / arch / statsmodels dependency at compute
> time — the GJR-GARCH-DCC Monte Carlo for SRISK / MES is ~300 lines of NumPy,
> the Diebold-Yilmaz GFEVD is ~150.
>
> Live dashboard (Streamlit Community Cloud): <YOUR_STREAMLIT_URL_HERE>
>
> Repo: https://github.com/pravo123/cbsrm
> Whitepaper: in `whitepaper/cbsrm_methodology_v1.md`
> Apache 2.0.
>
> Happy to answer questions about the methodology choices, the audit-chain
> design, or why the pure-Python path was worth the extra work vs depending
> on the academic-canonical R packages.

---

## First comment (post immediately after submission)

The first comment on a Show HN post is the second-highest-converting surface after the title. Use it to seed the discussion in your preferred direction.

> A few notes on the design choices that aren't obvious from the README:
>
> 1. **No statsmodels / arch / SciPy at compute time** — the OLS quantile
>    regression (for ΔCoVaR), the GJR-GARCH-DCC simulator (for SRISK/MES),
>    and the generalized FEVD (for Diebold-Yilmaz) are all pure NumPy.
>    This is for two reasons: (a) operators in supervisory shops often have
>    locked-down Python environments where adding a C-compiled dep is a
>    multi-week procurement; (b) ~600 lines of dependency-free code is
>    easier to audit than wrapping a black-box library.
>
> 2. **Audit chain is methodology, not infra** — every fetch / computation
>    / served value writes a sha256-linked lifecycle row. The query
>    "how did this number come to be?" has a one-SQL-statement answer.
>    This is the part that took the longest to design and is the most
>    differentiated from existing academic implementations.
>
> 3. **Public ships the methodology, private engine ships separately** —
>    CBSRM is the open-source half; a private companion (VolanX) applies
>    the same data + indicator + audit primitives to a multi-broker
>    derivatives execution platform. The public side is the credibility
>    surface; the private side is the engine.
>
> Open to feedback on the methodology choices or the architecture — that's
> the point of shipping it like this.

---

## Operator pre-flight checklist

- [ ] Streamlit demo URL is live (see `dashboard/STREAMLIT_DEPLOY.md`)
- [ ] First-comment text drafted in a notepad ready to paste
- [ ] HN account at least 7 days old with > 3 karma (or your post will be heavily down-weighted)
- [ ] You're sitting at the computer when you submit (post → reload HN front page → confirm "newest" placement → drop the first comment within 60 seconds → engage with replies as they arrive for the first 2-3 hours; that's the window the front-page algorithm cares about)
- [ ] Not posting at the same time as a major news event (HN traffic gets sucked into news threads)
- [ ] If the post hits page 1: pin your tab and stay reachable for 6 hours. The conversion to GitHub stars + cold inbound happens during the discussion, not before.

---

## What success looks like

- Tier 1 (typical): 30-60 karma, 5-15 comments, 50-100 GitHub stars in the first 48 hours, ~3-5 cold inbound emails (recruiters, consultants, fellow quants)
- Tier 2 (good): front page for 6-12 hours, 200+ karma, 50+ comments, 300-500 GitHub stars in week 1, 10-20 cold emails, 1-2 podcast invites
- Tier 3 (great): top-10 for a day, 500+ karma, 100+ comments, 1000+ GitHub stars in week 1, 30+ cold emails, dashboard URL gets 5-10k unique visitors

Tier 1 is realistic for a methodology-heavy Show HN with a working demo. Tier 2-3 requires either a viral angle (e.g. SVB-style timing) or a notable reshare.

---

## If the post flames out

It happens. HN is rough. Wait 2-3 days, post a different angle (e.g. a Show HN of just the dashboard, with the methodology paper as a follow-up). Don't repost the same title — HN's spam filter will catch it.

The CBSRM repo + the methodology paper compound regardless of any single HN post. Long game.
