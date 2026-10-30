from datetime import UTC, datetime

import polars as pl

from pm_macro.features.pit import asof_latest

T = lambda h: datetime(2026, 9, 16, h, tzinfo=UTC)


def test_future_dated_fact_is_invisible():
    spine = pl.DataFrame({"k": ["a"], "as_of_ts": [T(12)]})
    facts = pl.DataFrame(
        {"k": ["a", "a"], "available_ts": [T(10), T(13)], "v": [1.0, 999.0]}
    )  # planted future row
    out = asof_latest(spine, facts, key="k", value_cols=["v"])
    assert out["v"][0] == 1.0


def test_revised_vintage_not_visible_before_vintage_time():
    spine = pl.DataFrame({"k": ["cpi"], "as_of_ts": [T(15)]})
    facts = pl.DataFrame(
        {"k": ["cpi", "cpi"], "available_ts": [T(13), T(16)], "v": [3.1, 3.4]}
    )  # revision published later
    out = asof_latest(spine, facts, key="k", value_cols=["v"])
    assert out["v"][0] == 3.1


def test_no_fact_before_availability_gives_null():
    spine = pl.DataFrame({"k": ["a"], "as_of_ts": [T(9)]})
    facts = pl.DataFrame({"k": ["a"], "available_ts": [T(10)], "v": [5.0]})
    assert asof_latest(spine, facts, key="k", value_cols=["v"])["v"][0] is None
