"""Independently deployable job scheduler/dispatcher (ADR-007, task 3.1).

Usage: python -m backend.scripts.run_job_scheduler [--interval SECONDS]

Runs the single dispatcher: promotes due retry_wait jobs to queued and recovers
abandoned leases. Deploy exactly ONE instance (its work is idempotent, but a
singleton avoids redundant scans). SIGTERM/SIGINT stop it cleanly.
"""
import argparse
import logging
import os
import signal

from backend.jobs.runtime import JobScheduler

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("job_scheduler")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=5.0)
    args = ap.parse_args()

    scheduler = JobScheduler(interval_seconds=args.interval)

    def _stop(signum, _frame):
        logger.info("signal %s received — stopping scheduler", signum)
        scheduler.request_stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    scheduler.run()


if __name__ == "__main__":
    main()
