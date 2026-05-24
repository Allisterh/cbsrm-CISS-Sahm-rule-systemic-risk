# Claude Code Subagent Plan — CBSRM

> Design sketch for specialized subagents that may be installed later. **Nothing in this document is configured or active.** No subagents exist in `.claude/agents/` yet; this is a planning artifact only. The operator decides whether and when to install each one.

Each subagent below is described in six fields: purpose, when to invoke, allowed files, forbidden files, tools assumed, expected output. Together those fields are also the contract that should be transcribed into a future `.claude/agents/<name>.md` when (and if) the operator decides to install it.

---

## 1. CI Diagnostician

| Field | Value |
|---|---|
| **Purpose** | Diagnose a failing CI run on `main` or a feature branch and propose the smallest fix. |
| **When to invoke** | A `gh run view` shows `conclusion: failure`. Operator says "CI is red, investigate." |
| **Allowed files** | Read `.github/workflows/**`, `pyproject.toml`, `tests/**`, `cbsrm/**`. Write nothing. |
| **Forbidden files** | All writes. Especially `.github/workflows/**` (workflow edits are a separate operator-gated task). |
| **Tools assumed** | `Bash` (`gh run view --log-failed`, `git log`, `git show`), `Read`, `Grep`. No `Edit`, `Write`. |
| **Expected output** | (a) Failing job + first failing step; (b) classification env / regression / flake; (c) suspect commit if regression; (d) minimum-change fix proposal with branch name + diff sketch; (e) explicit "no action taken." |

---

## 2. Release Manager

| Field | Value |
|---|---|
| **Purpose** | Walk the operator through a release: branch hygiene, merge sequence, tag creation, GitHub Release publish. Strictly preview + propose; never executes the final state-changing step. |
| **When to invoke** | Operator says "cut v0.x.y" or "publish the Release for v0.8.0." |
| **Allowed files** | Read all. Edit only `CHANGELOG.md` and root Markdown launch copy. |
| **Forbidden files** | `cbsrm/**`, `tests/**`, `pyproject.toml` (version bumps are explicit operator-gated tasks), `.github/workflows/**`. |
| **Tools assumed** | `Bash` (`git`, `gh`), `Read`, `Edit` (Markdown only). |
| **Expected output** | (a) Pre-release checklist verified; (b) draft of `CHANGELOG.md` entry; (c) proposed git commands listed but not executed; (d) draft GitHub Release body rendered for operator paste; (e) explicit "awaiting operator publish." |

---

## 3. Docs Launch Editor

| Field | Value |
|---|---|
| **Purpose** | Refresh launch-facing Markdown for new milestones (test count change, new URL, new metric, new section). Pure editorial work. |
| **When to invoke** | Operator says "update SHOW_HN_POST.md for v0.8.1" or similar. |
| **Allowed files** | Root `.md` files only: `SHOW_HN_POST.md`, `SSRN_SUBMISSION.md`, `GITHUB_RELEASE_*.md`, `LAUNCH_*.md`, `PRODUCT_ROADMAP_*.md`, `CUSTOMER_DISCOVERY_*.md`, `CLAUDE_CODE_*.md`, `COLD_EMAILS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `README.md`. |
| **Forbidden files** | Anything under `cbsrm/**`, `tests/**`, `dashboard/**`, `whitepaper/**`, `pyproject.toml`, `.github/**`. |
| **Tools assumed** | `Read`, `Edit`, `Grep`. `Bash` for `git diff --stat`. |
| **Expected output** | (a) Branch `docs/<slug>`; (b) edited files; (c) `git diff --stat` showing only Markdown root paths touched; (d) explicit "no commit, no push." |

---

## 4. API Reviewer

| Field | Value |
|---|---|
| **Purpose** | Audit `cbsrm/api/**` and adjacent tests for surface drift, route hygiene, optional-dep posture, and contract stability. Diagnostic only. |
| **When to invoke** | Before any v0.x release that touches the API. Or operator-initiated audit. |
| **Allowed files** | Read `cbsrm/api/**`, `tests/test_api_*`, `pyproject.toml` (extras), `cbsrm/cli.py` (parity surfaces). Write nothing. |
| **Forbidden files** | All writes. |
| **Tools assumed** | `Read`, `Grep`, `Bash` (`pytest tests/test_api_*` if requested). |
| **Expected output** | (a) Inventory of public routes with shape; (b) lazy-import verification (FastAPI optional); (c) any route returning non-deterministic output; (d) audit-chain coverage; (e) recommended follow-ups, each as a `feat/...` or `fix/...` ticket. |

---

## 5. Security / Privacy Reviewer

| Field | Value |
|---|---|
| **Purpose** | Scan repo state for accidentally-committed secrets, PII, and license violations before any external surface action (Release publish, post, deploy). |
| **When to invoke** | Before any external publish step. Also opportunistically before merging branches that touched env/secrets/config-adjacent files. |
| **Allowed files** | Read all tracked files. Write nothing. |
| **Forbidden files** | All writes. Never echo a suspected secret value to chat in full — partial match + line ref only. |
| **Tools assumed** | `Read`, `Grep`, `Bash` (`git log -p` for selective inspection, `git secrets` if installed). |
| **Expected output** | (a) Pattern scan summary (API key regexes, JWT shapes, AWS keys, RSA blocks, `.env` style assignments); (b) any tracked file that looks like a credential; (c) license posture check on `LICENSE` + any vendored material; (d) GO / NO-GO recommendation for the imminent external action. |

---

## 6. Product Roadmap Analyst

| Field | Value |
|---|---|
| **Purpose** | Maintain `PRODUCT_ROADMAP_v0.9.md` and the next-quarter view. Synthesize customer-discovery notes, CI/test debt, and competitive signals into prioritized roadmap candidates. |
| **When to invoke** | After every batch of customer-discovery calls; weekly during a release cycle; on operator request. |
| **Allowed files** | Read all. Edit only `PRODUCT_ROADMAP_v0.9.md`, `CUSTOMER_DISCOVERY_*.md`, `NEXT_30_DAYS_AGENT_WORKFLOW.md`. |
| **Forbidden files** | `cbsrm/**`, `tests/**`, `pyproject.toml`, `.github/**`. |
| **Tools assumed** | `Read`, `Edit`, `Grep`. |
| **Expected output** | (a) Updated roadmap with explicit dated entries; (b) prioritization rationale per item (impact × effort × who-asked); (c) any item that conflicts with existing CHANGELOG / launch copy flagged for operator reconciliation; (d) no external posting. |

---

## Cross-cutting rules for all subagents

These bind whichever subagents are eventually installed:

1. **No state-changing actions toward `main`.** Subagents may stage work on feature branches; only the human operator merges or pushes.
2. **No tag creation, deletion, or movement.**
3. **No external posting, deploying, or sending.**
4. **No `.env` access.**
5. **Failed verification → stop.** If a subagent's verification step fails, it stops and reports. It does not "try harder."
6. **Forbidden-file violation → stop + report.** Any attempt to edit a forbidden path aborts the subagent run.
7. **Preview-first for any artifact** that will eventually be published externally.

---

## Installation plan (NOT executed)

If/when the operator decides to install one of the above, the steps would be:

1. Create `.claude/agents/<name>.md` with frontmatter (`description`, `tools`, `allowed-paths`).
2. Transcribe the contract above into the body of the file.
3. Smoke-test the subagent on a benign read-only task.
4. Add a one-line mention to `CLAUDE_CODE_OPERATING_SYSTEM.md` referencing the new subagent.

Until then this document is design notes, not configuration.
