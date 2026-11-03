import ast
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _is_pandas(name: str | None) -> bool:
    return bool(name) and (name == "pandas" or str(name).startswith("pandas."))


def _str_arg(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def pandas_uses(source: str) -> list[int]:
    """Line numbers of pandas imports (any form) or dynamic pandas imports."""
    hits: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(_is_pandas(a.name) for a in node.names):
                hits.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and _is_pandas(node.module):
                hits.append(node.lineno)
        elif isinstance(node, ast.Call):
            f = node.func
            dyn = (isinstance(f, ast.Name) and f.id == "__import__") or (
                isinstance(f, ast.Attribute) and f.attr == "import_module"
            ) or (isinstance(f, ast.Name) and f.id == "import_module")
            if dyn and _is_pandas(_str_arg(node)):
                hits.append(node.lineno)
    return hits


def test_detector_catches_all_forms():
    for bad in (
        "import pandas as pd",
        "import pandas",
        "import os as o, pandas",
        "x = 1; import pandas",
        "from pandas import x",
        "from pandas.core import y as z",
        "import pandas.io.json",
        "def f():\n    import pandas as p",
        "m = __import__('pandas')",
        'm = __import__("pandas.io")',
        "importlib.import_module('pandas')",
        "from importlib import import_module\nimport_module('pandas')",
    ):
        assert pandas_uses(bad), bad
    for ok in (
        "import polars as pl",
        "# import pandas",
        "x = 'import pandas'",
        "import pandas_like_name_x as q",
        "__import__('os')",
        "importlib.import_module('polars')",
    ):
        assert not pandas_uses(ok), ok


def _tracked_py() -> list[pathlib.Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "*.py"], capture_output=True, text=True, check=True
        ).stdout.split()
        files = [ROOT / f for f in out]
    except (OSError, subprocess.CalledProcessError):
        files = [p for p in ROOT.rglob("*.py") if ".git" not in p.parts]
    return [p for p in files if p.exists()]


def test_no_pandas_in_any_tracked_python_file():
    files = _tracked_py()
    assert files
    for p in files:
        assert not pandas_uses(p.read_text()), f"pandas use in {p}"
