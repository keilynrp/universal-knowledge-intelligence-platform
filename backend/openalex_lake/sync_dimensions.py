"""Dimension loader — OpenAlex S3 snapshot -> DuckDB dim_* tables.

The dimension entities (sources, institutions, topics) are small enough to load
in full from the public snapshot, giving the lake authoritative journal /
institution / topic metadata to join the API-pulled works against.

Two phases, either can run alone:
1. download: `aws s3 sync s3://openalex/data/<entity> <dir>/<entity>
   --no-sign-request` (opt-in; needs aws-cli + storage).
2. load: stream the gzipped JSON-Lines parts through the pure dimension
   transforms into the store (idempotent upsert).

Run:  python -m backend.openalex_lake.sync_dimensions --download
      python -m backend.openalex_lake.sync_dimensions --snapshot-dir ./snap
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import logging
import os
import subprocess  # nosec B404 - fixed argv, no shell
from typing import Callable, Iterator, Optional

from backend.openalex_lake.config import LakeSettings
from backend.openalex_lake.store import LakeStore
from backend.openalex_lake.transform import DIMENSION_TRANSFORMS

logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_DIR = os.environ.get("OPENALEX_SNAPSHOT_DIR", "data/openalex-snapshot")
BATCH_SIZE = 5000
DIMENSION_ENTITIES = tuple(DIMENSION_TRANSFORMS.keys())


def iter_jsonl_gz(path: str) -> Iterator[dict]:
    """Yield JSON objects from a gzipped JSON-Lines file (skips blank lines)."""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_entity_dir(
    store: LakeStore,
    entity: str,
    snapshot_dir: str = DEFAULT_SNAPSHOT_DIR,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Load all `<snapshot_dir>/<entity>/**/*.gz` parts into the dim table.

    Returns the number of rows written. Idempotent via the store's upsert.
    """
    if entity not in DIMENSION_TRANSFORMS:
        raise ValueError(f"unsupported dimension entity: {entity!r}")
    transform_fn, table = DIMENSION_TRANSFORMS[entity]
    pattern = os.path.join(snapshot_dir, entity, "**", "*.gz")
    parts = sorted(glob.glob(pattern, recursive=True))
    if not parts:
        logger.warning("openalex-lake: no snapshot parts under %s", pattern)
        return 0

    written = 0
    batch: list[dict] = []
    for part in parts:
        for rec in iter_jsonl_gz(part):
            row = transform_fn(rec)
            if row is None:
                continue
            batch.append(row)
            if len(batch) >= batch_size:
                written += store.insert_rows(table, batch)
                batch = []
    if batch:
        written += store.insert_rows(table, batch)
    logger.info("openalex-lake: loaded %d %s from %d part(s)", written, entity, len(parts))
    return written


def download_entity(
    entity: str,
    snapshot_dir: str = DEFAULT_SNAPSHOT_DIR,
    s3_uri: str = "s3://openalex",
    runner: Callable[[list[str]], None] = None,
) -> None:
    """`aws s3 sync` one entity's snapshot dir (public bucket, no credentials)."""
    dest = os.path.join(snapshot_dir, entity)
    os.makedirs(dest, exist_ok=True)
    cmd = ["aws", "s3", "sync", f"{s3_uri}/data/{entity}", dest, "--no-sign-request"]
    logger.info("openalex-lake: %s", " ".join(cmd))
    if runner is not None:
        runner(cmd)
    else:  # pragma: no cover - real network/CLI
        subprocess.run(cmd, check=True)  # nosec B603 - fixed argv, no shell


def run_sync(
    store: LakeStore,
    entities: tuple[str, ...] = DIMENSION_ENTITIES,
    snapshot_dir: str = DEFAULT_SNAPSHOT_DIR,
    download: bool = False,
    s3_uri: str = "s3://openalex",
) -> dict[str, int]:
    stats: dict[str, int] = {}
    for entity in entities:
        if download:
            download_entity(entity, snapshot_dir, s3_uri)
        stats[entity] = load_entity_dir(store, entity, snapshot_dir)
    return stats


def main() -> None:  # pragma: no cover - thin CLI wrapper
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Load OpenAlex dimension snapshots into DuckDB.")
    parser.add_argument("--download", action="store_true", help="aws s3 sync before loading (needs aws-cli + storage).")
    parser.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument("--entities", nargs="*", default=list(DIMENSION_ENTITIES), choices=DIMENSION_ENTITIES)
    args = parser.parse_args()

    settings = LakeSettings()
    with LakeStore(settings.db_path) as store:
        stats = run_sync(
            store,
            tuple(args.entities),
            snapshot_dir=args.snapshot_dir,
            download=args.download,
            s3_uri=settings.snapshot_s3_uri,
        )
    logger.info("openalex-lake dimensions loaded: %s", stats)


if __name__ == "__main__":  # pragma: no cover
    main()
