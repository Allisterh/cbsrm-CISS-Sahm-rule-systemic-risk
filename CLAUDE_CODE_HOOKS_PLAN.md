# Claude Code Hooks Plan — CBSRM

> Design sketch for guardrail hooks that **may** be implemented later in `.claude/settings.json` (or `.claude/settings.local.json`). **Nothing in this document is implemented.** No hooks are configured today; this is a planning artifact. The operator decides whether and when to install each hook.

Hooks in Claude Code are shell commands the harness runs in response to events (`PreToolUse`, `PostToolUse`, `Stop`, `UserPromptSubmit`, etc.). They can block actions, print warnings, or perform read-only checks. Because they execute on every matching event, the rule is: keep them fast and side-effect-free unless absolutely necessary.

Each entry below specifies: event, matcher, intent, draft command, expected behaviour, and risks. None of these are active.

---

## 1. Block pushes to `main` without an "approved" sentinel

| Field | Value |
|---|---|
| **Event** | `PreToolUse` |
| **Matcher** | `Bash` calls matching `git push.*\\bmain\\b` |
| **Intent** | Stop any unauthorized push to `main`. The operator must drop a sentinel file (e.g., `.claude/.push-main-approved`) for the current session, or the hook denies the push. |
| **Draft command (Unix)** | `test -f .claude/.push-main-approved || { echo "Refusing push to main: missing .claude/.push-main-approved sentinel"; exit 2; }` |
| **Expected behaviour** | Hook exits 2 → tool call blocked, message surfaced to Claude. |
| **Risks** | Sentinel file must be `.gitignore`d. Easy to forget to delete after use; consider auto-deleting on `Stop`. Does not protect against `git push origin HEAD:main` style spelling unless regex covers it. |

---

## 2. Warn on dirty worktree before `git checkout` or `git merge`

| Field | Value |
|---|---|
| **Event** | `PreToolUse` |
| **Matcher** | `Bash` calls matching `git (checkout|merge|rebase)\\b` |
| **Intent** | Refuse to switch branches or merge if the worktree has uncommitted changes, to prevent silent loss. |
| **Draft command** | `if [ -n "$(git status --porcelain)" ]; then echo "Refusing: dirty worktree."; git status --short; exit 2; fi` |
| **Expected behaviour** | Hook exits 2 → blocked. Operator must commit, stash, or explicitly override. |
| **Risks** | Will block legitimate `git checkout -- <file>` discards. Tighten matcher to branch-change forms only (`git checkout -b`, `git checkout <ref>`). |

---

## 3. Warn on release tag creation / move / delete

| Field | Value |
|---|---|
| **Event** | `PreToolUse` |
| **Matcher** | `Bash` calls matching `git tag\\b|git push .*--tags\\b|git push .*refs/tags/` |
| **Intent** | Make tag operations impossible to do silently. Surface the command for explicit operator confirmation. |
| **Draft command** | `echo "Tag operation detected: $TOOL_INPUT"; test -f .claude/.tag-approved || { echo "Refusing: missing .claude/.tag-approved sentinel"; exit 2; }` |
| **Expected behaviour** | Hook blocks unless sentinel exists. Sentinel must be added with explicit operator action. |
| **Risks** | Covers most patterns but `git push origin v0.8.0` (specific tag push) needs the second regex. Annotated-tag creation via `gh release create` would also need a `gh release\\b` matcher. |

---

## 4. Run `git status` automatically before any state-changing tool use

| Field | Value |
|---|---|
| **Event** | `PreToolUse` |
| **Matcher** | `Bash` calls matching `git (commit|merge|rebase|reset|push|tag)\\b|gh (pr|release)\\b` |
| **Intent** | Surface the worktree state into chat right before a state-changing op, so the operator sees the context inline. |
| **Draft command** | `git status --short --branch` |
| **Expected behaviour** | Hook exit 0 always (informational). Output captured into chat. |
| **Risks** | Adds noise. Tighten matcher to high-blast-radius ops only if signal-to-noise degrades. |

---

## 5. Detect accidental edits to forbidden files on docs-only tasks

| Field | Value |
|---|---|
| **Event** | `PostToolUse` |
| **Matcher** | `Edit` or `Write` calls whose `file_path` starts with `cbsrm/`, `tests/`, or matches `pyproject.toml`, `.github/`. |
| **Intent** | Warn (or block) when a docs-only task accidentally writes to code/tests/workflows/version-metadata. |
| **Draft command** | `case "$TOOL_FILE_PATH" in cbsrm/*|tests/*|pyproject.toml|.github/*) echo "Edit to forbidden path on docs-only task: $TOOL_FILE_PATH" >&2; exit 2 ;; esac` |
| **Expected behaviour** | Hook exits 2 → tool result flagged as blocked. Operator must override explicitly. |
| **Risks** | Hook can't know whether the current task is "docs-only" without an explicit session flag. Implementation requires a sentinel like `.claude/.task-mode=docs-only` that the operator sets at task start. |

---

## 6. Remind to run tests after code changes

| Field | Value |
|---|---|
| **Event** | `PostToolUse` |
| **Matcher** | `Edit` or `Write` calls whose `file_path` matches `cbsrm/.*\\.py$` |
| **Intent** | Print a single-line reminder ("run `pytest tests/test_<module>.py` or full suite"). |
| **Draft command** | `echo "[hook] cbsrm code changed: $TOOL_FILE_PATH — remember to run targeted pytest, then full suite before commit."` |
| **Expected behaviour** | Always exit 0; informational only. |
| **Risks** | Pure cosmetic. Useful as an early reminder but no enforcement. |

---

## 7. Block deletes of `.env` and credential files

| Field | Value |
|---|---|
| **Event** | `PreToolUse` |
| **Matcher** | `Bash` calls matching `rm .*\\.env\\b|del .*\\.env\\b|rm .*refresh.token|rm .*secret` |
| **Intent** | Defensive guard against accidentally deleting credential material. |
| **Draft command** | `echo "Refusing: credential-style file deletion detected: $TOOL_INPUT"; exit 2` |
| **Expected behaviour** | Hard block. |
| **Risks** | Pattern coverage is best-effort. Pair with: never store credentials inside the repo tree in the first place. |

---

## 8. Detect external posting commands

| Field | Value |
|---|---|
| **Event** | `PreToolUse` |
| **Matcher** | `Bash` calls matching `curl .*linkedin\\.com|curl .*news\\.ycombinator\\.com|gh release (create|edit)|gh issue create|gh pr (merge|review --approve)` |
| **Intent** | Force operator confirmation before any outbound action. |
| **Draft command** | `echo "External posting / release / merge detected: $TOOL_INPUT"; test -f .claude/.post-approved || exit 2` |
| **Expected behaviour** | Blocks unless explicit per-action sentinel. |
| **Risks** | Pattern set must be kept current as new tools or destinations enter the workflow. |

---

## Cross-cutting design notes

- **Sentinel files** (`.claude/.push-main-approved`, etc.) belong in `.gitignore`. They are single-shot operator-set tokens that authorize one action; consider auto-removing them on `Stop`.
- **Hooks run on every event match.** Keep commands well under 1 second. Anything heavier belongs in a subagent.
- **Cross-platform footnote.** This repo's primary operator runs Windows + Git Bash + Windows GH CLI. Draft commands above use POSIX sh; a parallel set may be needed for `cmd.exe` or PowerShell harnesses.
- **Exit codes.** `0` = pass through, `2` = block tool call. Anything else may surface as ambiguous errors.
- **Logging.** Consider an additional `PostToolUse` hook that appends hook decisions to `.claude/hooks.log` (gitignored) for audit.
- **Test before relying.** When any hook above is eventually installed, smoke-test by running an obviously-allowed action (e.g., `git status`) and then an obviously-blocked one (e.g., `git push origin main` without sentinel) to confirm both code paths.

---

## Installation plan (NOT executed)

If/when the operator decides to enable hooks:

1. Open `.claude/settings.json` (create if missing) and add a `hooks` block per the [Claude Code hooks reference](https://docs.claude.com/en/docs/claude-code/hooks).
2. Implement each hook as a one-line bash command first; promote to a script only if it exceeds 3 statements.
3. Add `.claude/.*-approved` and `.claude/hooks.log` to `.gitignore`.
4. Roll out one hook at a time. After each, run a sample state-changing op to confirm allow/block paths.
5. Document the active set in §13 of `CLAUDE_CODE_OPERATING_SYSTEM.md` (the quick-reference card) once stable.

Until then this is design notes, not configuration.
