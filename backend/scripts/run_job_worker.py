"""Independently deployable job worker (ADR-007, task 3.1).

Usage: python -m backend.scripts.run_job_worker [--worker-id ID] [--job-type T]
                                                 [--poll SECONDS] [--lease SECONDS]

Runs a durable-queue worker that claims and executes jobs. SIGTERM/SIGINT trigger
a graceful drain: the in-flight job finishes, no new work is claimed, then exit.
Runs in its own process — the API replicas start no worker loop.
"""
import argparse
import logging
import os
import signal
import socket

from backend.jobs import handlers as _handlers  # noqa: F401 — registers handlers
from backend.jobs.runtime import JobWorker

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("job_worker")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker-id", default=f"{socket.gethostname()}:{os.getpid()}")
    ap.add_argument("--job-type", default=None, help="only claim this job_type")
    ap.add_argument("--poll", type=float, default=2.0)
    ap.add_argument("--lease", type=int, default=60)
    args = ap.parse_args()

    worker = JobWorker(args.worker_id, job_type=args.job_type,
                       poll_seconds=args.poll, lease_seconds=args.lease)

    def _drain(signum, _frame):
        logger.info("signal %s received — draining worker %s", signum, args.worker_id)
        worker.request_stop()

    signal.signal(signal.SIGTERM, _drain)
    signal.signal(signal.SIGINT, _drain)
    worker.run()


if __name__ == "__main__":
    main()
