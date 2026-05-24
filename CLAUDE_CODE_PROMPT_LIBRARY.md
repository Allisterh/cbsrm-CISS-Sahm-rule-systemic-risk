# Claude Code Prompt Library — CBSRM

> Reusable prompt templates for the operator. Copy, edit placeholders in `<angle brackets>`, paste into Claude Code. Each template begins with the safety context Claude Code is expected to honour and ends with an explicit "stop and report" boundary.

All templates are operator-driven by design — Claude Code is never given blanket authority to merge, tag, push, deploy, or post.

---

## 1. Read-only repo diagnostic

```
You are doing read-only diagnostics on github.com/pravo123/cbsrm.
Do not modify any file. Do not create branches. Do not push.

Report:
1. Current branch + HEAD SHA + git status --short --branch.
2. main vs origin/main ahead/behind.
3. Local branch list with their head SHAs.
4. Open PRs (gh pr list) and their states.
5. Last 5 CI runs on main (gh run list --branch main --limit 5).
6. Result of `pytest tests/ -q` (count only; do not run if any merge is in progress).
7. Any tags created in the last 30 days.

Stop and report. Do not advance to any other task.
```

---

## 2. Feature implementation slice

```
Plan-mode task. Goal: <one-sentence outcome>.

Constraints:
- Open a new branch `feat/<slug>` off latest main.
- Touch only: <list of allowed paths>.
- Tests required. No green CI, no merge.
- Stop before push of any kind.

Phase 0: confirm branch + worktree clean + main == origin/main.
Phase 1: write or update the failing test that captures the behaviour.
Phase 2: implement the smallest change that turns the test green.
Phase 3: run targeted tests, then full `pytest tests/ -q`.
Phase 4: report files changed, diff stat, test result.

Do not commit. Do not push. Do not open PR.
Wait for operator review of the diff before any further action.
```

---

## 3. CI failure diagnosis

```
CI on main is red. Diagnose only. Do not push fixes.

Steps:
1. gh run list --repo pravo123/cbsrm --branch main --limit 5.
2. Identify the most-recent failing run and its commit SHA.
3. gh run view <id> --log-failed | head -200.
4. Classify the failure: environment / regression / flake.
5. Identify the minimum-change fix (e.g., add dep to [dev], pin a version, revert a commit).
6. Draft a one-commit fix-branch plan (branch name, files touched, diff size).

Stop and report. Wait for operator go-ahead before opening the branch.
```

---

## 4. Docs-only launch refresh

```
Docs-only task. Goal: update launch-copy to reflect <change, e.g. new Release URL, new test count, new metric>.

Hard rules:
- Touch only Markdown at repo root.
- Do not modify cbsrm/**, tests/**, pyproject.toml, .github/**.
- Do not modify version metadata anywhere.
- Branch: docs/<slug>.

Steps:
1. Confirm tree clean + on main.
2. Open docs/<slug>.
3. Edit only the agreed Markdown files.
4. `git diff --stat` to confirm only .md root files changed.
5. Stop. Report diff. Do not commit or push without explicit go.
```

---

## 5. Merge / tag / push release

```
Operator-driven release path. Hard constraint: do nothing irreversible without my explicit go for that specific step.

State of play:
- Branch <branch> is in sync with origin.
- PR <#N> is open, draft.
- PR CI is <green / pending / red>.

Sequence (operator-gated at each step):
1. Verify branch matches origin (`git rev-list --left-right --count`).
2. If PR is draft and CI green: ask whether to merge.
3. On approval: `git checkout main && git pull` and verify clean.
4. `git merge --no-ff <branch>`. Show resulting merge SHA.
5. On approval: `git push origin main`.
6. Watch new main CI. Report conclusion.
7. On approval: delete merged branch local + origin.

Tags:
- Do not create, move, or delete tags unless I explicitly request it.
- v0.8.0 is frozen at 410e3ac.

Stop and report after each step.
```

---

## 6. PR review

```
You are reviewing PR #<N> on github.com/pravo123/cbsrm. Read-only.

Report:
1. PR title, base, head, draft flag, head SHA.
2. Files changed with `git diff --stat <base>..<head>`.
3. For each file > 20 lines changed, summarize the change in 1-2 sentences.
4. Risk flags: did the diff touch tests/, cbsrm/, pyproject.toml, .github/?
5. Any TODO/FIXME/XXX introduced?
6. Test coverage: which tests cover the changed files?
7. CI status for the latest run on the PR head.

Recommend one of: approve, request-changes, comment-only. Do not merge.
```

---

## 7. Streamlit deploy checklist

```
Plan-mode task. Goal: deploy the v0.8 crisis-dossier Streamlit viewer.

Hard rules:
- Do not deploy. Surface the checklist only.
- Do not touch dashboard/** code unless an actual blocker is found.
- Do not commit secrets to the repo.

Steps:
1. Confirm `dashboard/crisis_dossier_viewer.py` runs locally with `streamlit run`.
2. Verify offline-deterministic posture (no FRED key required for fixture-backed dossiers).
3. Confirm `pyproject.toml` exposes the right extra (`[viewer]` or `[all]`).
4. Draft hosting options (Streamlit Community Cloud / Hugging Face Spaces / Fly.io) with trade-offs.
5. Identify required secrets, if any, and where they should live (operator-managed, never repo-committed).
6. Provide the deploy checklist: repo selector, branch, entry point file, Python version, secrets, post-deploy smoke.

Stop and report. Operator does the actual deploy.
```

---

## 8. Customer discovery prep

```
Docs-only task. Goal: prepare for a customer-discovery conversation with <persona / firm>.

Steps:
1. Read CUSTOMER_DISCOVERY_v0.8.md and identify the relevant persona section.
2. Draft a 20-minute conversation outline:
   - Opening (problem framing, no pitch).
   - 5 discovery questions (open-ended, behaviour-focused).
   - 3 falsifiable hypothesis questions.
   - Closing ask (next step, not a sell).
3. List the artifacts to send after the call (Release URL, whitepaper section refs, demo link if deployed).
4. List the entries to add to the customer-discovery log after the call.

Stop and report. Do not send anything externally.
```

---

## 9. Post-launch metrics review

```
Read-only task. Goal: summarize post-launch traction for week ending <YYYY-MM-DD>.

Inputs (operator supplies):
- GitHub Insights numbers (stars, clones, forks, traffic).
- Show HN post stats (rank, points, comments).
- LinkedIn post stats (impressions, reactions, comments).
- SSRN download count.
- Any inbound emails or messages worth flagging.

Output:
1. One-paragraph summary.
2. Three numbers that moved most week-over-week.
3. Three numbers that disappointed.
4. Two recommended next actions (operator-gated).

Do not post the summary externally. Do not modify the repo.
```

---

## Placeholders

- `<branch>` → e.g. `fix/ci-httpx-dev-extra`
- `<id>` → CI run id
- `<slug>` → kebab-case branch suffix
- `<N>` → PR number
- `<persona / firm>` → e.g. "BIS Innovation Hub", "V-Lab head of risk"
