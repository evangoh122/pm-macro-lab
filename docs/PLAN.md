# pm-macro-lab: project plan

Status: draft v1 (2026-10-30). Produced from a two-model discussion (Claude Opus and GPT Sol), then amended by the owner's decisions below.

## 1. Thesis

Prediction-market prices on US macro releases are the baseline. We test whether free nowcasts, official data and Fed communication, scored by an LLM, add out-of-sample information beyond the market price. A rigorous null result ("no edge after costs, and here is why") is a valid, publishable outcome. Sentiment is one feature, not the whole thesis.

Two targets are always scored separately:
1. the eventual outcome (resolution value)
2. a later executable price move

## 2. Owner decisions (binding)

| Decision | Choice |
|---|---|
| Venue | **Interactive Brokers (IBKR)** prediction contracts, because it is the legal route from Singapore. Not Kalshi directly. |
| Events | FOMC decision, CPI, Payrolls (NFP) |
| Build order | **CPI first**; FOMC and payrolls follow once the CPI pipeline works |
| Data | Free sources only |
| Trading | Paper trading only, eventually. No live capital without a separate owner decision. |
| Repo | `pm-macro-lab`, private |
| Platform | New Databricks workspace (separate from qp1) |
| LLM leakage | Opus-style `cutoff_guard` + cutoff registry (see section 6) |
| Code style | Polars only (no pandas); `data_source` column on every row |

## 3. Open item: IBKR venue facts must be verified in Week 1

The two models' research assumed Kalshi. The IBKR route changes the data-access picture and **nothing below about IBKR is verified yet**. Week-1 tasks:
- Confirm which IBKR event contracts exist for CPI, FOMC and payrolls, their strike ladders, tick size, fees and settlement source/timestamp.
- Confirm what the IBKR API (TWS/Gateway) gives us: live bid/ask and sizes, contract lists, and whether any **historical** quotes or trades exist.
- Confirm account/market-data permissions in Singapore and whether a paper account can access event contracts.
- If IBKR provides no history, then quotes must be captured **prospectively from day one**, and every earlier result is labelled "indicative, not executable".

If IBKR event contracts turn out to cover too few macro releases, fall back to a reference-price design: use free macro data plus a nowcast model and treat the market as an external benchmark only. This decision is made at the Week-1 gate.

## 4. Free data sources

| Need | Source | Notes |
|---|---|---|
| Macro history with vintages | FRED / **ALFRED** REST API | Default FRED values are revised; use vintages. Pipeline calls the REST API directly with the key in a Databricks secret scope. The FRED MCP is for interactive exploration only. |
| Release calendar | FRED releases/dates, BLS and Fed schedules | Record official release timestamps and our ingestion time separately. |
| First-print labels | BLS release pages / ALFRED earliest vintage | Labels must be the first-print value the contract resolved on. |
| Nowcasts | Cleveland Fed inflation nowcast, Atlanta Fed GDPNow, NY Fed nowcast | Check each site's terms and snapshot timing. |
| Fed communication | federalreserve.gov statements, minutes, speeches | Main text signal for H2. |
| News | GDELT (free, 15-minute) | Noisy; deduplicate syndicated stories. |
| Market quotes | IBKR API | Capture bid/ask/size every 5 minutes for all open macro contracts. |
| Consensus forecasts | none free and reliable | Open question: nowcasts only unless the owner has a paid source. |

Rule: store raw data in the private workspace; publish only derived aggregates. Record terms in `docs/data_licensing.md`.

## 5. Hypotheses

- **H1 (calibration):** strike-ladder probabilities are miscalibrated against a nowcast model at T-7d, T-1d, T-1h.
- **H2 (information flow):** LLM-extracted Fed-communication features add out-of-sample log-loss improvement beyond market + nowcast. Tested only under the leakage rules in section 6.
- **H3 (paper portfolio):** quarter-Kelly sizing with fills against captured books survives spread, fees, latency, and partial fills.
- **Consistency check:** each strike ladder should imply a monotone distribution; violations are logged as internal-arbitrage events.

## 6. LLM leakage control (cutoff guard)

- `config/llm_cutoffs.yaml` is the registry: model id -> training cutoff.
- `cutoff_guard` refuses to score or evaluate a document/event pair where the event resolves on or before the model's cutoff (plus a safety margin).
- Every `text_scores` row records `model_id`, `model_cutoff`, `prompt_ver`.
- A documented cutoff is necessary but **not sufficient**: memorization can still exist. So historical LLM results are labelled **exploratory**. The confirmatory H2 test uses articles scored prospectively with a pinned model and prompt, before the outcome is known.
- Scores are cached by (doc_hash, prompt_ver, model_id) for reproducibility.

## 7. Backtest and evaluation rules

- Market-only calibrated baseline first (Brier, log loss, reliability); sentiment model reports the incremental out-of-sample effect.
- Chronological splits grouped by release (strikes in one release are correlated). At each training cutoff include only labels already resolved. Purge window around the cutoff.
- Event-clustered errors; Holm correction across indicators.
- Fill at captured bid/ask plus fees plus modeled latency; periods with no captured quotes are "indicative".
- Exclude the final N hours before resolution; include voided/delisted contracts.
- Never use contract-rule versions that became valid after `as_of_ts`.
- Small-sample warning: about 8 FOMC meetings and 12 CPI releases per year. Power is limited; say so in every report.

## 8. Databricks design (new workspace)

Catalog `pm_macro`, schemas `bronze`, `silver`, `gold`, `ml`. Polars transforms, Spark I/O at the edges. Every row carries `data_source`, `ingest_ts`, `payload_hash`, `schema_ver` (bronze).

**Bronze (append-only, idempotent on source+endpoint+cursor):** `ibkr_contracts_raw`, `ibkr_quotes_raw`, `ibkr_trades_raw`, `fred_obs_raw`, `alfred_vintages_raw`, `release_calendar_raw`, `nowcast_raw`, `fed_docs_raw`, `gdelt_raw`.

**Silver:** `contracts` (SCD2 on rules text), `quotes` (best bid/ask, depth), `trades`, `macro_events` (event_id, indicator, release_ts), `event_contract_map`, `first_prints`, `vintages` (series, obs_date, vintage_ts, value), `text_docs` (pub_ts, available_ts, ingest_ts), `text_scores`.

**Gold:** `implied_dist` (pmf + monotone_flag), `features_pit` (UC feature table, time-series key on `as_of_ts`), `labels` (separate), `preds`, `signal_eval`, `paper_orders`, `paper_positions`, `paper_pnl`.

**Jobs (Databricks bundle):** quote capture every 5 minutes; contract refresh hourly; FRED/ALFRED and Fed text daily; a pre-release burst around each calendar entry. No streaming in the MVP. Data-quality expectations: prices in [0,1], monotone timestamps, no quotes after resolution.

Note: IBKR's API needs a running TWS/IB Gateway session, so quote capture needs a small always-on host (not a serverless Databricks job). Where that host lives is an open decision (section 11).

## 9. Phases and gates

| Phase | Weeks | Work | Gate |
|---|---|---|---|
| P0 | 1 | Verify IBKR facts (section 3); repo, bundle, catalog, secret scope, CI; start quote capture | 72h capture with no gaps; CI green; IBKR coverage documented |
| P1 | 1-3 | **CPI only**: contracts, resolutions, ALFRED vintages, release calendar, first prints, Fed/BLS text | First-print labels match contract resolutions in 100% of cases; sample size recorded |
| P2 | 3-5 | Market-only calibration, nowcast model, combined model | Point-in-time replay + leakage suite pass; baseline report merged |
| P3 | 5-7 | LLM scoring vs simple classifier on Fed/BLS text | Improvement across indicators with clustered errors + Holm, or a published null result |
| P4 | 7-12 | Extend to FOMC and payrolls; paper trading against captured books, minimum 6 weeks | Live capital requires a separate owner decision |

## 10. Repo layout

```
README.md  AGENTS.md  pyproject.toml  databricks.yml  .gitignore
.github/workflows/ci.yml   .coderabbit.yaml
config/  data_sources.py  indicators.yaml  llm_cutoffs.yaml  prompts/
resources/jobs/*.yml
src/pm_macro/
  ingest/{ibkr,fred_alfred,fed_text,gdelt,calendar}.py
  bronze/ silver/ gold/
  features/pit.py   labels/first_print.py
  llm/{score,cache,cutoff_guard}.py
  models/{calibration,nowcast,combined}.py
  backtest/{replay,fills,sizing,metrics}.py
  paper/broker_sim.py
tests/{unit,leakage,fixtures}/
docs/{PLAN.md,data_licensing.md,decisions.md,findings/}
```

CI: ruff, mypy, unit + leakage tests (`pytest -m "not spark and not databricks and not live"`), `databricks bundle validate`, and a check that fails on pandas imports or committed data files outside `tests/fixtures`. CI never needs licensed data and never places orders. Required leakage tests: a planted future-dated row is ignored by the feature builder; a revised vintage is not visible before its vintage time; `cutoff_guard` rejects pre-cutoff events.

## 11. Open questions

1. Which IBKR event contracts exist for CPI/FOMC/payrolls, and is there historical quote data? (Week 1)
2. Where does the always-on IBKR Gateway/quote-capture process run (home machine, small cloud VM)?
3. Is any paid consensus-forecast source available, or do we rely on nowcasts only?
4. Which LLM, and what is its training cutoff? (Defines the exploratory window.)
5. Databricks workspace URL, catalog permissions and a service identity for CI.

## 12. Key risks

Thin books at far strikes; few resolved events; resolution-rule mismatch; memorized outcomes in LLMs; free nowcast terms of use; IBKR API/session reliability; limited historical data making early results indicative only.
