"""Sequential PostgreSQL-backed job claimant; media handlers arrive in later tasks."""

from __future__ import annotations

import argparse
import logging
import re
import time
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_job_worker_poll_interval_seconds
from app.core.database import create_database_engine
from app.models import Job, JobStatus
from app.services.asr import transcribe_project
from app.services.translation import translate_project


logger = logging.getLogger("autodub.worker")
_WORKER_PROCESS_LOCK_KEY = 7_314_209_019
_WORKER_CLAIM_LOCK_KEY = 7_314_209_018
_SAFE_ERROR_MAX_LENGTH = 500
_CONNECTION_URL_RE = re.compile(r"(?i)\b(?:postgres(?:ql)?(?:\+[\w]+)?|https?)://\S+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(DATABASE_URL|[A-Z0-9_-]*(?:API[_ -]?KEY|TOKEN|SECRET|PASSWORD))\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|\S+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+\S+")
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s,;]+")
_UNIX_PATH_RE = re.compile(r"(?<![:\w])/(?:[^\s,;]+)")


class JobNotFoundError(LookupError):
    """A requested persisted Job does not exist."""


class JobTransitionError(RuntimeError):
    """A Job is not in a state that permits the requested transition."""


def claim_next_job(engine: Engine) -> UUID | None:
    """Atomically claim the oldest queued job if no other job is running."""
    with engine.begin() as connection:
        # Serialize claimers across processes and keep the MVP to one active job.
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _WORKER_CLAIM_LOCK_KEY},
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
                completed_at=None,
                safe_error=None,
            )
            .returning(Job.id)
        )
    return claimed_id


def recover_abandoned_jobs(engine: Engine) -> tuple[UUID, ...]:
    """Mark running Jobs from the prior worker process as interrupted history."""
    with engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _WORKER_CLAIM_LOCK_KEY},
        )
        job_ids = connection.execute(
            update(Job)
            .where(Job.status == JobStatus.RUNNING.value)
            .values(
                status=JobStatus.INTERRUPTED.value,
                stage="interrupted",
                safe_error="Worker restarted before this job completed.",
                completed_at=func.now(),
            )
            .returning(Job.id)
        ).scalars().all()
    return tuple(job_ids)


def safe_error_summary(message: str) -> str:
    """Bound and redact a one-line error summary before persisting it."""
    first_line = (message or "").strip().splitlines()[0:1]
    summary = " ".join(first_line[0].split()) if first_line else ""
    if summary.lower().startswith("traceback (most recent call last)"):
        summary = "Job failed; detailed error omitted."
    summary = _CONNECTION_URL_RE.sub("[connection details omitted]", summary)
    summary = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[redacted]", summary)
    summary = _BEARER_RE.sub("Bearer [redacted]", summary)
    summary = _WINDOWS_PATH_RE.sub("[path omitted]", summary)
    summary = _UNIX_PATH_RE.sub("[path omitted]", summary)
    summary = summary[:_SAFE_ERROR_MAX_LENGTH].strip()
    return summary or "Job failed; details omitted."


def _finish_running_job(
    engine: Engine,
    job_id: UUID,
    *,
    status_value: str,
    stage: str,
    safe_error: str | None,
) -> None:
    with engine.begin() as connection:
        updated_id = connection.scalar(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.RUNNING.value)
            .values(
                status=status_value,
                stage=stage,
                safe_error=safe_error,
                completed_at=func.now(),
            )
            .returning(Job.id)
        )
        if updated_id is not None:
            return
        current_status = connection.scalar(select(Job.status).where(Job.id == job_id))
        if current_status is None:
            raise JobNotFoundError("Job not found.")
        raise JobTransitionError(f"Job in state {current_status!r} cannot be finished.")


def mark_job_succeeded(engine: Engine, job_id: UUID, *, stage: str = "completed") -> None:
    """Persist a success transition for completed real work."""
    _finish_running_job(
        engine,
        job_id,
        status_value=JobStatus.SUCCEEDED.value,
        stage=stage,
        safe_error=None,
    )


def mark_job_failed(engine: Engine, job_id: UUID, error_summary: str) -> None:
    """Persist a bounded safe failure summary for a running Job."""
    _finish_running_job(
        engine,
        job_id,
        status_value=JobStatus.FAILED.value,
        stage="failed",
        safe_error=safe_error_summary(error_summary),
    )


def _set_running_job_stage(engine: Engine, job_id: UUID, stage: str) -> None:
    with engine.begin() as connection:
        updated_id = connection.scalar(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.RUNNING.value)
            .values(stage=stage)
            .returning(Job.id)
        )
        if updated_id is None:
            raise JobTransitionError("The Job is no longer running.")


def process_claimed_job(engine: Engine, job_id: UUID) -> None:
    """Run ASR and translation before marking the combined pipeline successful."""
    try:
        with Session(engine) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise JobNotFoundError("Job not found.")
            if job.status != JobStatus.RUNNING.value:
                raise JobTransitionError("The Job is no longer running.")
            if job.operation_type != "transcribe_translate":
                raise JobTransitionError("This Job type is not implemented by the worker yet.")
            project_id = job.project_id
            input_revision = job.input_revision

        _set_running_job_stage(engine, job_id, "preparing_asr")
        result = transcribe_project(
            engine,
            project_id=project_id,
            job_id=job_id,
            input_revision=input_revision,
            stage_callback=lambda stage: _set_running_job_stage(engine, job_id, stage),
        )
        if result.segment_count == 0:
            mark_job_succeeded(engine, job_id, stage="no_speech")
            logger.info("Job %s completed with no speech detected.", job_id)
        else:
            translation = translate_project(
                engine,
                project_id=project_id,
                job_id=job_id,
                input_revision=input_revision,
                stage_callback=lambda stage: _set_running_job_stage(engine, job_id, stage),
            )
            mark_job_succeeded(engine, job_id, stage="translation_ready")
            logger.info(
                "Job %s completed: translated %d Segments in %d Gemini batch(es).",
                job_id,
                translation.segment_count,
                translation.batch_count,
            )
    except Exception as error:
        try:
            mark_job_failed(engine, job_id, str(error))
        except Exception as transition_error:
            logger.warning(
                "Could not persist failure state for job %s (%s).",
                job_id,
                type(transition_error).__name__,
            )
        logger.warning(
            "Job %s failed during transcription/translation: %s",
            job_id,
            safe_error_summary(str(error)),
        )


def run_worker(*, poll_interval: float, once: bool = False) -> None:
    """Recover abandoned work, then poll and claim sequentially under one worker lock."""
    engine = create_database_engine()
    worker_connection = engine.connect()
    owns_worker_lock = False
    try:
        owns_worker_lock = bool(
            worker_connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": _WORKER_PROCESS_LOCK_KEY},
            )
        )
        worker_connection.commit()
        if not owns_worker_lock:
            logger.warning("Another worker process already owns the worker lock; exiting.")
            return

        recovered_job_ids = recover_abandoned_jobs(engine)
        if recovered_job_ids:
            logger.info("Marked %d abandoned job(s) interrupted.", len(recovered_job_ids))

        while True:
            job_id = claim_next_job(engine)
            if job_id is not None:
                logger.info("Claimed job %s", job_id)
                process_claimed_job(engine, job_id)
                if once:
                    return
            elif once:
                return
            time.sleep(poll_interval)
    finally:
        if owns_worker_lock:
            worker_connection.scalar(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": _WORKER_PROCESS_LOCK_KEY},
            )
            worker_connection.commit()
        worker_connection.close()
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
