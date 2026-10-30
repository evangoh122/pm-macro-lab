import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_no_pandas_imports():
    pat = re.compile(r"^\s*(import pandas|from pandas)", re.MULTILINE)
    for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        if p.name == "test_no_pandas.py":
            continue
        assert not pat.search(p.read_text()), f"pandas import in {p}"
