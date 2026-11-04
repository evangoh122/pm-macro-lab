"""Count Board speeches since a start date. Usage: python -I scripts/count_fed_speeches.py FEED.json"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pm_macro.ingest.fed_speeches import parse_feed

items = parse_feed(Path(sys.argv[1]).read_text(encoding="utf-8"))
start = datetime(2024, 8, 1)
print(sum(1 for i in items if i.scheduled_local >= start), "speeches since 2024-08-01")
