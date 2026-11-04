import os
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from pm_macro.llm.cutoff_guard import (
    ModelCutoff,
    Registration,
    is_confirmatory,
    verified_registration_map,
)
from pm_macro.llm.prereg_provenance import registration_commit_ts

ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@x",
}  # fmt: skip

R1 = Registration("r1", "m", "h")


def iso(day: int, hour: int = 0) -> str:
    return f"2026-09-{day:02d}T{hour:02d}:00:00+00:00"


def utc(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, tzinfo=UTC)


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


def commit_other(repo: Path, name: str, when: str):
    (repo / name).write_text(name)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", name, when=when)


def block(id="r1", model="m", h="h", extra=""):
    return f"registrations:\n- id: {id}\n  model_id: {model}\n  prompt_hash: {h}\n{extra}"


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    commit_prereg(tmp_path, "registrations: []\n", iso(1))
    return tmp_path


def test_early_commit_timestamp_and_unchanged_across_unrelated_commits(repo):
    commit_prereg(repo, block(), iso(5))
    for i in range(6, 12):
        commit_other(repo, f"f{i}.txt", iso(i))
    commit_prereg(repo, block(extra="  committed_on: 2020-01-01\n"), iso(12))  # note-only edit
    assert registration_commit_ts(repo, R1) == utc(5)


def test_reformatting_keeps_early_timestamp(repo):
    commit_prereg(repo, block(), iso(5))
    flow = "registrations:\n  - {prompt_hash: h,   model_id: m, id: r1}\n"
    commit_prereg(repo, flow, iso(20))
    reordered = "registrations:\n- model_id: 'm'\n  id: \"r1\"\n\n  prompt_hash: h\n"
    commit_prereg(repo, reordered, iso(21))
    assert registration_commit_ts(repo, R1) == utc(5)


def test_prompt_hash_edited_after_event_gives_late_ts(repo):
    commit_prereg(repo, block(h="old"), iso(5))
    commit_prereg(repo, block(h="h"), iso(20))
    assert registration_commit_ts(repo, R1) == utc(20)
    assert registration_commit_ts(repo, Registration("r1", "m", "old")) is None


def test_model_id_edited_gives_late_ts(repo):
    commit_prereg(repo, block(model="other"), iso(5))
    commit_prereg(repo, block(model="m"), iso(20))
    assert registration_commit_ts(repo, R1) == utc(20)


def test_primary_hypothesis_is_material(repo):
    r = Registration("r1", "m", "h", primary_hypothesis="partial corr > 0")
    commit_prereg(repo, block(extra="  primary_hypothesis: weaker claim\n"), iso(5))
    commit_prereg(repo, block(extra="  primary_hypothesis: partial corr > 0\n"), iso(20))
    assert registration_commit_ts(repo, r) == utc(20)
    # whitespace-only reflow of the hypothesis does not restart the clock
    commit_prereg(repo, block(extra="  primary_hypothesis: >\n    partial\n    corr   > 0\n"), iso(21))
    assert registration_commit_ts(repo, r) == utc(20)


def test_deleted_then_readded_same_id_after_event_gives_late_ts(repo):
    commit_prereg(repo, block(), iso(5))
    commit_prereg(repo, "registrations: []\n", iso(10))
    commit_prereg(repo, block(), iso(20))
    assert registration_commit_ts(repo, R1) == utc(20)


def test_entry_absent_at_tip_is_none(repo):
    commit_prereg(repo, block(), iso(5))
    commit_prereg(repo, "registrations: []\n", iso(10))
    assert registration_commit_ts(repo, R1) is None


def test_duplicate_id_with_conflicting_content_is_ambiguous(repo):
    commit_prereg(repo, block() + "- id: r1\n  model_id: m\n  prompt_hash: evil\n", iso(5))
    assert registration_commit_ts(repo, R1) is None


def test_comment_lookalike_does_not_count(repo):
    commit_prereg(repo, "# id: r1\nregistrations: []\n", iso(2))
    assert registration_commit_ts(repo, R1) is None


def test_prefix_id_does_not_match_longer_id(repo):
    commit_prereg(repo, block(id="r10"), iso(5))
    assert registration_commit_ts(repo, R1) is None


def test_not_a_git_repo_returns_none(tmp_path):
    assert registration_commit_ts(tmp_path / "missing", R1) is None


def test_unknown_ref_returns_none(repo):
    commit_prereg(repo, block(), iso(5))
    assert registration_commit_ts(repo, R1, verified_ref="nope") is None


def test_file_rename_is_unsupported_counts_from_new_path_creation(repo):
    # documented: history of other paths is not followed; the constant path is what is read
    commit_prereg(repo, block(), iso(5))
    git(repo, "mv", "config/preregistration.yaml", "config/old.yaml")
    git(repo, "commit", "-q", "-m", "mv", when=iso(6))
    assert registration_commit_ts(repo, R1) is None  # file gone at the tip path
    git(repo, "mv", "config/old.yaml", "config/preregistration.yaml")
    git(repo, "commit", "-q", "-m", "back", when=iso(30))
    assert registration_commit_ts(repo, R1) == utc(30)


def test_shallow_repo_returns_none(repo, tmp_path_factory):
    commit_prereg(repo, block(), iso(5))
    commit_other(repo, "x.txt", iso(6))
    shallow = tmp_path_factory.mktemp("shallow") / "c"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow)],
        check=True, capture_output=True,
    )  # fmt: skip
    assert registration_commit_ts(shallow, R1) is None


# ---- trusted-line (first-parent) behaviour -------------------------------------------------


def test_direct_commit_on_trusted_line_is_early(repo):
    commit_prereg(repo, block(), iso(5))
    assert registration_commit_ts(repo, R1, verified_ref="main") == utc(5)


def test_side_branch_before_event_merged_after_gets_merge_time(repo):
    git(repo, "checkout", "-q", "-b", "side")
    commit_prereg(repo, block(), iso(5))  # before the event, but on a side branch
    git(repo, "checkout", "-q", "main")
    commit_other(repo, "main.txt", iso(6))
    git(repo, "merge", "-q", "--no-ff", "-m", "merge", "side", when=iso(20))
    assert registration_commit_ts(repo, R1, verified_ref="main") == utc(20)


def test_merge_commit_introducing_entry_uses_merge_time_not_side_commit_time(repo):
    git(repo, "checkout", "-q", "-b", "side")
    commit_prereg(repo, block(), iso(5))
    git(repo, "checkout", "-q", "main")
    commit_other(repo, "main.txt", iso(6))
    git(repo, "merge", "-q", "--no-ff", "-m", "merge", "side", when=iso(8))
    assert registration_commit_ts(repo, R1, verified_ref="main") == utc(8)


def test_entry_only_on_side_branch_not_on_verified_ref(repo):
    git(repo, "checkout", "-q", "-b", "side")
    commit_prereg(repo, block(), iso(5))
    assert registration_commit_ts(repo, R1, verified_ref="HEAD") == utc(5)
    assert registration_commit_ts(repo, R1, verified_ref="main") is None


# ---- guard integration ---------------------------------------------------------------------


def _confirm(repo: Path, event: datetime, regs=None) -> bool:
    reg = {"m": ModelCutoff("m", date(2026, 6, 30), 31, "https://x", date(2026, 10, 30))}
    regs = regs or [Registration("r1", "m", "h", date(2020, 1, 1))]  # back-dated YAML note
    cts = verified_registration_map(repo, regs, "main")
    return is_confirmatory(
        registry=reg, pinned_model_id="m", model_id="m",
        doc_available_ts=utc(1), event_release_ts=event,
        score_ts=utc(10), prompt_hash="h",
        registrations=regs, registration_commit_ts=cts, external_retrieval=False,
    )  # fmt: skip


def test_backdated_yaml_but_late_commit_not_confirmatory(repo):
    commit_prereg(repo, block(extra="  committed_on: 2020-01-01\n"), iso(18))
    assert not _confirm(repo, utc(16))


def test_commit_before_event_is_confirmatory(repo):
    commit_prereg(repo, block(), iso(5))
    assert _confirm(repo, utc(16))


def test_hash_edited_after_event_not_confirmatory(repo):
    commit_prereg(repo, block(h="old"), iso(5))
    commit_prereg(repo, block(h="h"), iso(20))
    assert not _confirm(repo, utc(16))


def test_same_day_earlier_instant_counts_later_instant_does_not(repo):
    commit_prereg(repo, block(), iso(16, 5))
    assert _confirm(repo, utc(16, 6))  # commit 05:00 < event 06:00, same UTC day
    assert not _confirm(repo, utc(16, 5))  # equal instant: not strictly before
    assert not _confirm(repo, utc(16, 5) - timedelta(minutes=1))  # commit after event


def test_unregistered_id_not_confirmatory(repo):
    assert not _confirm(repo, utc(16))


def test_conflicting_duplicate_ids_in_input_all_omitted(repo):
    commit_prereg(repo, block(), iso(5))
    regs = [Registration("r1", "m", "h"), Registration("r1", "m", "h2")]
    assert verified_registration_map(repo, regs, "main") == {}
