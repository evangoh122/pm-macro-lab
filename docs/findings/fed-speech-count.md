# Fed speech count (2026-10-30)

Source: `https://www.federalreserve.gov/json/ne-speeches.json` (Board feed; 1,349 items back to 2008-11).

**Single-run numbers (2026-10-30), reproduce with `scripts/count_fed_speeches.py`:**

```
curl -sSL -o /tmp/ne-speeches.json https://www.federalreserve.gov/json/ne-speeches.json
python3 -I scripts/count_fed_speeches.py /tmp/ne-speeches.json   # prints the "since 2024-08-01" count
```

The script reproduces only the 226 total (and the item count); the blackout, keyword-filter and by-speaker figures below came from ad-hoc one-off analysis that is not yet scripted, and the feed itself changes as new speeches are added, so later runs will differ.

Since 2024-08-01 (to 2026-10-14):

| Measure | Count |
|---|---|
| Board speech items | **226** |
| Outside approximate FOMC blackout windows | 214 |
| Heuristic policy/economy-titled (keyword filter on title and venue, excludes supervision/regulation/payments/AI/crypto titles) | **~93** |
| Policy-titled and outside blackout | **~91** |

By speaker (all items): Bowman 55, Waller 41, Barr 38, Cook 25, Jefferson 23, Powell 19, Kugler 18, Miran 6, Warsh 1.

Caveats:
- The feed is **Board members only**. Regional Reserve Bank presidents (most FOMC voters rotate from there) are NOT included, so this undercounts policy-relevant speech.
- Many Board speeches are supervision/regulation, which is why the policy-titled count is far below 226. The keyword filter is a rough heuristic; labeling should be done by the LLM and checked by hand.
- The `d` field has 90 distinct times of day, so it looks like a real scheduled time, but whether it is Eastern time and whether the text was posted then is **unverified**. Primary rule stays: use first-observed `available_ts`, fall back to end of day.
- The blackout filter is an approximation (second Saturday before each meeting through the day after).
- A few months have only 2-3 items (Dec 2024, Dec 2025, Jun 2026, Aug 2026).

Implication for power: ~90 policy-relevant speeches over ~26 months is far fewer than the "several hundred" Opus assumed. Detectable standardised effect at n=90 is about 2.8/sqrt(90) = 0.30 if speeches were independent, so the speech experiment is more likely to be inconclusive than decisive. Clustering by meeting window lowers effective n further. Run the P1 power simulation before committing, and consider adding regional Fed speeches.
