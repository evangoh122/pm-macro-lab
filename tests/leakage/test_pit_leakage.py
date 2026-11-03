from datetime import UTC, datetime

import polars as pl
import pytest

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


def test_shuffled_multigroup_input_and_spine_order_preserved():
    spine = pl.DataFrame(
        {"k": ["b", "a", "b", "a"], "as_of_ts": [T(15), T(12), T(11), T(18)]}
    )
    facts = pl.DataFrame(
        {
            "k": ["a", "b", "a", "b", "a", "b"],
            "available_ts": [T(17), T(10), T(10), T(14), T(19), T(16)],
            "v": [2.0, 20.0, 1.0, 21.0, 999.0, 998.0],
        }
    )
    out = asof_latest(spine, facts, key="k", value_cols=["v"])
    assert out["k"].to_list() == ["b", "a", "b", "a"]  # spine order kept
    assert out["v"].to_list() == [21.0, 1.0, 20.0, 2.0]  # 998/999 are in the future


def test_fact_exactly_at_as_of_ts_is_visible():
    spine = pl.DataFrame({"k": ["a"], "as_of_ts": [T(12)]})
    facts = pl.DataFrame({"k": ["a"], "available_ts": [T(12)], "v": [7.0]})
    assert asof_latest(spine, facts, key="k", value_cols=["v"])["v"][0] == 7.0


def test_tied_timestamps_raise():
    spine = pl.DataFrame({"k": ["a"], "as_of_ts": [T(12)]})
    facts = pl.DataFrame({"k": ["a", "a"], "available_ts": [T(10), T(10)], "v": [1.0, 2.0]})
    with pytest.raises(ValueError, match="ambiguous"):
        asof_latest(spine, facts, key="k", value_cols=["v"])


def test_tied_timestamps_resolved_by_version_column():
    spine = pl.DataFrame({"k": ["a"], "as_of_ts": [T(12)]})
    facts = pl.DataFrame(
        {"k": ["a", "a"], "available_ts": [T(10), T(10)], "v": [1.0, 2.0], "ver": [2, 1]}
    )
    out = asof_latest(spine, facts, key="k", value_cols=["v"], version_col="ver")
    assert out["v"][0] == 1.0  # ver=2 row wins (v=1.0)
    assert "ver" not in out.columns


def test_tied_timestamps_and_version_still_raise():
    spine = pl.DataFrame({"k": ["a"], "as_of_ts": [T(12)]})
    facts = pl.DataFrame(
        {"k": ["a", "a"], "available_ts": [T(10), T(10)], "v": [1.0, 2.0], "ver": [1, 1]}
    )
    with pytest.raises(ValueError, match="ambiguous"):
        asof_latest(spine, facts, key="k", value_cols=["v"], version_col="ver")


def test_null_key_rejected_in_facts_and_spine():
    good_spine = pl.DataFrame({"k": ["a"], "as_of_ts": [T(12)]})
    bad_facts = pl.DataFrame({"k": [None], "available_ts": [T(10)], "v": [1.0]})
    with pytest.raises(ValueError, match="null"):
        asof_latest(good_spine, bad_facts, key="k", value_cols=["v"])
    bad_spine = pl.DataFrame({"k": [None], "as_of_ts": [T(12)]}, schema={"k": pl.String, "as_of_ts": pl.Datetime("us", "UTC")})
    good_facts = pl.DataFrame({"k": ["a"], "available_ts": [T(10)], "v": [1.0]})
    with pytest.raises(ValueError, match="null"):
        asof_latest(bad_spine, good_facts, key="k", value_cols=["v"])
