# pm-macro-lab

Research lab testing whether free macro data, nowcasts and LLM-scored Fed communication add information beyond prediction-market prices on US macro releases (CPI first, then FOMC and payrolls). Venue: Interactive Brokers event contracts. Built on Databricks (Delta, Unity Catalog, Jobs, MLflow).

**Status:** planning. Research and paper trading only; not investment advice. Private repo.

See [docs/PLAN.md](docs/PLAN.md) for the thesis, decisions, data sources, Databricks design, phases and gates.

## Phase status

| Phase | State |
|---|---|
| P0 foundation + IBKR verification | scaffold in PR (package, `cutoff_guard`, PIT helper, leakage tests, CI); IBKR checks and Databricks bundle pending |
| P1 CPI data | not started |
| P2 baseline models | not started |
| P3 LLM signal | not started |
| P4 paper trading, FOMC/payrolls | not started |

## Develop

```
pip install -e ".[dev]"
ruff check . && mypy src && pytest -m "not spark and not databricks and not live"
```

Findings so far: [Fed speech count](docs/findings/fed-speech-count.md).

## Agent-coordinated builds

The `.agents/` directory implements a multi-agent build and validation workflow (see [.agents/PROTOCOL.md](.agents/PROTOCOL.md)):

- **Coder** (DeepSeek or MiMo): builds feature and writes `BUILD DONE` report
- **Validator** (different model): independent review on exact SHA, writes `VALIDATION DONE` verdict
- **Codex Sol** (`gpt-6.1-sol`): final gate for every change, writes `CODEX FINAL` verdict
  (Opus 5.5 fallback only if Sol hits token/usage limits; substitution recorded in PR)
- **Claude**: coordinator, dispatcher orchestration

Coder/validator roles follow the DeepSeek UTC peak window: MiMo codes while
DeepSeek is in peak, otherwise DeepSeek codes and MiMo validates. Get the pair
from `.agents/pick-roles.sh` (pass `--keep <coder> <validator>` on fix rounds).
The peak window is supplied by the owner via `PEAK_START_UTC` / `PEAK_END_UTC`
(UTC hours, may wrap midnight); the script exits 2 rather than guess when they
are unset.

Dispatch with `.agents/dispatch.sh <agent> <request-file> [timeout-seconds]` (pass 7200 for long-running work). Agents read the protocol and their role, then execute the request and write a verdict file. Logs are written to `.agents/.agentlogs/` (gitignored).
