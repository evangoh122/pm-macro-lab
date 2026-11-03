from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pm_macro.llm.cutoff_guard import (
    CutoffGuardError,
    ModelCutoff,
    Registration,
    is_confirmatory,
    load_registrations,
    load_registry,
    safe_start,
)

ROOT = Path(__file__).resolve().parents[2]
SRC = "https://example.org/model-card"
REG = {"m": ModelCutoff("m", date(2026, 6, 30), 31, source=SRC, verified_on=date(2026, 10, 30))}
PREREG = [Registration("r1", "m", "h", date(2026, 9, 1))]


def T(m, d, h=0):
    return datetime(2026, m, d, h, tzinfo=UTC)


def base(**kw):
    args: dict = dict(  # noqa: C408
        registry=REG,
        pinned_model_id="m",
        model_id="m",
        doc_available_ts=T(9, 1),
        event_release_ts=T(9, 16),
        score_ts=T(9, 10),
        prompt_hash="h",
        registrations=PREREG,
        external_retrieval=False,
    )
    args.update(kw)
    return args


def test_happy_path():
    assert is_confirmatory(**base())


def test_pre_cutoff_event_rejected():
    assert not is_confirmatory(**base(event_release_ts=T(7, 15)))


def test_pre_cutoff_doc_rejected():
    assert not is_confirmatory(**base(doc_available_ts=T(7, 30)))


def test_scored_after_release_rejected():
    assert not is_confirmatory(**base(score_ts=T(9, 17)))


def test_score_before_doc_availability_rejected():
    assert not is_confirmatory(**base(doc_available_ts=T(9, 5), score_ts=T(9, 4)))


def test_score_exactly_at_doc_availability_ok():
    assert is_confirmatory(**base(doc_available_ts=T(9, 5), score_ts=T(9, 5)))


def test_score_exactly_at_release_rejected():
    assert not is_confirmatory(**base(score_ts=T(9, 16)))


def test_no_registrations_rejected():
    assert not is_confirmatory(**base(registrations=[]))


def test_registration_committed_after_event_rejected():
    late = [Registration("r1", "m", "h", date(2026, 9, 17))]
    assert not is_confirmatory(**base(registrations=late))


def test_registration_committed_on_event_day_rejected():
    same_day = [Registration("r1", "m", "h", date(2026, 9, 16))]
    assert not is_confirmatory(**base(registrations=same_day))


def test_registration_wrong_model_rejected():
    assert not is_confirmatory(**base(registrations=[Registration("r1", "other", "h", date(2026, 9, 1))]))


def test_registration_hash_mismatch_rejected():
    assert not is_confirmatory(**base(prompt_hash="h2"))


def test_wrong_model_rejected():
    assert not is_confirmatory(**base(model_id="other"))


def test_unknown_model_fails_closed():
    assert not is_confirmatory(**base(registry={}, pinned_model_id="m"))
    with pytest.raises(CutoffGuardError):
        safe_start({}, "m")


def test_unverified_registry_entry_rejected():
    unverified = {"m": ModelCutoff("m", date(2026, 6, 30), 31, source=SRC, verified_on=None)}
    assert not is_confirmatory(**base(registry=unverified))


def test_registry_entry_without_source_rejected():
    nosrc = {"m": ModelCutoff("m", date(2026, 6, 30), 31, source=None, verified_on=date(2026, 10, 30))}
    assert not is_confirmatory(**base(registry=nosrc))


def test_missing_timestamp_fails_closed():
    assert not is_confirmatory(**base(doc_available_ts=None))


def test_naive_timestamp_raises():
    naive = datetime(2026, 9, 1)  # noqa: DTZ001  (deliberately naive: asserts the guard rejects it)
    with pytest.raises(CutoffGuardError):
        is_confirmatory(**base(doc_available_ts=naive))


def test_external_retrieval_true_rejected():
    assert not is_confirmatory(**base(external_retrieval=True))


def test_external_retrieval_none_rejected():
    assert not is_confirmatory(**base(external_retrieval=None))


def test_shipped_registry_carries_verification_and_llama_is_unverified():
    reg = load_registry(ROOT / "config" / "llm_cutoffs.yaml")
    assert reg["claude-opus-5-5"].verified
    llama = reg["meta-llama/Llama-3.1-70B-Instruct"]
    assert llama.verified_on is None and not llama.verified
    assert not is_confirmatory(
        **base(registry=reg, pinned_model_id=llama.model_id, model_id=llama.model_id,
               registrations=[Registration("r", llama.model_id, "h", date(2026, 9, 1))])
    )


def test_load_registrations_roundtrip(tmp_path):
    f = tmp_path / "p.yaml"
    f.write_text(
        "registrations:\n- {id: a, model_id: m, prompt_hash: h, committed_on: 2026-09-01}\n"
    )
    assert load_registrations(f) == [Registration("a", "m", "h", date(2026, 9, 1))]
    assert load_registrations(ROOT / "config" / "preregistration.yaml") == []
