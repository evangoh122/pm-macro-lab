"""Parse the federalreserve.gov speeches JSON feed.

The ``d`` field is a scheduled date/time, NOT a verified publication time. Callers must store
their own first-observed ``available_ts``; ``scheduled_ts`` is only used for ordering and for
conservative end-of-day fallbacks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

FEED_URL = "https://www.federalreserve.gov/json/ne-speeches.json"
DATA_SOURCE = "frb_speech"


@dataclass(frozen=True)
class SpeechItem:
    scheduled_ts: datetime  # naive feed time interpreted as US/Eastern is UNVERIFIED; kept as UTC-tagged
    title: str
    speaker: str
    location: str
    path: str


def parse_feed(raw: str) -> list[SpeechItem]:
    items = json.loads(raw.lstrip("﻿"))
    out: list[SpeechItem] = []
    for r in items:
        try:
            ts = datetime.strptime(r["d"], "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=UTC)
        except (KeyError, ValueError):
            continue
        out.append(
            SpeechItem(ts, r.get("t", ""), r.get("s", ""), r.get("lo", ""), r.get("l", ""))
        )
    out.sort(key=lambda x: x.scheduled_ts)
    return out


def conservative_available_ts(item: SpeechItem) -> datetime:
    """Used only when the true availability time is unverified: end of the scheduled day."""
    d = item.scheduled_ts
    return d.replace(hour=23, minute=59, second=59)
