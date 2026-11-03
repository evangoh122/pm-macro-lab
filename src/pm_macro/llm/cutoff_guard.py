"""cutoff_guard: decide whether an LLM score may count as confirmatory.

A row is confirmatory only if every condition holds; anything unknown fails closed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


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
    """A pre-registration committed before the event it covers."""

    id: str
    model_id: str
    prompt_hash: str
    committed_on: date


def _as_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def load_registry(path: str | Path) -> dict[str, ModelCutoff]:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text())
    out: dict[str, ModelCutoff] = {}
    for model_id, v in (data.get("models") or {}).items():
        cutoff_end = _as_date(v["cutoff_end"])
        if cutoff_end is None:
            raise CutoffGuardError(f"{model_id}: cutoff_end missing")
        out[model_id] = ModelCutoff(
            model_id,
            cutoff_end,
            int(v["margin_days"]),
            source=v.get("source") or None,
            verified_on=_as_date(v.get("verified_on")),
        )
    return out


def load_registrations(path: str | Path) -> list[Registration]:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text()) or {}
    out: list[Registration] = []
    for r in data.get("registrations") or []:
        committed = _as_date(r.get("committed_on"))
        if not (r.get("id") and r.get("model_id") and r.get("prompt_hash") and committed):
            raise CutoffGuardError(f"incomplete registration: {r!r}")
        out.append(
            Registration(str(r["id"]), str(r["model_id"]), str(r["prompt_hash"]), committed)
        )
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
    external_retrieval: bool | None,
) -> bool:
    """True only if the row satisfies every confirmatory condition. Fails closed.

    Conditions: pinned model; registry entry with source and verified_on; document and event
    after the cutoff safe start; doc_available_ts <= score_ts < event_release_ts; a registration
    for this exact (model_id, prompt_hash) committed on a UTC date strictly before the event;
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
    return any(
        r.model_id == model_id
        and r.prompt_hash == prompt_hash
        and r.committed_on < event.date()
        for r in registrations
    )
