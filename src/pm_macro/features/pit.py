"""Point-in-time helpers: nothing may be joined unless it was available at as_of_ts."""

from __future__ import annotations

import polars as pl


def asof_latest(
    spine: pl.DataFrame,
    facts: pl.DataFrame,
    *,
    key: str,
    value_cols: list[str],
) -> pl.DataFrame:
    """For each spine row (key, as_of_ts) attach the latest fact with available_ts <= as_of_ts.

    ``facts`` must carry ``key``, ``available_ts`` and ``value_cols``. Facts with
    available_ts later than as_of_ts are never visible, regardless of their observation date.
    """
    left = spine.sort("as_of_ts")
    right = facts.select([key, "available_ts", *value_cols]).sort("available_ts")
    return left.join_asof(
        right,
        left_on="as_of_ts",
        right_on="available_ts",
        by=key,
        strategy="backward",
        check_sortedness=False,
    )
