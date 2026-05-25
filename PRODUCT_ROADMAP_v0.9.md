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

Test count at the `v0.8.0` tag: **555 passed**. Optional extras at the tag: `cbsrm[api]`, `cbsrm[indicators]`, `cbsrm[dev]`, `cbsrm[all]`.

### 0.1 — v0.9 work landed on `main` (post-`v0.8.0`, not in the tag)

Additive only. Operator-gated merges, all green CI on `main`.

| Slice | Modules | Notes |
|---|---|---|
| **Report registry / catalog** (v0.9 slice 1) | `cbsrm/reporting/registry.py` | `get_report_catalog` / `list_report_ids` / `get_report_metadata`; deterministic; deep-copies per call |
| **Catalog HTTP API** | `cbsrm/api/routes.py` (`GET /reports`) | Pure pass-through; never executes a report |
| **Catalog CLI** | `cbsrm/cli.py` (`cbsrm reports`) | JSON dump of the catalog |
| **Catalog Streamlit landing page** | `dashboard/report_catalog_viewer.py` | Pure helper `build_catalog_view(...)`; Streamlit lazy-imported |
| **Second registry entry** (now Python-executable; see follow-up row below) | `cbsrm/reporting/registry.py` | `macro-composite` — pins `_REPORT_BUILDERS` insertion order; initially metadata-only, promoted to an executable builder in a later slice |
| **HTML report renderer** | `cbsrm/reporting/html_renderer.py` | `render_dossier_html(...)`; deterministic full HTML doc for browser print-to-PDF. Optional dep `cbsrm[html]` (`markdown>=3.5,<4`). Binary PDF byte-stream is NOT in this slice. |
| **HTML CLI** | `cbsrm/cli.py` (`--format html`) | UTF-8-safe stdout via existing helper |
| **HTML HTTP API** | `cbsrm/api/routes.py` (`/reports/crisis-dossiers/{window_id}/html`) | `text/html; charset=utf-8` |
| **HTML Streamlit download** | `dashboard/crisis_dossier_viewer.py` | Third download button next to `.md` / `.json` |
| **CI install** | `.github/workflows/test.yml` | Extended to install `[html]` extra so the 10-job matrix exercises the HTML path |

Additional v0.9 slices landed on `main` since the prior docs checkpoint:

| Slice | Modules | Notes |
|---|---|---|
| **Manifest foundation** | `cbsrm/reporting/manifest.py` | `build_report_manifest(...)`, `sha256_text`, `sha256_jsonable`, `MANIFEST_VERSION`. Deterministic-by-default (no wall-clock); JSON-serializable. |
| **Manifest CLI surface** | `cbsrm/cli.py` (`--manifest PATH`) | Writes deterministic manifest JSON; stdout unchanged. |
| **Manifest API surface** | `cbsrm/api/routes.py` (`?manifest=true`) | Adds `"manifest"` key only when opted in; default envelope unchanged. |
| **Manifest Streamlit surface** | `dashboard/crisis_dossier_viewer.py` | 4th download button beside Markdown / JSON / HTML. |
| **Audit-chain bridge** | `cbsrm/reporting/audit_manifest.py` | `stamp_manifest_to_chain`, `manifest_subject`, `AUDIT_EVENT_KIND="REPORT_EXPORTED"`. `cbsrm/audit/chain.py` untouched. |
| **Audit-chain API surface** | `cbsrm/api/routes.py` (`?audit=true`) | Auto-builds manifest, appends `REPORT_EXPORTED` row, surfaces row metadata. |
| **Audit-chain CLI surface** | `cbsrm/cli.py` (`--audit-db PATH`) | Opens/creates sqlite, stamps manifest, prints one stderr line; stdout unchanged. |
| **Audit-chain Streamlit surface** | `dashboard/crisis_dossier_viewer.py` | Sidebar "Stamp manifest to audit chain" button driven by `CBSRM_AUDIT_DB`. Trio complete. |
| **CLI audit helper refactor** | `cbsrm/cli.py` | Collapsed inline `sqlite3.connect → AuditChain → stamp → close` block to one call to `stamp_manifest_to_db_path`. Behaviour unchanged. |
| **Report persistence foundation** | `cbsrm/reporting/persistence.py` | SQLite-backed, content-addressed by manifest's `output_sha256` (PRIMARY KEY). `init_report_store`, `store_report_artifact` (idempotent, returns `was_existing: bool`), `get_report_artifact`, `list_report_artifacts`. `cbsrm/audit/chain.py` untouched — `output_sha256` is the natural join key between the two. |
| **Persistence CLI surface** | `cbsrm/cli.py` (`--store-db PATH`) | Opens/creates sqlite, persists rendered output, prints one stderr line; stdout unchanged. |
| **Persistence API surface** | `cbsrm/api/routes.py` (`?store=true` + `GET /reports/stored/{output_sha256}`) | `build_app(report_store_db_path=…)` operator-config seam (filesystem paths never accepted in requests). Adds `stored` projection only when opted in; default envelope unchanged. Lookup endpoint returns persisted row or 404. |
| **Persistence Streamlit surface** | `dashboard/crisis_dossier_viewer.py` | Sidebar "Report store (opt-in)" block driven by `CBSRM_REPORT_STORE`. Persists only on explicit button click. Trio complete. |
| **Macro-composite executable builder** | `cbsrm/reporting/macro_composite_report.py`, `cbsrm/reporting/registry.py` | `build_macro_composite_report(window_id) -> dict` + `render_macro_composite_markdown(report) -> str` + `list_macro_composite_windows()` + `MACRO_COMPOSITE_WINDOWS` + `MACRO_COMPOSITE_REPORT_VERSION`. Phase-classifier-only first cut; deterministic, offline, fixture-backed; JSON + Markdown for `2008Q4` / `2020Q1` / `2023Q1`; drift-guarded against `cbsrm.diagnostics.crisis_dossiers.get_fixture_snapshot`. Registry entry promoted from metadata-only to executable (now ships `formats: ["json","markdown"]` and pinned `windows`). |
| **Macro-composite CLI subcommand** | `cbsrm/cli.py` (`cmd_macro_composite`) | `cbsrm macro-composite WINDOW [--format json\|markdown]`. UTF-8-safe stdout via existing helper; JSON default; non-zero exit on unknown window. |
| **Macro-composite HTTP API routes** | `cbsrm/api/routes.py` | `GET /reports/macro-composite`, `GET /reports/macro-composite/{window_id}`, `GET /reports/macro-composite/{window_id}/markdown`. Read-only siblings to crisis-dossier routes; lazy FastAPI; no auth; 404+detail on unknown window. |
| **Macro-composite Streamlit viewer** | `dashboard/macro_composite_viewer.py` | Standalone offline page; pure `build_viewer_artifacts(window_id) -> dict` helper is the testable surface; Streamlit lazy-imported inside `render()`; selectbox + inline Markdown body + `.md`/`.json` download buttons. |
| **Macro-composite registry surfaces flip** | `cbsrm/reporting/registry.py` | One-shot catalog-honesty flip: macro-composite entry's `surfaces` field now advertises the three executable front-ends (CLI subcommand + 3 API routes + standalone Streamlit viewer) instead of the prior catalog-only pointer. Drift guards across the registry, API-catalog, API-macro-composite, and Streamlit-viewer test files flipped in lockstep. |

Test count on current `main`: **944 passed** (+389 vs `v0.8.0` tag; zero regressions).

Surfaces that remain NOT yet on `main`: real binary PDF byte stream, unified `PipelineRecord` composer, manifest / audit / persistence exposure for the `macro-composite` report (CLI / API / Streamlit front-ends now all shipped), `classify_regime` integration for the macro-composite builder, live-data adapters, multi-tenant accounts.

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
| 1 | ~~**Report registry**~~ — **SHIPPED on `main`** (see §0.1) | high | low | First registry entry was `crisis-dossier`; second metadata-only entry `macro-composite` followed. The `_REPORT_BUILDERS` insertion order is now pinned by tests. |
| 1b | ~~**Export-time manifests + audit-chain bridge**~~ — **SHIPPED on `main`** (CLI + API + Streamlit trio complete). | high | low | `cbsrm.reporting.build_report_manifest` + `stamp_manifest_to_chain` + `stamp_manifest_to_db_path` are wired into `cbsrm crisis-dossier --manifest PATH --audit-db PATH`, `?manifest=true&audit=true`, and the Streamlit sidebar "Stamp manifest to audit chain" button (env var `CBSRM_AUDIT_DB` + sidebar override). `cbsrm/audit/chain.py` untouched. |
| 2 | ~~**Streamlit audit-chain stamping**~~ — **SHIPPED on `main`** (PR #18). Closes the v0.9 audit-stamping trio. | medium | medium | Opt-in sidebar UX; `build_viewer_artifacts` stays pure; stamp fires only on explicit button click. |
| 2b | **CLI audit helper refactor** — collapse the CLI's inline `sqlite3.connect → AuditChain → stamp_manifest_to_chain → close` block to one call to the new `stamp_manifest_to_db_path` helper. | low | low | Pure cleanup. ~10-line diff. Behaviour unchanged; existing tests pass without modification. Reduces drift between the CLI and Streamlit code paths now that both can use the same path-based helper. |
| 3 | ~~**Report persistence + content-addressed storage**~~ — **SHIPPED on `main`** (foundation PR #21, exposure trio PR #22). | high | low | `cbsrm.reporting.persistence` (SQLite, `output_sha256` PRIMARY KEY, `INSERT OR IGNORE` idempotency) + CLI `--store-db PATH` + API `?store=true` & `GET /reports/stored/{output_sha256}` + Streamlit "Report store" sidebar (`CBSRM_REPORT_STORE`). Not coupled to the audit chain in code — `output_sha256` is the natural join key. |
| 3b | **Audit-chain persistence UX** — operator-config flow for picking a long-lived audit DB across surfaces (not just opt-in per-invocation). | medium | medium | Today: API `?audit=true` writes to the in-memory chain; CLI `--audit-db` opens a file each call. A persistent operator-config seam would let dashboards, scheduled CLI jobs, and the API all stamp the same chain without reconfiguration. |
| 4 | **PDF export** — _HTML foundation SHIPPED_ on `main`; binary PDF byte stream still deferred (`render_dossier_pdf(dossier) -> bytes` via reportlab or weasyprint; `cbsrm[pdf]` extra) | medium | medium | The HTML path already covers most "operator wants a PDF for a meeting" use cases via browser File → Print. Binary PDF is only required for environments that cannot run a browser. Risk: dependency footprint — keep reportlab/weasyprint under `cbsrm[pdf]` extra so the core stays markdown-only. |
| 4b | ~~**Executable `macro-composite` report**~~ — **BUILDER + CLI + API + STREAMLIT SHIPPED on `main`** (PR #24 builder; PR #25 CLI; PR #26 API; PR #28 Streamlit; registry surfaces flipped one-shot in this docs slice). Phase-classifier-only first cut: `build_macro_composite_report(window_id) -> dict` + `render_macro_composite_markdown(report) -> str`, deterministic / offline / fixture-backed, drift-guarded against the diagnostics fixture, surfaced through dedicated CLI subcommand + 3 read-only HTTP API routes + standalone Streamlit viewer. Manifest / audit / persistence exposure for this report and `classify_regime` integration are still deferred to follow-up slices. | medium | medium | Catalog is now two-executables with three executable front-ends each (crisis-dossier + macro-composite). The remaining deferred slices (manifest / audit / persistence) can layer over the generic surfaces without modifying the builder. |
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

### Slice 2 — Report persistence (`cbsrm/reporting/persistence.py`) — **SHIPPED on `main`** (PR #21 foundation + PR #22 CLI/API/Streamlit exposure)

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
- **Pre-merge gate:** full suite green (currently at 944 on `main`, +389 since `v0.8.0`; remaining slices will continue the growth), no `.py` changes outside the allowlist for each slice, CHANGELOG entry present.
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

v0.9 work-in-progress slices on `main` (post-`v0.8.0` tag; no v0.8.x patch tag created):

```
[2026-05-24] slice=v0.9-registry      branch=feat/report-registry-catalog     merge=e4436bb tag=- tests=579 notes=Python+HTTP catalog (PR #2)
[2026-05-24] slice=v0.9-changelog     branch=docs/changelog-v090-reset        merge=77936b1 tag=- tests=579 notes=Reset Unreleased for v0.9 (PR #3)
[2026-05-24] slice=v0.9-claude-os     branch=docs/claude-code-operating-system merge=69a3ca9 tag=- tests=579 notes=Claude Code operating-system docs (PR #4)
[2026-05-24] slice=v0.9-readme        branch=docs/readme-v090-pointer         merge=1f0eaaf tag=- tests=579 notes=README v0.9 pointer refresh (PR #5)
[2026-05-24] slice=v0.9-cli-catalog   branch=feat/cli-report-catalog          merge=2135266 tag=- tests=588 notes=cbsrm reports CLI (PR #6)
[2026-05-24] slice=v0.9-streamlit-cat branch=feat/streamlit-report-catalog    merge=b5b0a34 tag=- tests=597 notes=Streamlit catalog landing page (PR #7)
[2026-05-24] slice=v0.9-2nd-report    branch=feat/macro-composite-report      merge=5043289 tag=- tests=604 notes=macro-composite metadata entry (PR #8)
[2026-05-24] slice=v0.9-html-renderer branch=feat/report-html-renderer        merge=008684b tag=- tests=619 notes=render_dossier_html foundation (PR #9)
[2026-05-24] slice=v0.9-html-cli-api  branch=feat/cli-api-html-format         merge=464eb99 tag=- tests=636 notes=CLI --format html + /html API route (PR #10)
[2026-05-24] slice=v0.9-html-streaml  branch=feat/streamlit-html-download     merge=5a84cc6 tag=- tests=641 notes=Streamlit HTML download button (PR #11)
[2026-05-24] slice=v0.9-docs-chk-1    branch=docs/v090-status-checkpoint      merge=62325d2 tag=- tests=641 notes=Docs checkpoint v0.9 catalog+HTML (PR #12)
[2026-05-24] slice=v0.9-manifest      branch=feat/report-manifest             merge=8d4d0aa tag=- tests=677 notes=Deterministic manifest foundation (PR #13)
[2026-05-24] slice=v0.9-mani-surfaces branch=feat/manifest-cli-api-streamlit  merge=d0798c3 tag=- tests=700 notes=Manifest exposure CLI/API/Streamlit (PR #14)
[2026-05-24] slice=v0.9-api-audit     branch=feat/api-audit-export-stamping   merge=7f7057d tag=- tests=727 notes=API audit-chain export stamping (PR #15)
[2026-05-24] slice=v0.9-cli-audit     branch=feat/cli-audit-export-stamping   merge=ebb2b1a tag=- tests=739 notes=CLI audit-chain export stamping (PR #16)
[2026-05-24] slice=v0.9-docs-chk-2    branch=docs/v090-audit-status-checkpoint merge=2ac00bc tag=- tests=739 notes=Docs checkpoint v0.9 manifest+audit (PR #17)
[2026-05-24] slice=v0.9-strm-audit    branch=feat/streamlit-audit-export-stamping merge=f6f6096 tag=- tests=754 notes=Streamlit audit-chain export stamping — trio complete (PR #18)
[2026-05-24] slice=v0.9-docs-chk-3    branch=docs/v090-audit-trio-checkpoint   merge=e7118ad tag=- tests=754 notes=Docs checkpoint v0.9 audit-trio (PR #19)
[2026-05-24] slice=v0.9-cli-audit-rf  branch=refactor/cli-audit-via-db-path-helper merge=5957544 tag=- tests=754 notes=CLI audit refactor via stamp_manifest_to_db_path (PR #20)
[2026-05-24] slice=v0.9-persistence   branch=feat/report-persistence           merge=b3bc70f tag=- tests=786 notes=SQLite content-addressed report persistence foundation (PR #21)
[2026-05-24] slice=v0.9-pers-surfaces branch=feat/persistence-cli-api-streamlit-exposure merge=b3e432c tag=- tests=815 notes=Persistence CLI/API/Streamlit exposure — trio complete (PR #22)
[2026-05-24] slice=v0.9-macro-composite branch=feat/macro-composite-builder        merge=dd75aa1 tag=- tests=865 notes=Executable macro-composite report builder (phase-classifier-only) (PR #24)
[2026-05-24] slice=v0.9-docs-chk-4    branch=docs/v090-macro-composite-checkpoint merge=ac1b949 tag=- tests=865 notes=Docs checkpoint v0.9 macro-composite builder (PR #25)
[2026-05-24] slice=v0.9-cli-macro     branch=feat/cli-macro-composite             merge=a99a75c tag=- tests=883 notes=CLI cbsrm macro-composite subcommand (PR #26)
[2026-05-24] slice=v0.9-api-macro     branch=feat/api-macro-composite             merge=95b86ad tag=- tests=908 notes=HTTP API /reports/macro-composite sibling routes (PR #27)
[2026-05-24] slice=v0.9-strm-macro    branch=feat/streamlit-macro-composite       merge=b5894f0 tag=- tests=943 notes=Streamlit macro_composite_viewer.py — three executable front-ends complete (PR #28)
[2026-05-24] slice=v0.9-macro-surfaces branch=docs/v090-macro-composite-surfaces  merge=-       tag=- tests=944 notes=One-shot registry surfaces flip + docs checkpoint after macro-composite CLI/API/Streamlit exposure
```
