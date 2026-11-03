from datetime import UTC, datetime

from pm_macro.ingest.fed_speeches import SpeechItem, conservative_available_ts, parse_feed

RAW = '﻿[{"d":"10/8/2026 4:30:00 AM","t":"T","s":"Governor X","lo":"L","l":"/a.htm"},{"d":"bad"}]'


def item(y, m, d, h=12):
    return SpeechItem(datetime(y, m, d, h), "raw", "t", "s", "l", "/p")  # noqa: DTZ001


def test_parse_skips_bad_rows_and_sorts():
    items = parse_feed(RAW)
    assert len(items) == 1 and items[0].speaker == "Governor X"


def test_parse_keeps_naive_local_and_raw_string():
    it = parse_feed(RAW)[0]
    assert it.scheduled_local == datetime(2026, 10, 8, 4, 30)  # noqa: DTZ001
    assert it.scheduled_local.tzinfo is None
    assert it.raw_d == "10/8/2026 4:30:00 AM"


def test_conservative_ts_is_utc_aware_next_day_end_ny():
    t = conservative_available_ts(parse_feed(RAW)[0])
    assert t.tzinfo is not None and t.utcoffset().total_seconds() == 0
    # 2026-10-09 23:59:59 EDT (UTC-4) == 2026-10-10 03:59:59 UTC
    assert t == datetime(2026, 10, 10, 3, 59, 59, tzinfo=UTC)


def test_conservative_ts_spring_forward_boundary():
    # scheduled 2026-03-07; next day 03-08 is the DST start (EDT, UTC-4 after 02:00)
    assert conservative_available_ts(item(2026, 3, 7)) == datetime(2026, 3, 9, 3, 59, 59, tzinfo=UTC)


def test_conservative_ts_fall_back_boundary():
    # scheduled 2026-10-31; next day 11-01 is the DST end (EST, UTC-5 at 23:59:59)
    assert conservative_available_ts(item(2026, 10, 31)) == datetime(
        2026, 11, 2, 4, 59, 59, tzinfo=UTC
    )


def test_conservative_ts_never_before_scheduled_day_end():
    t = conservative_available_ts(item(2026, 1, 15, 23))
    assert t == datetime(2026, 1, 17, 4, 59, 59, tzinfo=UTC)


def test_assumed_availability_is_tagged_uncorroborated():
    from pm_macro.ingest.fed_speeches import AVAILABILITY_BASIS, assumed_availability

    est = assumed_availability(item(2026, 10, 8))
    assert est.basis == AVAILABILITY_BASIS == "assumed_scheduled_day_plus_1"
    assert est.corroborated is False
    assert est.available_ts == conservative_available_ts(item(2026, 10, 8))
