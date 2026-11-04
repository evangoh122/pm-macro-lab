"""cutoff_guard: decide whether an LLM score may count as confirmatory.

A row is confirmatory only if every condition holds; anything unknown fails closed.

Pre-registration trust model: the YAML ``committed_on`` is a human note and is IGNORED. A
registration counts only if ``registration_commit_ts`` (see ``prereg_provenance``) supplies the
git COMMITTER timestamp of the commit that introduced it, and that instant is strictly before
``event_release_ts``. Residual trust assumption: the git history of the default branch is not
rewritten or back-dated by a committer, and CI runs on a full-depth checkout (``fetch-depth: 0``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from pm_macro.llm.prereg_provenance import Material, material_key, registration_commit_ts


class CutoffGuardError(ValueError):
    """Raised when the registry is unusable for the requested model."""


@dataclass(frozen=True)
class ModelCutoff:
    model_id: str
    cutoff_end: date
    margin_days: int
    source: str | None = None
    verified_on: date | None = None

    @property
    def verified(self) -> bool:
        """A cutoff is usable for confirmatory rows only with a source and a verification date."""
        return bool(self.source) and self.verified_on is not None

    @property
    def safe_start(self) -> datetime:
        d = self.cutoff_end + timedelta(days=self.margin_days)
        return datetime(d.year, d.month, d.day, tzinfo=UTC)


@dataclass(frozen=True)
class Registration:
    """A pre-registration entry. ``committed_on`` is an unverified human note, never used."""

    id: str
    model_id: str
    prompt_hash: str
    committed_on: date | None = None
    primary_hypothesis: str | None = None  # material: part of the frozen spec

    def material(self) -> Material:
        return material_key(self.id, self.model_id, self.prompt_hash, self.primary_hypothesis)


def _as_date(v: Any, field: str) -> date | None:
    """None -> None; pure date -> itself; aware datetime -> UTC date; naive datetime/other -> error."""
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            raise CutoffGuardError(f"{field}: naive datetime not allowed")
        return v.astimezone(UTC).date()
    if isinstance(v, date):
        return v
    raise CutoffGuardError(f"{field}: expected a date, got {type(v).__name__}")


def _pure_date(v: Any, field: str) -> date:
    if isinstance(v, datetime) or not isinstance(v, date):
        raise CutoffGuardError(f"{field}: expected a plain date, got {type(v).__name__}")
    return v


def load_registry(path: str | Path) -> dict[str, ModelCutoff]:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text()) or {}
    out: dict[str, ModelCutoff] = {}
    for model_id, v in (data.get("models") or {}).items():
        cutoff_end = _pure_date(v.get("cutoff_end"), f"{model_id}.cutoff_end")
        margin = v.get("margin_days")
        if type(margin) is not int or margin <= 0:
            raise CutoffGuardError(f"{model_id}.margin_days: expected int > 0, got {margin!r}")
        source = v.get("source")
        if not isinstance(source, str) or not source.startswith("http"):
            raise CutoffGuardError(f"{model_id}.source: expected an http(s) URL, got {source!r}")
        out[model_id] = ModelCutoff(
            model_id,
            cutoff_end,
            margin,
            source=source,
            verified_on=_as_date(v.get("verified_on"), f"{model_id}.verified_on"),
        )
    return out


def load_registrations(path: str | Path) -> list[Registration]:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text()) or {}
    out: list[Registration] = []
    for r in data.get("registrations") or []:
        if not (r.get("id") and r.get("model_id") and r.get("prompt_hash")):
            raise CutoffGuardError(f"incomplete registration: {r!r}")
        out.append(
            Registration(
                str(r["id"]),
                str(r["model_id"]),
                str(r["prompt_hash"]),
                _as_date(r.get("committed_on"), "committed_on"),
                None if r.get("primary_hypothesis") is None else str(r["primary_hypothesis"]),
            )
        )
    return out


def verified_registration_map(
    repo_root: str | Path,
    registrations: Sequence[Registration],
    verified_ref: str = "HEAD",
) -> dict[str, datetime]:
    """id -> git-verified UTC commit instant, for registrations whose exact content is provable.

    Registrations with no provable provenance on ``verified_ref`` (edited, re-added, side-branch,
    shallow clone, git failure) are omitted, so the guard rejects them. Duplicate ids with
    different material content are all omitted.
    """
    seen: dict[str, Material] = {}
    conflicts: set[str] = set()
    for r in registrations:
        if r.id in seen and seen[r.id] != r.material():
            conflicts.add(r.id)
        seen[r.id] = r.material()
    out: dict[str, datetime] = {}
    for r in registrations:
        if r.id in conflicts:
            continue
        ts = registration_commit_ts(repo_root, r, verified_ref)
        if ts is not None:
            out[r.id] = ts
    return out


def safe_start(registry: dict[str, ModelCutoff], model_id: str) -> datetime:
    if model_id not in registry:
        raise CutoffGuardError(f"unknown model_id {model_id!r}: cannot score")
    return registry[model_id].safe_start


def _utc(ts: datetime | None) -> datetime | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        raise CutoffGuardError("naive timestamp: all timestamps must be timezone-aware (UTC)")
    return ts.astimezone(UTC)


def is_confirmatory(
    *,
    registry: dict[str, ModelCutoff],
    pinned_model_id: str,
    model_id: str,
    doc_available_ts: datetime | None,
    event_release_ts: datetime | None,
    score_ts: datetime | None,
    prompt_hash: str | None,
    registrations: Sequence[Registration],
    registration_commit_ts: Mapping[str, datetime],
    external_retrieval: bool | None,
) -> bool:
    """True only if the row satisfies every confirmatory condition. Fails closed.

    Conditions: pinned model; registry entry with source and verified_on; document and event
    after the cutoff safe start; doc_available_ts <= score_ts < event_release_ts; a registration
    for this exact (model_id, prompt_hash) whose git-verified commit timestamp
    (``registration_commit_ts[id]``, tz-aware) is strictly before ``event_release_ts``. The
    comparison is on the full UTC INSTANT, not the date: a same-day commit earlier in time counts,
    a same-day commit at or after the event instant does not. Production callers MUST obtain
    ``registration_commit_ts`` only from ``verified_registration_map`` (this function is pure and
    trusts the mapping it is given). The YAML
    ``committed_on`` is ignored, and a registration without a verified commit ts never counts;
    and external_retrieval explicitly False (None or any other value fails).
    """
    if model_id != pinned_model_id:
        return False
    entry = registry.get(model_id)
    if entry is None or not entry.verified:
        return False
    if external_retrieval is not False:
        return False
    doc, event, score = _utc(doc_available_ts), _utc(event_release_ts), _utc(score_ts)
    if doc is None or event is None or score is None or not prompt_hash:
        return False
    start = entry.safe_start
    if not (doc > start and event > start and doc <= score < event):
        return False
    for r in registrations:
        if r.model_id != model_id or r.prompt_hash != prompt_hash:
            continue
        committed = _utc(registration_commit_ts.get(r.id))
        if committed is not None and committed < event:
            return True
    return False
