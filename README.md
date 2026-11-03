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

Review fixes (Sol round 1): `cutoff_guard` now requires a verified registry entry, a matching pre-registration committed before the event, `doc_available_ts <= score_ts < event_release_ts` and explicit `external_retrieval=False`; the Fed speech feed time is kept naive/unverified with a conservative New York availability fallback; `asof_latest` rejects null keys and tied facts; CI data-file and no-pandas checks are broader; the P2b label rule is bounded to 3 days.
