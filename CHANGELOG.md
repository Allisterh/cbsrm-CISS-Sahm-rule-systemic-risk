# Changelog

All notable changes to CBSRM are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and CBSRM adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

> **Status:** v0.8.0 shipped 2026-05-24 (annotated tag `v0.8.0` at commit
> `410e3ac9`). The v0.9 work-in-progress block below tracks additive
> slices on top of v0.8.0; the first one — the report registry/catalog —
> is already on `main`. Source versions in `pyproject.toml` /
> `cbsrm/__init__.py` are deferred for a single bump at the v0.9.0 final
> tag, consistent with the v0.8 release pattern.

### Added — v0.9 work in progress

**`macro-composite` executable report — builder only**
- New module `cbsrm/reporting/macro_composite_report.py` exposing `MACRO_COMPOSITE_REPORT_VERSION = "1.0.0"`, `MACRO_COMPOSITE_WINDOWS = ("2008Q4", "2020Q1", "2023Q1")`, `list_macro_composite_windows()`, `build_macro_composite_report(window_id)`, and `render_macro_composite_markdown(report)`. Re-exported from `cbsrm.reporting`.
- Deterministic, offline, fixture-backed. Same `window_id` → byte-identical dict under `json.dumps(..., sort_keys=True)`. Phase z-scores are pinned in-module and drift-guarded by a test against `cbsrm.diagnostics.crisis_dossiers.get_fixture_snapshot(window_id)["phase_features"]`.
- First-cut composition is **phase-classifier-only**: builder uses `cbsrm.macro.classify_phase` over the pinned per-window z-scores. Tests pin that the builder does NOT call `build_crisis_dossier` and does NOT call `classify_regime` — the latter integration is deferred pending sub-indicator-metadata fixtures per window.
- Registry entry `macro-composite` updated: `formats` is now `["json", "markdown"]` (was `["json"]`), `windows` is now `["2008Q4", "2020Q1", "2023Q1"]` (was `[]`), description rewritten to call out the executable builder + the deferred CLI/API/Streamlit exposure + the deferred `classify_regime` integration. Surfaces field unchanged (still points at catalog-level `cbsrm reports` / `GET /reports` / `report_catalog_viewer.py`) until a follow-up slice ships dedicated execution surfaces.
- 27 new tests in `tests/test_macro_composite_report.py` (with parametrisation across the 3 windows): version/window shape; unknown-window `ValueError`; required top-level keys; determinism via `json.dumps(sort_keys=True)`; JSON-serializability; fresh-copy-per-call mutation guard; spec-block version pins; `phase_classification.rule_version` pin; `dominant_drivers` + `risk_posture` presence; diagnostics-fixture drift guard via the public `get_fixture_snapshot` seam; `disclaimer == NFA_DISCLAIMER`; offline contract (monkeypatched `urllib.request.urlopen` + `requests`); pin that `build_crisis_dossier` is not called; pin that `classify_regime` is not called; markdown renderer returns `str`, contains title and window_id, contains `## Disclaimer`, ends with a single trailing newline, is deterministic, rejects non-`Mapping`, rejects missing keys. Existing `tests/test_report_registry.py` updated: `formats == ["json", "markdown"]`, and the old `test_macro_composite_windows_are_empty_by_design` is replaced by `test_macro_composite_windows_match_pinned_set` which asserts the windows match `list_macro_composite_windows()`.
- No CLI / API / Streamlit / manifest / audit / persistence wiring in this slice — builder-only. Downstream surfaces will layer over the generic `build_report_manifest` + `store_report_artifact` + audit-chain helpers without modifying this module. No new dependencies. No edits to `cbsrm/reporting/report_renderer.py`, `cbsrm/reporting/html_renderer.py`, `cbsrm/reporting/manifest.py`, `cbsrm/reporting/persistence.py`, `cbsrm/reporting/audit_manifest.py`, `cbsrm/audit/**`, `cbsrm/diagnostics/**`, `cbsrm/macro/**`, `cbsrm/cli.py`, `cbsrm/api/routes.py`, `dashboard/**`, `pyproject.toml`, `cbsrm/__init__.py`, or `.github/workflows/**`.

**`cbsrm.reporting.registry` — deterministic report catalog**
- New module `cbsrm/reporting/registry.py` exposing `get_report_catalog()`, `list_report_ids()`, `get_report_metadata(report_id)`, and `REPORT_REGISTRY_VERSION = "1.0.0"`. Pure metadata layer — never executes a report, never touches the network, never writes to disk. All return values are fresh deep copies, JSON-serializable, deterministic.
- Bridges the v0.8 hardcoded `crisis-dossier` surface toward a future SaaS-style report catalog. For each report the catalog returns `id`, `title`, `description`, `formats`, `windows`, and `surfaces` (CLI invocation, API routes, Streamlit command). For `crisis-dossier`, `windows` is sourced live from `cbsrm.diagnostics.list_dossier_windows()` so the catalog cannot drift as new dossier fixtures land.
- `get_report_metadata` raises `ValueError` with the supported-id list for unknown ids, mirroring the `get_fixture_snapshot` error contract elsewhere in the package.
- New public re-exports from `cbsrm.reporting.__init__`: `get_report_catalog`, `list_report_ids`, `get_report_metadata`, `REPORT_REGISTRY_VERSION`. Existing renderer surface (`render_dossier_markdown`, `build_report_payload`, `REPORT_RENDERER_VERSION`, `NFA_DISCLAIMER`) unchanged.

**`cbsrm.api.routes` — read-only catalog endpoint**
- `GET /reports` → `{"reports": [...]}` JSON catalog, using the same lazy-FastAPI route style as the rest of `cbsrm/api/routes.py`. Pure pass-through over `cbsrm.reporting.get_report_catalog()`. Does not execute any report, does not change any existing endpoint, does not introduce a new dependency.
- Existing `/reports/crisis-dossiers`, `/reports/crisis-dossiers/{window_id}`, and `/reports/crisis-dossiers/{window_id}/markdown` routes preserved bit-for-bit.

**`cbsrm reports` — CLI catalog command**
- New subcommand `cbsrm reports` prints the deterministic registry catalog as JSON (`indent=2`, `ensure_ascii=False`), using the existing `_write_stdout_utf8_safe` helper for Windows-cp1252-safe output. Pure pass-through over `cbsrm.reporting.get_report_catalog()`. Mirrors the `GET /reports` API endpoint for CLI/API parity. Metadata-only — the command never executes a report, never touches the network, never writes to disk. No existing CLI command modified.

**Persistence exposure across CLI / API / Streamlit (`cbsrm crisis-dossier --store-db`, `?store=true` + `GET /reports/stored/{output_sha256}`, sidebar "Persist report to store" button)**
- `cbsrm crisis-dossier WINDOW --store-db PATH` opens (or creates) a sqlite report-artifact store at PATH, persists `output_text` + the deterministic manifest content-addressed by `output_sha256` via `store_report_artifact(...)`, and prints one stderr line: `stored: output_sha256=<hash> was_existing=<bool> db=<path>`. Independent of `--manifest` / `--audit-db`; stdout bytes preserved byte-for-byte. The manifest is built **once** and reused across `--manifest` / `--audit-db` / `--store-db` so the file, the audit row, and the stored row all describe the same bytes. Bad path → exit code 2 with `error: cannot open report store '<path>': <msg>` and no traceback.
- HTTP API: `GET /reports/crisis-dossiers/{window_id}?store=true` adds a `stored` key to the JSON envelope when the app was constructed via `build_app(report_store_db_path=PATH)`. When the app is **not** configured with a store path, `?store=true` returns `HTTP 400` with `{detail:{error,hint}}` — a request **never** supplies a filesystem path, so there is no path-traversal surface. The `stored` key projection is `{output_sha256, was_existing, byte_length, content_type, created_at_utc}` (intentionally omits `output_text` and `manifest`, both already in the envelope). New `GET /reports/stored/{output_sha256}` lookup returns the full stored row on 200, 404 with `{detail:{error,output_sha256}}` for an unknown hash, and the same 400 with hint when the app is unconfigured. Default `{report, dossier}` envelope unchanged on a configured app.
- Streamlit crisis-dossier viewer: new opt-in sidebar block **"Report store (opt-in)"** below the existing audit-chain block. Reads DB path from env var `CBSRM_REPORT_STORE` by default; sidebar text input override per session. Single explicit button **"Persist report to store"** disabled when no path is configured. On click, calls `store_report_artifact(store_path, output_text=artifacts["markdown"], manifest=artifacts["manifest"])` and shows row metadata (`output_sha256`, `was_existing`, `byte_length`, `created_at_utc`) as a sidebar success block. `sqlite3.OperationalError` is caught and shown as a sidebar error. New Streamlit-free pure helper `resolve_report_store_path(*, sidebar_override, env=None) -> str | None` parallel to the existing `resolve_audit_db_path`; same precedence (sidebar override wins, env fallback, both blank → `None`, whitespace stripped). `build_viewer_artifacts(window_id)` unchanged.
- 9 new CLI tests in `tests/test_cli_crisis_dossier.py` (11 with parametrization across json / markdown / html): DB created + one row written; `was_existing=False` on first store; `was_existing=True` on second store (idempotency, row count stays 1); stderr line shape pinned (64-hex hash, path, bool); stdout byte-identical with vs without `--store-db`; `--store-db` alone works; `--store-db + --audit-db` together both fire and the audit chain records the matching `REPORT_EXPORTED` row; format-suffix integrity across json / markdown / html; bad path → exit 2 + clean stderr + no traceback. 10 new API tests in `tests/test_api_crisis_dossiers.py`: default envelope unchanged; `?store=true` 400 when unconfigured; configured `build_app(report_store_db_path=...)` + `?store=true` adds `stored` key; pinned 5-field projection; `was_existing` flips on second call; `manifest=true&audit=true&store=true` returns all three keys with audit subject matching; lookup endpoint 404 for unknown hash; lookup endpoint 200 full row after persistence via JSON endpoint; lookup endpoint 400 when unconfigured; default envelope on configured app is byte-identical to unconfigured app. 8 new Streamlit tests in `tests/test_streamlit_crisis_dossier_viewer.py`: 7 for `resolve_report_store_path` (parallel to `resolve_audit_db_path` shape — sidebar override, env fallback, both-empty → `None`, whitespace-only sidebar lets env win, env stripped, blank env → `None`, `None` sidebar uses env), plus an end-to-end integration test that stores `artifacts["markdown"]` + `artifacts["manifest"]` to a `tmp_path` DB and verifies `output_sha256 == sha256(artifacts["markdown"])` plus a `get_report_artifact` round-trip.
- No new dependencies. No edits to `cbsrm/reporting/persistence.py`, `cbsrm/reporting/manifest.py`, `cbsrm/reporting/audit_manifest.py`, `cbsrm/reporting/registry.py`, renderers, `cbsrm/reporting/__init__.py`, `cbsrm/audit/**`, `cbsrm/diagnostics/**`, `cbsrm/macro/**`, `dashboard/streamlit_app.py`, `dashboard/report_catalog_viewer.py`, `pyproject.toml`, `cbsrm/__init__.py`, or `.github/workflows/**`. No audit-chain coupling — the two surfaces converge naturally on `output_sha256` as the join key. The existing `audit_chain` closure variable from PR #15 is joined by `report_store_db_path` as a second closure variable; both operator-config, neither request-supplied.

**`cbsrm.reporting.persistence` — content-addressed sqlite report artifact store**
- New module `cbsrm/reporting/persistence.py` exposing `REPORT_STORE_VERSION = "1.0.0"`, `init_report_store(db_path)`, `store_report_artifact(db_path, *, output_text, manifest, content_type=None, created_at_utc=None) -> dict`, `get_report_artifact(db_path, output_sha256) -> dict | None`, and `list_report_artifacts(db_path, *, limit=100) -> list[dict]`. Re-exported from `cbsrm.reporting`. Single-operator scope; stdlib only (`sqlite3` + `json` + `hashlib`). No new dependencies.
- Schema: one table `cbsrm_report_artifacts` with `output_sha256` PRIMARY KEY + `report_id` / `window_id` / `format` / `source` / `output_text` / `manifest_json` / `content_type` / `byte_length` / `created_at_utc`. Four indexes (`report_id`, `window_id`, `format`, `created_at_utc DESC`). Idempotent schema creation (`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`).
- `store_report_artifact` is content-addressed and idempotent via `INSERT OR IGNORE`: same hash → no overwrite; pre-existing `created_at_utc` and bytes preserved; return dict carries `was_existing=True`. Defensive validation: hash mismatch between `manifest["hashes"]["output_sha256"]` and `sha256_text(output_text)` raises `ValueError`; non-str `output_text` raises `TypeError`; missing required manifest fields raise `ValueError`; blank `db_path` raises `ValueError`. `sqlite3.OperationalError` from bad paths propagates so callers can surface a user-facing error (mirrors `stamp_manifest_to_db_path`).
- Content-type defaulting: `json → application/json`, `markdown → text/markdown; charset=utf-8`, `html → text/html; charset=utf-8`. Caller may override explicitly. `created_at_utc` is opt-in (caller-supplied str → stored verbatim, no parsing); when omitted the helper sets `datetime.now(timezone.utc).isoformat()` — same pattern as `AuditChain.append`. Tests inject a fixed string for deterministic storage rows. `manifest_json` serialised with `json.dumps(manifest, sort_keys=True, ensure_ascii=False)`; `get` / `list` decode it back to a dict in the returned `manifest` field.
- No CLI / API / Streamlit consumer in this slice (foundation only; matches the manifest + audit-chain foundation rollout pattern). No audit-chain writes — the two surfaces converge naturally on `output_sha256` as the shared join key but each does its own thing.
- 30 new tests in `tests/test_report_persistence.py` (32 with content-type parametrization across json / markdown / html): version shape; init creates schema and is idempotent; blank `db_path` raises; store inserts row + required fields; deterministic store row with injected timestamp; duplicate store returns `was_existing=True` and preserves original `created_at_utc` (row count stays 1); hash mismatch raises (both tampered-hash and tampered-output paths); non-str `output_text` raises; non-Mapping manifest / missing required fields raise; content-type derivation parametrised over `json` / `markdown` / `html`; explicit content-type override; `created_at_utc` default shape / injection / blank-string rejection; `byte_length` matches UTF-8 byte count (and ≠ `len(str)`); `get` round-trip + `None` for unknown hash + blank-hash rejection; `list` returns rows DESC by `created_at_utc` with injected timestamps + limit respected + non-positive-limit rejection; manifest round-trip; offline contract (monkeypatched `urlopen` + `requests`); end-to-end crisis-dossier render + manifest + store + sha256 parity; bad path raises `sqlite3.OperationalError` for both `init` and `store`.
- No edits to `cbsrm/audit/**`, `cbsrm/reporting/manifest.py`, `cbsrm/reporting/audit_manifest.py`, `cbsrm/reporting/registry.py`, renderers, `cbsrm/cli.py`, `cbsrm/api/routes.py`, `dashboard/**`, `cbsrm/diagnostics/**`, `cbsrm/macro/**`, `pyproject.toml`, `cbsrm/__init__.py`, or `.github/workflows/**`.

**Streamlit audit-chain export stamping — opt-in sidebar surface (closes the v0.9 audit-stamping trio)**
- New generic helper `cbsrm.reporting.stamp_manifest_to_db_path(manifest, db_path) -> dict` in `cbsrm/reporting/audit_manifest.py`. Thin path-based wrapper over the existing `stamp_manifest_to_chain`: opens a `sqlite3.Connection`, wraps in `AuditChain`, stamps, closes the connection in `finally`. Returns the same 6-key row metadata. Validates non-empty `db_path` (`ValueError` on blank/`None`). Propagates `sqlite3.OperationalError` on unwritable paths so callers can surface a user-facing error. Re-exported from `cbsrm.reporting`. Deliberately not Streamlit-coupled by name — a future CLI refactor can collapse the inline `sqlite3.connect → AuditChain → stamp_manifest_to_chain → close` block to one call.
- Streamlit crisis-dossier viewer (`dashboard/crisis_dossier_viewer.py`): new opt-in sidebar block **"Audit chain (opt-in)"**. Reads audit DB path from env var `CBSRM_AUDIT_DB` by default; a sidebar text input lets the operator override per session. Single explicit button **"Stamp manifest to audit chain"** is disabled when no path is configured. On click, calls `stamp_manifest_to_db_path(artifacts["manifest"], db_path)` and shows row metadata (`row_id`, `subject`, `hash`, `ts`) as a sidebar success block. `sqlite3.OperationalError` (bad path) is caught and shown as a sidebar error. Main report pane and existing Markdown / JSON / HTML / Manifest download buttons unchanged.
- New Streamlit-free pure helper `resolve_audit_db_path(*, sidebar_override, env=None) -> str | None` in the same module: non-blank sidebar override wins, else non-blank `CBSRM_AUDIT_DB` from env, else `None`. Whitespace-only strings on either side are treated as unset. Fully testable without Streamlit installed.
- `build_viewer_artifacts(window_id)` is **unchanged** — purity / determinism / Streamlit-free contract preserved. Stamping never happens inside the artifact-build path; it requires the explicit sidebar button.
- 7 new tests in `tests/test_audit_manifest.py` for the path-based helper: creates DB + appends row; 6-key row shape pinned to `report:crisis-dossier:2008Q4:json`; two calls link via `prev_hash`; `AuditChain.verify()` clean after multi-write across formats; connection closes (DB reopens with no lock); bad path raises `sqlite3.OperationalError`; blank/`None` `db_path` raises `ValueError`. 8 new tests in `tests/test_streamlit_crisis_dossier_viewer.py`: 7 for `resolve_audit_db_path` (sidebar override wins, env fallback, both-empty → `None`, whitespace-only sidebar lets env win, env value stripped, blank env → `None`, `None` sidebar uses env), plus an end-to-end integration test that calls `stamp_manifest_to_db_path` against a real `build_viewer_artifacts` manifest and asserts the subject is `"report:crisis-dossier:2008Q4:markdown"`. No live-Streamlit driving.
- No new dependencies. No edits to `cbsrm/audit/chain.py`, `cbsrm/reporting/manifest.py`, `cbsrm/reporting/registry.py`, renderers, `cbsrm/cli.py` (CLI inline-stamp pattern preserved; one-line refactor to use the new helper is a future operator-gated slice), `cbsrm/api/routes.py`, `dashboard/streamlit_app.py`, `dashboard/report_catalog_viewer.py`, `pyproject.toml`, `cbsrm/__init__.py`, or `.github/workflows/**`.

**`cbsrm crisis-dossier --audit-db PATH` — CLI audit-chain export stamping**
- New optional `--audit-db PATH` flag on the existing `crisis-dossier` CLI command. When supplied, opens (or creates) a sqlite DB at PATH, wraps it in the existing `AuditChain`, and appends the export manifest as one `REPORT_EXPORTED` row via the v0.9 `stamp_manifest_to_chain` helper. The DB file is created if it does not exist; `AuditChain._ensure_schema` is idempotent.
- One concise stderr line printed only when the flag is supplied: `audit: row_id=<id> subject=<subject> hash=<hash>`. Stdout report bytes are byte-identical with vs without `--audit-db` (pinned by test).
- `--audit-db` is independent of `--manifest`. When both flags are supplied the same manifest dict drives both side effects (one `build_report_manifest` call, then the same dict is written to disk and stamped into the chain) — guarantees the manifest file and the audit row describe bit-identical bytes. The manifest file content is byte-identical with vs without `--audit-db` (no audit metadata leakage).
- Bad `--audit-db PATH` (non-existent parent dir, permission denied) raises `sqlite3.OperationalError`; the CLI catches it, prints `error: cannot open audit db '<path>': <msg>` to stderr, and exits with code 2 (no traceback). Pinned by test.
- Stamps `source="cli"`. Subject pattern `"report:crisis-dossier:<window>:<format>"` works across all three formats (json / markdown / html). Existing `cbsrm verify-audit --db PATH` reads back rows written by `--audit-db`.
- 13 new tests in `tests/test_cli_crisis_dossier.py` (15 with parametrization across the 3 formats): DB created + one row written; stderr line shape (audit: prefix, row_id / subject / hash, 64-hex hash); stdout byte-identical with/without; `--audit-db` alone audits without manifest file; both flags together write both surfaces and keep manifest file byte-identical to the no-audit case; subject `report:crisis-dossier:2020Q1:{fmt}` across formats; payload `source="cli"`; two runs append two linked rows (`prev_hash` chain); `AuditChain.verify()` clean after multi-run; bad path fails with exit 2 and no traceback.
- No edits to `cbsrm/audit/chain.py`, `cbsrm/reporting/audit_manifest.py`, `cbsrm/reporting/manifest.py`, `cbsrm/reporting/registry.py`, renderers, `cbsrm/api/routes.py`, `dashboard/**`, `pyproject.toml`, `cbsrm/__init__.py`, or `.github/workflows/**`. No new dependencies. Streamlit audit-chain integration still deferred.

**`cbsrm.reporting.audit_manifest` + `GET /reports/crisis-dossiers/{window_id}?audit=true` — audit-chain export stamping**
- New module `cbsrm/reporting/audit_manifest.py` exposing `AUDIT_EVENT_KIND = "REPORT_EXPORTED"`, `manifest_subject(manifest) -> str`, and `stamp_manifest_to_chain(chain, manifest) -> dict`. Bridges the v0.9 report-manifest layer into the existing `cbsrm/audit/chain.py` tamper-evident log without modifying audit internals: passes the kind as a raw string (`AuditChain.append` already supports raw-string kinds), constructs an `AuditEvent`, appends it, and reads back the canonical row to surface `{row_id, hash, prev_hash, ts, subject, kind}`. Subject pattern `"report:{report_id}:{window_id}:{format}"` with `"-"` placeholder for missing window. Re-exported from `cbsrm.reporting`.
- JSON crisis-dossier API endpoint extended with an opt-in `audit: bool = False` query param. Default (`audit=false`) preserves the v0.8 / prior-slice envelope byte-for-byte. `?audit=true` auto-builds the manifest (no need to also pass `manifest=true`), appends it to the app's `AuditChain` as one `REPORT_EXPORTED` row, and surfaces `{report, dossier, manifest, audit}` where `audit` is the row metadata. CLI ↔ API hash parity preserved: the manifest's `output_sha256` still hashes the canonical payload JSON (not the self-referential envelope).
- 17 new tests in `tests/test_audit_manifest.py` (helper unit tests against an in-memory sqlite `AuditChain`): `AUDIT_EVENT_KIND` constant, `manifest_subject` full / missing-window / empty-window / format-propagation / invalid-`report_id` / invalid-`format`, `stamp_manifest_to_chain` returned keys / row exists / kind / subject / payload round-trip / two-event linked `prev_hash` / `chain.verify()` after multiple stamps / type guard on non-`AuditChain` arg / ISO-8601 `ts` shape / subject queryable via `chain.query_subject`. 10 new tests in `tests/test_api_crisis_dossiers.py` covering the 4-row response-shape matrix, audit-payload metadata, pinned subject, `REPORT_EXPORTED` kind, integration with `GET /audit/{subject}`, no-row-written-when-`audit=false`, 404 path doesn't append.
- Internal refactor: closure variable `audit` (the `AuditChain` instance in `build_app`) renamed to `audit_chain` to free the name for the new query parameter. Three call sites updated. No behaviour change to `/audit/{subject}` or `/audit/verify`.
- No edits to `cbsrm/audit/chain.py`, `cbsrm/audit/audited_indicator.py`, `cbsrm/reporting/manifest.py`, `cbsrm/reporting/registry.py`, `cbsrm/reporting/report_renderer.py`, `cbsrm/reporting/html_renderer.py`, `cbsrm/cli.py`, `dashboard/**`, `cbsrm/diagnostics/**`, `cbsrm/macro/**`, `pyproject.toml`, `cbsrm/__init__.py`, or `.github/workflows/**`. No new dependencies. CLI and Streamlit audit-chain integration deferred to future slices.

**Manifest exposure across CLI / API / Streamlit surfaces (`cbsrm crisis-dossier --manifest`, `?manifest=true`, "Download Manifest" button)**
- `cbsrm crisis-dossier WINDOW --manifest PATH` writes a deterministic export-time manifest JSON to PATH (UTF-8, `indent=2`, `ensure_ascii=False`, trailing newline). Stdout report output is byte-identical with or without the flag — the manifest is purely additive. Manifest is stamped `source="cli"`; `output_sha256` matches the bytes written to stdout for any format (json / markdown / html). `--manifest` works with all three `--format` choices.
- HTTP API: `GET /reports/crisis-dossiers/{window_id}?manifest=true` appends a `manifest` key to the existing `{report, dossier}` envelope. Default path (`manifest` query absent) preserves the existing envelope byte-for-byte. Manifest is stamped `source="api"`, `format="json"`; `output_sha256` hashes the canonical payload JSON text (matching CLI `--format json` output byte-for-byte) — NOT the self-referential envelope-with-manifest. Markdown and HTML endpoints are unchanged in this slice. Unknown windows still return 404 with the same detail contract.
- Streamlit crisis-dossier viewer: `build_viewer_artifacts(window_id)` adds two new keys, `manifest` (dict) and `manifest_json` (pretty-printed JSON string). Manifest describes the Markdown rendering displayed inline (`source="streamlit"`, `format="markdown"`). The download row in `render()` goes from 3 to 4 columns; a fourth "Download Manifest (.manifest.json)" button (MIME `application/json`, filename `cbsrm_crisis_dossier_<window_id>.manifest.json`) sits beside the existing Markdown / JSON / HTML buttons.
- 7 new CLI tests in `tests/test_cli_crisis_dossier.py` (9 with parametrization across json/markdown/html): manifest file written; source pinned to `cli`; format matches `--format` choice; `output_sha256` matches captured stdout bytes; window_id pinned; no file when flag omitted; stdout byte-identical with vs without the flag. 7 new API tests in `tests/test_api_crisis_dossiers.py`: default envelope unchanged; `?manifest=true` adds the `manifest` key; source `api`; format `json`; `output_sha256` matches canonical payload text; unknown window still 404; byte-identical repeated calls. 7 new Streamlit tests in `tests/test_streamlit_crisis_dossier_viewer.py`: artifacts include `manifest` and `manifest_json`; source `streamlit`; format `markdown`; `output_sha256` matches `artifacts["markdown"]`; `manifest_json` round-trips through `json.loads`; window_id pinned; determinism across calls.
- No edits to `cbsrm/reporting/manifest.py` (foundation already shipped). No persistence layer, no audit-chain writes, no new dependencies, no version-metadata changes.

**`cbsrm.reporting.manifest` — deterministic export-time manifest layer**
- New module `cbsrm/reporting/manifest.py` exposing `build_report_manifest(...)` (keyword-only, required `report_id` / `output_text` / `output_format`; optional `window_id` / `source` / `dossier` / `payload` / `generated_at_utc`), `sha256_text(text)`, `sha256_jsonable(obj)`, and `MANIFEST_VERSION = "1.0.0"`. Pure metadata layer — describes what was rendered (report id, window, format, source, output sha256, package + renderer + registry + dossier + fixture versions) without re-rendering or executing anything. Re-exported from `cbsrm.reporting`.
- **Deterministic by default.** No wall-clock anywhere. `generated_at_utc` is opt-in (caller-supplied string, stored verbatim, no parsing). Two calls with the same inputs produce equal manifests.
- `sha256_jsonable` canonicalises the payload via `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",",":"))` so the hash is dict-key-order-independent and Unicode-safe (`→` round-trips intact). `sha256_text` is a thin wrapper around `hashlib.sha256(...).hexdigest()` with explicit `str` validation.
- Manifest schema: `{manifest_version, report_id, window_id, format, source, generated_at_utc, versions:{cbsrm, registry, report_renderer, html_renderer, dossier, fixture}, hashes:{output_sha256[, payload_sha256]}, disclaimer_present}`. JSON-serializable. `payload_sha256` only present when a `payload` is supplied. `disclaimer_present` is a substring check against the canonical NFA `Disclaimer` heading: true for the Markdown, HTML, and standard JSON-envelope crisis-dossier exports (the JSON envelope embeds the disclaimer under `payload["report"]["disclaimer"]`); false when a caller emits a stripped-down output. The flag tracks actual bytes, not assumptions about format.
- Validation: empty/non-str `report_id` → `ValueError`; non-str `output_text` → `TypeError`; `output_format` outside `{"json","markdown","html"}` → `ValueError`; `source` outside `{"python","cli","api","streamlit"}` → `ValueError`; non-str injected `generated_at_utc` → `TypeError`.
- 32 unique tests (36 with parametrization over the 4 supported `source` values) in `tests/test_report_manifest.py`: `MANIFEST_VERSION` shape, `sha256_text` hashlib parity / determinism / unicode-safety / non-str rejection, `sha256_jsonable` key-order-independence / value-sensitivity / unicode-safety, end-to-end Markdown + HTML + JSON manifests, default-no-timestamp determinism, injected-timestamp verbatim preservation, payload hash conditionality, version field population from packages and dossier spec, disclaimer-flag true on Markdown/HTML/JSON crisis-dossier exports + false on disclaimer-stripped synthetic outputs, JSON round-trip, every validation path, every supported source value, no-network offline contract.
- No CLI / API / Streamlit integration in this slice — Python-only foundation. Downstream consumers (persistence, audit-chain stamping, `--emit-manifest` CLI flag, API manifest headers, Streamlit manifest panel, composer `PipelineRecord`) are separate operator-gated slices on top of this foundation. No new dependencies; `hashlib` and `json` are stdlib.

**`dashboard/crisis_dossier_viewer.py` — HTML download button (Streamlit HTML surface parity)**
- The crisis-dossier Streamlit viewer now offers a third download button next to the existing Markdown (`.md`) and JSON (`.json`) buttons: **Download HTML (.html)**, served from `cbsrm.reporting.render_dossier_html(dossier)` and saved as `cbsrm_crisis_dossier_<window_id>.html` with MIME `text/html`. Closes the HTML surface trio (CLI ⊕ API ⊕ Streamlit) over the same renderer.
- `build_viewer_artifacts(window_id)` now also returns an `html` field. The helper remains pure / deterministic / Streamlit-free. The `render()` layout uses a 3-column `st.columns(3)` for the download buttons; existing Markdown and JSON button behaviour is preserved bit-for-bit.
- Requires the optional `cbsrm[html]` extra at runtime (installed in CI by the prior workflow change). The helper raises a friendly `RuntimeError` with install hint if `markdown` is unavailable. No new dependency added.
- 3 new tests in `tests/test_streamlit_crisis_dossier_viewer.py` (parametrized over the 3 dossier windows): `html` artifact is a string starting with `<!DOCTYPE html>`/`<html`, contains the window id and the disclaimer, and is byte-identical across repeated calls. The existing 6 tests for markdown/json/dossier/streamlit-import-safety are unchanged. `pytest.importorskip("markdown")` is added between the streamlit-only test (which still runs without markdown) and the artifact tests (which now require markdown), so test discovery degrades gracefully on environments without the optional extra.

**`cbsrm crisis-dossier --format html` + `GET /reports/crisis-dossiers/{window_id}/html` — CLI / API exposure of the HTML renderer**
- `cbsrm crisis-dossier WINDOW --format html` adds a third format alongside the existing `json` (default) and `markdown` choices. Thin pass-through over `cbsrm.reporting.render_dossier_html(dossier, title_prefix=...)`, written via the existing `_write_stdout_utf8_safe` helper for Windows-cp1252-safe output. `--title-prefix` now applies to both `markdown` and `html` formats (previously markdown-only); behaviour for `json` and `markdown` is unchanged byte-for-byte.
- `GET /reports/crisis-dossiers/{window_id}/html` mirrors the existing markdown endpoint at the HTTP API surface. Returns `text/html; charset=utf-8` via `fastapi.responses.HTMLResponse`. Body is identical to the CLI output. Unknown windows surface the same 404 contract (`{"detail": {"error": ..., "window_id": ..., "supported_windows": [...]}}`, no traceback) via the existing `_resolve_dossier_or_404` helper. Lazy imports keep `cbsrm.api.routes` import-safe without the `cbsrm[html]` extra.
- 6 new CLI tests in `tests/test_cli_crisis_dossier.py` (`<!DOCTYPE html>` start, all 3 windows × html, disclaimer preserved, `title_prefix` in `<title>` + `<h1>`, byte-identical determinism, argparse accepts `html` and still rejects bogus formats with no traceback).
- 7 new API tests in `tests/test_api_crisis_dossiers.py` (route registered, 200 on 2008Q4, content-type `text/html; charset=utf-8`, body contains DOCTYPE / window / disclaimer, all 3 windows parametrized, 404 contract on unknown window, byte-identical determinism across calls).
- No existing CLI/API behaviour modified. No renderer/dossier/macro/network changes. No new dependencies — relies on the optional `cbsrm[html]` extra installed in CI by the prior slice. No Streamlit changes in this slice (deferred to a future HTML-download slice).

**`cbsrm.reporting.html_renderer` — deterministic HTML report renderer (browser print-to-PDF)**
- New module `cbsrm/reporting/html_renderer.py` exposing `render_dossier_html(dossier, *, title_prefix=None, embed_stylesheet=True) -> str` and `HTML_RENDERER_VERSION = "1.0.0"`. Composition: pipes the existing `render_dossier_markdown` output through the `markdown` library (lazy import) and wraps the result in a minimal HTML shell with an embedded print-friendly stylesheet adapted from the existing whitepaper-print tooling. **Not** a binary PDF byte stream — output is HTML suitable for browser "File → Print → Save as PDF"; a real `reportlab`/`weasyprint` PDF backend is deferred to a future slice.
- `embed_stylesheet=False` returns the body-only HTML fragment for composition into a larger document. Pure, deterministic, offline — same dossier in → byte-identical HTML out, no network, no file writes.
- Missing `markdown` raises a friendly `RuntimeError` with the install hint `pip install cbsrm[html]`. New optional extra `[html] = ["markdown>=3.5,<4"]` in `pyproject.toml`; `[all]` extra updated. No new install-time dependency for users not exporting HTML.
- 13 tests in `tests/test_report_renderer_html.py` (15 with parametrization across the 3 dossier windows): lazy-import safety, version shape, missing-`markdown` error path, per-window happy path, structural content (window id / title / disclaimer), stylesheet embedding default, `embed_stylesheet=False` body-only mode, `title_prefix` propagation into `<title>` and `<h1>`, byte-identical determinism, no-network offline contract, validation delegation. No existing test modified.
- CI workflow `.github/workflows/test.yml` install command extended from `[dev,api,indicators]` to `[dev,api,indicators,html]` so the 10-job matrix actually exercises the HTML path.
- No CLI / HTTP API / Streamlit surface change in this slice. CLI/API/Streamlit HTML exposure is a separate operator-gated slice on top of this foundation.

**`cbsrm.reporting.registry` — second registry entry: `macro-composite`**
- Adds a metadata-only `macro-composite` entry to the v0.9 report registry: id `macro-composite`, title "Macro Composite Snapshot", `formats=["json"]`, `windows=[]`, surfaces pointing back at the catalog endpoints (`cbsrm reports`, `GET /reports`, the landing-page Streamlit command). Description names the operator-driven helpers (`cbsrm.macro.classify_regime`, `cbsrm.macro.classify_phase`) but the entry itself adds no executable surface and invents no live-data behavior on top of v0.8.
- Exercises the `_REPORT_BUILDERS` abstraction with a real second entry. The existing CLI / API / Streamlit catalog surfaces (`cbsrm reports`, `GET /reports`, `dashboard/report_catalog_viewer.py`) pick up the new entry automatically; no code in those layers was touched.
- New deterministic-ordering test pins insertion order as `[crisis-dossier, macro-composite]`. 7 new tests across registry, API, CLI, and Streamlit catalog suites. No existing test modified.

**`dashboard/report_catalog_viewer.py` — Streamlit landing page for the report registry**
- New standalone offline Streamlit page that lists every report in `cbsrm.reporting.get_report_catalog()` — id, title, description, supported formats, supported windows, and the per-report CLI / HTTP API / Streamlit surfaces — and points users to the existing `dashboard/crisis_dossier_viewer.py` for per-window detail. Mirrors the `cbsrm reports` CLI command and the `GET /reports` HTTP endpoint over the same registry, completing CLI / API / Streamlit parity for the v0.9 catalog surface.
- All data logic lives in `build_catalog_view(catalog=None) -> dict` — pure, Streamlit-free, deterministic, no network, no report execution. Accepts an optional pre-fetched catalog dict as a test-injection seam (so callers can drive the viewer with a synthetic catalog without monkeypatching the registry).
- Streamlit is imported lazily inside `render()`, keeping the module import-safe (and unit-testable) in environments without Streamlit installed.
- 9 tests in `tests/test_streamlit_report_catalog_viewer.py` (module loaded via `importlib.util.spec_from_file_location`, same pattern as the existing crisis-dossier viewer test): import without Streamlit; default call uses the live registry; default output matches `get_report_catalog()`; output is JSON-serializable; caller-supplied catalog overrides the registry without falling back to it; monkeypatched `build_crisis_dossier` proves the viewer never executes a report; v0.8 crisis-dossier metadata pinned (formats / windows / surfaces); byte-identical determinism across calls; mutation-isolation across calls.

---

## [0.8.0] — 2026-05-24

> Annotated tag `v0.8.0` at commit `410e3ac9`. 555/555 tests passing at
> the release commit. Three front-ends (CLI / FastAPI / Streamlit) with
> bit-for-bit parity over the v0.8 research flow. Offline-deterministic
> posture pinned by tests.

### Added — v0.8.0 milestone: crisis-window research flow + report renderer + CLI/API/Streamlit front-ends

**`dashboard/crisis_dossier_viewer.py` — offline Streamlit crisis-dossier viewer**
- Standalone Streamlit page (separate file from `dashboard/streamlit_app.py`, which is left untouched) that mirrors the v0.8 report surface on the desktop: selectbox over `list_dossier_windows()` → `build_crisis_dossier` → `render_dossier_markdown` displayed inline plus Markdown (`.md`) and JSON (`.json`) download buttons. The JSON download uses `ensure_ascii=False` so the literal `→` composition arrow survives in the file.
- All data logic lives in `build_viewer_artifacts(window_id) -> dict` — pure, Streamlit-free, deterministic, no network. The Streamlit `render()` function is a thin presentation wrapper that imports Streamlit lazily, so the module itself is import-safe (and unit-testable) in environments without Streamlit installed.
- Offline by design — no FRED key, no live data, no API-server dependency, no auth/billing/PDF/persistence.
- 6 tests in `tests/test_streamlit_crisis_dossier_viewer.py` (module loaded via `importlib.util.spec_from_file_location` so the new file does not require turning `dashboard/` into a package). Covers: import without Streamlit, all 3 windows × full artifact contract (window-id echo, dossier id, Markdown H1 + window-id + disclaimer, payload envelope, JSON round-trip, literal `→` preserved), `ValueError` on unknown window, byte-identical determinism.
- Bit-for-bit parity with `cbsrm crisis-dossier WINDOW` (CLI) and `GET /reports/crisis-dossiers/{window_id}...` (API). All three front-ends share the same dossier + reporting composition; no methodology added in this slice.

**`cbsrm.api.routes` — read-only FastAPI crisis-dossier report endpoints**
- `GET /reports/crisis-dossiers` → `{"windows": ["2008Q4", "2020Q1", "2023Q1"]}` (live from `list_dossier_windows()` so the set stays in sync as fixtures evolve).
- `GET /reports/crisis-dossiers/{window_id}` → the `{report: {...}, dossier: {...}}` JSON envelope, identical to `cbsrm crisis-dossier WINDOW --format json`.
- `GET /reports/crisis-dossiers/{window_id}/markdown` → `PlainTextResponse` with media type `text/markdown; charset=utf-8`; body identical to `cbsrm crisis-dossier WINDOW --format markdown`.
- Unknown `window_id` → HTTP 404 with `{"detail": {"error": "...", "window_id": "...", "supported_windows": [...]}}`. No traceback exposed. Centralised in a private `_resolve_dossier_or_404` helper so the JSON and Markdown routes share the same error contract.
- Pure pass-through over `cbsrm.diagnostics.build_crisis_dossier` + `cbsrm.reporting.build_report_payload` / `render_dossier_markdown`. No methodology added. Reporting/dossier internals unchanged.
- Lazy imports inside each route body and inside `build_app` for FastAPI, Starlette `PlainTextResponse`, and the reporting/diagnostics layers, keeping `cbsrm.api.routes` import-safe in environments without the `cbsrm[api]` extras.
- 15 tests in `tests/test_api_crisis_dossiers.py` covering: offline app construction (route registration check + monkeypatched `urllib`/`requests` failure), list endpoint shape, JSON endpoint envelope for `2008Q4`, all 3 windows × both endpoints, 404 detail shape on both endpoints (incl. supported-window list + no-traceback contract), Markdown `content-type` + UTF-8 charset + `→` byte-level integrity, and read-only determinism (repeated calls byte-identical).

**`cbsrm crisis-dossier` — CLI export of crisis-window dossiers (JSON / Markdown)**
- New subcommand `cbsrm crisis-dossier WINDOW [--format json|markdown] [--title-prefix TEXT]`. Default format is `json`; `--title-prefix` applies to Markdown rendering only and is silently ignored for JSON.
- Composes `cbsrm.diagnostics.build_crisis_dossier` with `cbsrm.reporting.build_report_payload` / `render_dossier_markdown`. Pure pass-through — adds zero methodology, duplicates zero logic.
- Unknown windows exit with code 2 and a clean `error: unknown crisis-dossier window 'XYZ'. Supported windows: …` message on stderr (no traceback). Supported set is discovered live via `list_dossier_windows()` so it stays in sync as new dossier fixtures land.
- UTF-8-safe stdout writer (`_write_stdout_utf8_safe`) bypasses the Windows cp1252 console codepage by going through `sys.stdout.buffer.write(...encode("utf-8"))` when available, with a graceful text fallback. The renderer emits `→` and em-dashes; the old `print()` path would have crashed on a default Windows console.
- JSON output uses `ensure_ascii=False` so the literal `→` composition arrow round-trips through `json.loads` without escape-sequence noise.
- Offline by design — no live API calls, no file writes; explicit `test_no_external_network_io` regression test monkeypatches `urllib.request.urlopen` and `requests.Session.request` to fail on any call.
- 18 tests in `tests/test_cli_crisis_dossier.py` covering: default format, explicit JSON format, all 3 supported windows × both formats, Markdown structural sections (H2 headers + disclaimer), title-prefix application, unicode delivery (`→` literal in JSON and Markdown), unknown-window error path (no traceback, supported set listed), argparse rejection of invalid `--format` and missing window, byte-identical re-runs (determinism), and the no-network-IO contract.

**`cbsrm.reporting.report_renderer` — deterministic Markdown + JSON export of crisis-window dossiers**
- Pure function `render_dossier_markdown(dossier, *, title_prefix=None) -> str` turns the output of `build_crisis_dossier` into a publication-ready Markdown report: title, window-id + period, shock summary, phase classification (label / posture / dominant drivers), macro event score table, replay table, network stress summary, research notes, spec/version metadata, and a canonical NFA disclaimer footer.
- Pure function `build_report_payload(dossier) -> dict` wraps the dossier in a `{report: {...}, dossier: {...}}` envelope that round-trips cleanly through `json.dumps`. Recursive sanitizer handles numpy scalars, numpy arrays, pandas `Timestamp` values, sets/tuples, and non-finite floats (→ `None`).
- New subpackage `cbsrm.reporting/` (first member; module split chosen so future renderers — single-jurisdiction macro report, multi-jurisdiction composite report, etc. — slot in next to this one without coupling).
- Validation: non-Mapping input, missing required top-level keys, malformed `period`, and malformed `network_stress_summary` all raise `ValueError` with explicit guidance.
- Empty inner sections (`macro_event_scores=[]`, `replay_summary=[]`, `dominant_drivers=[]`) render as explicit `_(none)_` placeholders so reports remain well-formed.
- Offline by design — no live API calls, no file writes, no PDF generation, no web app, no auth, no billing. Explicit no-I/O regression test in the suite (no `urllib` / `requests` / `httpx` / `socket` / `sqlite3` / `subprocess` / file-`open` reachable in the rendering path).
- Canonical NFA disclaimer exported as `cbsrm.reporting.NFA_DISCLAIMER`; renderer version pinned at `REPORT_RENDERER_VERSION = "1.0.0"`, independent of the dossier spec version.
- 41 tests in `tests/test_report_renderer.py` covering: all 3 windows render, required Markdown sections, window-id / period / phase echoed, macro-event table, network-stress metrics, research notes preserved, spec versions, NFA disclaimer, title-prefix, determinism (Markdown and JSON), JSON payload schema, json.dumps round-trip, numpy scalar / Timestamp / NaN sanitization, validation paths, empty-section graceful rendering, no-I/O sanity, and an end-to-end dossier→Markdown→payload→JSON narrative.

**`cbsrm.diagnostics.crisis_dossiers` — historical crisis-window research dossiers**
- Pure function `build_crisis_dossier(window_id, *, fixtures=None, config=None)` composes the v0.8 stack (`macro_events.score_event` → `macro_replay.replay_macro_events` → `networks.debt_rank` → `macro.classify_phase`) into a single deterministic, fixture-backed research dossier. First reporting-ready artifact on top of v0.8.
- Three pinned canonical windows: `2008Q4` (credit/liquidity crisis, Lehman aftermath), `2020Q1` (COVID volatility shock), `2023Q1` (regional banking stress — SVB/SBNY/FRC).
- Output schema: `window_id`, `title`, `period`, `shock_summary`, `macro_event_scores`, `replay_summary`, `network_stress_summary`, `phase_label`, `dominant_drivers`, `risk_posture`, `research_notes`, `spec` (versioning + source attribution + composition trace).
- Fixtures are calibrated to plausible contemporaneous prints (e.g. NFP −240k Nov 2008 release, NFP −701k Apr 2020 release) but are pinned in-module for bit-for-bit determinism; operators wanting production runs should swap in real source data via the existing `cbsrm.data` adapters.
- 2023Q1 fixture deliberately demonstrates the macro-vs-network split: macro prints look benign, phase classifier returns `indeterminate`, but DebtRank against a thin-equity regional seed bank still reveals concentrated fragility.
- Companion helpers: `list_dossier_windows()`, `get_fixture_snapshot(window_id)`, `CRISIS_DOSSIER_WINDOWS` tuple.
- Manifest at `notebooks/crisis_replay/fixtures/crisis_windows.csv` (window_id / title / period / n_macro_events / n_price_series / n_banks / seed_node / shock_summary).
- Offline by design — explicit no-I/O regression test in the suite (no urllib / requests / httpx / socket / sqlite3 / subprocess imports reachable from the module).
- 32 tests in `tests/test_crisis_dossiers.py` covering all 3 window IDs, invalid IDs, schema completeness, phase-classifier integration, DebtRank integration, macro-event scoring integration, replay-surface integration, version metadata, caller-config echo, fixture-override seam, no-I/O sanity, narrative-text integrity, and determinism.

**`cbsrm.macro.phase_classifier` — Acemoglu-style deterministic phase classifier**
- Pure function `classify_phase(features, *, config=None)` labels a macro/market feature snapshot into one of 8 phases: `expansion`, `overheating`, `slowdown`, `contraction`, `disinflationary_recovery`, `stagflationary_stress`, `financial_stress`, `indeterminate`.
- Feature inputs (all optional, all z-scored, caller-supplied): `growth_z`, `inflation_z`, `unemployment_z` (or its synonym `labor_slack_z`), `rates_z`, `credit_spread_z`, `volatility_z`, `liquidity_z`, `systemic_risk_z`. Minimum 3 features required for a non-indeterminate label.
- Outputs `phase`, `score` (0..1 confidence), `dominant_drivers` (features with |z| ≥ 1, magnitude-sorted), `risk_posture` (`risk_on` / `balanced` / `defensive` / `risk_off` / `stress_mitigation`), `input_features_used`, `rule_version`, and a `spec` block with the human-readable rule book + config.
- Accepts dict, `pandas.Series`, or `pandas.DataFrame` (batch mode returns a DataFrame with one row per input row; original index preserved).
- Validation: non-finite values, unsupported feature keys, non-numeric values, empty DataFrames, and unknown input types all raise `ValueError`.
- `PhaseClassifierConfig` (frozen dataclass) exposes every threshold knob for caller-overridable rule tuning; `DEFAULT_CONFIG` ships as a singleton.
- Pure / deterministic / offline — research classification layer, **not** a trading or execution signal. Pairs with the v0.7 `macro_composite.classify_regime` 4-state regime tone.
- 32 tests in `tests/test_phase_classifier.py` covering all 8 phase rules, override precedence (financial_stress > overheating, stagflation > overheating), validation paths, DataFrame batch mode, `Series` input, synonym folding, dominant-driver sort order, custom-config behaviour, score bounds, and determinism.

**`cbsrm.networks.debt_rank` — pure-numpy DebtRank systemic-risk engine** (Battiston, Puliga, Kaushik, Tasca, Caldarelli 2012, *Scientific Reports*)
- Function `debt_rank(L, E, h0, v=None, max_iter=100, tol=1e-9)` returns a dict with `distress_final`, `distress_initial`, `debt_rank` (scalar), `node_contributions`, `iterations`, `converged`, `leverage_matrix`, and `economic_weights`.
- Constructs the leverage matrix `W[i,j] = min(L[i,j] / E[i], 1)` (self-loops zeroed, rows with non-positive equity zeroed) and runs the U/D/I state-machine cascade described in the paper.
- Caller may supply custom economic-importance weights `v` (auto-renormalized with a `RuntimeWarning` if they do not sum to 1); default is uniform `1/N`.
- Validation: shape mismatches, negative `L`, out-of-range `h0`, and negative `v` raise `ValueError`; negative equities are clipped to 0 with a `RuntimeWarning`.
- 20 tests in `tests/test_debt_rank.py` cover the 2/3-node chain cascades, scaling invariance, self-loop invariance, custom-`v` semantics, `max_iter` truncation, and every validation path. Pairs with the v0.7 Diebold-Yilmaz spillover indicator on the market-return side.

**`cbsrm.macro.macro_events` — discrete macro-event surprise scorer**
- Pure function `score_event(event, actual, consensus, previous=None, unit=None, history=None)` returns a normalised surprise (`surprise`, `surprise_z`, `abs_z`), a `direction` (`hotter_than_expected` / `cooler_than_expected` / `in_line`), a `severity` bucket (`trivial` / `mild` / `moderate` / `large` / `extreme`), and a coarse `risk_bias` tag (`rates_up_equities_down` etc).
- Event registry covers 12 prints: CPI, CORE_CPI, PCE, CORE_PCE, NFP, UNRATE, INITIAL_CLAIMS, GDP, RETAIL_SALES, ISM_MANUFACTURING, ISM_SERVICES, FOMC_RATE. Per-event polarity (e.g. UNRATE: higher = cooler) and conservative historical-surprise σ anchors so z-scoring works with zero caller-supplied history.
- z-score auto-prefers a caller-supplied surprise history (NaN/None filtered, ≥ 2 finite obs required, non-zero variance), otherwise falls back to the registry default scale.
- Companion helpers: `list_supported_events()`, `get_event_spec(event)`.
- Intended as *decision intelligence*, not a trading signal — coarse `risk_bias` mapping, in-line band defaults to |z| < 0.25 = `neutral`.
- 23 tests in `tests/test_macro_events.py`.
- **Docs** — `docs/v0.8_research_flow.md` walks the end-to-end research flow (macro shock → crisis replay → cross-asset spillover → systemic DebtRank), with runnable Stage 1 + Stage 3 snippets, forward-looking Stage 2 + Stage 4 snippets (Lanes A and B), and an API-consistency note section pre-flagged for a later unification pass.

**`cbsrm.diagnostics.macro_replay` — windowed price reaction around macro events**
- `replay_macro_events(events_df, prices_df, pre_window_days=5, post_window_days=5)` composes `macro_events.score_event` with as-of-or-prior price lookups on a wide-form price panel, returning a long-form DataFrame keyed by `(event, price_series)` with `surprise`, `surprise_z`, `direction`, `severity`, `risk_bias`, and pre/post log returns. Pure function, no I/O.
- Runnable walkthrough at `notebooks/crisis_replay/macro_event_replay.py` driving deterministic fixtures (`fixtures/events.csv` mixing CPI/NFP/UNRATE 2023-2024, `fixtures/prices.csv` covering all event dates ± 15 days for SPY_PROXY / TLT_PROXY).
- 10 tests in `tests/test_macro_replay.py` covering returned schema, hotter-direction propagation, hand-calculated pre/post log returns on a linear ramp, missing-column / empty-input / non-positive-window / non-DataFrame `ValueError` paths, fixture round-trip, and unknown-event passthrough.

### Deferred from v0.8.0 (carried into v0.9)
- `arch`-backed GJR-GARCH-DCC fitter for end-to-end SRISK from raw returns
- LBS (locational banking statistics) + BIS EER (effective exchange rates)
- *(Optional / downstream)* VolanX wiring of `macro_events.score_event`, `classify_phase`, and `build_crisis_dossier` as decision-intelligence features (operator-tracked, not in-tree)

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
