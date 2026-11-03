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
ruff check . && pytest -m "not spark and not databricks and not live"
```

Findings so far: [Fed speech count](docs/findings/fed-speech-count.md).

Review fixes (Sol rounds 1-3, CodeRabbit round 4): `cutoff_guard` trusts git provenance bound to the exact registration content on the first-parent line of a verified ref and validates the registry strictly; `asof_latest` has no tie-break and rejects ties, null keys and overlapping spine columns; Fed speech availability is an uncorroborated assumption excluded from confirmatory work; CI is least-privilege, NUL-safe and blocks more data files; the no-pandas check is AST-based; first-print labels need an audited availability timestamp; diagram a11y fixes.
