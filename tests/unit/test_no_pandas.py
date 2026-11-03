import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCAN_DIRS = ("src", "tests", "scripts", "config", "notebooks", "docs")
PANDAS = re.compile(
    r"""^\s*(?:import\s+(?:[\w.]+\s*,\s*)*pandas\b|from\s+pandas\b)"""  # import / from forms
    r"""|__import__\(\s*['"]pandas\b"""
    r"""|import_module\(\s*['"]pandas\b""",
    re.MULTILINE,
)


def scan(text: str) -> bool:
    return bool(PANDAS.search(text))


def test_detector_catches_all_forms():
    for bad in (
        "import pandas as pd",
        "import pandas",
        "  import os, pandas",
        "from pandas import x",
        "from pandas.core import y",
        "m = __import__('pandas')",
        'm = __import__( "pandas" )',
        "importlib.import_module('pandas')",
        "importlib.import_module(\"pandas.io\")",
    ):
        assert scan(bad), bad
    for ok in ("import polars as pl", "# pandas is banned", "x = 'pandas'", "import os"):
        assert not scan(ok), ok


def test_no_pandas_anywhere_in_python_files():
    files = [p for d in SCAN_DIRS if (ROOT / d).is_dir() for p in (ROOT / d).rglob("*.py")]
    files += list(ROOT.glob("*.py"))
    assert files
    for p in files:
        if p.name == "test_no_pandas.py":
            continue
        assert not scan(p.read_text()), f"pandas import in {p}"
