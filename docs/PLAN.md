# pm-macro-lab: project plan

Status: draft v4 (2026-10-30). Produced from a two-model discussion (Claude Opus and GPT Sol), two research rounds and one debate round, then amended by the owner's decisions below. Items marked **UNVERIFIED** were not confirmed from a primary source and must be checked in P0.

## 1. Thesis

Prediction-market prices on US macro releases are the baseline. We test whether free macro data, nowcasts and Fed communication scored by a strong LLM add out-of-sample information beyond the market price, and whether the market's own structure offers hedged or relative-value opportunities. A rigorous null result ("no edge after costs, and here is why") is a valid, publishable outcome.

Two targets are always scored separately:
1. the eventual outcome (resolution value)
2. a later executable price move

## 2. Owner decisions (binding)

| Decision | Choice |
|---|---|
| Venue | **Interactive Brokers (IBKR) / ForecastEx** event contracts (legal route from Singapore). IBKR Gateway runs on the owner's own device. |
| Events | FOMC, CPI, Payrolls |
| Build order | CPI pipeline first (owner decision), but see section 3: the first *calibration test* runs on FOMC because CPI is thin |
| Data | Free sources only ("freecast": free nowcasts). Model inference cost is separate from the free-data rule. |
| LLM | **Strong model** as the primary scorer (section 7) |
| Trading | Paper trading only. No live capital without a separate owner decision. |
| Repo | `pm-macro-lab`, private |
| Platform | New Databricks workspace (separate from qp1) |
| Code style | Polars only (no pandas); `data_source` column on every row |

## 3. Venue facts (ForecastEx via IBKR)

**Verified by at least one model from a primary page, and re-checked where noted:**
- Products: `CPIY` (US CPI Yearly, **year-over-year, not month-over-month**; NSA headline), `CPIC` (core CPI, YoY), `FF` (Fed funds target "above X%", 25bp steps), `FFDEC` (Fed decision), `PREMP` (payroll employment thresholds). Rule PDFs: `data.forecastex.com/regulatory/CPIYTermsandConditions.pdf`, `CPICTermsandConditions.pdf`.
- Each contract pays $1 or $0, quoted in $0.01 ticks. No selling: exit by buying the opposite side (IBKR nets the pair). Limit orders only (DAY, GTC, IOC).
- Stop times reported in ForecastEx files: payrolls and CPI around 07:30 CT, Fed contracts around 13:00 CT. Settlement source: initial BLS release for CPI/payrolls (plausible; **UNVERIFIED**, read the contract specs).
- Fees: $0 IBKR commission plus a $0.01 exchange fee per contract, charged on each side per the ForecastEx FAQ. Reconcile against the paper account to avoid double-counting.
- Incentive coupon: IBKR displays about 3.38% APY on position value, variable, paid monthly. It must be included in P&L and carry analysis.
- API: contracts are `secType=OPT`, `exchange=FORECASTX`, Right `C`=Yes and `P`=No. `BID` is the highest bid and `ASK` means "Buy Yes Now at", not an ordinary sell quote. IBKR says historical TRADES and real-time LAST are not available through the API.
- Free history from the exchange itself (re-verified 2026-10-30 by direct request, HTTP 200 text/csv): `https://forecastex.com/api/download?type={prices|pairs|summary}&date=YYYYMMDD`. `prices` and `pairs` returned data for 2024-08-01 and 2026-09-24; `summary` returned 404 for 2024-08-01 but data for 2026-09-24. Opus reports `pairs` has matched trades with nanosecond timestamps; schemas, completeness and redistribution terms are **UNVERIFIED**. One model got 404s earlier, so treat availability as flaky and retry with backoff. There is no order-book history.
- Liquidity snapshot (single day, 2026-09-24, `total_pairs`): `FFDEC` 5,349; `FF` 1,928; `PREMP` 185; `CPIY` 86; `CPIC` 57. One day is a warning, not a measurement: P0 must measure volume, quote size and freshness across strikes and time.

**UNVERIFIED, account-specific P0 gates:** the owner's Singapore eligibility and permission name; whether live (not delayed) quotes are free; whether a paper account can see and trade `FORECASTX` contracts; historical `BID`/`ASK`/`MIDPOINT` bars via `reqHistoricalData`; ForecastEx rulebook details.

**Consequences for the plan**
- Week-1 gate is split. *Historical research* (ForecastEx CSVs + FRED) can start now. *Executable claims* need captured quotes from the owner's Gateway.
- First calibration test runs on FOMC (`FF`/`FFDEC`) because it has far more volume. CPI remains the first data-pipeline build because its labels and nowcast mapping are the hardest part to get right.
- CPI target is **YoY on the NSA index (CPIAUCNS)**, not MoM. 11 of 12 months in a YoY print are already known, so the contract is a bet on one month's NSA change plus a base effect. The nowcast model must be built accordingly.

## 4. Free data sources

| Need | Source | Notes |
|---|---|---|
| Historical market prices/trades | ForecastEx CSV downloads | Indicative history only; no order books. Check terms. |
| Live quotes | IBKR TWS/Gateway on owner's device | Capture **both YES and NO legs** (do not derive NO from YES). |
| Macro history with vintages | FRED / **ALFRED** REST API | Use vintages; key in a Databricks secret scope. FRED MCP is for exploration only. |
| First-print labels | BLS release pages / ALFRED earliest vintage | Must match contract resolutions. |
| Release calendar | FRED release dates, BLS, Fed | Store official release time and our ingestion time separately. |
| Fed dot plot (SEP) | federalreserve.gov `monetarypolicy/fomcprojtabl{YYYYMMDD}.htm` (HTML tables; Figure 2 = anonymous dot histogram per 1/8-point midpoint); FRED release 326 series `FEDTARMD`, `FEDTARMDLR`, `GDPC1MD`, `UNRATEMD`, `PCECTPIMD`, `JCXFEMD` | Released 14:00 ET on the meeting's last day (Mar/Jun/Sep/Dec). FRED serves only the latest projection by default: use ALFRED vintages for history (depth **UNVERIFIED**), parse the Fed HTML for each release, and reconcile two releases by hand against the PDF. About 9 releases since Sep 2024. Dots are anonymous and cannot be linked to speakers. |
| Nowcasts | Cleveland Fed inflation nowcast, Atlanta Fed GDPNow, NY Fed | Check terms and snapshot timing. |
| Energy prices | FRED GASREGW (EIA) | For CPI energy pass-through. |
| Rates | FRED DTB4WK, DTB3, EFFR, SOFR, DGS2 | Daily only; cannot validate intraday fills. |
| Fed communication | federalreserve.gov statements, minutes, speeches | Main text signal for H2. |
| News | GDELT (free, 15-minute) | Noisy; dedupe. |
| Consensus forecasts | none free | Nowcasts only. |

Raw data stays in the private workspace; publish only derived aggregates. Record terms in `docs/data_licensing.md`.

## 5. Hypotheses

- **H1 (calibration):** strike-ladder probabilities are miscalibrated against a nowcast/base-effect model at T-7d, T-1d, T-1h. First test on FOMC, then CPI. SEP `dot_minus_market_bp` is a conditioning control.
- **H2 (information flow):** LLM-extracted Fed-communication features add out-of-sample log-loss improvement beyond market + nowcast. Confirmatory test uses only Track C in section 7.
- **H4 (historical translation):** relationships found in 1994-2024 synthetic outcomes translate out of sample (R5 holdout) and into the ForecastEx era under the criteria in section 7c.
- **H3 (paper portfolio):** quarter-Kelly sizing with fills against captured books survives spread, fees, latency and partial fills.

## 6. Quant analyses and market-neutral strategies

Mechanics: ForecastEx does not allow selling, so "short" means buying the NO contract; positions are fully collateralized. Hedging with CME futures/options through IBKR likely needs paid market data (**UNVERIFIED** whether delayed or paper data is free). For any external hedge, start with measurement using FRED data and add a tradable hedge only after confirming free timestamped prices and paper-instrument access.

| # | Analysis | Why it is hedged/neutral | Free data | Feasibility | Main risk |
|---|---|---|---|---|---|
| 1 | **Ladder no-arbitrage scan.** For thresholds K1<K2, buying YES(K2) + NO(K1) pays at least $1 in every outcome; flag executable cost below $1 after fees. Also YES/NO parity and `FFDEC` vs `FF` coherence for the same meeting. Do not assume vanilla-option butterfly convexity for digital prices. | Payoff locked in every state if both legs fill | CSVs + captured quotes | High for FF/FFDEC; CPI thin | Fees (~$0.02 per round trip) eat most gaps; stale/asynchronous quotes; legging. Doubles as a data-quality and simulator test. |
| 2 | **CPI YoY ladder vs base-effect + nowcast model** (Cleveland nowcast, ALFRED CPIAUCNS, gasoline). | Not market-neutral: limited-risk directional relative value, e.g. bounded YES/NO strike spreads | ALFRED, nowcast, FRED | Medium (thin book) | YoY mapping, seasonal factors, first print vs revision |
| 3 | **Fed-path relative value.** `FF` ladder distribution vs path implied by bills, EFFR, SOFR. | Measured as relative value now; estimated duration-neutral paper hedge later. A basis trade, not arbitrage. | FRED rates | High (most liquid) | Meeting-date and average-rate mismatch, risk premia, coarse bill curve |
| 4 | **Event-implied width vs realized surprise** and release-day moves in rates/SPY/TLT/FX. | Buying both tails is a hedged long-volatility shape; beta-hedged relative returns for the cross-asset study | ForecastEx, ALFRED, FRED/free prices | Medium | Few events; tails are costly at the tick |
| 5 | **Core vs headline CPI consistency** (`CPIC` vs `CPIY`) vs energy-implied spread. | One ladder long, other short | ForecastEx, FRED | Low (both thin) | Not mechanically neutral; food/shelter noise |
| 6 | **Pre-release drift and repricing speed** from trade timestamps; repricing of `FF` after CPI/payrolls. | Research, not a trade | pairs CSV | High as a study | Not monetisable at this size; 5-minute capture cannot resolve fast repricing |
| 7 | **Coupon carry**: deep in-the-money long-dated YES earns coupon plus convergence vs T-bills. | Carry vs risk-free | ForecastEx, FRED DTB3 | Medium | Tail loss; coupon can change |
| 8 | Ladder vs TIPS breakeven | n/a | FRED T5YIE | Low | Horizon mismatch; descriptive only. Skip. |
| 9 | **SEP-day far-meeting repricing** (positive control). Does the `FF` ladder for later meetings visibly reprice around 14:00 ET on SEP days? Also which path moves toward which: dots, ForecastEx ladder, bills/SOFR. | Research/context, not a trade | pairs CSV, SEP tables, FRED rates | High as a study | About 9 events; a sign check, not inference. Own-meeting contracts stop before the release. |

**Run first: #1, #3, #2.** (Both models independently ranked ladder consistency, the nowcast comparison and Fed-path relative value as the top three, with differences in order.) Cross-asset hedges come after the executable-data question is answered.

## 7. LLM design (strong model, two tracks)

**Primary (Track C, confirmatory):** a strong model, `claude-opus-5-5` (Anthropic-documented cutoff June 2026) or `claude-sonnet-5-5` (same cutoff); the choice is made by a small hand-labeled evaluation in P2. Cost is negligible at a few hundred documents a year. Strict JSON schema output; score each document 3 times and store median and spread, because temperature cannot be set; cache every response (doc_hash, prompt_ver, model_id) permanently. Anthropic lists retirement no sooner than September 2027, so finish the confirmatory study before then.

**Exploratory (Track E):** pinned open-weight `Llama-3.1-70B-Instruct` (published cutoff December 2023; verify on the model card) on Databricks GPU, run over ForecastEx history from August 2024. Used for feature selection, prompt design and effect-size estimates only. `Llama-3.1-8B-Instruct` is an optional cheap comparator.

**Rules:**
- Prefer *extractive* features (wording changes, forward-guidance phrase counts, dissents) over judgment features ("hawkish surprise"); they leak less and transfer better across models.
- Pre-register the specification Track E picks (features, horizons, test statistic, alpha spent across indicators) in `config/preregistration.yaml`, committed before each event.
- Bridge test: score post-June-2026 documents with both tracks; if feature rank correlation is at least 0.8, Track E informs Track C, otherwise label Track E a different instrument.
- Score at ladder level (log loss of the implied distribution) and pool across indicators with event-clustered errors.
- A documented cutoff is necessary but not sufficient; post-cutoff scoring is still exploratory.

**`cutoff_guard`:**
1. Registry `config/llm_cutoffs.yaml`: `model_id`, `cutoff_end`, source URL, `verified_on`. Unknown cutoff, timestamps or model revision fails closed.
2. `safe_start = cutoff_end + 31 days` (2026-07-31 for the Claude models; use a 90-day margin for Llama, i.e. 2024-03-30).
3. A row is **confirmatory** only if: `doc.available_ts > safe_start`, `event.release_ts > safe_start`, `score_ts < event.release_ts`, `model_id` equals the pinned model, `prompt_hash` is in the pre-registration file committed before the event, and external retrieval was disabled.
4. All other rows are written with `confirmatory=false`.
5. A material model or prompt change starts a new confirmatory series; never mix models within one test.

Expected power: roughly 10 post-cutoff events so far and about 32 a year (12 CPI, 12 payrolls, 8 FOMC). The confirmatory H2 test is a 12-18 month collection horizon, not a guaranteed conclusion.

## 7b. Sentiment workstream: Fed speech repricing experiment

Both models agree sentiment runs **alongside** the ladder analyses, not instead of them. Key constraint: each contract stops trading at its own release (CPI and payrolls about 07:30 CT, FOMC about 13:00 CT), so a statement, BLS release or press conference can never predict its own contract. Text feeds the *next* event. Useful text arrives between events: speeches until the blackout (second Saturday before a meeting), minutes about three weeks after a meeting, Beige Book about two weeks before one.

**Sources.** Core: federalreserve.gov statements, minutes, Beige Book (exact release times), Board speeches and testimony (date reliable; time of day often only the scheduled time). Next-meeting only: press-conference transcripts (do not timestamp at conference start unless the real publication time is verified). Control: SEP/dot plot as a number. Phase 2: regional Fed speeches and district Beige Book text. Outcome only: BLS CPI/payroll text (labels and surprise, never a feature for the same event). Defer: GDELT (15-minute cadence is not a publication guarantee; use only as an attention control later). Skip: X, Reddit, full-text wires, earnings calls, Google Trends. Store `published_ts`, first-observed `available_ts`, `ingest_ts`, URL, content hash and version per document. Unverified intraday availability: set `available_ts` to end of day (primary rule) and exclude the document from intraday tests.

**Extraction (strict JSON schema, evidence spans, "not stated" option).** Never ask the LLM for a forecast probability. Compute diffs deterministically (`difflib`) against the previous document of the same type and the same speaker's previous speech; the LLM classifies each changed span for direction (-2..+2) and topic. Levels are not used (Fed tone is persistent). Speech features: `near_term_policy`, `hawk_delta_vs_own_prior`, uncertainty, speaker weight (Chair/Vice Chair 3, governor 2, voting president 1.5, non-voter 1). Minutes: quantifier counts ("many", "several") on the rate path. Dissents come straight from the statement. Novelty: embedding distance from the previous five documents. Beige Book price and labor sections feed CPI and payroll contexts later. A hand-labeled blinded sample and a dictionary/phrase-diff baseline validate the LLM; a fluent explanation is not validation.

**Targets.** Primary (Target B, repricing): change in the implied next-meeting expected rate (one predefined near-the-money FF threshold rule, not the best-performing strike) from the last trade before a document's `available_ts` to the volume-weighted price over the following 24 hours, from the pairs CSV, with a minimum trade count. Secondary (Target A, outcome): market-implied distribution at decision time (FOMC: blackout start; CPI/payrolls: T-1d) with `logit(p') = logit(p) + beta * s`, one beta per indicator shared across strikes. Outcome log loss is tested separately from price moves.

**Baselines to beat.** Recalibrated market alone; then market + nowcast residual (analysis #2) + rates-path residual (analysis #3). Orthogonalise each text score against the change in nowcast and in DGS2 since the previous document; store raw and residual scores in `gold.text_features_pit` keyed `(event_id, as_of_ts)`.

**First experiment (Track E, historical, about 4 weeks): "Fed speech -> ForecastEx repricing".**
- Corpus: Board speeches, statements, minutes, Beige Books, Aug 2024 to Jun 2026, scored by pinned Llama-3.1-70B (`hawk_delta_vs_own_prior`, `near_term_policy`, `novelty`).
- Model A: next-meeting implied-rate change over 24h ~ same-day change in DGS2. Model B: Model A + speech score x `near_term_policy`.
- Primary statistic: partial correlation of the score with repricing, permutation p-value, block bootstrap by event. Placebo: shifting scores by one meeting must kill the effect. Sanity: hawkish sign must raise the implied rate.
- Limits: the pairs CSV gives trade prints, not quotes. This is a "did the price move" study, not a "was it tradable" study. The decision time for any paper simulation (later) is the first valid captured quote after scoring, within a preregistered quote-age limit.
- **Null result:** the 95% interval for the partial correlation contains 0 and is narrower than +/-0.15. Interpretation: Fed-speak is priced in by the next trade or uninformative. Then drop text-as-prediction for FOMC, keep text only as an event clock for analyses #1 and #3, and do not spend 18 months collecting for H2. A wide interval is inconclusive, not proof of no edge.
- **If positive:** pre-register exactly this specification for Track C (`claude-opus-5-5`) on events after 2026-07-31 and keep the prospective crawler running.

**Speech count (measured 2026-10-30, `docs/findings/fed-speech-count.md`).** The Board feed has 226 speech items since 2024-08-01 but only about 93 with policy/economy-titled content (about 91 outside blackout windows), far fewer than the "several hundred" assumed. The feed covers Board members only, not regional presidents. Detectable d at n=90 independent speeches is about 0.30, less after clustering by meeting window. The experiment is therefore more likely inconclusive than decisive; consider adding regional Fed speeches before P3.

**Power (disagreement flagged).** Detectable standardised effect is about 2.8/sqrt(n) (80% power, alpha 0.05): 8 FOMC events about 1.0; 32 events about 0.5; about 70 events (Track E history) about 0.33. Opus estimated several hundred speeches would detect d of about 0.15-0.2; the measured count above is lower, as Sol cautioned. **The speech count and variance are unverified: estimate power by simulation in P1 before committing to the experiment.**

**SEP (dot plot) integration.** Both models: track it as a point-in-time anchor and information shock, not as a predictor (about 4 releases a year, about 9 in sample; dots forecast poorly and markets absorb them within minutes). Minimal roles: (1) **positive control** for the speech experiment: if ForecastEx does not visibly reprice far meetings after an SEP (analysis #9), the speech study cannot detect anything smaller; (2) **construct-validity check** for the LLM scorer: average `hawk_delta` of speeches between two SEPs should have the sign of the next `dot_median_shift` (nine points, a sign check only); (3) slow-moving control in the PIT tables. The SEP cannot predict its own meeting's `FF`/`FFDEC` contracts (it is released with the decision); it informs later meetings. In the speech experiment, use the **last SEP before the speech**, never the next. The year-end dot for year Y maps to the December `FF` ladder for Y; whether "above X" lines up with the 1/8-point midpoint grid is **UNVERIFIED** (read the contract spec). Features: `dot_median_shift` (same horizon vs previous SEP), dispersion (IQR, count above/below market), `dot_minus_market_bp` (vs December FF ladder implied mean and a bills/SOFR proxy; relative-value context, not arbitrage), `market_repricing_sep`. Disagreement: Opus expects dots to chase the market (gap closes from the dot side); this is a hypothesis for #9, not a finding. Engineering budget: about 2 days; no separate trading claim.

**Prior.** Likely adds nothing: CPI YoY (base effect, nowcast and gasoline dominate), payrolls, FOMC meetings already priced above 90%. Possible value: slow ForecastEx repricing after speeches and minutes, FF meetings 2-3 meetings out, meetings priced 20-80%. Thin CPI strikes are a staleness problem (analysis #1), not a sentiment problem.

**Testing rules.** One pre-registered primary hypothesis per track; everything else exploratory with Benjamini-Hochberg correction; pool indicators only in a separately preregistered hierarchical analysis.

## 7c. Historical synthetic-binary backtest (1994-2024)

Purpose: before ForecastEx existed (market data starts about 2024-08), build the same yes/no questions from real outcomes, test classic hypotheses about whether rates go up or down, and then ask whether what works historically translates out of sample and into the ForecastEx era. Both models agree this is a **historical forecasting lab, not a trading backtest**: without contemporaneous executable prices it cannot establish a historical trading edge. Before 2024 there is no market price for CPI or payrolls (no free consensus, fixings or CPI swaps), so those tests are model-versus-model. For FOMC a free proxy exists (bills + EFFR) but needs its own bridge test.

**Synthetic labels (all point-in-time, timestamps stored: `decision_ts`, `label_ts`).**
- **Fed target ladder:** `Y_{m,K} = 1[target_after_m > K]`, equality resolves NO. Target = `DFEDTAR` to 2008-12-15, then the upper bound (`DFEDTARU`; Opus used the midpoint of upper/lower, Sol the upper bound; reconcile with the ForecastEx `FF` spec before claiming a match). Scheduled meetings from Feb 1994 (about 248 through 2024).
- **Decision class:** hike/hold/cut = target after minus target immediately before the announcement. Unscheduled moves (2001, 2008, Mar 2020) are tagged `intermeeting`, folded into the next meeting's pre-state, never counted as outcomes.
- **CPI YoY:** `Y = 1[round(CPIAUCNS_t / CPIAUCNS_{t-12} - 1, 1dp) > K]`; core uses `CPILFENS`. NSA CPI-U is not revised, but read it from ALFRED as of release date and reconcile rounding with BLS published YoY.
- **Payrolls:** `Y = 1[first-print change in PAYEMS > N]` from the ALFRED vintage at release date (never today's revised levels). ALFRED depth for `PAYEMS` is **UNVERIFIED**; label as missing if the first print cannot be audited.
- **Timing:** `decision_ts` = T-1 business day close; `label_ts` = 08:30 ET (BLS) or 14:00 ET (FOMC). Vintage dates alone do not establish intraday availability.
- **Strike grids are chosen before each event** from information then available: a fixed preregistered grid plus a near-the-money strike centred on the **baseline's** median at decision time, never on the outcome. Mimic ForecastEx spacing (CPI +/-0.1/0.2/0.3pp; payrolls +/-50k/100k/150k; Fed 25bp around the pre-meeting target +/-75bp).

**Baselines (never called "market-implied" unless a bridge test passes).**
- **Universal:** expanding-window regularised model on the current target, prior changes, time to event and recent first prints.
- **FOMC rates proxy:** bill yield (`DTB4WK` from 2001, `DTB3` before) and `DFF`/EFFR versus the target, mapped to probabilities by a walk-forward ordered logit fitted only on prior meetings. Contaminated by bill supply, flight to quality and debt-ceiling episodes; flag them.
- **CPI:** base-effect arithmetic + AR model of seasonal NSA monthly changes + gasoline (`GASREGW`); Cleveland nowcast only where its history exists (**UNVERIFIED**).
- **Payrolls:** 3-month trend + initial claims (`ICSA`) (+ ADP if FRED coverage is confirmed).
- Optional benchmarks: Philadelphia Fed SPF (quarterly); CME FedWatch history only if free bulk access is verified (**not verified**).

**Bridge test.** In the ForecastEx era compare the bill-proxy FOMC probabilities with ForecastEx `FF`/`FFDEC` prices. If MAE <= 10pp and r >= 0.8, the proxy is a credible stand-in for "the market" in history; otherwise historical "edge vs market" claims are downgraded to "edge vs a noisy proxy". (Threshold proposed by Opus; not independently tested.)

**Hypotheses (power: detectable standardised d is about 2.8/sqrt(n_events); counts are events, not independent strikes).**

| # | Hypothesis (literature) | Target; baseline to beat | n / detectable d |
|---|---|---|---|
| 1 | Data surprises reprice the next meeting (Gurkaynak-Sack-Swanson style): first print minus model surprise vs release-day change in bill/2y yield | Release-day change in proxy probability; martingale | about 744 releases / 0.10 |
| 2 | The Fed rarely surprises a strongly priced market ("follows the market"): bill proxy | Decision class; persistence | 248 (about 175 excl. ZLB) / 0.21 |
| 3 | CPI base-effect + energy model calibration | CPI ladder labels; climatology | 372 / 0.15 |
| 4 | Yield-curve slope predicts cuts within 4 meetings (Estrella-Mishkin), `T10Y3M` | Cut within 4 meetings; bill proxy | about 175, overlapping / 0.21 |
| 5 | Sahm rule / labour slack predicts cuts (`SAHMREALTIME`, `UNRATE` vintages) | Cut within 2 meetings; bill proxy | about 175 / 0.21 |
| 6 | Financial conditions "Fed put" (`NFCI`, `VIXCLS`; NFCI is revised, verify vintages) | Next cut; bill proxy | about 175 / 0.21 |
| 7 | Policy persistence / momentum (Rudebusch; Clarida-Gali-Gertler); time since last change | Next move; bill proxy. **Prior: adds nothing beyond the market**; holds dominate | about 175 |
| 8 | Real-time Taylor-rule gap from vintage inflation and slack (Orphanides) | Direction 2-4 meetings ahead; bill proxy | about 175 / 0.21 |
| 9 | Inflation expectations predict hikes (`T5YIE` from 2003, `MICH`, SPF) | Hike within 4 meetings; bill proxy | about 140 / 0.24 |
| 10 | Payroll momentum / claims calibration | Payroll labels; rolling first-print trend | 372 / 0.15 |
| 11 | Fed communication tone and statement diffs predict the next decision | Decision class; bill proxy + #2. Leakage-constrained | about 175 / 0.21 |

Run first: **#1, #2, #3** (they build and validate the baselines; #1 has the most power). Opus ranks #1 first; Sol's ranking starts with persistence and short-rate path (his #1-#2 are essentially the baseline models) and puts surprises and communication later; both agree communication has low incremental power. Published effects tend to shrink after publication (McLean-Pontiff); treat post-publication years as extra out-of-sample. Test families get Benjamini-Hochberg control; overlapping horizons use HAC (Newey-West) errors. Term-premium and "Fed follows markets" causal claims are out of scope until genuinely point-in-time series exist; timing association cannot establish that the Fed followed the market.

**Text and leakage in history.** Both planned LLMs were trained after essentially all this history, so assume they know what happened. Do not override `cutoff_guard` or treat retrospective LLM scores as confirmatory.
1. Text-free first: hypotheses #1-#10 use no text.
2. Classical NLP as primary text features: deterministic statement diffs (added/removed forward-guidance phrases), a fixed policy lexicon (Apel-Blix Grimaldi style), TF-IDF novelty, Loughran-McDonald as a general financial-language comparator (check licence; it is not a validated hawkishness dictionary). Train embeddings only on prior documents; modern pretrained embeddings can leak too.
3. LLM scoring only after a dictionary baseline exists, with masking (dates, names, numeric levels, event words) and extraction-only questions about changed spans. Masking is a sensitivity check, **not a cure** for memorization.
4. Leak probe: ask the model to identify the year/meeting of a masked document; if accuracy exceeds about 2x chance, masking failed for that document class.
5. Cutoff contrast: if the LLM beats the dictionary only before its cutoff, that is memorization.
6. A historical LLM result cannot select a strategy unless the dictionary or text-free version shows the same sign.
Features that did not exist early: statements from 1994, forward guidance from 2003, press conferences from 2011, dots from 2012.

**Regimes and out-of-sample design.**

| Regime | Period | FOMC tests |
|---|---|---|
| R1 | 1994-2008, single target | Yes |
| R2 | 2008-12 to 2015-12, ZLB | No (trivial outcomes); CPI and payrolls kept |
| R3 | 2016-2019 | Yes |
| R4 | 2020-2021, ZLB | No |
| R5 | 2022 to 2024-07, hikes then cuts | **Sealed holdout** (both models) |
| R6 | 2024-08 onward, ForecastEx era | Translation test |

- Expanding-window walk-forward, minimum 10-year warm-up (Opus: refit annually from 2002, purge one meeting around each refit); transformations, thresholds and calibration fitted inside each training window; group all strikes by event.
- Leave-one-regime-out coefficients plus structural-break tests (Andrews sup-Wald, Bai-Perron).
- R5 stays sealed until `config/preregistration.yaml` freezes the specification; report ZLB, hiking and crisis periods separately with counts and intervals.

**H4: "historical relationships translate" (what that means).** Freeze one or two selected signals before looking at ForecastEx data. A hypothesis translates only if all hold: (1) same sign in every non-ZLB regime; (2) the R5 holdout coefficient lies inside the historical 90% interval and holdout log loss improves (one-sided p < 0.05); (3) in R6, market-only vs market + frozen signal, event-weighted out-of-sample log loss and Brier, improves by a preregistered practical threshold (Sol suggests 0.01 absolute Brier), with confidence intervals; the R6 estimate is not significantly below the historical one. With about 17 FOMC, 26 CPI and 26 payroll events in R6 expect "not contradicted" or inconclusive, not proof. Only the repricing version (#1) has real power. Require prospective quoted, fee-adjusted paper results before any execution claim.

**Risks.** The biggest: beating a weak proxy baseline looks like edge and is not. Strike-grid construction bias; features that did not exist yet; multiple testing across 11 hypotheses; overlapping horizons; holds dominating the sample; ALFRED/first-print gaps; regime breaks.

**Disagreements flagged.** Strike grid: Sol uses a fixed preregistered grid plus a near-the-money strike; Opus centres on the baseline median and mimics ForecastEx spacing (the plan uses both). Practical translation threshold: Sol proposes a Brier margin; Opus proposes sign/holdout criteria (the plan requires both). Target bound: upper bound vs midpoint (to be reconciled with the contract spec).

## 8. Backtest and evaluation rules

- Market-only calibrated baseline first (Brier, log loss, reliability), then the incremental out-of-sample effect.
- Chronological splits grouped by release; strikes within a release are correlated. At each training cutoff include only labels already resolved; purge window around the cutoff.
- Event-clustered errors; Holm correction across indicators.
- Fills use captured bid/ask plus fees plus modeled latency. Results from CSV-only periods (no quotes) are labelled **indicative, not executable**.
- Include the incentive coupon in P&L; record the historical coupon rate.
- Exclude the final N hours before resolution; include voided contracts.
- Never use contract-rule versions that became valid after `as_of_ts`.
- Small-sample warning in every report.

## 9. Databricks design (new workspace)

Catalog `pm_macro`, schemas `bronze`, `silver`, `gold`, `ml`. Polars transforms, Spark I/O at the edges. Every row carries `data_source`, `ingest_ts`; bronze adds `payload_hash`, `schema_ver`.

**Bronze (append-only, idempotent):** `forecastex_prices_raw`, `forecastex_pairs_raw`, `forecastex_summary_raw` (serverless job, no device needed); `ibkr_contracts_raw`, `ibkr_quotes_raw` (from the device); `fred_obs_raw`, `alfred_vintages_raw`, `release_calendar_raw`, `nowcast_raw`, `fed_docs_raw` (with first-seen `available_ts`), `fed_sep_html_raw` (url, meeting_date, fetched_ts, payload_hash, `data_source="frb_sep"`; SEP FRED series go into `alfred_vintages_raw`), `gdelt_raw`.

**Silver:** `fomc_decisions`, `synthetic_events`, `contracts` (SCD2 on rules), `quotes` (YES and NO legs, bid/ask, size, field semantics, stale flag), `trades`, `macro_events`, `event_contract_map`, `first_prints`, `vintages`, `text_docs` (pub_ts, available_ts, ingest_ts), `text_scores` (model_id, model_cutoff, prompt_ver, confirmatory flag), `sep_releases` (sep_id, meeting_date, release_ts, n_participants), `sep_dots` (sep_id, variable, horizon, midpoint, n), `sep_summary` (median, central tendency, range per variable and horizon).

**Gold:** `implied_dist` (pmf + monotone_flag), `ladder_arb_flags`, `features_pit` (UC feature table, time-series key `as_of_ts`), `labels` (separate), `synthetic_binaries` (event_id, qtype, strike, label, decision_ts, label_ts, baseline_prob, baseline_src, regime), `proxy_bridge`, `text_features_classical`, `preds`, `sep_features_pit` (keyed `(as_of_ts, horizon)`), `sep_event_study`, `signal_eval`, `paper_orders`, `paper_positions`, `paper_pnl`.

**Capture on the owner's device:** `ib_async` against IB Gateway, both legs, rotating batches under the 100 market-data-line default every 5 minutes, 50 messages/second pacing. Local Parquet with `capture_ts` and `data_source="ibkr_tws"`, uploaded hourly to a UC Volume. Daily Gateway restart and periodic re-login (2FA; no unattended headless login) are expected: log heartbeats and mark known gaps.

**Jobs (bundle):** ForecastEx CSV pulls daily; FRED/ALFRED and Fed text daily; pre-release burst around each calendar entry; no streaming in the MVP.

## 10. Phases and gates

| Phase | Weeks | Work | Gate |
|---|---|---|---|
| P0 | 1 | Repo, bundle, catalog, secret scope, CI. IBKR checks: eligibility, live quotes, paper orders, `reqHistoricalData`, fee convention. ForecastEx CSV audit (schemas, coverage, terms). Start both-leg quote capture. **Start the Fed speech/first-seen crawler (federalreserve.gov RSS/pages, store `available_ts` on first observation).** | CSV audit documented; 72h capture with no gaps; IBKR gates passed or fallback chosen |
| P1 | 1-3 | CPI YoY pipeline: contracts, ALFRED CPIAUCNS, first prints, calendar, base-effect + nowcast inputs. FOMC data from CSVs. Analysis #1 (ladder scan) on history. SEP parser + backfill (about 9 releases) with human reconciliation; analysis #9. | First-print labels match contract resolutions 100%; liquidity measured per strike |
| P2 | 3-6 | FOMC calibration (H1), analysis #3 (Fed-path RV), CPI analysis #2, market-only baselines. Select Track C model on a labeled sample. | Leakage suite passes; baseline report merged |
| P2b | 3-7 (parallel with P2) | Historical synthetic-binary lab (section 7c): labels, ALFRED/first-print audit, baselines, hypotheses #1-#3, proxy bridge test. Needs no device; reuses the P1 pipeline. | Label audit against archived BLS/FOMC data; R5 sealed |
| P3 | 6-9 | **Fed speech repricing experiment (section 7b)** on Track E; power simulation first; pre-registration, bridge test, Track C prospective scoring begins only if the result is positive | Pre-registration committed; or null result written up |
| P3b | 8-12 | Hypotheses #4-#10, dictionary/diff text features, then masked LLM scoring with leak probe; H4 translation test (freeze signals first) | Pre-registration committed; H4 verdict or inconclusive |
| P4 | 9-14+ | Payrolls; remaining analyses (#4-#7); paper trading against captured books, minimum 6 weeks. Cross-asset hedge only if free timestamped data and paper access are confirmed. | Live capital requires a separate owner decision |

## 11. Repo layout

```
README.md  AGENTS.md  pyproject.toml  databricks.yml  .gitignore
.github/workflows/ci.yml   .coderabbit.yaml
config/  data_sources.py  indicators.yaml  llm_cutoffs.yaml  preregistration.yaml  prompts/
resources/jobs/*.yml
src/pm_macro/
  ingest/{forecastex_csv,ibkr_capture,fred_alfred,fed_text,gdelt,calendar}.py
  bronze/ silver/ gold/
  features/pit.py   labels/first_print.py
  analysis/{synthetic_binaries,ladder_arb,fed_path_rv,cpi_base_effect,speech_repricing,sep_repricing}.py
  ingest/sep.py
  llm/{score,cache,cutoff_guard}.py
  models/{calibration,nowcast,combined}.py
  backtest/{replay,fills,sizing,metrics}.py
  paper/broker_sim.py
tests/{unit,leakage,fixtures}/
docs/{PLAN.md,data_licensing.md,decisions.md,findings/}
```

CI: ruff, mypy, unit + leakage tests (`pytest -m "not spark and not databricks and not live"`), `databricks bundle validate`, a check that fails on pandas imports or committed data files outside `tests/fixtures`. CI never needs licensed data and never places orders. Required leakage tests: planted future-dated row ignored; revised vintage not visible before its vintage time; `cutoff_guard` rejects pre-cutoff events and unknown cutoffs; confirmatory flag requires a pre-registered prompt hash; SEP rows are invisible before 14:00 ET on the release date; FRED SEP values are read only from vintages existing at `as_of_ts`; SEP parser output is reconciled against two PDFs; strike grids are computed from data at or before `decision_ts` only; the R5 holdout is unreadable without a pre-registration hash.

## 12. Open questions

1. IBKR P0 gates (section 3): eligibility, live quote cost, paper access to `FORECASTX`, historical bars, fee convention.
2. ForecastEx CSV terms of use and schema/completeness audit.
3. Do free delayed prices exist for a tradable rates hedge (ZQ/SOFR futures), or do cross-asset analyses stay measurement-only?
4. Track C model choice (Opus vs Sonnet) and GPU budget for Track E on Databricks.
5. Databricks workspace URL, catalog permissions and a service identity for CI (deferred by the owner).

## 13. Key risks

Thin books at far strikes and for CPI; few resolved events; fees of about $0.02 per round trip eating ladder gaps; stale or asynchronous quotes and legging; resolution-rule mismatch; LLM memorization and non-determinism; model retirement before the confirmatory study ends; flaky or restricted free data endpoints; IBKR Gateway session reliability; indicative-only results where no quote history exists.
