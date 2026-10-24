"""Minimal project upload API."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import create_database_engine, create_session_factory
from app.core.config import get_edge_tts_voice, get_tts_optimization_max_rate_percent
from app.models import Artifact, Job, JobStatus, Project, Segment
from app.schemas import (
    JobCreated,
    JobDetail,
    ProjectListItem,
    TTSReadiness,
    SegmentRead,
    SegmentTranslationUpdate,
    TTSArtifactRead,
    TTSTimelinePlan,
    TTSOptimizationResult,
    TTSNormalizationResult,
    RenderArtifactRead,
)
from app.services.uploads import (
    UploadStorageError,
    UploadValidationError,
    remove_source_upload,
    resolve_storage_path,
    save_source_upload,
    source_relative_path,
)
from app.services.tts_readiness import (
    ProjectNotFoundError,
    validate_project_tts_readiness,
)
from app.services.tts import TTS_MEDIA_TYPE, adaptive_rate_percent, translation_fingerprint
from app.services.audio_normalization import read_normalization_metadata
from app.services.tts_timeline import build_project_timeline_plan
from app.services.tts_optimization import enqueue_tts_optimization, read_tts_optimization_result
from app.services.tts_normalization import enqueue_tts_normalization, read_tts_normalization_result
from app.services.video_render import RenderError, enqueue_render_job, get_current_render


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "/{project_id}/render-jobs",
    response_model=JobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_project_render(project_id: uuid.UUID) -> JobCreated:
    """Queue rendering from the server-built current timeline plan."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session, session.begin():
            try:
                return enqueue_render_job(session, project_id)
            except ProjectNotFoundError:
                raise HTTPException(status_code=404, detail="Project not found.") from None
            except RenderError as error:
                raise HTTPException(status_code=409, detail=str(error)) from None
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to enqueue Project rendering.") from error
    finally:
        engine.dispose()


def _current_render_response(project_id: uuid.UUID) -> tuple[RenderArtifactRead, Path]:
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            try:
                return get_current_render(session, project_id)
            except ProjectNotFoundError:
                raise HTTPException(status_code=404, detail="Project not found.") from None
            except LookupError:
                raise HTTPException(status_code=404, detail="Current rendered video is not available.") from None
            except RenderError:
                raise HTTPException(status_code=404, detail="Current rendered video is not available.") from None
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to read rendered video metadata.") from error
    finally:
        engine.dispose()


@router.get("/{project_id}/rendered-video", response_model=RenderArtifactRead)
def get_project_rendered_video(project_id: uuid.UUID) -> RenderArtifactRead:
    metadata, _path = _current_render_response(project_id)
    return metadata


@router.get("/{project_id}/rendered-video/preview")
def preview_project_rendered_video(project_id: uuid.UUID) -> FileResponse:
    _metadata, path = _current_render_response(project_id)
    return FileResponse(
        path, media_type="video/mp4", filename="dubbed-video.mp4",
        content_disposition_type="inline",
    )


@router.get("/{project_id}/rendered-video/download")
def download_project_rendered_video(project_id: uuid.UUID) -> FileResponse:
    _metadata, path = _current_render_response(project_id)
    return FileResponse(
        path, media_type="video/mp4", filename="dubbed-video.mp4",
        content_disposition_type="attachment",
    )


@router.get("/{project_id}/tts-readiness", response_model=TTSReadiness)
def get_project_tts_readiness(project_id: uuid.UUID) -> TTSReadiness:
    """Return read-only validation results for a Project's persisted TTS inputs."""
    database_engine = create_database_engine()
    try:
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            try:
                return validate_project_tts_readiness(session, project_id)
            except ProjectNotFoundError:
                raise HTTPException(status_code=404, detail="Project not found.") from None
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail="Unable to validate Project TTS readiness.",
        ) from error
    finally:
        database_engine.dispose()


@router.get("/{project_id}/tts-timeline-plan", response_model=TTSTimelinePlan)
def get_project_tts_timeline_plan(project_id: uuid.UUID) -> TTSTimelinePlan:
    """Build a read-only, provenance-validated output timeline plan for TTS audio."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            try:
                return build_project_timeline_plan(session, project_id)
            except ProjectNotFoundError:
                raise HTTPException(status_code=404, detail="Project not found.") from None
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to analyze the Project timeline.") from error
    finally:
        engine.dispose()


@router.post(
    "/{project_id}/tts-optimization-jobs",
    response_model=JobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_project_tts_optimization(project_id: uuid.UUID) -> JobCreated:
    """Queue bounded duration optimization when persisted audio has blocking conflicts."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session, session.begin():
            try:
                return enqueue_tts_optimization(
                    session,
                    project_id,
                    maximum_rate_percent=get_tts_optimization_max_rate_percent(),
                )
            except ProjectNotFoundError:
                raise HTTPException(status_code=404, detail="Project not found.") from None
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from None
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to enqueue TTS optimization.") from error
    finally:
        engine.dispose()


@router.get(
    "/{project_id}/tts-optimization-jobs/{job_id}",
    response_model=TTSOptimizationResult,
)
def get_project_tts_optimization_result(project_id: uuid.UUID, job_id: uuid.UUID) -> TTSOptimizationResult:
    """Return persisted optimization Job state and the current reanalyzed conflicts."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            try:
                return read_tts_optimization_result(session, project_id, job_id)
            except ProjectNotFoundError:
                raise HTTPException(status_code=404, detail="Project not found.") from None
            except LookupError:
                raise HTTPException(status_code=404, detail="TTS optimization Job not found.") from None
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to read TTS optimization results.") from error
    finally:
        engine.dispose()


@router.post(
    "/{project_id}/tts-normalization-jobs",
    response_model=JobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_project_tts_normalization(project_id: uuid.UUID) -> JobCreated:
    """Queue safe normalization of the current audio without regenerating speech."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session, session.begin():
            try:
                return enqueue_tts_normalization(session, project_id)
            except ProjectNotFoundError:
                raise HTTPException(status_code=404, detail="Project not found.") from None
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from None
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to enqueue TTS audio normalization.") from error
    finally:
        engine.dispose()


@router.get(
    "/{project_id}/tts-normalization-jobs/{job_id}",
    response_model=TTSNormalizationResult,
)
def get_project_tts_normalization_result(project_id: uuid.UUID, job_id: uuid.UUID) -> TTSNormalizationResult:
    """Return persisted normalization Job state and measured per-Segment results."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            try:
                return read_tts_normalization_result(session, project_id, job_id)
            except ProjectNotFoundError:
                raise HTTPException(status_code=404, detail="Project not found.") from None
            except LookupError:
                raise HTTPException(status_code=404, detail="TTS normalization Job not found.") from None
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to read TTS normalization results.") from error
    finally:
        engine.dispose()


@router.post(
    "/{project_id}/tts-jobs",
    response_model=JobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_project_tts_job(project_id: uuid.UUID) -> JobCreated:
    """Revalidate readiness and persist an explicit user-requested TTS Job."""
    database_engine = create_database_engine()
    try:
        session_factory = create_session_factory(database_engine)
        with session_factory() as session, session.begin():
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            if project is None:
                raise HTTPException(status_code=404, detail="Project not found.")
            active_job = session.scalar(
                select(Job.id).where(
                    Job.project_id == project_id,
                    Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
                ).limit(1)
            )
            if active_job is not None:
                raise HTTPException(status_code=409, detail="Another Job is already active for this Project.")
            readiness = validate_project_tts_readiness(session, project_id)
            if not readiness.ready:
                raise HTTPException(status_code=409, detail="Project is not ready for Vietnamese voice generation.")
            job = Job(
                project_id=project_id,
                operation_type="tts",
                input_revision=project.current_revision,
                status=JobStatus.QUEUED.value,
                stage="queued",
            )
            session.add(job)
            session.flush()
            result = JobCreated(id=job.id, project_id=job.project_id, status=job.status)
        return result
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to enqueue TTS generation.") from error
    finally:
        database_engine.dispose()


def _artifact_is_current(artifact: Artifact, segment: Segment, job: Job | None = None) -> bool:
    if not segment.translated_text or not segment.translated_text.strip() or not artifact.voice:
        return False
    try:
        configured_voice = get_edge_tts_voice()
        adaptive_rate_percent(
            segment.translated_text, Decimal(segment.end_seconds) - Decimal(segment.start_seconds)
        )
        rate = artifact.rate_percent
    except (ValueError, RuntimeError):
        return False
    if not (
        artifact.provenance_fingerprint == translation_fingerprint(
        segment.translated_text, configured_voice, rate
        )
        and artifact.voice == configured_voice
        and rate in {0, 6, 12, 14, 20, 22, 35}
        and artifact.revision == segment.revision
        and artifact.duration_ms is not None
        and artifact.duration_ms > 0
    ):
        return False
    expected = f"projects/{artifact.project_id}/jobs/{artifact.job_id}/tts/{segment.id}.mp3"
    if artifact.storage_reference != expected:
        return False
    try:
        audio_path = resolve_storage_path(PurePosixPath(expected))
        if not audio_path.is_file():
            return False
        if job is not None and job.operation_type == "tts_normalize":
            metadata = read_normalization_metadata(audio_path)
            return bool(
                job.status == JobStatus.SUCCEEDED.value
                and job.stage == "tts_normalization_complete"
                and metadata is not None
                and metadata.get("final_duration_ms") == artifact.duration_ms
            )
        return True
    except (UploadStorageError, OSError, ValueError):
        return False


@router.get("/{project_id}/tts-audio", response_model=list[TTSArtifactRead])
def list_project_tts_audio(project_id: uuid.UUID) -> list[TTSArtifactRead]:
    """List latest persisted per-Segment audio; current reflects provenance validation."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            if session.get(Project, project_id) is None:
                raise HTTPException(status_code=404, detail="Project not found.")
            rows = session.execute(
                select(Artifact, Segment)
                .join(Segment, Segment.id == Artifact.segment_id)
                .where(
                    Artifact.project_id == project_id,
                    Artifact.media_type == TTS_MEDIA_TYPE,
                    Artifact.is_current.is_(True),
                )
                .order_by(Segment.position, Segment.id)
            ).all()
            output: list[TTSArtifactRead] = []
            for artifact, segment in rows:
                job = session.get(Job, artifact.job_id)
                if artifact.duration_ms is None:
                    continue
                output.append(TTSArtifactRead(
                    id=artifact.id,
                    project_id=artifact.project_id,
                    segment_id=segment.id,
                    duration_ms=artifact.duration_ms,
                    voice=artifact.voice or "",
                    rate_percent=artifact.rate_percent or 0,
                    audio_url=f"/api/projects/{project_id}/segments/{segment.id}/audio",
                    current=_artifact_is_current(artifact, segment, job),
                ))
            return output
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to list generated Segment audio.") from error
    finally:
        engine.dispose()


@router.get("/{project_id}/segments/{segment_id}/audio")
def get_project_segment_audio(project_id: uuid.UUID, segment_id: uuid.UUID) -> FileResponse:
    """Serve only current, provenance-matching audio for a known Project Segment."""
    engine = create_database_engine()
    try:
        sessions = create_session_factory(engine)
        with sessions() as session:
            segment = session.scalar(select(Segment).where(
                Segment.id == segment_id, Segment.project_id == project_id
            ))
            if segment is None:
                raise HTTPException(status_code=404, detail="Segment audio not found.")
            artifact = session.scalar(
                select(Artifact).where(
                    Artifact.project_id == project_id,
                    Artifact.segment_id == segment_id,
                    Artifact.media_type == TTS_MEDIA_TYPE,
                    Artifact.is_current.is_(True),
                ).order_by(desc(Artifact.created_at), desc(Artifact.id)).limit(1)
            )
            artifact_job = session.get(Job, artifact.job_id) if artifact is not None else None
            if artifact is None or not _artifact_is_current(artifact, segment, artifact_job):
                raise HTTPException(status_code=404, detail="Current Segment audio is not available.")
            expected = (
                f"projects/{project_id}/jobs/{artifact.job_id}/tts/{segment_id}.mp3"
            )
            if artifact.storage_reference != expected:
                raise HTTPException(status_code=404, detail="Current Segment audio is not available.")
            try:
                audio_path = resolve_storage_path(PurePosixPath(expected))
            except (UploadStorageError, ValueError, OSError):
                raise HTTPException(status_code=404, detail="Current Segment audio is not available.") from None
            if not audio_path.is_file():
                raise HTTPException(status_code=404, detail="Current Segment audio is not available.")
        return FileResponse(audio_path, media_type="audio/mpeg", filename=f"segment-{segment_id}.mp3")
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to load Segment audio.") from error
    finally:
        engine.dispose()


@router.get("/{project_id}/segments", response_model=list[SegmentRead])
def list_project_segments(project_id: uuid.UUID) -> list[SegmentRead]:
    """Return persisted transcript rows for one existing Project in stable order."""
    database_engine = create_database_engine()
    try:
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            if session.get(Project, project_id) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found.",
                )
            segments = session.scalars(
                select(Segment)
                .where(Segment.project_id == project_id)
                .order_by(Segment.position, Segment.id)
            ).all()
            return [
                SegmentRead(
                    id=row.id,
                    project_id=row.project_id,
                    position=row.position,
                    start_seconds=row.start_seconds,
                    end_seconds=row.end_seconds,
                    source_text=row.source_text,
                    translated_text=row.translated_text,
                )
                for row in segments
            ]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail="Unable to load the project transcript.",
        ) from error
    finally:
        database_engine.dispose()


@router.get("/{project_id}/video")
def get_project_video(project_id: uuid.UUID) -> FileResponse:
    """Stream only the canonical UUID-derived source video for an existing Project."""
    database_engine = create_database_engine()
    try:
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            if project is None:
                raise HTTPException(status_code=404, detail="Project not found.")
            if not project.source_media_reference:
                raise HTTPException(status_code=404, detail="Source video not found.")
        try:
            canonical_relative_path = source_relative_path(project_id)
            if project.source_media_reference != canonical_relative_path.as_posix():
                raise UploadStorageError("Stored source reference is not canonical.")
            source_path = resolve_storage_path(canonical_relative_path)
            if not source_path.is_file():
                raise FileNotFoundError
        except (UploadStorageError, OSError, ValueError):
            raise HTTPException(status_code=404, detail="Source video not found.") from None
        return FileResponse(
            source_path,
            media_type="video/mp4",
            filename="source-video.mp4",
        )
    except SQLAlchemyError as error:
        raise HTTPException(status_code=500, detail="Unable to load the source video.") from error
    finally:
        database_engine.dispose()


@router.patch(
    "/{project_id}/segments/{segment_id}",
    response_model=SegmentRead,
)
def update_project_segment_translation(
    project_id: uuid.UUID,
    segment_id: uuid.UUID,
    payload: SegmentTranslationUpdate,
) -> SegmentRead:
    """Update only one persisted Vietnamese translation in a ready Project."""
    database_engine = create_database_engine()
    try:
        session_factory = create_session_factory(database_engine)
        with session_factory() as session, session.begin():
            project = session.scalar(
                select(Project).where(Project.id == project_id).with_for_update()
            )
            if project is None:
                raise HTTPException(status_code=404, detail="Project not found.")

            latest_job = session.scalar(
                select(Job)
                .where(
                    Job.project_id == project_id,
                    Job.operation_type == "transcribe_translate",
                )
                .order_by(desc(Job.created_at), desc(Job.id))
                .limit(1)
                .with_for_update()
            )
            active_job_id = session.scalar(
                select(Job.id)
                .where(
                    Job.project_id == project_id,
                    Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
                )
                .limit(1)
            )
            if (
                active_job_id is not None
                or latest_job is None
                or latest_job.status != JobStatus.SUCCEEDED.value
                or latest_job.stage != "translation_ready"
                or latest_job.input_revision != project.current_revision
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Translations can only be edited after the current translation Job succeeds.",
                )

            segment = session.scalar(
                select(Segment)
                .where(
                    Segment.id == segment_id,
                    Segment.project_id == project_id,
                )
                .with_for_update()
            )
            if segment is None:
                raise HTTPException(status_code=404, detail="Segment not found.")
            if segment.revision != project.current_revision:
                raise HTTPException(status_code=409, detail="Segment is not in the current Project revision.")

            # Updating this one field leaves the Whisper text, timestamps, identity, and order intact.
            segment.translated_text = payload.translated_text
            session.flush()
            result = SegmentRead(
                id=segment.id,
                project_id=segment.project_id,
                position=segment.position,
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                source_text=segment.source_text,
                translated_text=segment.translated_text,
            )
        return result
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail="Unable to save the Segment translation.",
        ) from error
    finally:
        database_engine.dispose()


@router.post("/{project_id}/jobs", response_model=JobCreated, status_code=status.HTTP_202_ACCEPTED)
def enqueue_project_job(project_id: uuid.UUID) -> JobCreated:
    """Persist an analysis job and return without performing media work."""
    database_engine = create_database_engine()
    try:
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found.",
                )
            active_tts_job = session.scalar(select(Job.id).where(
                Job.project_id == project_id,
                Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
            ).limit(1))
            if active_tts_job is not None:
                raise HTTPException(status_code=409, detail="Another Job is already active for this Project.")
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


@router.get("/{project_id}/jobs", response_model=list[JobDetail])
def list_project_jobs(project_id: uuid.UUID) -> list[JobDetail]:
    """Return persisted Jobs for a Project, newest first, for UI state recovery."""
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
            jobs = session.scalars(
                select(Job)
                .where(Job.project_id == project_id)
                .order_by(desc(Job.created_at), desc(Job.id))
            ).all()
            return [
                JobDetail(
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
                for job in jobs
            ]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to list project Jobs.",
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
