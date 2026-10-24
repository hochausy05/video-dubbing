"""Tracked, atomic normalization of current Project TTS Artifacts."""

from __future__ import annotations

import logging
import hashlib
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine

from app.core.config import get_edge_tts_voice
from app.models import Artifact, Job, JobStatus, Project, Segment
from app.schemas import JobCreated
from app.schemas.tts_normalization import TTSNormalizationResult, TTSNormalizedSegmentRead
from app.services.audio_normalization import (
    AudioNormalizationError,
    measured_audio_duration_ms,
    normalize_audio_file,
    read_normalization_metadata,
    write_normalization_metadata,
)
from app.services.tts import TTS_MEDIA_TYPE, translation_fingerprint, _safe_tts_dir
from app.services.tts_readiness import ProjectNotFoundError, validate_project_tts_readiness
from app.services.uploads import UploadStorageError, resolve_storage_path


logger = logging.getLogger("autodub.tts_normalization")
_VALID_RATES = {0, 6, 12, 14, 20, 22, 35}
_TIMING_ISSUES = {"stretch_limit_exceeded", "stretch_interval_overlaps_dialogue"}


class TTSNormalizationError(ValueError):
    """Safe normalization failure for existing Job handling."""


@dataclass(frozen=True)
class _InputArtifact:
    segment: Segment
    artifact: Artifact
    source_path: Path
    content_sha256: str


def _load_valid_inputs(session: Session, project_id: UUID, *, ignore_active_job_id: UUID | None = None) -> tuple[Project, list[_InputArtifact]]:
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError
    readiness = validate_project_tts_readiness(
        session, project_id, ignore_active_job_id=ignore_active_job_id
    )
    if not readiness.ready:
        raise TTSNormalizationError("Project translations are not ready for TTS audio normalization.")
    voice = get_edge_tts_voice()
    segments = session.scalars(select(Segment).where(
        Segment.project_id == project_id,
        Segment.revision == project.current_revision,
    ).order_by(Segment.position, Segment.id)).all()
    artifacts = session.scalars(select(Artifact).where(
        Artifact.project_id == project_id,
        Artifact.media_type == TTS_MEDIA_TYPE,
        Artifact.is_current.is_(True),
    ).order_by(Artifact.segment_id, Artifact.id)).all()
    by_segment: dict[UUID, list[Artifact]] = {}
    for artifact in artifacts:
        if artifact.segment_id is not None:
            by_segment.setdefault(artifact.segment_id, []).append(artifact)
    if not segments or set(by_segment) != {segment.id for segment in segments} or any(
        len(items) != 1 for items in by_segment.values()
    ):
        raise TTSNormalizationError("Every current Segment must have exactly one TTS Artifact to normalize.")

    result: list[_InputArtifact] = []
    for segment in segments:
        artifact = by_segment[segment.id][0]
        if (
            artifact.revision != project.current_revision
            or artifact.duration_ms is None or artifact.duration_ms <= 0
            or artifact.voice != voice
            or artifact.rate_percent not in _VALID_RATES
            or artifact.provenance_fingerprint != translation_fingerprint(
                segment.translated_text or "", voice, int(artifact.rate_percent)
            )
        ):
            raise TTSNormalizationError("Current TTS audio is stale or has invalid provenance.")
        origin_job = session.get(Job, artifact.job_id)
        if (
            origin_job is None or origin_job.project_id != project_id
            or origin_job.input_revision != project.current_revision
            or origin_job.operation_type not in {"tts", "tts_optimize", "tts_normalize"}
            or origin_job.status != JobStatus.SUCCEEDED.value
        ):
            raise TTSNormalizationError("Current TTS audio does not belong to a successful current-revision Job.")
        expected = f"projects/{project_id}/jobs/{artifact.job_id}/tts/{segment.id}.mp3"
        if artifact.storage_reference != expected:
            raise TTSNormalizationError("Current TTS audio has an invalid storage association.")
        try:
            source_path = resolve_storage_path(PurePosixPath(expected))
        except (UploadStorageError, OSError, ValueError):
            raise TTSNormalizationError("Current TTS audio is unavailable for normalization.") from None
        if not source_path.is_file():
            raise TTSNormalizationError("Current TTS audio is unavailable for normalization.")
        try:
            if measured_audio_duration_ms(source_path) != artifact.duration_ms:
                raise TTSNormalizationError("Current TTS audio duration does not match its persisted Artifact.")
        except AudioNormalizationError as error:
            raise TTSNormalizationError("Current TTS audio is invalid or unreadable.") from error
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        result.append(_InputArtifact(segment, artifact, source_path, digest))
    return project, result


def enqueue_tts_normalization(session: Session, project_id: UUID) -> JobCreated:
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise ProjectNotFoundError
    active = session.scalar(select(Job.id).where(
        Job.project_id == project_id,
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    ).limit(1))
    if active is not None:
        raise TTSNormalizationError("Another Job is already active for this Project.")
    _load_valid_inputs(session, project_id)
    job = Job(
        project_id=project_id,
        operation_type="tts_normalize",
        input_revision=project.current_revision,
        status=JobStatus.QUEUED.value,
        stage="queued",
    )
    session.add(job)
    session.flush()
    return JobCreated(id=job.id, project_id=project_id, status=job.status)


def normalize_project_tts(
    engine: Engine,
    *,
    project_id: UUID,
    job_id: UUID,
    input_revision: int,
    stage_callback: Callable[[str], None],
    normalizer: Callable[[Path, Path], object] | None = None,
) -> int:
    """Normalize current audio without Edge-TTS, then atomically publish its replacement set."""
    normalizer = normalizer or normalize_audio_file
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None or job.status != JobStatus.RUNNING.value or job.operation_type != "tts_normalize":
            raise TTSNormalizationError("TTS normalization Job is no longer available.")
        project, inputs = _load_valid_inputs(session, project_id, ignore_active_job_id=job_id)
        if project.current_revision != input_revision or job.input_revision != input_revision:
            raise TTSNormalizationError("Project revision changed before audio normalization started.")
        segment_snapshot = [
            (item.segment.id, item.segment.position, item.segment.start_seconds,
             item.segment.end_seconds, item.segment.source_text,
             item.segment.translated_text, item.segment.revision)
            for item in inputs
        ]
        artifact_snapshot = sorted([
            (item.artifact.id, item.artifact.segment_id, item.artifact.revision,
             item.artifact.storage_reference, item.artifact.duration_ms,
             item.artifact.provenance_fingerprint, item.artifact.voice,
             item.artifact.rate_percent, item.artifact.is_current)
            for item in inputs
        ], key=lambda snapshot: str(snapshot[0]))

    temporary_dir = _safe_tts_dir(project_id, job_id, temporary=True)
    final_dir = _safe_tts_dir(project_id, job_id, temporary=False)
    temporary_dir.mkdir(parents=True, exist_ok=False)
    reports: list[tuple[_InputArtifact, Path, dict[str, object]]] = []
    try:
        stage_callback("normalizing_tts")
        for item in inputs:
            output = temporary_dir / f"{item.segment.id}.mp3"
            try:
                result = normalizer(item.source_path, output)
            except AudioNormalizationError as error:
                raise TTSNormalizationError(str(error)) from None
            metadata = result.as_metadata() if hasattr(result, "as_metadata") else {
                "version": "boundary-silence-v1",
                "original_duration_ms": item.artifact.duration_ms,
                "final_duration_ms": item.artifact.duration_ms,
                "removed_silence_ms": 0,
                "trimmed": False,
                "skipped_reason": "No safe trim was reported.",
            }
            metadata.update({
                "voice": item.artifact.voice,
                "rate_percent": item.artifact.rate_percent,
                "translation_fingerprint": item.artifact.provenance_fingerprint,
                "input_artifact_id": str(item.artifact.id),
                "input_storage_reference": item.artifact.storage_reference,
                "original_file": item.artifact.storage_reference,
            })
            # Probe the exact staged output before recording the duration report.
            from app.services.audio_normalization import measured_audio_duration_ms

            final_duration = measured_audio_duration_ms(output)
            if final_duration != int(metadata["final_duration_ms"]):
                metadata["final_duration_ms"] = final_duration
                metadata["removed_silence_ms"] = max(
                    0, int(metadata["original_duration_ms"]) - final_duration
                )
                metadata["trimmed"] = int(metadata["removed_silence_ms"]) > 0
            if final_duration <= 0:
                raise TTSNormalizationError("Normalized TTS audio failed duration validation.")
            write_normalization_metadata(output, metadata)
            reports.append((item, output, metadata))

        stage_callback("validating_tts_normalization")
        if final_dir.exists():
            raise TTSNormalizationError("TTS normalization output already exists for this Job.")
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temporary_dir), str(final_dir))

        with Session(engine) as session, session.begin():
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            segments = session.scalars(select(Segment).where(
                Segment.project_id == project_id,
            ).order_by(Segment.position, Segment.id).with_for_update()).all()
            current_artifacts = session.scalars(select(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.media_type == TTS_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            ).order_by(Artifact.segment_id, Artifact.id).with_for_update()).all()
            current_segment_snapshot = [
                (item.id, item.position, item.start_seconds, item.end_seconds,
                 item.source_text, item.translated_text, item.revision)
                for item in segments
            ]
            current_artifact_snapshot = sorted([
                (item.id, item.segment_id, item.revision, item.storage_reference,
                 item.duration_ms, item.provenance_fingerprint, item.voice,
                 item.rate_percent, item.is_current)
                for item in current_artifacts
            ], key=lambda snapshot: str(snapshot[0]))
            input_digests = {item.artifact.id: item.content_sha256 for item in inputs}
            media_unchanged = all(
                hashlib.sha256(item.source_path.read_bytes()).hexdigest() == input_digests.get(item.artifact.id)
                for item in inputs
            )
            if (
                project is None or job is None or job.status != JobStatus.RUNNING.value
                or project.current_revision != input_revision
                or current_segment_snapshot != segment_snapshot
                or current_artifact_snapshot != artifact_snapshot
                or not media_unchanged
            ):
                raise TTSNormalizationError("Project translations or TTS Artifacts changed; normalized audio was discarded.")
            session.execute(update(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.media_type == TTS_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            ).values(is_current=False))
            for item, output, metadata in reports:
                final_output = final_dir / output.name
                session.add(Artifact(
                    project_id=project_id,
                    job_id=job_id,
                    segment_id=item.segment.id,
                    revision=input_revision,
                    media_type=TTS_MEDIA_TYPE,
                    storage_reference=f"projects/{project_id}/jobs/{job_id}/tts/{item.segment.id}.mp3",
                    duration_ms=int(metadata["final_duration_ms"]),
                    provenance_fingerprint=item.artifact.provenance_fingerprint,
                    voice=item.artifact.voice,
                    rate_percent=item.artifact.rate_percent,
                    is_current=True,
                ))
                # Replace temp-relative metadata with an internal recoverable input Artifact reference.
                metadata["normalized_file"] = final_output.name
                write_normalization_metadata(final_output, metadata)
            job.status = JobStatus.SUCCEEDED.value
            job.stage = "tts_normalization_complete"
            job.safe_error = None
            job.completed_at = session.scalar(select(func.now()))
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        shutil.rmtree(final_dir, ignore_errors=True)
        raise
    logger.info("TTS normalization Job %s published %d verified audio files.", job_id, len(reports))
    return len(reports)


def read_tts_normalization_result(
    session: Session, project_id: UUID, job_id: UUID
) -> TTSNormalizationResult:
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError
    job = session.get(Job, job_id)
    if job is None or job.project_id != project_id or job.operation_type != "tts_normalize":
        raise LookupError
    artifacts = session.scalars(select(Artifact).where(
        Artifact.project_id == project_id,
        Artifact.job_id == job_id,
        Artifact.media_type == TTS_MEDIA_TYPE,
    ).order_by(Artifact.created_at, Artifact.segment_id)).all()
    segments: list[TTSNormalizedSegmentRead] = []
    for artifact in artifacts:
        if artifact.segment_id is None:
            continue
        try:
            path = resolve_storage_path(PurePosixPath(artifact.storage_reference))
        except (UploadStorageError, OSError, ValueError):
            continue
        metadata = read_normalization_metadata(path)
        if metadata is None:
            continue
        segments.append(TTSNormalizedSegmentRead(
            segment_id=artifact.segment_id,
            rate_percent=int(artifact.rate_percent or 0),
            original_duration_ms=int(metadata.get("original_duration_ms", artifact.duration_ms or 0)),
            final_duration_ms=int(metadata.get("final_duration_ms", artifact.duration_ms or 0)),
            removed_silence_ms=int(metadata.get("removed_silence_ms", 0)),
            trimmed=bool(metadata.get("trimmed", False)),
            skipped_reason=metadata.get("skipped_reason") if isinstance(metadata.get("skipped_reason"), str) else None,
        ))
    return TTSNormalizationResult(
        job_id=job_id,
        project_id=project_id,
        status=job.status,
        stage=job.stage,
        error=job.safe_error,
        files_processed=len(segments),
        files_shortened=sum(item.trimmed for item in segments),
        total_recovered_ms=sum(item.removed_silence_ms for item in segments),
        segments=segments,
    )
