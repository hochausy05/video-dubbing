"""Sequential PostgreSQL-backed job claimant; media handlers arrive in later tasks."""

from __future__ import annotations

import argparse
import logging
import time
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.engine import Engine

from app.core.config import get_job_worker_poll_interval_seconds
from app.core.database import create_database_engine
from app.models import Job, JobStatus


logger = logging.getLogger("autodub.worker")
_WORKER_LOCK_KEY = 7_314_209_018


def claim_next_job(engine: Engine) -> UUID | None:
    """Atomically claim the oldest queued job if no other job is running."""
    with engine.begin() as connection:
        # Serialize claimers across processes and keep the MVP to one active job.
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _WORKER_LOCK_KEY},
        )
        active_job_id = connection.scalar(
            select(Job.id).where(Job.status == JobStatus.RUNNING.value).limit(1)
        )
        if active_job_id is not None:
            return None

        queued_job_id = connection.scalar(
            select(Job.id)
            .where(Job.status == JobStatus.QUEUED.value)
            .order_by(Job.created_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if queued_job_id is None:
            return None

        claimed_id = connection.scalar(
            update(Job)
            .where(Job.id == queued_job_id, Job.status == JobStatus.QUEUED.value)
            .values(
                status=JobStatus.RUNNING.value,
                stage="claimed",
                started_at=func.now(),
            )
            .returning(Job.id)
        )
    return claimed_id


def run_worker(*, poll_interval: float, once: bool = False) -> None:
    """Poll and claim one job; keep polling while the claimed job remains active.

    JOB-01 intentionally has no processing handler. Claimed jobs remain `running`
    until a later pipeline task supplies real work and terminal state transitions.
    """
    engine = create_database_engine()
    try:
        while True:
            job_id = claim_next_job(engine)
            if job_id is not None:
                logger.info("Claimed job %s", job_id)
                if once:
                    return
            elif once:
                return
            time.sleep(poll_interval)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll and claim AutoDub jobs from PostgreSQL.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="perform one polling/claim attempt and exit (useful for controlled verification)",
    )
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_worker(poll_interval=get_job_worker_poll_interval_seconds(), once=arguments.once)


if __name__ == "__main__":
    main()
