"""Sentinel for the CI partition-union guard (issue #293).

`scripts/backend_test_partitions.py verify` is what CI trusts to prove that
the parallel shards it runs cover every test the exhaustive suite would have
collected, with no test double-run across shards. That trust is only worth
something if the guard actually fails on every way it could be lied to —
this file proves it does, as a permanent, fast, DB-free regression test
rather than a one-off manual demonstration.

No fixtures, no DB, no FastAPI import: this exercises `verify_union()`,
`validate_shard_file_count()`, and `_run_pytest_collect()`'s fail-closed exit
code handling in isolation, which is exactly what the `unit` marker means in
this repo's taxonomy.
"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
import backend_test_partitions as btp  # noqa: E402
from backend_test_partitions import (  # noqa: E402
    partition,
    shard_of,
    validate_shard_file_count,
    verify_union,
)

pytestmark = pytest.mark.unit


_FAKE_NODE_IDS = [f"backend/tests/test_fixture_{i}.py::test_case" for i in range(200)]


def test_shard_of_is_deterministic():
    ids = _FAKE_NODE_IDS
    assert [shard_of(nid, 6) for nid in ids] == [shard_of(nid, 6) for nid in ids]


def test_partition_union_covers_every_node_id_by_construction():
    """The correct-partition case: passes with zero missing/extra/overlap."""
    shards = partition(_FAKE_NODE_IDS, num_shards=6)
    result = verify_union(_FAKE_NODE_IDS, shards)
    assert result.ok
    assert result.missing == set()
    assert result.extra == set()
    assert result.overlap_count == 0
    assert result.exhaustive_count == len(_FAKE_NODE_IDS)
    assert result.union_count == len(_FAKE_NODE_IDS)


def test_guard_fails_when_a_partition_is_missing_one_test():
    """The mutation/sentinel required by #293's evidence checklist.

    Deliberately drop one node ID from one shard's list — simulating a shard
    definition that silently omitted a test — and assert the guard notices.
    """
    shards = partition(_FAKE_NODE_IDS, num_shards=6)
    mutated = [list(shard) for shard in shards]

    non_empty = next(i for i, s in enumerate(mutated) if s)
    removed_id = mutated[non_empty].pop(0)

    result = verify_union(_FAKE_NODE_IDS, mutated)

    assert not result.ok
    assert result.missing == {removed_id}
    assert result.extra == set()


def test_guard_flags_a_stale_id_that_no_longer_exists_in_the_exhaustive_suite():
    """The inverse mutation: a shard file listing an ID that isn't collected
    anymore (e.g. a stale cached shard file after a test was renamed)."""
    shards = partition(_FAKE_NODE_IDS, num_shards=6)
    mutated = [list(shard) for shard in shards]
    mutated[0].append("backend/tests/test_renamed_away.py::test_ghost")

    result = verify_union(_FAKE_NODE_IDS, mutated)

    assert not result.ok
    assert result.extra == {"backend/tests/test_renamed_away.py::test_ghost"}


def test_guard_fails_when_one_node_id_is_duplicated_across_shards():
    """A hash partition assigns every ID to exactly one shard — any overlap
    is a real defect (wrong --count, hand-edited file, stale data), so the
    guard must fail rather than silently tolerate it."""
    shards = partition(_FAKE_NODE_IDS, num_shards=6)
    mutated = [list(shard) for shard in shards]
    duplicate_id = mutated[1][0]
    mutated[0].append(duplicate_id)

    result = verify_union(_FAKE_NODE_IDS, mutated)

    assert not result.ok
    assert result.missing == set()
    assert result.extra == set()
    assert result.overlap_count == 1


def test_validate_shard_file_count_rejects_a_missing_shard_file():
    with pytest.raises(ValueError, match="expected exactly 6"):
        validate_shard_file_count(num_shard_files=5, expected_count=6)


def test_validate_shard_file_count_rejects_an_extra_shard_file():
    with pytest.raises(ValueError, match="expected exactly 6"):
        validate_shard_file_count(num_shard_files=7, expected_count=6)


def test_validate_shard_file_count_accepts_exactly_n():
    validate_shard_file_count(num_shard_files=6, expected_count=6)  # no raise


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_collection_error_exit_code_is_fatal_not_a_valid_empty_collection():
    """The mutation/sentinel for finding 2: force a pytest collection error
    (exit code 2 — EXIT_INTERRUPTED, what pytest actually returns for a
    broken import during --collect-only) and prove `_run_pytest_collect`
    raises rather than returning `[]` as if zero tests were legitimately
    collected."""
    fake_run = lambda *a, **k: _FakeCompletedProcess(  # noqa: E731
        returncode=2, stdout="", stderr="ERROR backend/tests/test_broken.py - ImportError"
    )
    with pytest.raises(RuntimeError, match="failed closed"):
        btp._run_pytest_collect(["backend/tests"], runner=fake_run)


def test_exit_code_1_is_also_fatal_not_silently_accepted():
    """EXIT_TESTSFAILED (1) is unreachable for a pure --collect-only run, so
    its presence signals something unexpected happened during collection —
    it must not be treated as a legitimate outcome either."""
    fake_run = lambda *a, **k: _FakeCompletedProcess(returncode=1)  # noqa: E731
    with pytest.raises(RuntimeError, match="failed closed"):
        btp._run_pytest_collect(["backend/tests"], runner=fake_run)


def test_exit_code_0_and_5_are_accepted_as_legitimate():
    fake_ok = lambda *a, **k: _FakeCompletedProcess(  # noqa: E731
        returncode=0, stdout="backend/tests/test_x.py::test_y\n"
    )
    assert btp._run_pytest_collect(["backend/tests"], runner=fake_ok) == [
        "backend/tests/test_x.py::test_y"
    ]

    fake_empty = lambda *a, **k: _FakeCompletedProcess(returncode=5, stdout="")  # noqa: E731
    assert btp._run_pytest_collect(["backend/tests"], runner=fake_empty) == []


def test_a_real_broken_import_makes_collect_exhaustive_raise():
    """End-to-end version of the same sentinel: a genuinely unimportable test
    module must make collection fail closed, not silently shrink the
    exhaustive count. Uses the real subprocess path (patching only
    sys.executable's target module list would be circular), scoped to a
    throwaway temp file so it never touches the real suite."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "test_intentionally_broken.py").write_text(
            "import this_module_does_not_exist_anywhere\n"
        )
        with patch.object(btp, "REPO_ROOT", tmp_path):
            with pytest.raises(RuntimeError, match="failed closed"):
                btp.collect_exhaustive(test_root=".")
