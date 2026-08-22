#!/usr/bin/env python3
"""Deterministic backend/tests/ partitioning for CI (issue #293).

Why a hand-rolled splitter instead of marker-based partitions
---------------------------------------------------------------
The pytest marker taxonomy registered in pyproject.toml (unit, contract,
integration, reporting, security, postgres, slow) exists for *documentation*
and *focused local runs* — it lets a developer run `pytest -m security`
without guessing file names. It deliberately does NOT decide which tests run
in which CI shard: only ~50 of ~300 test files carry a category marker today
(the rest are an audited, visible catch-all — see `audit-markers` below), and
gating CI parallelism on marker coverage would silently drop any test whose
marker is missing or wrong.

CI parallelism instead uses a marker-independent, content-addressed hash of
each test's own node ID: `shard_of()` below. Every node ID collected by the
exhaustive suite maps to exactly one shard by construction, so the union of
all shards is the exhaustive suite by definition — completeness does not
depend on anyone having tagged the test correctly. `verify()` still proves
this at CI time against each shard's *actual* pytest invocation (not just the
hash function in isolation), so a shard job that runs the wrong file list, or
a stale/edited shard file, is still caught.

Commands
--------
  list-shard --index I --count N [--out FILE]
      Print (or write) the node IDs belonging to shard I of N, freshly
      collected from backend/tests/.

  verify --count N --shard-file S0 --shard-file S1 ... --shard-file SN-1
      Requires EXACTLY N --shard-file arguments (a missing or extra shard
      file fails immediately, before collection even runs). Freshly collects
      the exhaustive backend/tests/ suite, unions the given shard files, and
      fails (exit 1) unless the union equals the exhaustive collection AND
      overlap is exactly zero — this is a hash partition, so a real overlap
      means a shard file was generated with a different --count, hand-edited,
      or otherwise corrupted, not something to tolerate as "intentional".
      Prints the missing set (in exhaustive, not in any shard — an omission),
      the extra set (in a shard, not in exhaustive — e.g. a stale ID), and
      any duplicated node IDs.

  audit-markers
      Freshly collect the exhaustive suite and, for each registered taxonomy
      marker, collect the subset carrying it. Prints a histogram plus the
      count of tests carrying none of the category markers (unit, contract,
      integration, reporting, security, postgres) — the audited catch-all.
      This is the "unmarked tests remain visible" guard: it never excludes
      anything, only counts and reports.

Local usage
-----------
  # One CI-equivalent shard (of the default shard count) on SQLite. Use
  # mapfile, not $(cat file): some parametrize ids contain spaces, and
  # unquoted command substitution would word-split one node ID into several
  # bogus pytest arguments.
  python scripts/backend_test_partitions.py list-shard --index 0 --count 6 --out /tmp/shard0.txt
  mapfile -t ids < /tmp/shard0.txt && pytest "${ids[@]}" -q

  # Prove no test was dropped by the shard definitions:
  python scripts/backend_test_partitions.py list-shard --index 0 --count 6 --out /tmp/s0.txt
  ...
  python scripts/backend_test_partitions.py verify --count 6 \\
      --shard-file /tmp/s0.txt --shard-file /tmp/s1.txt ... --shard-file /tmp/s5.txt

  # Marker taxonomy visibility:
  python scripts/backend_test_partitions.py audit-markers
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEST_ROOT = "backend/tests"

# Category markers used by audit-markers to compute the visible catch-all.
# Kept in sync with pyproject.toml's [tool.pytest.ini_options] markers list;
# "slow" is intentionally excluded — it is an orthogonal modifier, not a
# category, and can coexist with any of the categories below.
CATEGORY_MARKERS = [
    "unit",
    "contract",
    "integration",
    "reporting",
    "security",
    "postgres",
]
ALL_MARKERS = CATEGORY_MARKERS + ["slow"]


def _run_pytest_collect(
    pytest_args: list[str], runner=subprocess.run
) -> list[str]:
    """Run `pytest --collect-only -q <args>` and return collected node IDs.

    Fails closed: only pytest's own EXIT_OK (0) and EXIT_NOTESTSCOLLECTED (5)
    are legitimate collection outcomes. Every other exit code — 1
    (EXIT_TESTSFAILED, unreachable for a pure --collect-only run, so its
    presence would mean something unexpected happened), 2
    (EXIT_INTERRUPTED — what pytest actually returns for a collection error,
    e.g. a broken import in a test module), 3 (EXIT_INTERNALERROR), 4
    (EXIT_USAGEERROR), or anything else — must never be treated as "collected
    fine, just fewer/zero tests". A silently-swallowed collection error is
    exactly the failure mode that would let the exhaustive count, a shard's
    count, or a marker's count look valid while actually being wrong or
    empty.

    `runner` is injectable so tests can simulate a collection error without
    needing a broken test file or a real pytest install — see
    backend/tests/test_partition_guard.py.
    """
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", *pytest_args]
    proc = runner(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 5):
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise RuntimeError(
            f"pytest collection failed closed (exit {proc.returncode}, "
            f"only 0/5 are accepted as legitimate): {cmd}"
        )

    node_ids = []
    for line in proc.stdout.splitlines():
        if "::" in line and (".py::" in line):
            node_ids.append(line.strip())
    return node_ids


def collect_exhaustive(test_root: str = DEFAULT_TEST_ROOT) -> list[str]:
    return _run_pytest_collect([test_root])


def collect_marker(marker: str, test_root: str = DEFAULT_TEST_ROOT) -> list[str]:
    return _run_pytest_collect(["-m", marker, test_root])


def shard_of(node_id: str, num_shards: int) -> int:
    """Deterministic, content-addressed shard assignment.

    A pure function of the node ID string — stable across collection order,
    test additions/removals elsewhere in the suite, and process/platform.
    """
    return zlib.crc32(node_id.encode("utf-8")) % num_shards


def partition(node_ids: list[str], num_shards: int) -> list[list[str]]:
    shards: list[list[str]] = [[] for _ in range(num_shards)]
    for node_id in node_ids:
        shards[shard_of(node_id, num_shards)].append(node_id)
    return shards


class VerifyResult:
    def __init__(
        self,
        missing: set[str],
        extra: set[str],
        overlap_count: int,
        exhaustive_count: int,
        union_count: int,
    ):
        self.missing = missing
        self.extra = extra
        self.overlap_count = overlap_count
        self.exhaustive_count = exhaustive_count
        self.union_count = union_count

    @property
    def ok(self) -> bool:
        # This is a hash partition (shard_of): every node ID is assigned to
        # exactly ONE shard by construction, so a legitimate run can never
        # produce overlap. Any overlap_count > 0 means the shard files were
        # generated with a different --count than what's being verified, hand
        # -edited, or otherwise corrupted — a real defect, not "intentional
        # duplication" to tolerate.
        return not self.missing and not self.extra and self.overlap_count == 0


def verify_union(exhaustive: list[str], shards: list[list[str]]) -> VerifyResult:
    """Pure comparison: union(shards) must equal exhaustive exactly, with
    zero overlap between shards.

    Exercised directly (no subprocess, no pytest collection) by the sentinel
    tests in backend/tests/test_partition_guard.py, which prove that dropping
    one ID from one shard, adding a stale ID, or duplicating one ID across two
    shards each make `.ok` False.
    """
    exhaustive_set = set(exhaustive)
    all_shard_ids: list[str] = [nid for shard in shards for nid in shard]
    union_set = set(all_shard_ids)

    missing = exhaustive_set - union_set
    extra = union_set - exhaustive_set
    overlap_count = len(all_shard_ids) - len(union_set)

    return VerifyResult(
        missing=missing,
        extra=extra,
        overlap_count=overlap_count,
        exhaustive_count=len(exhaustive_set),
        union_count=len(union_set),
    )


def validate_shard_file_count(num_shard_files: int, expected_count: int) -> None:
    """Raise if the number of --shard-file arguments != --count.

    A missing or extra shard file is exactly the kind of silent omission
    (or double-count) the partition-union guard exists to catch — checked
    before collection even runs, so it fails fast and unambiguously.
    """
    if num_shard_files != expected_count:
        raise ValueError(
            f"expected exactly {expected_count} --shard-file arguments "
            f"(one per shard, matching --count {expected_count}), got "
            f"{num_shard_files}"
        )


def cmd_list_shard(args: argparse.Namespace) -> int:
    node_ids = collect_exhaustive(args.root)
    shards = partition(node_ids, args.count)
    shard_ids = shards[args.index]
    text = "\n".join(shard_ids) + ("\n" if shard_ids else "")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(
            f"shard {args.index}/{args.count}: {len(shard_ids)} tests -> {args.out}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(text)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        validate_shard_file_count(len(args.shard_file), args.count)
    except ValueError as exc:
        print(f"PARTITION-UNION GUARD FAILED: {exc}", file=sys.stderr)
        return 1

    exhaustive = collect_exhaustive(args.root)
    shards = []
    for shard_file in args.shard_file:
        lines = Path(shard_file).read_text(encoding="utf-8").splitlines()
        shards.append([line for line in lines if line.strip()])

    result = verify_union(exhaustive, shards)

    print(f"exhaustive collected: {result.exhaustive_count}")
    print(f"shard files:          {len(shards)} (expected {args.count})")
    print(f"union collected:      {result.union_count}")
    print(f"overlap:              {result.overlap_count} (must be 0 for a hash partition)")

    if not result.ok:
        if result.missing:
            print(f"\nMISSING ({len(result.missing)}) — in exhaustive, in no shard:")
            for nid in sorted(result.missing):
                print(f"  - {nid}")
        if result.extra:
            print(f"\nEXTRA ({len(result.extra)}) — in a shard, not in exhaustive:")
            for nid in sorted(result.extra):
                print(f"  - {nid}")
        if result.overlap_count:
            dupes = _find_duplicates(shards)
            print(f"\nOVERLAP ({result.overlap_count}) — node ID present in more than one shard:")
            for nid in sorted(dupes):
                print(f"  - {nid}")
        print("\nPARTITION-UNION GUARD FAILED: shards do not equal the exhaustive suite.")
        return 1

    print("\nPARTITION-UNION GUARD PASSED: union(shards) == exhaustive collection, zero overlap.")
    return 0


def _find_duplicates(shards: list[list[str]]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for shard in shards:
        for nid in shard:
            (dupes if nid in seen else seen).add(nid)
    return dupes


def cmd_audit_markers(args: argparse.Namespace) -> int:
    exhaustive = set(collect_exhaustive(args.root))
    category_union: set[str] = set()

    print(f"{'marker':<12} {'count':>7}")
    print("-" * 20)
    for marker in ALL_MARKERS:
        ids = set(collect_marker(marker, args.root))
        print(f"{marker:<12} {len(ids):>7}")
        if marker in CATEGORY_MARKERS:
            category_union |= ids

    uncategorized = exhaustive - category_union
    print("-" * 20)
    print(f"{'exhaustive':<12} {len(exhaustive):>7}")
    print(f"{'uncategorized':<12} {len(uncategorized):>7}  (no category marker — audited catch-all, still exhaustively CI-covered by hash-sharding)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_shard = sub.add_parser("list-shard", help="Print node IDs for one shard")
    p_shard.add_argument("--index", type=int, required=True)
    p_shard.add_argument("--count", type=int, required=True)
    p_shard.add_argument("--root", default=DEFAULT_TEST_ROOT)
    p_shard.add_argument("--out", default=None)
    p_shard.set_defaults(func=cmd_list_shard)

    p_verify = sub.add_parser("verify", help="Prove union(shards) == exhaustive")
    p_verify.add_argument("--count", type=int, required=True)
    p_verify.add_argument("--shard-file", action="append", required=True)
    p_verify.add_argument("--root", default=DEFAULT_TEST_ROOT)
    p_verify.set_defaults(func=cmd_verify)

    p_audit = sub.add_parser("audit-markers", help="Print marker taxonomy histogram")
    p_audit.add_argument("--root", default=DEFAULT_TEST_ROOT)
    p_audit.set_defaults(func=cmd_audit_markers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
