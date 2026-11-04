# P2b data feasibility check (2026-10-30)

Method: FRED connector metadata and small observation pulls. The direct FRED/ALFRED hosts were unreachable from the dev shell (HTTP 000/timeouts) and no FRED API key is configured, so **ALFRED vintage depth and first-print availability were NOT verified**.

## Coverage (verified, single-run)

Single-run numbers from 2026-10-30; not yet reproducible by a script. To re-check, query each series' metadata and observation range through the FRED connector or the public series page `https://fred.stlouisfed.org/series/<SERIES_ID>` (for example `https://fred.stlouisfed.org/series/DFEDTARU`) and compare start/end dates. A reproducing script (`scripts/check_fred_coverage.py`, needs the FRED API key) is a P1 to-do. The end dates move daily; the start dates should not.

| Series | Start | End (at check) | Notes |
|---|---|---|---|
| `DFEDTAR` | 1982-09-27 | 2008-12-15 | discontinued; single target |
| `DFEDTARU` | 2008-12-16 | current | upper limit of range, daily |
| `DTB4WK` | 2001-07-31 | 2026-10-28 | |
| `DTB3` | 1954-01-04 | 2026-10-28 | used pre-2001 |
| `EFFR` | 2000-07-03 | 2026-10-28 | `DFF` not checked |
| `T10Y3M` | 1982-01-04 | 2026-10-29 | |
| `T5YIE` | 2003-01-02 | 2026-10-29 | |
| `CPIAUCNS` | 1913-01 | 2026-09 | NSA headline |
| `CPILFENS` | 1957-01 | 2026-09 | NSA core |
| `PAYEMS` | 1939-01 | 2026-09 | SA; first prints need ALFRED |
| `ICSA` | 1967-01-07 | 2026-10-24 | weekly |
| `SAHMREALTIME` | 1959-12 | 2026-09 | |
| `NFCI` | 1971-01-08 | 2026-10-23 | revised history; vintage coverage unchecked |
| `GASREGW` | 1990-08-20 | 2026-10-26 | |

All series needed for hypotheses #1-#10 exist back to at least 1994 except `DTB4WK` (2001, so `DTB3` before) and `T5YIE` (2003).

## Label-timing gotcha (found)

FRED target series are dated by **effective date**, not announcement date. Example: the 2022 hike was announced 2022-03-16 at 14:00 ET, but `DFEDTARU` shows 0.25 on 03-15 and 03-16 and 0.50 from **03-17**. In the 1994 sample the change shows on 1994-02-04, the meeting day, because effectiveness was same-day then.

Rule for `synthetic_binaries`: take the meeting date from the FOMC calendar (announcement date), set `label_ts` = 14:00 ET that day, define the outcome as the target in effect on the **next calendar day after the announcement**, bounded to at most 3 calendar days after the announcement and reconciled with the statement text; never search beyond that window (searching for "the first date the change shows" could pick up a later meeting's decision after a hold), and the pre-state as the target on the day before the announcement. Reconcile against the statement text for a sample of meetings. Never read the target at `announcement date` and call it post-decision.

## Not verified (open)

- ALFRED first-print depth for `PAYEMS` and release timestamps (needs an API key and network access from the build host).
- First-print label rule: a first print is usable only if `available_ts <= label_ts` (08:30 ET release) is established from the release calendar or a first-observed record; an ALFRED vintage date alone is not proof. Otherwise the label is missing and excluded.
- Cleveland Fed nowcast history start; ADP coverage on FRED; `DFF` and CME FedWatch free history.
- FOMC calendar completeness 1994-2024 (about 248 scheduled meetings is an estimate).
- Whether `NFCI` vintages exist (its history is revised).

## Next

Get a FRED API key (free) into a Databricks secret scope and a dev `.env`, then run the ALFRED first-print audit for `PAYEMS` (1994-) and reconcile the CPI YoY rounding against BLS.
