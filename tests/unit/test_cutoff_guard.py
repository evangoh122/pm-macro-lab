from datetime import UTC, date, datetime

import pytest

from pm_macro.llm.cutoff_guard import CutoffGuardError, ModelCutoff, is_confirmatory, safe_start

REG = {"m": ModelCutoff("m", date(2026, 6, 30), 31)}
T = lambda m, d: datetime(2026, m, d, tzinfo=UTC)


def base(**kw):
    args: dict = dict(  # noqa: C408
        registry=REG,
        pinned_model_id="m",
        model_id="m",
        doc_available_ts=T(9, 1),
        event_release_ts=T(9, 16),
        score_ts=T(9, 10),
        prompt_hash="h",
        preregistered_hashes={"h"},
        prompt_registered_before_event=True,
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


def test_unregistered_prompt_rejected():
    assert not is_confirmatory(**base(preregistered_hashes=set()))


def test_wrong_model_rejected():
    assert not is_confirmatory(**base(model_id="other"))


def test_unknown_model_fails_closed():
    assert not is_confirmatory(**base(registry={}, pinned_model_id="m"))
    with pytest.raises(CutoffGuardError):
        safe_start({}, "m")


def test_missing_timestamp_fails_closed():
    assert not is_confirmatory(**base(doc_available_ts=None))


def test_naive_timestamp_raises():
    with pytest.raises(CutoffGuardError):
        is_confirmatory(**base(doc_available_ts=datetime(2026, 9, 1)))  # noqa: DTZ001


def test_external_retrieval_rejected():
    assert not is_confirmatory(**base(external_retrieval=True))
