"""Git-backed provenance for pre-registrations.

``registration_commit_ts`` returns the COMMITTER timestamp of the earliest commit that introduced
a registration with ``id: <registration_id>`` into ``config/preregistration.yaml``. The YAML ``committed_on``
field is self-declared and is never trusted.

Residual trust assumption: the git history of the default branch is not rewritten or back-dated,
and CI runs on a full-depth checkout (``fetch-depth: 0``). Shallow or failing git returns None,
which the guard treats as "not confirmatory".
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

PREREG_PATH = "config/preregistration.yaml"


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def registration_commit_ts(repo_root: str | Path, registration_id: str) -> datetime | None:
    """UTC committer time of the first commit whose YAML contains ``id: <registration_id>``.

    Each commit that touched the file is parsed with ``yaml.safe_load`` and checked for a
    registration with that exact id; the earliest such committer timestamp wins. This is
    robust to YAML flow/block style and ignores comments and look-alike ids (a plain
    ``git log -S/-G`` text match is spoofable by a comment, and ``--diff-filter=A`` only matches
    commits that create the whole file, so neither is used). Returns None if not found, if the
    repository is shallow or unavailable, or if git fails.
    """
    root = Path(repo_root)
    shallow = _git(root, "rev-parse", "--is-shallow-repository")
    if shallow is None or shallow.strip() != "false":
        return None
    log = _git(root, "log", "--format=%H %ct", "--", PREREG_PATH)
    if log is None:
        return None
    best: int | None = None
    for line in log.splitlines():
        sha, _, ct = line.partition(" ")
        if not ct.isdigit():
            continue
        body = _git(root, "show", f"{sha}:{PREREG_PATH}")
        if body is None:
            continue
        try:
            data = yaml.safe_load(body) or {}
            regs = data.get("registrations") or []
            found = any(isinstance(r, dict) and str(r.get("id")) == registration_id for r in regs)
        except (yaml.YAMLError, AttributeError, TypeError):
            continue
        if found and (best is None or int(ct) < best):
            best = int(ct)
    return None if best is None else datetime.fromtimestamp(best, tz=UTC)
