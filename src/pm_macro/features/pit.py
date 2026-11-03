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
    version_col: str | None = None,
) -> pl.DataFrame:
    """For each spine row (key, as_of_ts) attach the latest fact with available_ts <= as_of_ts.

    ``facts`` must carry ``key``, ``available_ts`` and ``value_cols``. Facts with
    available_ts later than as_of_ts are never visible; a fact with available_ts == as_of_ts is
    visible (inclusive boundary). Output rows keep the spine's original order.

    Ambiguity rules (all raise ``ValueError``):
    - null ``key`` in spine or facts, null ``as_of_ts`` in spine, null ``available_ts`` in facts;
    - two or more facts with the same (key, available_ts), unless ``version_col`` is supplied, in
      which case the highest version wins; a tie on (key, available_ts, version) still raises.
    """
    if spine[key].null_count() or facts[key].null_count():
        raise ValueError(f"null values in key column {key!r}")
    if spine["as_of_ts"].null_count():
        raise ValueError("null as_of_ts in spine")
    if facts["available_ts"].null_count():
        raise ValueError("null available_ts in facts")

    cols = [key, "available_ts", *value_cols]
    if version_col is not None and version_col not in cols:
        cols.append(version_col)
    right = facts.select(cols)

    tie_cols = [key, "available_ts"] + ([version_col] if version_col else [])
    dups = right.group_by(tie_cols).len().filter(pl.col("len") > 1)
    if dups.height:
        raise ValueError(
            "ambiguous facts: duplicate "
            f"{tie_cols} ({dups.height} groups), e.g. {dups.head(5).to_dicts()}"
        )
    if version_col is not None:
        right = (
            right.sort(version_col)
            .group_by([key, "available_ts"], maintain_order=True)
            .last()
            .drop(version_col)
        )

    left = spine.with_row_index(_IDX).sort("as_of_ts")
    right = right.select([key, "available_ts", *value_cols]).sort("available_ts")
    out = left.join_asof(
        right,
        left_on="as_of_ts",
        right_on="available_ts",
        by=key,
        strategy="backward",
        check_sortedness=False,
    )
    return out.sort(_IDX).drop(_IDX)
