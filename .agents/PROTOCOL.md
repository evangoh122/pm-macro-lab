# Multi-agent build & verify protocol — pm-macro-lab

Four agents run as separate CLIs with no shared memory. They coordinate through
files in this repo. Ported from the Rag_workbench protocol.

## Agents, lanes, and verified routes

| Agent      | Role                                             | Route (verified working)              | Report                        |
| :--------- | :----------------------------------------------- | :------------------------------------ | :---------------------------- |
| Coder      | **Builder** — implementation (DeepSeek/MiMo)    | model-specific via opencode           | `BUILD DONE \| status: ... \| sha: <40-char> \| branch: ... \| evidence: <path>` |
| Validator  | **Independent** — different model, exact SHA    | model-specific (not coder's model)    | `VALIDATION DONE \| verdict: <APPROVED\|CHANGES_REQUESTED\|FAILED> \| sha: <40-char> \| evidence: <path>` |
| Codex Sol  | **Final gate** — correctness, security, tests   | `codex exec` (`gpt-6.1-sol`)          | `CODEX FINAL \| verdict: <APPROVED\|CHANGES_REQUESTED\|FAILED> \| sha: <SHA>` |
| Opus 5.5   | **Fallback final gate** — only if Sol unavailable | Claude Opus 5.5 (token/usage limits)   | `OPUS FINAL \| verdict: ... \| sha: <SHA>` (recorded in PR) |

Broken routes — do not use: `mimo/*` (literal `BASE_URL` placeholder in
`~/.config/opencode/opencode.json`), `xiaomi/*` (insufficient account balance),
`opencode/mimo-v2.5-free` (upstream error).

## Roles

Builders write code. Validators do not write feature code; they read the diff
and return a verdict. Claude never hand-writes a slice that a builder can do —
coordination and gating only.

## Message types

1. **BUILD-REQUEST** → `.agents/requests/BUILD-<feature>.md`
   Written by Claude. Contains: scope, exact files to create/modify, acceptance
   criteria, and explicit non-goals.
2. **VERDICT** → each agent's lane file above. Format below.
3. **SUMMARY** → `.agents/requests/SUMMARY-<feature>.md`
   Written by Claude once all verdicts are in. Sets the gate.

## Terminal reports

Every agent writes one terminal report before exiting:

**Coder:**
```
BUILD DONE | status: <SUCCESS|FAILURE> | sha: <40-char SHA or NO_COMMIT> | branch: <branch> | evidence: <path>
```

**Validator** (on exact commit SHA only):
```
VALIDATION DONE | verdict: <APPROVED|CHANGES_REQUESTED|FAILED> | sha: <40-char SHA or SHA_NOT_VERIFIED> | evidence: <path>
```

**Final gate** (Codex Sol or Opus 5.5):
```
CODEX FINAL | verdict: <APPROVED|CHANGES_REQUESTED|FAILED> | sha: <SHA>
OPUS FINAL | verdict: <APPROVED|CHANGES_REQUESTED|FAILED> | sha: <SHA>
```

## Verdict format

```markdown
# VERDICT: <feature> — <AGENT>
**Status:** APPROVED | CHANGES_REQUESTED | BLOCKED
**Round:** N

## Blocking findings
- [file:line] <defect> → <concrete failure scenario>

## Non-blocking notes
- ...

## Checks run
- <command> → pass/fail
```

## CI parity gate

Before approval, all required checks must pass:
- `ruff check .`
- `mypy src`
- `pytest -m "not spark and not databricks and not live"`

## Lifecycle

```
Coder (e.g., DeepSeek or MiMo) builds feature
   → Commits to branch (not main/master)
   → Writes BUILD DONE | status: SUCCESS | sha: <40-char> | branch: <branch> | evidence: <path>

Independent Validator (different model from coder)
   → Runs CI parity gate (above checks must all pass)
   → Validates exact commit SHA
   → Writes VALIDATION DONE | verdict: APPROVED | sha: <40-char> | evidence: <path>
   → Only APPROVED verdict allows final gate to proceed

Codex Sol final gate (gpt-6.1-sol)
   → Independent review on exact validated SHA
   → If Codex Sol unavailable (token/usage limits): use Opus 5.5, record in PR
   → Writes CODEX FINAL | verdict: APPROVED | sha: <SHA>

PR + CodeRabbit
   → Keep PR draft until final gate approves
   → Once approved, trigger CodeRabbit review (if needed)
   → Merge only when owner says so explicitly
```

## Hard rules

- No coder or validator pushes to `main` or `master`. dispatch.sh enforces this.
- Validator must be independent: different model from coder, or different agent.
- Validator verdict must be for exact commit SHA; later commits require new validation.
- Final gate must be Codex Sol (`gpt-6.1-sol`) for every change. Only use Opus 5.5 if
  Sol hits token/usage limits, and record that substitution in the PR.
- No secrets in committed files. Config via env var or secure secrets store only.
- No parameterized SQL violations. A single f-string interpolation is a blocker.
- A builder may not approve its own work as the sole verdict.
- CI parity gate must pass: `ruff check .`, `mypy src`, `pytest -m "not spark and not databricks and not live"`.
- Tests must actually run. A verdict claiming "tests pass" without pasted output is blocking.
- Terminal reports (BUILD DONE, VALIDATION DONE, CODEX FINAL/OPUS FINAL) are required.
- Timeouts are passed at dispatch call site, not hardcoded: `.agents/dispatch.sh <agent> <request> [7200]`.
