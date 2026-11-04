"""Parse the federalreserve.gov speeches JSON feed.

The feed's ``d`` field is a *scheduled* date/time of UNVERIFIED timezone (it may be Eastern, but
that is not established) and is NOT a verified publication time. It is therefore kept as a naive
``scheduled_local`` datetime plus the raw string; it is never labelled UTC. Callers must store
their own first-observed ``available_ts``; ``conservative_available_ts`` is only an uncorroborated
assumption.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

FEED_URL = "https://www.federalreserve.gov/json/ne-speeches.json"
DATA_SOURCE = "frb_speech"
AVAILABILITY_BASIS = "assumed_scheduled_day_plus_1"
_NY = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class AvailabilityEstimate:
    """An availability timestamp plus how it was derived.

    Rows with ``corroborated=False`` (basis ``AVAILABILITY_BASIS``) must be excluded from
    leakage-sensitive or confirmatory analysis.
    """

    available_ts: datetime  # timezone-aware UTC
    basis: str
    corroborated: bool = False


@dataclass(frozen=True)
class SpeechItem:
    scheduled_local: datetime  # NAIVE, timezone UNVERIFIED, scheduled time only
    raw_d: str  # the feed's original ``d`` string
    title: str
    speaker: str
    location: str
    path: str


def parse_feed(raw: str) -> list[SpeechItem]:
    items = json.loads(raw.lstrip("﻿"))
    out: list[SpeechItem] = []
    for r in items:
        try:
            ts = datetime.strptime(r["d"], "%m/%d/%Y %I:%M:%S %p")
        except (KeyError, ValueError):
            continue
        out.append(
            SpeechItem(ts, r["d"], r.get("t", ""), r.get("s", ""), r.get("lo", ""), r.get("l", ""))
        )
    out.sort(key=lambda x: x.scheduled_local)
    return out


def conservative_available_ts(item: SpeechItem) -> datetime:
    """ASSUMED availability instant (timezone-aware UTC), not an observed one.

    The feed time has an unverified timezone and is only a schedule, so the real posting time is
    unknown. We ASSUME the scheduled calendar day is in America/New_York (the Board's home zone) and
    add a one-day margin: the result is 23:59:59 America/New_York on the day AFTER the scheduled
    day, converted to UTC. This is an assumption, not a guarantee: it is not proven to be an upper
    bound on posting time. Values from here must be EXCLUDED from leakage-sensitive and
    confirmatory analysis unless corroborated by a first-observed timestamp (see
    ``assumed_availability``). DST is handled by building the wall-clock time in the zone (not by
    adding a fixed UTC offset).
    """
    next_day = item.scheduled_local.date() + timedelta(days=1)
    return datetime.combine(next_day, time(23, 59, 59), tzinfo=_NY).astimezone(UTC)


def assumed_availability(item: SpeechItem) -> AvailabilityEstimate:
    """Assumed availability tagged as uncorroborated; ``corroborated`` stays False until a
    first-observed ``available_ts`` confirms it (set by the caller that observed the page)."""
    return AvailabilityEstimate(conservative_available_ts(item), AVAILABILITY_BASIS, False)
