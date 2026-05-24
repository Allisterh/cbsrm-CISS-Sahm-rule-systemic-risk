# CBSRM v0.8.0 — Launch Command Center

> **Single source of truth** for everything between "code shipped" and "public can use it." All other launch artifacts in this repo are linked from here. Operator-driven; nothing in this file posts, emails, deploys, or pushes on its own.

---

## 0. Current shipped state (verified)

| Surface | Status | Reference |
|---|---|---|
| **Tag** | `v0.8.0` annotated on origin | commit `410e3ac9f3e2d3e79484571ef16fc92cd3099d10` |
| **`main`** | `== origin/main == v0.8.0^{commit}` | clean |
| **Tests** | **555 passed** on `v0.8.0` | `pytest tests/` |
| **CLI** | `cbsrm crisis-dossier WINDOW [--format json\|markdown] [--title-prefix TEXT]` | `cbsrm/cli.py` |
| **HTTP API** | `GET /reports/crisis-dossiers`, `…/{window_id}`, `…/{window_id}/markdown` (read-only, lazy FastAPI) | `cbsrm/api/routes.py` |
| **Streamlit viewer** | `streamlit run dashboard/crisis_dossier_viewer.py` (offline, no FRED key) | `dashboard/crisis_dossier_viewer.py` |
| **Six methodology stages** | `score_event` → `replay_macro_events` → `debt_rank` → `classify_phase` → `build_crisis_dossier` → `render_dossier_markdown` / `build_report_payload` | composed pipeline |
| **Sibling launch-copy branch** | `docs/v08-launch-copy-refresh` (commit `54c6241`, pushed) — refreshes `SHOW_HN_POST.md` + `SSRN_SUBMISSION.md` for v0.8 | open PR-ready |

**RC sequence into v0.8.0:** `rc1` → `rc2` → `rc3` → `rc4` → `rc5` → `rc6` → `v0.8.0`. All tags on origin.

---

## 1. What v0.8.0 proves

Stated as load-bearing claims a reader can verify from the repo:

1. A solo author can ship a 7-layer, methodology-first, open-source systemic-risk platform with **555 tests**, audit-chain integrity, multi-jurisdiction coverage, and three front-ends in one cohesive release.
2. The v0.8 research flow chains six methodology stages into one composition that drives three independent front-ends (CLI / FastAPI / Streamlit) at **bit-for-bit parity** — pinned by tests.
3. Pure-Python posture holds across new code: DebtRank is a pure-numpy U/D/I state-machine cascade; surprise scorer + replay + dossier + renderer have no SciPy / arch / statsmodels at compute time.
4. UTF-8 correctness on Windows cp1252 consoles is a deliberate, tested invariant (renderer emits `→` and em-dashes; `_write_stdout_utf8_safe` bypasses the codepage).
5. Offline-deterministic posture is enforced by tests: `urllib.request.urlopen` and `requests.Session.request` are monkeypatched to fail in the new test files.
6. Optional-dependency hygiene: FastAPI stays optional under `cbsrm[api]`; Streamlit is imported lazily inside `render()` so the viewer module is import-safe (and unit-testable) without Streamlit installed.

**What v0.8.0 deliberately does NOT prove:**
- Live-data crisis dossier (current path is fixture-backed).
- Hosted multi-tenant API (current API is a single-process FastAPI you run yourself).
- Auth / billing / persistence / PDF (all deferred).
- Anything about trading, execution, signals, or P&L (CBSRM is research-only; the trading work lives in the private companion).

---

## 2. Public launch checklist (master)

Order matters. Top-down. Each item links to its own checklist below.

- [ ] **A — GitHub Release for `v0.8.0` published** (the tag exists; the Release page does not auto-populate). See §3.
- [ ] **B — Streamlit demo for the v0.8 crisis-dossier viewer is live** OR explicitly deferred. See §4.
- [ ] **C — Screenshot of the v0.8 viewer captured** (the existing `dashboard/screenshot.png` is the v0.5 dashboard). See §5.
- [ ] **D — Launch-copy branch (`docs/v08-launch-copy-refresh`) merged to `main`** — keeps `SHOW_HN_POST.md` / `SSRN_SUBMISSION.md` in sync with v0.8. Operator-approved merge.
- [ ] **E — This command-center branch (`docs/v08-launch-command-center`) merged to `main`** — adds operational docs. Operator-approved merge.
- [ ] **F — LinkedIn launch post drafted and reviewed** before posting. See §6 + `LAUNCH_POSTS_v0.8.0.md`.
- [ ] **G — Show HN post window picked and pre-flight complete.** See §7 + `SHOW_HN_POST.md`.
- [ ] **H — Stocktwits short post drafted.** See §6.
- [ ] **I — SSRN package final-check + paper PDF generated.** See §8 + `SSRN_SUBMISSION.md` + `SUBMISSION_CHECKLIST.md`.
- [ ] **J — Cold outreach sequencing decided.** See §9 + `COLD_EMAILS.md`.

---

## 3. GitHub Release checklist

The tag `v0.8.0` is annotated and on `origin`, but GitHub's "Releases" page is a separate surface that must be populated by hand.

- [ ] Open <https://github.com/pravo123/cbsrm/releases/new?tag=v0.8.0>
- [ ] Confirm the tag selector shows `v0.8.0` (not "Create new tag")
- [ ] Release title: `CBSRM v0.8.0`
- [ ] Body: paste `GITHUB_RELEASE_v0.8.0.md` verbatim
- [ ] "Set as the latest release" → on
- [ ] "Set as a pre-release" → off
- [ ] Do **not** upload extra binaries — the install path is `pip install cbsrm[all]` from PyPI (if/when published) or `pip install -e .[all]` from source
- [ ] Publish
- [ ] After publish: copy the Release URL into the LinkedIn post draft and into the Show HN body in place of the GitHub repo URL where appropriate

**Skip if:** the GitHub Release for `v0.8.0` already exists. (Check at <https://github.com/pravo123/cbsrm/releases>.)

---

## 4. Streamlit demo checklist

Two surfaces, both real, both already in-repo. Pick a deploy strategy before posting.

| App | File | Needs FRED key? | Best demo for v0.8? |
|---|---|---|---|
| Macro / SRISK panels | `dashboard/streamlit_app.py` | yes (`FRED_API_KEY`) | no — shows v0.5 readings |
| Crisis dossier viewer | `dashboard/crisis_dossier_viewer.py` | **no** | **yes** |

- [ ] Decide: deploy `crisis_dossier_viewer.py` as the headline demo (recommended — frictionless)
- [ ] Streamlit Community Cloud: add a second app entry on the same repo, main file path `dashboard/crisis_dossier_viewer.py`, branch `main`
- [ ] Set Python version + requirements per `dashboard/STREAMLIT_DEPLOY.md`
- [ ] Smoke-test the deploy: pick each window from the selectbox, download both `.md` and `.json`, confirm the disclaimer renders
- [ ] Capture the live URL — substitute into `<STREAMLIT_VIEWER_URL>` placeholders in:
  - `SHOW_HN_POST.md`
  - `LAUNCH_POSTS_v0.8.0.md`
  - `LAUNCH_COMMAND_CENTER.md` §11
- [ ] (Optional) Add a small "Live demo: …" line near the top of the repo README

**Defer if:** you would rather launch with screenshots only. In that case mark §4 explicitly "deferred" in §11 and skip §5's "live demo" bullets.

---

## 5. Screenshot checklist

- [ ] Launch the v0.8 viewer locally **or** open the deployed URL from §4
- [ ] Pick the most visually informative window (recommendation: `2020Q1` — COVID; the dossier shows the largest replay-return spread)
- [ ] Capture at 1440×900 viewport (most LinkedIn-readable)
- [ ] Crop to remove the OS chrome
- [ ] Save as either:
  - `dashboard/screenshot_v08_viewer.png` (new file, leaves the existing v0.5 `screenshot.png` alone — recommended), or
  - `dashboard/screenshot.png` (overwrites v0.5; breaks the v0.5 README image until refreshed)
- [ ] Add the screenshot to the README in a new "Live demo (v0.8 crisis-dossier viewer)" section if you want it surfaced on the repo homepage
- [ ] Add the same screenshot to the GitHub Release body if you want it surfaced there

---

## 6. LinkedIn / Stocktwits launch checklist

Drafts live in `LAUNCH_POSTS_v0.8.0.md`. **Preview-first** per the standing operator rule.

- [ ] Choose between the two LinkedIn variants in `LAUNCH_POSTS_v0.8.0.md` (professional / visionary)
- [ ] Substitute every `<…>` placeholder (Streamlit URL, GH Release URL, screenshot image)
- [ ] Re-read for: (a) no live-trading claims, (b) "not financial advice" present, (c) WaverVanir International / CBSRM brand consistent, (d) no overpromise about hosted SaaS that does not exist
- [ ] Post window: weekday 7-10 AM ET (LinkedIn) or market hours US (Stocktwits)
- [ ] After posting: set a 48-hour reminder to re-engage with comments
- [ ] Capture the post URL into the Cold Outreach worksheet in `COLD_EMAILS.md` for anchoring in follow-ups

---

## 7. Show HN checklist

Full checklist lives in `SHOW_HN_POST.md` (sibling branch `docs/v08-launch-copy-refresh` has the v0.8-refreshed version). High-level gates:

- [ ] Sibling branch `docs/v08-launch-copy-refresh` is merged so the post body says **555** tests and names the three front-ends
- [ ] `<YOUR_STREAMLIT_URL_HERE>` placeholder in the post body is replaced (or removed) per §4
- [ ] HN account ≥ 7 days old, > 3 karma
- [ ] Window: weekday 7-9 AM ET, not on a major news day
- [ ] First-comment text is in clipboard before submitting
- [ ] You are at the keyboard for 2-3 hours after submission
- [ ] Pre-decide which alternate title to fall back to if the first attempt flames out (HN spam filter catches repost-with-same-title)

---

## 8. SSRN checklist

Full mechanics in `SUBMISSION_CHECKLIST.md`; SSRN form fields in `SSRN_SUBMISSION.md` (sibling branch has the v0.8-refreshed version explicitly framing v0.5 as the paper snapshot and v0.8.0 as the current public reference release).

- [ ] Sibling branch `docs/v08-launch-copy-refresh` merged (so the package says **555 tests** and names the three v0.8 front-ends in the code-availability statement)
- [ ] Paper PDF generated (Word → PDF is the fastest path per `SUBMISSION_CHECKLIST.md` §Step 0 Path A)
- [ ] Title, abstract, JEL codes, keywords copied from `SSRN_SUBMISSION.md`
- [ ] FEN sub-network selected
- [ ] Cover letter pasted
- [ ] Conflict-of-interest disclosure (VolanX) included
- [ ] After SSRN gives back an abstract URL, capture it into `COLD_EMAILS.md` so outbound emails anchor to it

---

## 9. Cold outreach checklist

Templates live in `COLD_EMAILS.md` (Aldasoro, Schrimpf, V-Lab, HF CTO, BIS Hub). Customer-discovery templates live in `CUSTOMER_DISCOVERY_v0.8.md`. **Operator-only send.** Preview-first.

- [ ] SSRN paper URL exists (anchor for all emails)
- [ ] GitHub Release URL exists (anchor for "current release")
- [ ] Streamlit URL exists OR is explicitly skipped
- [ ] Each email re-read for: (a) no recruiter-style mass-send tone, (b) ≤ 200 words, (c) specific reference to recipient's published work, (d) one clear ask, (e) "not financial advice" softening present where the recipient is a regulator
- [ ] Send one email at a time, with at least 24 hours between sends so threads don't collide
- [ ] Log each send in `COLD_EMAILS.md` under a new "Sent log" section (date, recipient, anchor URL)

---

## 10. Do **not** do yet

| Action | Why not yet |
|---|---|
| Publish a hosted multi-tenant API | No auth, no rate-limiting, no quotas, no billing in repo — see `PRODUCT_ROADMAP_v0.9.md` |
| Add a "Sign in with Google" button anywhere | No accounts subsystem; would require auth + persistence first |
| Take payments / add Stripe | No accounts, no SaaS, no commercial entity wiring; legal/tax setup separate from this repo |
| Claim PDF export | Renderer emits Markdown + JSON only; PDF is on the roadmap |
| Claim live data in crisis dossiers | Current path is fixture-backed (deliberate, deterministic, offline). Live-data path is a v0.9 slice |
| Frame CBSRM as a trading product | CBSRM is research analytics; trading work is private and not in this repo |
| Auto-post to LinkedIn / Stocktwits / Telegram from CI | Standing preview-first rule applies; every public message gets operator eyes |
| Force-push to `main` | Standing safety rule |
| Tag `v0.9.0` or any pre-release tag | No `v0.9` work has landed yet |

---

## 11. Exact order of operations for launch day

A 90-minute sequence assuming the prerequisites in §§3-9 are complete. Steps that depend on the prior step are marked **▸**.

| # | Step | Approx time | Depends on |
|---|---|---:|---|
| 1 | Final `pytest tests/` on `main` — confirm **555 passed** | 1 min | — |
| 2 | Open <https://github.com/pravo123/cbsrm/releases/new?tag=v0.8.0> | 1 min | Step 1 |
| 3 | ▸ Paste `GITHUB_RELEASE_v0.8.0.md`; publish | 3 min | Step 2 |
| 4 | ▸ Capture the Release URL | 0 min | Step 3 |
| 5 | Verify Streamlit demo URL still loads (or skip if §4 deferred) | 2 min | §4 |
| 6 | ▸ Substitute Release URL + Streamlit URL into LinkedIn draft | 5 min | Steps 4-5 |
| 7 | Operator final-read LinkedIn draft → post | 5 min | Step 6 |
| 8 | ▸ Copy LinkedIn post URL | 0 min | Step 7 |
| 9 | Substitute Release URL + Streamlit URL into Show HN body | 3 min | Step 4 |
| 10 | ▸ Submit Show HN | 1 min | Step 9 |
| 11 | ▸ Immediately paste first-comment from clipboard | 1 min | Step 10 |
| 12 | Stocktwits short post — operator final-read → post | 3 min | Step 7 |
| 13 | Engage with comments on HN + LinkedIn for the next ~2 hours | 120 min | Steps 10, 7 |
| 14 | After 2-hour engagement window: send Aldasoro cold email (just one, sequence per §9) | 5 min | SSRN URL present |
| 15 | End of day: log results in a new EOD section appended to this file | 10 min | — |

**Abort gate:** if at any step a fact in the post does not match reality (e.g., the Streamlit URL 404s, the test count drifted, a v0.8 module reference is wrong), stop, fix the docs, then resume from the prior step.

---

## 12. Source-of-truth pointers (no duplication)

| Topic | Authoritative file |
|---|---|
| GitHub Release body | `GITHUB_RELEASE_v0.8.0.md` |
| Show HN package | `SHOW_HN_POST.md` (refreshed on `docs/v08-launch-copy-refresh`) |
| SSRN package | `SSRN_SUBMISSION.md` (refreshed on `docs/v08-launch-copy-refresh`) + `SUBMISSION_CHECKLIST.md` |
| Cold-email templates | `COLD_EMAILS.md` |
| LinkedIn + Stocktwits + HN-comment drafts | `LAUNCH_POSTS_v0.8.0.md` |
| Roadmap to v0.9 / SaaS MVP | `PRODUCT_ROADMAP_v0.9.md` |
| ICPs + discovery questions | `CUSTOMER_DISCOVERY_v0.8.md` |
| Methodology + research flow | `docs/v0.8_research_flow.md` |
| Whitepaper | `whitepaper/cbsrm_methodology_v1.md` |
| Changelog | `CHANGELOG.md` |

---

## 13. Working-tree positioning disclaimer

CBSRM is **research analytics**. All v0.8 surfaces are deterministic, offline, fixture-backed. **Not financial advice. No live broker, Telegram, credential, or execution wiring exists in this repository.** This positioning is preserved in every artifact linked from §12; the command-center exists to keep it that way under launch-day pressure.
