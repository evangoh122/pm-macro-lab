"""Point-in-time helpers: nothing may be joined unless it was available at as_of_ts."""

from __future__ import annotations

import polars as pl

_IDX = "__spine_idx__"


def asof_latest(
    spine: pl.DataFrame,
    facts: pl.DataFrame,
    *,
    key: str,
    value_cols: list[str],
) -> pl.DataFrame:
    """For each spine row (key, as_of_ts) attach the latest fact with available_ts <= as_of_ts.

    ``facts`` must carry ``key``, ``available_ts`` and ``value_cols``. Each fact (including every
    revision/vintage of the same observation) must carry its OWN real availability timestamp;
    this function never picks between versions, so a later revision can never be exposed at an
    earlier as_of_ts. Facts with available_ts later than as_of_ts are never visible; a fact with
    available_ts == as_of_ts is visible (inclusive boundary). Output rows keep the spine's order.

    Raises ``ValueError`` on: spine columns named ``available_ts`` or any of ``value_cols``
    (an earlier join would silently shadow the new values), null ``key`` in spine or facts, null ``as_of_ts`` in spine, null
    ``available_ts`` in facts, and any two facts sharing the same (key, available_ts). There is
    no tie-break: ambiguity is always an error.
    """
    overlap = sorted(set(spine.columns) & {"available_ts", *value_cols})
    if overlap:
        raise ValueError(
            f"spine already has columns {overlap} that the join would add or collide with; "
            "rename or drop them first"
        )
    if spine[key].null_count() or facts[key].null_count():
        raise ValueError(f"null values in key column {key!r}")
    if spine["as_of_ts"].null_count():
        raise ValueError("null as_of_ts in spine")
    if facts["available_ts"].null_count():
        raise ValueError("null available_ts in facts")

    right = facts.select([key, "available_ts", *value_cols])
    dups = right.group_by([key, "available_ts"]).len().filter(pl.col("len") > 1)
    if dups.height:
        raise ValueError(
            f"ambiguous facts: duplicate ({key}, available_ts) in {dups.height} groups, "
            f"e.g. {dups.head(5).to_dicts()}"
        )

    left = spine.with_row_index(_IDX).sort("as_of_ts")
    right = right.sort("available_ts")
    out = left.join_asof(
        right,
        left_on="as_of_ts",
        right_on="available_ts",
        by=key,
        strategy="backward",
        check_sortedness=False,
    )
    return out.sort(_IDX).drop(_IDX)
