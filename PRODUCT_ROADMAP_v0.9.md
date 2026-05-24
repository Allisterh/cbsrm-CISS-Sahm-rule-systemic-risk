# CBSRM Product Roadmap — v0.8 → v0.9 → SaaS MVP

> Repo-grounded. Every slice references real modules. Nothing here invents a surface that does not exist today, and nothing promises a slice that has not been scoped against the actual code.

---

## 0. Shipped baseline (v0.8.0 — `410e3ac`)

Verified surfaces in repo at the time of writing:

| Layer | Module(s) |
|---|---|
| Data adapters | `cbsrm/data/fred.py`, `cbsrm/data/ecb.py`, `cbsrm/data/ofr.py`, `cbsrm/data/bis/*` |
| Stress indicators | `cbsrm/indicators/ciss_us.py`, `cbsrm/indicators/ecb_ciss.py`, `cbsrm/indicators/stlfsi.py`, `cbsrm/indicators/ofr_fsi.py` |
| Macro engine | `cbsrm/macro/*` (yield_curve, nfp_momentum, ffr_change, dxy_regime, jpy_regime, cpi_surprise, oil_macro, credit_spread, sahm_rule, macro_composite) |
| Connectedness | `cbsrm/indicators/dy_spillover.py` |
| Risk pricing | `cbsrm/risk/srisk.py`, `cbsrm/risk/delta_covar.py`, `cbsrm/risk/mes.py` |
| **Network systemic risk (v0.8)** | `cbsrm/networks/debt_rank.py` |
| **Macro events (v0.8)** | `cbsrm/macro/macro_events.py` |
| **Macro replay (v0.8)** | `cbsrm/diagnostics/macro_replay.py` |
| **Phase classifier (v0.8)** | `cbsrm/macro/phase_classifier.py` |
| **Crisis dossiers (v0.8)** | `cbsrm/diagnostics/crisis_dossiers.py` |
| **Reporting (v0.8)** | `cbsrm/reporting/report_renderer.py` |
| Audit | `cbsrm/audit/chain.py` |
| **CLI (v0.8 entry)** | `cbsrm/cli.py` (added `cmd_crisis_dossier`) |
| **API (v0.8 entry)** | `cbsrm/api/routes.py` (added `/reports/crisis-dossiers/...`) |
| **Streamlit (v0.8 entry)** | `dashboard/crisis_dossier_viewer.py` |

Test count: **555 passed**. Optional extras: `cbsrm[api]`, `cbsrm[all]`.

---

## 1. v0.8.x maintenance candidates

Low-risk, additive-only, no public-API breakage. Operator-eligible without major review.

| Candidate | Likely effort | Notes |
|---|---|---|
| Fix the residual whitepaper-sections badge in `README.md` (says 12; v0.7 added §§13-14) | trivial | Single Markdown line |
| Add `cbsrm/__init__.py` re-export of the v0.8 surface (`from cbsrm.reporting import …`, etc.) | small | Convenience only; behavior unchanged |
| Add an explicit `[project.urls]` `Changelog`, `Documentation`, `Repository` block in `pyproject.toml` | trivial | Improves PyPI page once published |
| Add the v0.8 viewer screenshot to README under "Live demo" | small | After §5 of `LAUNCH_COMMAND_CENTER.md` |
| Add a `Makefile` or `justfile` for `test`, `lint`, `release-notes`, `serve-api`, `viewer` shortcuts | small | Operator workflow only |
| Tighten `CONTRIBUTING.md` for methodology-PR template | small | No code |
| Add a `.github/workflows/ci.yml` if not present that runs `pytest tests/` on push | small | One CI file; no source touched |

---

## 2. v0.9 product goal (one sentence)

**Make the v0.8 research output something a non-Python user can consume and pay for, without compromising the audit-chain or fixture-deterministic posture.**

Operationally: take what the CLI + read-only API + Streamlit viewer already do, and add the four missing pieces a paying user would actually need — report persistence (so they can refer back), authenticated access (so we know who they are), live data wiring (so the dossiers aren't purely fixture-backed), and PDF export (so they can share inside a regulated environment).

---

## 3. Candidate slices, ranked by leverage / risk

Leverage = how much it moves the product toward something a paying user touches. Risk = the chance the slice breaks the v0.8 posture (offline-determinism, audit-chain integrity, optional-deps hygiene, "research analytics, not advice").

| Rank | Slice | Leverage | Risk | Rationale |
|---|---|---|---|---|
| 1 | **Report registry** (named, versioned report definitions; `RegistryEntry` w/ `report_id`, `composition`, `inputs_schema`, `output_schema`, `renderer_version`) | high | low | Pure-Python, additive, sets up everything below. The crisis-dossier surface becomes the first registry entry, so we get one re-usable abstraction at zero behavior cost. |
| 2 | **Report persistence + content-addressed storage** (sqlite or filesystem, sha256 → JSON / Markdown blobs) | high | low | Lets the API and Streamlit show a real "Recent reports" surface; pairs with audit-chain primitive so every persisted report has provenance. No multi-tenant logic yet — single-operator. |
| 3 | **PDF export over the existing Markdown renderer** (`render_dossier_pdf(dossier) -> bytes` via WeasyPrint or pandoc subprocess; pdf extra) | high | medium | Operators in regulated environments actually share PDFs. Risk is dependency footprint — keep WeasyPrint under `cbsrm[pdf]` extra so the core remains numpy-only. |
| 4 | **Hosted API hardening** (CORS, rate-limit middleware, request-IDs, structured logging, OpenAPI metadata polish, optional bearer-token gate) | medium | medium | Required before any non-local deploy. Risk is that "hosted" implies hosting; keep all infra-implying behavior gated behind explicit config so single-process usage stays the default. |
| 5 | **Live-data-backed crisis dossier builder** (`build_crisis_dossier_live(start, end)`; uses existing `cbsrm.data` adapters; FALLS BACK to fixture mode if data fetch fails) | high | high | The biggest user-visible upgrade — turns research analytics into "show me how this looks for the *current* window." Risk is offline-determinism: must add an explicit `mode=fixture|live` parameter, keep `mode=fixture` as the default, and never let the live path silently flip a deterministic test. |
| 6 | **Streamlit viewer multi-page upgrade** (`pages/01_crisis_dossier.py`, `pages/02_macro_composite.py`, `pages/03_systemic_network.py`) — surfaces the three pillars of v0.8 in one nav | medium | low | Pure Streamlit shape change. Keeps standalone `dashboard/crisis_dossier_viewer.py` as the legacy entrypoint for backward compatibility. |
| 7 | **`arch`-backed GJR-GARCH-DCC fitter** under `cbsrm[arch]` extra | medium | medium | Closes the v0.5 deferral. Risk: heavyweight dep; gate behind extra; numpy fallback stays the default. |
| 8 | **BIS LBS + EER adapters** under `cbsrm/data/bis/` | low-medium | low | Completes the cross-border data surface; no public API change beyond new adapter classes. |
| 9 | **Composer layer** — unified `PipelineRecord` shape, uniform date convention, uniform identifier/version contract across the v0.8 stages | medium | medium | Big internal refactor; pays off when the registry above grows beyond one entry. Defer until rank 1-2 are in. |
| 10 | **Multi-tenant accounts + billing** | high | very high | Out of scope for v0.9. Requires legal/tax/payments infra outside the repo. Listed only to mark it as not-now. |

---

## 4. Recommended next 5 implementation slices

In order. Each one fits the rc-style discipline used through v0.8: feature branch off `main`, narrow scope, full test suite green before merge.

### Slice 1 — Report registry (`cbsrm/reporting/registry.py`)

- **Branch:** `feat/report-registry`
- **Files likely touched:**
  - new: `cbsrm/reporting/registry.py`, `tests/test_report_registry.py`
  - updated: `cbsrm/reporting/__init__.py` (export `REPORT_REGISTRY`, `RegistryEntry`, `lookup_report`)
  - updated: `cbsrm/diagnostics/crisis_dossiers.py` — **only** to register the existing function; behavior unchanged
  - updated: `CHANGELOG.md`
- **Files to avoid touching:** macro / risk-pricing / data / audit / indicator modules, CLI, FastAPI, Streamlit (all integrate via the registry in later slices, not now)
- **Test strategy:** registry shape contract, idempotent registration, lookup by `report_id`, validation of `composition` + `renderer_version` fields, no-network-IO contract preserved on the crisis-dossier registry entry
- **DoD:** `from cbsrm.reporting import REPORT_REGISTRY` works; the existing dossier surface is callable via `REPORT_REGISTRY["crisis_dossier"].build("2008Q4")` and returns bit-for-bit-identical output to direct `build_crisis_dossier("2008Q4")`

### Slice 2 — Report persistence (`cbsrm/reporting/persistence.py`)

- **Branch:** `feat/report-persistence`
- **Files likely touched:**
  - new: `cbsrm/reporting/persistence.py`, `tests/test_report_persistence.py`
  - new (optional): `cbsrm/reporting/_backends/sqlite.py`, `cbsrm/reporting/_backends/fs.py`
  - updated: `cbsrm/api/routes.py` — add `POST /reports/store`, `GET /reports/stored/{report_id_hash}`; existing `/reports/crisis-dossiers` routes unchanged
  - updated: `CHANGELOG.md`
- **Files to avoid touching:** the existing read-only crisis-dossier routes (do not break the v0.8 contract; persistence is a separate surface)
- **Test strategy:** content-addressed `sha256` of `(report_id, inputs, renderer_version)`, idempotent storage, lookup by hash returns the same bytes, no-network-IO contract on storage path, optional sqlite vs filesystem backend selectable via env
- **DoD:** persisted report URL is shareable across sessions; chain-of-custody (audit row → storage hash) is one query away

### Slice 3 — PDF export (`cbsrm/reporting/pdf.py`)

- **Branch:** `feat/pdf-export`
- **Files likely touched:**
  - new: `cbsrm/reporting/pdf.py`, `tests/test_pdf_export.py`
  - updated: `cbsrm/cli.py` — add `--format pdf` to `crisis-dossier` command
  - updated: `cbsrm/api/routes.py` — add `GET /reports/crisis-dossiers/{window_id}/pdf` with `application/pdf` media type
  - updated: `dashboard/crisis_dossier_viewer.py` — add a third download button
  - updated: `pyproject.toml` — `[project.optional-dependencies] pdf = ["weasyprint>=60"]`
  - updated: `CHANGELOG.md`
- **Files to avoid touching:** the Markdown renderer (`cbsrm/reporting/report_renderer.py`) — PDF goes Markdown → HTML → PDF; rendering contract stays as-is
- **Test strategy:** PDF byte signature (`%PDF-`), page count > 0, deterministic for the same input, graceful `RuntimeError` with install hint if `cbsrm[pdf]` not installed
- **DoD:** all three front-ends emit a PDF for any of the 3 supported windows; PDF dependencies stay optional

### Slice 4 — API hardening (`cbsrm/api/middleware.py` + config)

- **Branch:** `feat/api-hardening`
- **Files likely touched:**
  - new: `cbsrm/api/middleware.py`, `cbsrm/api/_config.py`, `tests/test_api_middleware.py`
  - updated: `cbsrm/api/routes.py` — accept a config object; default config preserves current single-process posture
  - updated: `CHANGELOG.md`
- **Files to avoid touching:** the route handlers themselves (middleware is the seam; routes stay pure)
- **Test strategy:** rate-limit headers present, CORS responds to preflight, request-ID echo, optional bearer-token gate enforced when configured and **fully bypassed when not configured** (key invariant)
- **DoD:** `build_app()` without args returns the same app you have today; `build_app(config=APIConfig(bearer_tokens=[...], rate_limit_rpm=60))` returns a hardened app suitable for a single-tenant hosted deploy

### Slice 5 — Live-data crisis dossier (`cbsrm/diagnostics/crisis_dossiers_live.py`)

- **Branch:** `feat/live-data-dossier`
- **Files likely touched:**
  - new: `cbsrm/diagnostics/crisis_dossiers_live.py`, `tests/test_crisis_dossiers_live.py`
  - updated: `cbsrm/cli.py` — add `--mode fixture|live` (default `fixture`)
  - updated: `cbsrm/api/routes.py` — add `?mode=fixture|live` query param (default `fixture`)
  - updated: `dashboard/crisis_dossier_viewer.py` — radio toggle (default `fixture`)
  - updated: `CHANGELOG.md`
- **Files to avoid touching:** the existing `build_crisis_dossier` function (fixture path stays exactly as is — live path is an additive sibling)
- **Test strategy:** fixture mode still bit-for-bit identical to v0.8; live mode tests mock `cbsrm.data` adapter calls (no actual network during pytest); fallback-to-fixture-on-error path tested; explicit determinism caveat in docstrings
- **DoD:** existing v0.8 tests still pass byte-identical; new live-mode tests exist and pass with mocked adapters; offline-determinism contract on fixture mode preserved

---

## 5. Test strategy across all five slices

- **Default mode is the v0.8 mode.** Every new surface defaults to the behavior that already exists. Opt-in for new behavior, not opt-out.
- **No new network in tests.** The convention established in `tests/test_cli_crisis_dossier.py` and `tests/test_api_crisis_dossiers.py` (monkeypatch `urllib.request.urlopen` and `requests.Session.request` to fail) extends to every new test file.
- **Optional deps stay optional.** PDF requires `cbsrm[pdf]`; live-data live mode does not require new deps (uses existing `cbsrm.data`); API hardening adds no required deps.
- **Pre-merge gate:** full suite green (will grow from 555 toward ~700 over these 5 slices), no `.py` changes outside the allowlist for each slice, CHANGELOG entry present.
- **Branch discipline:** one slice = one branch = one merge commit = one annotated tag where appropriate (`v0.8.1` after slice 1, etc., to keep the audit trail clean).

---

## 6. "Commercial SaaS MVP in 30 days" plan

Realistic if-and-only-if the goal is a single-tenant paid offering with a small initial user list, not a full multi-tenant marketplace.

### Week 1 — Foundations (slices 1 + 2)

- **Day 1-2:** Slice 1 (report registry). Merge.
- **Day 3-5:** Slice 2 (report persistence). Merge.
- **Day 6-7:** Add a tiny landing page under `docs/` describing the offering; static, no JS framework. Wire `cbsrm.api.routes:app` into a single VPS (Hetzner / Fly.io / Render) behind a CDN.

### Week 2 — User-visible (slices 3 + 4)

- **Day 8-10:** Slice 3 (PDF export). Merge.
- **Day 11-13:** Slice 4 (API hardening — bearer-token gate, rate limit, CORS, request-ID). Merge.
- **Day 14:** Deploy hardened API behind a domain; issue one bearer token per first user manually (no signup form yet).

### Week 3 — Live data + viewer polish (slice 5 + slice 6 lite)

- **Day 15-18:** Slice 5 (live-data dossier). Merge.
- **Day 19-21:** Streamlit multi-page upgrade (slice 6) — deploy on Streamlit Community Cloud as a separate URL.

### Week 4 — Customers

- **Day 22-26:** First 5 cold-list outreaches per `CUSTOMER_DISCOVERY_v0.8.md`. Goal: 2 discovery calls.
- **Day 27-28:** First paid pilot — manual invoice via Stripe Invoicing (no auth-server integration yet). $X/month for API access + viewer.
- **Day 29-30:** Iterate on whichever surface the pilot user actually touches. **Do not build anything they did not ask for.**

### Deliberately deferred past day 30

- Multi-tenant signup flow
- Self-service Stripe checkout
- OAuth (BIS, ECB, FRED-style identity)
- Anything implying production reliability SLAs

### Honest caveats

- This plan assumes the operator has weekday writing time and no other blocking commitments. Halve the pace for a side-project rhythm.
- "30 days to revenue" depends on a warm cold-list. Without one, week 4 stretches to week 6-8.
- Legal / tax / commercial-entity setup is **not** in this plan. Operator must handle that separately before invoicing.
- This is **research-analytics SaaS**, not trading SaaS. Anyone trying to wire CBSRM outputs into a live execution path is on their own — do not let a customer conversation drift into "can you also run my trades?"

---

## 7. Anti-roadmap (what is explicitly NOT next)

| Not doing | Why |
|---|---|
| Bigger ML / "AI" surface on top of the methodology layer | The audit-chain story is the differentiator. Adding a black-box predictor would dilute it. |
| Trading / execution / signals in CBSRM | Out of scope by design. Lives in the private companion. |
| A "VolanX public release" parallel | Same reason. Keep the public CBSRM credibility surface clean. |
| Rewriting in another language | Pure-Python posture is methodology, not implementation accident. |
| A web dashboard framework swap (FastAPI → Django, Streamlit → React) | The frameworks are doing their job; switching is months of work for zero user-visible value. |

---

## 8. Tracking

After each slice merges, append a one-line entry here in `## 9. Shipped slice log` so the roadmap stays grounded in what actually happened, not what was planned.

## 9. Shipped slice log

```
[YYYY-MM-DD] slice=<n> branch=<branch> merge=<sha> tag=<v0.8.x> tests=<count> notes=<short>
```
