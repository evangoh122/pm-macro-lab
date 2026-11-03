import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
_m = re.search(r"grep -iE '([^']+)'", CI)
assert _m, "data-file grep not found in ci.yml"
PATTERN = re.compile(_m.group(1), re.IGNORECASE)


def blocked(path: str) -> bool:
    return bool(PATTERN.search(path)) and not path.startswith("tests/fixtures/")


def test_ci_data_file_regex():
    for bad in (
        "data/prices.csv.gz", "data/prices.tsv", "DATA/A.CSV", "a.tsv.gz", "a.json.gz",
        "a.parquet.gz", "a.zip", "a.tar", "a.gz", "a.PKL", "a.duckdb",
        "data/observations.jsonl", "data/o.ndjson", "data/x.ORC", "a.jsonl.gz", "a.ndjson.gz",
        "a.avro", "a.h5", "a.hdf5", "a.npy", "a.NPZ", "a.dta", "a.sav", "a.feather",
        "warehouse/delta/part-0.snappy", "warehouse/t/_delta_log/00000.json", "_delta_log/0.json",
    ):  # fmt: skip
        assert blocked(bad), bad
    for ok in ("tests/fixtures/a.csv", "tests/fixtures/o.jsonl", "tests/fixtures/delta/x", "src/pm_macro/deltas.py", "src/a.py", "docs/a.html", "README.md"):
        assert not blocked(ok), ok


def test_ci_uses_full_depth_checkout():
    assert "fetch-depth: 0" in CI


def test_no_tracked_data_files():
    files = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert not [f for f in files if blocked(f)]
