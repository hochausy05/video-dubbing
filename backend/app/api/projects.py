"""Minimal project upload API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import create_database_engine, create_session_factory
from app.models import Job, JobStatus, Project
from app.schemas import JobCreated, ProjectListItem
from app.services.uploads import (
    UploadStorageError,
    UploadValidationError,
    remove_source_upload,
    save_source_upload,
)


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/{project_id}/jobs", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
def enqueue_project_job(project_id: uuid.UUID) -> JobCreated:
    """Persist an analysis job and return without performing media work."""
    database_engine = create_database_engine()
    try:
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found.",
                )
            job = Job(
                project_id=project.id,
                operation_type="transcribe_translate",
                input_revision=project.current_revision,
                status=JobStatus.QUEUED.value,
                stage="queued",
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return JobCreated(id=job.id, project_id=job.project_id, status=job.status)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to enqueue the project job.",
        ) from error
    finally:
        database_engine.dispose()


@router.get("", response_model=list[ProjectListItem])
def list_projects() -> list[ProjectListItem]:
    """Return persisted projects in deterministic newest-first order."""
    database_engine = create_database_engine()
    try:
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            projects = session.scalars(
                select(Project)
                .order_by(desc(Project.created_at), desc(Project.id))
            ).all()
            return [
                ProjectListItem(
                    id=project.id,
                    name=project.name,
                    status=project.business_status,
                    source_media_reference=project.source_media_reference,
                    created_at=project.created_at,
                )
                for project in projects
            ]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to list projects.",
        ) from error
    finally:
        database_engine.dispose()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_source_video(
    name: Annotated[str, Form(min_length=1, max_length=255)],
    source_video: Annotated[UploadFile, File()],
) -> dict[str, str]:
    """Persist one project and store its source video at a server-controlled path."""
    project_id = uuid.uuid4()
    relative_path = None
    database_engine = None

    try:
        relative_path = await save_source_upload(source_video, project_id)
        database_engine = create_database_engine()
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project = Project(
                id=project_id,
                name=name,
                source_media_reference=relative_path.as_posix(),
            )
            session.add(project)
            session.commit()
    except UploadValidationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except UploadStorageError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to store the source video.",
        ) from error
    except SQLAlchemyError as error:
        if relative_path is not None:
            remove_source_upload(relative_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create the project.",
        ) from error
    finally:
        if database_engine is not None:
            database_engine.dispose()
        await source_video.close()

    return {
        "id": str(project_id),
        "name": name,
        "source_media_reference": relative_path.as_posix(),
    }
