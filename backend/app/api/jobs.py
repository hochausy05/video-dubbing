"""Persisted Job state and explicit retry endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import create_database_engine, create_session_factory
from app.models import Job, JobStatus
from app.schemas import JobCreated, JobDetail


router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_detail(job: Job) -> JobDetail:
    return JobDetail(
        id=job.id,
        project_id=job.project_id,
        job_type=job.operation_type,
        status=job.status,
        stage=job.stage,
        error=job.safe_error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.completed_at,
    )


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: uuid.UUID) -> JobDetail:
    """Return persisted lifecycle fields for one Job."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
            return _job_detail(job)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to read the Job.",
        ) from error
    finally:
        engine.dispose()


@router.post("/{job_id}/retry", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: uuid.UUID) -> JobCreated:
    """Create a fresh queued Job from a failed or interrupted historical Job."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            original = session.get(Job, job_id)
            if original is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
            if original.status not in {JobStatus.FAILED.value, JobStatus.INTERRUPTED.value}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only failed or interrupted Jobs can be retried.",
                )

            retry = Job(
                project_id=original.project_id,
                operation_type=original.operation_type,
                input_revision=original.input_revision,
                status=JobStatus.QUEUED.value,
                stage="queued",
            )
            session.add(retry)
            session.commit()
            session.refresh(retry)
            return JobCreated(id=retry.id, project_id=retry.project_id, status=retry.status)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retry the Job.",
        ) from error
    finally:
        engine.dispose()
