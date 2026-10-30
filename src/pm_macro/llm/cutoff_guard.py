"""cutoff_guard: decide whether an LLM score may count as confirmatory.

A row is confirmatory only if every condition holds; anything unknown fails closed.
"""

from __future__ import annotations

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

    @property
    def safe_start(self) -> datetime:
        d = self.cutoff_end + timedelta(days=self.margin_days)
        return datetime(d.year, d.month, d.day, tzinfo=UTC)


def load_registry(path: str | Path) -> dict[str, ModelCutoff]:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text())
    out: dict[str, ModelCutoff] = {}
    for model_id, v in (data.get("models") or {}).items():
        out[model_id] = ModelCutoff(model_id, v["cutoff_end"], int(v["margin_days"]))
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
    preregistered_hashes: set[str],
    prompt_registered_before_event: bool,
    external_retrieval: bool,
) -> bool:
    """True only if the row satisfies every confirmatory condition. Fails closed."""
    if model_id != pinned_model_id:
        return False
    if model_id not in registry:
        return False
    doc, event, score = _utc(doc_available_ts), _utc(event_release_ts), _utc(score_ts)
    if doc is None or event is None or score is None or not prompt_hash:
        return False
    start = registry[model_id].safe_start
    return (
        doc > start
        and event > start
        and score < event
        and prompt_hash in preregistered_hashes
        and prompt_registered_before_event
        and not external_retrieval
    )
