from pm_macro.ingest.fed_speeches import conservative_available_ts, parse_feed

RAW = '﻿[{"d":"10/8/2026 4:30:00 AM","t":"T","s":"Governor X","lo":"L","l":"/a.htm"},{"d":"bad"}]'


def test_parse_skips_bad_rows_and_sorts():
    items = parse_feed(RAW)
    assert len(items) == 1 and items[0].speaker == "Governor X"


def test_conservative_ts_is_end_of_day():
    t = conservative_available_ts(parse_feed(RAW)[0])
    assert (t.hour, t.minute) == (23, 59)
