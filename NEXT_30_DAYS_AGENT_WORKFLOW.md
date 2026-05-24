# Next 30 Days — Agent Workflow (CBSRM)

> A practical operating cadence for the post-v0.8.0 window. Operator-driven. Claude Code is the staging hand. Nothing in this file authorizes external action; every cadence step is operator-gated.

This document complements:
- `CLAUDE_CODE_OPERATING_SYSTEM.md` — the contract.
- `CLAUDE_CODE_PROMPT_LIBRARY.md` — the templates.
- `LAUNCH_COMMAND_CENTER.md` — the 90-minute launch order-of-operations.

---

## 1. Daily launch checklist

Pull this out once a day, normally during the operator's first focused block.

- [ ] Open the repo. Run the read-only diagnostic (`CLAUDE_CODE_PROMPT_LIBRARY.md` §1).
- [ ] Confirm `main == origin/main` and last 3 CI runs on `main` are green.
- [ ] Open issues / PRs scanned; flag any inbound community contribution.
- [ ] Inbox triage: any v0.8.0-related inbound message (LinkedIn, HN, SSRN, email).
- [ ] If GitHub Release for v0.8.0 is still unpublished, decide: publish today or defer with a documented reason.
- [ ] If Streamlit demo decision is still open, decide: ship a hosted demo or hold to "run locally" stance.
- [ ] Update the `LAUNCH_COMMAND_CENTER.md` checklist boxes when something moves.

If everything above is steady, switch to the productization sprint (§2). If anything is red, fix CI first (§3).

---

## 2. Weekly productization sprint

Pick exactly **one** weekly theme. Resist context switching.

| Week | Theme | Outcome |
|---|---|---|
| **W1** | Launch follow-through | Release published, posts live or deliberately deferred, demo decision locked, customer-discovery list seeded. |
| **W2** | Telemetry & metrics | Lightweight metrics doc (stars, clones, traffic, post engagement) reviewed weekly. Roadmap candidates derived from real signal. |
| **W3** | v0.9 scope | Translate top-3 customer-discovery learnings + roadmap doc into a 1-page v0.9 spec. Open `feat/...` branches as needed. |
| **W4** | Hygiene & polish | CI matrix audit, dependency refresh review (no upgrades yet, just inventory), whitepaper §13 draft, contributor experience polish. |

Inside each week, daily focus blocks are 90 min max. Anything that needs more than two focus blocks turns into Plan Mode and lives on its own branch.

---

## 3. CI hygiene

Goal: zero red CI on `main`. Always.

- Every fix branch goes through draft PR → PR-event matrix → green → merge → main matrix green. No shortcuts.
- If `main` goes red post-merge, the next action is revert-or-fix on a fresh `fix/...` branch, not a manual `--force` or rerun.
- Flakes are tracked (frequency + job). Three flakes from the same job in 30 days → investigate root cause; never normalize.
- Matrix expansion (new Python version, new OS) is its own `fix/ci-...` branch.
- Workflow file (`.github/workflows/test.yml`) is touched only in Plan Mode with explicit operator authorization.

Useful one-liners for the operator:
- `gh run list --repo pravo123/cbsrm --branch main --limit 5`
- `gh run watch <id> --repo pravo123/cbsrm --exit-status`
- `gh run view <id> --repo pravo123/cbsrm --log-failed | head -200`

---

## 4. Docs / release hygiene

- Every public-facing assertion in `README.md`, `LAUNCH_COMMAND_CENTER.md`, `SHOW_HN_POST.md`, `SSRN_SUBMISSION.md`, `GITHUB_RELEASE_v0.8.0.md` is checked weekly for drift (test count, URL freshness, dead links).
- Drift fixes live on `docs/<slug>` branches; never inline on `main`.
- `CHANGELOG.md` gets an `[Unreleased]` entry as soon as a behaviour change lands on `main`. Even drafts.
- New launch posts → preview-first inside `LAUNCH_POSTS_v0.8.0.md` (or a sibling file). Never posted by Claude Code.
- Tag `v0.8.0` is frozen at `410e3ac9...`. Any patch-level event (e.g., `v0.8.1`) is a fresh tag, a fresh Release, fresh launch decision.

---

## 5. Customer discovery logging

- Every external conversation is logged in `CUSTOMER_DISCOVERY_v0.8.md` (or a successor file) within 24 hours of the call.
- Logs are append-only, dated, persona-tagged.
- Each entry includes: who, when, channel, what we asked, what we heard verbatim (paraphrase only with marker), three takeaways, follow-up next-step.
- Logs feed §6 (metrics review) and §7 (Product Roadmap synthesis).
- Personally identifying information is kept to the minimum required (name + firm; no email addresses in this file — those live in a private offline list).

---

## 6. Post-launch metrics review

Weekly, normally Sunday evening (operator clock).

- Inputs: GitHub Insights (stars, clones, forks, referrers), HN post stats if applicable, LinkedIn analytics, SSRN download count, any inbound mention.
- Output: 5-bullet weekly note appended to `LAUNCH_COMMAND_CENTER.md` (or a sibling `LAUNCH_TRACTION.md` if it grows).
- Three numbers up. Three numbers flat-or-down. Two recommended next actions (always operator-gated).
- Claude Code may draft the note; the operator publishes nothing externally from it.

---

## 7. Human ↔ Claude clean handoff

The handoff rule: at the end of every working session, drop a 5-line state block in chat (or commit a `SESSION_STATE.md` if it grows). The next session begins by reading it.

State block fields:
1. Current branch + HEAD SHA.
2. What just happened (1 sentence).
3. What is in flight (branch / PR / CI run id).
4. What the next action is.
5. What gates the next action (operator approval, CI completion, external event).

Reverse handoff (operator → Claude) follows the same shape: start of a session, the operator drops the state block as the opening message. Claude Code's first action is to verify the live repo matches the asserted state (SHAs, branches, CI), then propose the next step.

Anti-patterns to avoid:
- "Continue where we left off" with no state block → ambiguous; Claude must ask.
- Long sessions with no checkpoint → bigger blast radius if something goes wrong.
- Mixing themes in one session (e.g., CI fix + launch copy + new feature) → split into separate branches, separate sessions.

---

## 8. Anti-patterns we will not repeat

These come from real session history; they are first-class to avoid:

- **Posting before preview-first review.** Every external surface goes through render-and-confirm.
- **Force-push to clear a conflict.** Always resolve, never overwrite published history.
- **Modifying live trading / production code on a docs branch.** Branches are single-concern; cross-cutting changes need Plan Mode.
- **Auto-rotating tokens in `.env` from a test harness.** Tests must never touch the operator's real credential files.
- **Letting CI stay red while shipping docs on top.** Red main → stop shipping until green.
- **Cutting a new tag to "fix" a Release page issue.** GitHub Release ≠ git tag; fix the page, leave the tag frozen.

---

## 9. End-of-30-days exit criteria

By day 30 we expect (operator confirms):

- [ ] CI on `main` has been green for 30 consecutive days.
- [ ] GitHub Release for v0.8.0 is published OR explicitly deferred with documented reason.
- [ ] Streamlit demo decision is locked.
- [ ] At least 5 logged customer-discovery conversations.
- [ ] A one-page v0.9 spec exists on a `docs/v09-spec` branch (or merged into `PRODUCT_ROADMAP_v0.9.md`).
- [ ] No protocol violations on the `CLAUDE_CODE_OPERATING_SYSTEM.md` "never do" list have occurred.
- [ ] This file is reviewed and either renewed or rewritten for the next 30 days.
