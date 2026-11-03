import os
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pm_macro.llm.cutoff_guard import ModelCutoff, Registration, is_confirmatory
from pm_macro.llm.prereg_provenance import registration_commit_ts

ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@x",
}  # fmt: skip


def git(repo: Path, *args: str, when: str | None = None):
    env = {**os.environ, **ENV}
    if when:
        env["GIT_COMMITTER_DATE"] = when
        env["GIT_AUTHOR_DATE"] = when
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def commit_prereg(repo: Path, body: str, when: str):
    (repo / "config").mkdir(exist_ok=True)
    (repo / "config" / "preregistration.yaml").write_text(body)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "c", when=when)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    commit_prereg(tmp_path, "registrations: []\n", "2026-09-01T00:00:00+00:00")
    return tmp_path


def test_first_introducing_commit_timestamp(repo):
    body = "registrations:\n- {id: r1, model_id: m, prompt_hash: h, committed_on: 2020-01-01}\n"
    commit_prereg(repo, body, "2026-09-20T12:00:00+00:00")
    commit_prereg(repo, body + "# note\n", "2026-10-01T00:00:00+00:00")
    assert registration_commit_ts(repo, "r1") == datetime(2026, 9, 20, 12, tzinfo=UTC)


def test_prefix_id_does_not_match_longer_id(repo):
    commit_prereg(
        repo, "registrations:\n- {id: r10, model_id: m, prompt_hash: h}\n", "2026-09-20T00:00:00+00:00"
    )
    assert registration_commit_ts(repo, "r1") is None


def test_comment_lookalike_does_not_count(repo):
    commit_prereg(repo, "# id: r1\nregistrations: []\n", "2026-09-02T00:00:00+00:00")
    assert registration_commit_ts(repo, "r1") is None


def test_absent_id_returns_none(repo):
    assert registration_commit_ts(repo, "nope") is None


def test_not_a_git_repo_returns_none(tmp_path):
    assert registration_commit_ts(tmp_path / "missing", "r1") is None


def test_shallow_repo_returns_none(repo, tmp_path_factory):
    commit_prereg(repo, "registrations:\n- {id: r1, model_id: m, prompt_hash: h}\n", "2026-09-20T00:00:00+00:00")
    shallow = tmp_path_factory.mktemp("shallow") / "c"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow)],
        check=True, capture_output=True,
    )  # fmt: skip
    assert registration_commit_ts(shallow, "r1") is None


def _confirm(repo: Path, event: datetime) -> bool:
    reg = {"m": ModelCutoff("m", date(2026, 6, 30), 31, "https://x", date(2026, 10, 30))}
    regs = [Registration("r1", "m", "h", date(2020, 1, 1))]  # back-dated YAML note
    ts = registration_commit_ts(repo, "r1")
    cts = {"r1": ts} if ts else {}
    return is_confirmatory(
        registry=reg, pinned_model_id="m", model_id="m",
        doc_available_ts=datetime(2026, 9, 1, tzinfo=UTC), event_release_ts=event,
        score_ts=datetime(2026, 9, 10, tzinfo=UTC), prompt_hash="h",
        registrations=regs, registration_commit_ts=cts, external_retrieval=False,
    )  # fmt: skip


def test_backdated_yaml_but_late_commit_not_confirmatory(repo):
    body = "registrations:\n- {id: r1, model_id: m, prompt_hash: h, committed_on: 2020-01-01}\n"
    commit_prereg(repo, body, "2026-09-18T00:00:00+00:00")  # after the event
    assert not _confirm(repo, datetime(2026, 9, 16, tzinfo=UTC))


def test_commit_before_event_is_confirmatory(repo):
    body = "registrations:\n- {id: r1, model_id: m, prompt_hash: h}\n"
    commit_prereg(repo, body, "2026-09-05T00:00:00+00:00")
    assert _confirm(repo, datetime(2026, 9, 16, tzinfo=UTC))


def test_unregistered_id_not_confirmatory(repo):
    assert not _confirm(repo, datetime(2026, 9, 16, tzinfo=UTC))
