# CBSRM v0.8.0 — Launch Command Center

> **Single source of truth** for everything between "code shipped" and "public can use it." All other launch artifacts in this repo are linked from here. Operator-driven; nothing in this file posts, emails, deploys, or pushes on its own.

---

## 0. Current shipped state (verified)

### 0.1 — Released tag `v0.8.0` (frozen)

| Surface | Status | Reference |
|---|---|---|
| **Tag** | `v0.8.0` annotated on origin | commit `410e3ac9f3e2d3e79484571ef16fc92cd3099d10` |
| **Tests at tag** | **555 passed** on `v0.8.0` | `pytest tests/` at the tag commit |
| **CLI (v0.8)** | `cbsrm crisis-dossier WINDOW [--format json\|markdown] [--title-prefix TEXT]` | `cbsrm/cli.py` |
| **HTTP API (v0.8)** | `GET /reports/crisis-dossiers`, `…/{window_id}`, `…/{window_id}/markdown` (read-only, lazy FastAPI) | `cbsrm/api/routes.py` |
| **Streamlit viewer (v0.8)** | `streamlit run dashboard/crisis_dossier_viewer.py` (offline, no FRED key) | `dashboard/crisis_dossier_viewer.py` |
| **Six methodology stages** | `score_event` → `replay_macro_events` → `debt_rank` → `classify_phase` → `build_crisis_dossier` → `render_dossier_markdown` / `build_report_payload` | composed pipeline |

### 0.2 — Current `main` (v0.9 work in progress; NOT in the `v0.8.0` tag)

| Surface | Status | Reference |
|---|---|---|
| **`main`** | ahead of `v0.8.0` by additive v0.9 commits; CI green | `git log v0.8.0..main` |
| **Tests on `main`** | **944 passed** (was 555 at `v0.8.0`; +389 from v0.9 additive slices) | `pytest tests/` |
| **Report registry (v0.9)** | `cbsrm.reporting.get_report_catalog` / `list_report_ids` / `get_report_metadata`; 2 entries (`crisis-dossier`, `macro-composite`) | `cbsrm/reporting/registry.py` |
| **Catalog CLI (v0.9)** | `cbsrm reports` — JSON dump of the registry catalog | `cbsrm/cli.py` |
| **Catalog API (v0.9)** | `GET /reports` — JSON catalog endpoint | `cbsrm/api/routes.py` |
| **Catalog Streamlit (v0.9)** | `streamlit run dashboard/report_catalog_viewer.py` | `dashboard/report_catalog_viewer.py` |
| **HTML renderer (v0.9)** | `cbsrm.reporting.render_dossier_html(dossier, *, title_prefix=None, embed_stylesheet=True) -> str`; deterministic full HTML doc suitable for browser print-to-PDF; binary PDF byte-stream NOT in scope yet | `cbsrm/reporting/html_renderer.py` |
| **HTML CLI (v0.9)** | `cbsrm crisis-dossier WINDOW --format html` | `cbsrm/cli.py` |
| **HTML API (v0.9)** | `GET /reports/crisis-dossiers/{window_id}/html` (`text/html; charset=utf-8`) | `cbsrm/api/routes.py` |
| **HTML Streamlit (v0.9)** | "Download HTML (.html)" button in the existing crisis-dossier viewer | `dashboard/crisis_dossier_viewer.py` |
| **Manifest foundation (v0.9)** | `cbsrm.reporting.build_report_manifest(...)`; `sha256_text`; `sha256_jsonable`; `MANIFEST_VERSION`. Deterministic-by-default (no wall-clock); JSON-serializable; describes report export with versions + output sha256 + optional payload sha256 + disclaimer-present flag. | `cbsrm/reporting/manifest.py` |
| **Manifest CLI (v0.9)** | `cbsrm crisis-dossier --manifest PATH` — writes deterministic manifest JSON to PATH; stdout report bytes unchanged. | `cbsrm/cli.py` |
| **Manifest API (v0.9)** | `GET /reports/crisis-dossiers/{window_id}?manifest=true` — appends `"manifest"` key to JSON envelope; default response unchanged byte-for-byte. | `cbsrm/api/routes.py` |
| **Manifest Streamlit (v0.9)** | "Download Manifest (.manifest.json)" button next to Markdown / JSON / HTML buttons in the crisis-dossier viewer. | `dashboard/crisis_dossier_viewer.py` |
| **Audit-chain bridge (v0.9)** | `cbsrm.reporting.stamp_manifest_to_chain(chain, manifest)`; `manifest_subject(manifest)`; `AUDIT_EVENT_KIND = "REPORT_EXPORTED"`. Thin bridge from manifests to the existing `cbsrm/audit/chain.py` tamper-evident log; audit chain module untouched. | `cbsrm/reporting/audit_manifest.py` |
| **Audit-chain API (v0.9)** | `GET /reports/crisis-dossiers/{window_id}?audit=true` — opt-in; auto-builds manifest, appends to the app's `AuditChain`, returns `{report, dossier, manifest, audit}`. Audit row queryable via existing `GET /audit/{subject}`. | `cbsrm/api/routes.py` |
| **Audit-chain CLI (v0.9)** | `cbsrm crisis-dossier --audit-db PATH` — opens (or creates) a sqlite DB, stamps the export manifest, prints one stderr line `audit: row_id=… subject=… hash=…`. Stdout report bytes unchanged. | `cbsrm/cli.py` |
| **Audit-chain Streamlit (v0.9)** | Sidebar "Stamp manifest to audit chain" button in `dashboard/crisis_dossier_viewer.py`. Reads DB path from env var `CBSRM_AUDIT_DB`; sidebar text input overrides per session. Stamps only on explicit button click — never on render or window selection. `build_viewer_artifacts` stays pure. | `dashboard/crisis_dossier_viewer.py` |
| **Report persistence foundation (v0.9)** | `cbsrm.reporting.persistence` — `REPORT_STORE_VERSION`, `init_report_store`, `store_report_artifact`, `get_report_artifact`, `list_report_artifacts`. SQLite-backed, content-addressed by the manifest's `output_sha256` (PRIMARY KEY); `INSERT OR IGNORE` semantics return `was_existing: bool`; defensive hash-match validation between `sha256_text(output_text)` and the manifest's declared hash. Not coupled to `cbsrm/audit/chain.py` — `output_sha256` is the natural join key between the two. | `cbsrm/reporting/persistence.py` |
| **Persistence CLI (v0.9)** | `cbsrm crisis-dossier --store-db PATH` — opens (or creates) a sqlite DB, persists the rendered output, prints one stderr line `stored: output_sha256=… was_existing=… db=…`. Stdout report bytes unchanged. Idempotent; second call with same content sets `was_existing=true`. | `cbsrm/cli.py` |
| **Persistence API (v0.9)** | `build_app(audit_conn=None, report_store_db_path=None)` accepts an operator-configured store path (filesystem paths never accepted in HTTP requests). New `GET /reports/crisis-dossiers/{window_id}?store=true` adds a `stored` projection (`output_sha256`, `was_existing`, `byte_length`, `content_type`, `created_at_utc`); 400 with hint when `?store=true` but no store is configured. New `GET /reports/stored/{output_sha256}` lookup endpoint returns the persisted row or 404. Default envelope unchanged byte-for-byte when no new flags. | `cbsrm/api/routes.py` |
| **Persistence Streamlit (v0.9)** | Sidebar "Report store (opt-in)" block in `dashboard/crisis_dossier_viewer.py` parallel to the audit-chain block. Reads DB path from env var `CBSRM_REPORT_STORE`; sidebar text input overrides per session. Stamps only on explicit "Persist report to store" button click. `build_viewer_artifacts` stays pure. | `dashboard/crisis_dossier_viewer.py` |
| **Macro-composite executable builder (v0.9)** | `cbsrm.reporting.build_macro_composite_report(window_id) -> dict` + `cbsrm.reporting.render_macro_composite_markdown(report) -> str` + `list_macro_composite_windows()` + `MACRO_COMPOSITE_WINDOWS` + `MACRO_COMPOSITE_REPORT_VERSION`. Phase-classifier-only first cut; deterministic, offline, fixture-backed; JSON + Markdown for the same canonical windows as the crisis-dossier report (`2008Q4` / `2020Q1` / `2023Q1`); drift-guarded against `cbsrm.diagnostics.crisis_dossiers.get_fixture_snapshot`. Registry entry ships `formats: ["json","markdown"]` and pinned `windows`. CLI / API / Streamlit front-ends now all on `main` (rows below); manifest / audit / persistence wiring for this report and `classify_regime` integration remain deferred. | `cbsrm/reporting/macro_composite_report.py`, `cbsrm/reporting/registry.py` |
| **Macro-composite CLI (v0.9)** | `cbsrm macro-composite WINDOW [--format json\|markdown]` — dedicated subcommand, UTF-8-safe stdout, JSON default, exits non-zero on unknown window. | `cbsrm/cli.py` |
| **Macro-composite HTTP API (v0.9)** | `GET /reports/macro-composite`, `GET /reports/macro-composite/{window_id}`, `GET /reports/macro-composite/{window_id}/markdown` — read-only sibling surface to crisis-dossier routes; lazy FastAPI; no auth; 404+detail on unknown window. | `cbsrm/api/routes.py` |
| **Macro-composite Streamlit viewer (v0.9)** | `streamlit run dashboard/macro_composite_viewer.py` — standalone offline page; selectbox over the 3 canonical windows; inline Markdown body; `.md` + `.json` download buttons. Pure `build_viewer_artifacts(window_id)` helper is the testable surface (Streamlit lazy-imported inside `render()`). | `dashboard/macro_composite_viewer.py` |
| **Macro-composite registry surfaces (v0.9)** | One-shot honesty flip: registry `macro-composite` entry's `surfaces` field now advertises the three dedicated executable front-ends (CLI subcommand + 3 API routes + standalone Streamlit viewer) instead of the prior catalog-only pointer. Drift guards in the registry, API-catalog, API-macro-composite, and Streamlit-viewer test files flipped in lockstep from negative ("not yet advertising") to positive ("does advertise") pins. | `cbsrm/reporting/registry.py` |
| **Optional dep (v0.9)** | `cbsrm[html]` extra — `markdown>=3.5,<4`. Used by the HTML renderer; lazy-imported; raises `RuntimeError` with install hint when missing. CI install matrix updated to include `[html]`. | `pyproject.toml`, `.github/workflows/test.yml` |
| **Sibling launch-copy branch** | `docs/v08-launch-copy-refresh` — already merged to `main` | merged |

The v0.9 surfaces above are **only on `main`**. They are not in the `v0.8.0` tag and should not be implied to be by any external launch copy.

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
