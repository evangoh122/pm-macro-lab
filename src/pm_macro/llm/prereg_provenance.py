"""Git-backed provenance for pre-registrations.

``registration_commit_ts`` returns the COMMITTER timestamp of the first commit on the trusted
first-parent line from which the EXACT registration (all material fields equal) is present
continuously through the tip of ``verified_ref``. The YAML ``committed_on`` is self-declared and
never trusted.

Binding rules
- Material fields: ``id``, ``model_id``, ``prompt_hash``, ``primary_hypothesis`` (whitespace
  collapsed). Other keys (e.g. ``committed_on``) are notes and may change freely. YAML style
  (flow vs block), key order and whitespace never matter: entries are compared after parsing.
- If the entry was ever absent or different in a later commit, the clock restarts at the commit
  where the current exact entry reappeared. Editing ``prompt_hash``/``model_id``, or deleting and
  re-adding an entry, therefore yields a late timestamp.
- If the same id appears more than once with differing material content in a snapshot, that
  snapshot counts as "absent" (ambiguous, fail closed).
- Only ``git rev-list --first-parent <verified_ref> -- config/preregistration.yaml`` is walked.
  Side-branch commits are invisible; an entry counts from the first-parent commit (for example the
  merge commit) at which it entered the trusted line, using that commit's committer time.
- Renaming/moving the file is unsupported: the old path's history is not followed, so a moved file
  counts from the commit that created it at the new path.

Residual trust assumptions: the history of ``verified_ref`` is not rewritten and its commits are
not back-dated by a committer. A fast-forward merge or rebase keeps the original committer
times, so the trusted branch should be updated by merge commits or squash merges (which take
the merge time) and protected against force-pushes. CI must use a full-depth checkout
(``fetch-depth: 0``). A shallow repository, a missing ref or any git failure returns None, which
the guard treats as "not confirmatory".
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

PREREG_PATH = "config/preregistration.yaml"
MATERIAL_FIELDS = ("id", "model_id", "prompt_hash", "primary_hypothesis")

Material = tuple[str | None, str | None, str | None, str | None]


def material_key(
    id: str | None,
    model_id: str | None,
    prompt_hash: str | None,
    primary_hypothesis: str | None = None,
) -> Material:
    """Canonical comparison key for the material fields of a registration."""

    def s(v: Any) -> str | None:
        return None if v is None else str(v)

    hyp = None if primary_hypothesis is None else " ".join(str(primary_hypothesis).split())
    return (s(id), s(model_id), s(prompt_hash), hyp)


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


def _entry_present(body: str, target: Material) -> bool:
    try:
        data = yaml.safe_load(body) or {}
        regs = data.get("registrations") or []
        same_id = [
            material_key(
                r.get("id"), r.get("model_id"), r.get("prompt_hash"), r.get("primary_hypothesis")
            )
            for r in regs
            if isinstance(r, dict) and str(r.get("id")) == target[0]
        ]
    except (yaml.YAMLError, AttributeError, TypeError):
        return False
    return bool(same_id) and all(m == target for m in same_id)


def registration_commit_ts(
    repo_root: str | Path,
    registration: Any,
    verified_ref: str = "HEAD",
) -> datetime | None:
    """UTC committer time from which this exact registration has been continuously present.

    ``registration`` needs ``id``, ``model_id``, ``prompt_hash`` and optionally
    ``primary_hypothesis`` attributes (a ``cutoff_guard.Registration``). Returns None if the entry
    is not present at the tip of ``verified_ref``, the repo is shallow/unavailable, or git fails.
    """
    root = Path(repo_root)
    target = material_key(
        registration.id,
        registration.model_id,
        registration.prompt_hash,
        getattr(registration, "primary_hypothesis", None),
    )
    shallow = _git(root, "rev-parse", "--is-shallow-repository")
    if shallow is None or shallow.strip() != "false":
        return None
    # newest first; "<committer-ts> <sha>" per line
    log = _git(root, "rev-list", "--first-parent", "--timestamp", verified_ref, "--", PREREG_PATH)
    if log is None:
        return None
    since: int | None = None
    for line in log.splitlines():  # walk from the tip backwards while the exact entry is present
        ct, _, sha = line.partition(" ")
        if not ct.isdigit() or not sha:
            return None
        body = _git(root, "show", f"{sha}:{PREREG_PATH}")
        if body is None or not _entry_present(body, target):
            break
        since = int(ct)
    return None if since is None else datetime.fromtimestamp(since, tz=UTC)
