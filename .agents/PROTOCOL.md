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

## Coder and Validator selection

The coder and validator are **MiMo and DeepSeek**, chosen by UTC peak hours:
- **While DeepSeek is in peak hours:** MiMo codes, DeepSeek validates
- **Outside DeepSeek peak hours:** DeepSeek codes, MiMo validates
- **Fix rounds:** keep the original coder/validator pair

Read the pair from `.agents/pick-roles.sh` at the start of every round:

```
.agents/pick-roles.sh              # CODER=<mimo|deepseek>, VALIDATOR=<...>
.agents/pick-roles.sh --keep mimo deepseek   # fix round: echo the original pair
```

The DeepSeek peak window is **not hardcoded in the repo**. The owner supplies it
via two environment variables, both UTC hours `0-23`:

| Variable | Meaning |
|:---|:---|
| `PEAK_START_UTC` | first peak hour (inclusive) |
| `PEAK_END_UTC` | first non-peak hour (exclusive); may wrap midnight, e.g. `22` → `6` |

The window is half-open `[PEAK_START_UTC, PEAK_END_UTC)`. If either variable is
unset, non-numeric, out of range, or both are equal, the script exits **2**
without printing a pair — fail closed, never guess a window. `NOW_UTC_HOUR`
overrides the clock for tests only. A missing window is a blocker: stop and ask
the owner rather than assuming a default.

## Model configuration

Dispatch uses environment variable overrides for agent models (set in `.agents/dispatch.sh`):

| Model | Default | Override |
|:---|:---|:---|
| **DeepSeek coder** | `deepseek/deepseek-flash` | `DEEPSEEK_MODEL=deepseek/deepseek-v4-pro` (for validator) |
| **MiMo** | `xiaomi-token-plan-sgp/mimo-v2.6-pro` | `MIMO_MODEL=<custom-model>` |
| **Codex Sol final gate** | `gpt-6.1-sol` | `CODEX_MODEL=<custom-model>` |

**Codex Sol invocation:** Uses `--sandbox workspace-write` to enable pytest/uv
with writable `/tmp` (read-only sandbox cannot create temp files). Codex CANNOT
write to `.agents/` (dot-directories blocked by sandbox even under workspace-write).
Instead, Codex prints its verdict between sentinel lines on stdout:
```
=== VERDICT BEGIN ===
CODEX FINAL | verdict: APPROVED | sha: <SHA>
<additional evidence lines>
=== VERDICT END ===
```
The coordinator extracts the block between the sentinel lines from the Codex log
(`.agents/.agentlogs/codex-<request>.log`) and writes it as the verdict file.
Stdin is closed with `< /dev/null` to prevent stdin blocking.

**Opus 5.5 fallback:** Used as the final gate only if Codex Sol hits token/usage
limits (rate-limit, quota, or usage error). This is a separate Claude route, not
a dispatch.sh override. Substitution must be recorded in the PR.

## Validator fallback order

If the designated validator runs out of tokens or quota, use fallback validators
in this order:
1. GLM (must be independent model from coder, positively identified)
2. Kimi (must be independent model from coder, positively identified)
3. Antigravity (agy) (must be independent model from coder, positively identified)

Each fallback validator must:
- Be a different model from the coder's model
- Return an `APPROVED` verdict for the exact commit SHA being validated
- Provide evidence with the same exactness as the designated validator
- Record the substitution in the PR comments

If a fallback route is unavailable or cannot be positively identified, **stop**
and ask the owner. Other validator failures also stop and ask the owner.

## CI parity gate

Before approval, all required checks must pass:

```
ruff check .
mypy src
pytest -m "not spark and not databricks and not live"
```

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
   → Keep PR in draft until final gate (Codex Sol or Opus 5.5) approves
   → Once final gate approves, trigger `@coderabbitai review` once per head SHA
     if new commits were pushed since CodeRabbit's last review (compare head SHA
     with last review commit_id) or no automatic review ran; at most once per head
     SHA, never in a loop; max 2 per PR without owner approval (see standing rule)
   → Merge only when owner says so explicitly
```

## CodeRabbit re-review rule (standing)

**After validator and final gate both approve,** trigger CodeRabbit review once
per new head SHA only if a trigger is actually warranted — i.e. commits were
pushed since CodeRabbit's last review (compare the last review's `commit_id`
with the current PR head SHA) or no automatic review has run at all:
- Run `~/ci-parity/cr_budget.sh` first to check tier and remaining slots
- Trigger **once per head SHA** with `@coderabbitai review` (never in a loop)
- Maximum **2 CodeRabbit reviews per PR** without explicit owner approval
- If CodeRabbit answers "Review rate limited", stop immediately; retry no sooner
  than 1 hour later (its limit counts over 7 days, so retrying makes it worse)

## Hard rules

- No coder or validator pushes to `main` or `master`. dispatch.sh refuses to
  start a dispatch from those branches; push protection comes from GitHub branch
  protection rules, not from this script.
- Validator must be independent: a different model from the coder's model.
- Validator verdict must be for exact commit SHA; later commits require new validation.
- Final gate must be Codex Sol (`gpt-6.1-sol`) for every change. Only use Opus 5.5 if
  Sol hits token/usage limits, and record that substitution in the PR.
- No secrets in committed files. Config via env var or secure secrets store only.
- No parameterized SQL violations. A single f-string interpolation is a blocker.
- A builder may not approve its own work as the sole verdict.
- CI parity gate must pass all checks: `ruff check .`, `mypy src`,
  `pytest -m "not spark and not databricks and not live"`.
- Tests must actually run. A verdict claiming "tests pass" without pasted output is blocking.
- Terminal reports (BUILD DONE, VALIDATION DONE, CODEX FINAL/OPUS FINAL) are required.
- Timeouts are passed at dispatch call site, not hardcoded: `.agents/dispatch.sh <agent> <request> [7200]`.
