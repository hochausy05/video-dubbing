"""Edge-TTS synthesis, adaptive pacing, provenance, and measured media duration."""

from __future__ import annotations

import asyncio
import logging
import shutil
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from uuid import UUID, uuid4

import aiohttp
import edge_tts
from edge_tts.exceptions import NoAudioReceived, SkewAdjustmentError, WebSocketError
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import (
    get_edge_tts_concurrency,
    get_edge_tts_voice,
)
from app.models import Artifact, Job, JobStatus, Project, Segment
from app.services.audio_normalization import (
    AudioNormalizationError,
    measured_audio_duration_ms as measure_decoded_audio_duration_ms,
    normalize_audio_file,
    write_normalization_metadata,
)
from app.services.uploads import resolve_storage_path
from app.services.tts_readiness import validate_project_tts_readiness
from app.services.tts_artifacts import (
    TTS_MEDIA_TYPE, TTSArtifactError, translation_fingerprint, validate_segment_tts_artifact,
)


logger = logging.getLogger("autodub.tts")
MAX_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 0.5
SYNTHESIS_TIMEOUT_SECONDS = 90


class TTSError(ValueError):
    """Safe TTS failure suitable for existing bounded Job failure handling."""


def adaptive_rate_percent(text: str, original_duration_seconds: Decimal | float) -> int:
    """Legacy v3.4.1 whitespace-token WPS policy; Vietnamese syllables are tokens."""
    try:
        duration = Decimal(str(original_duration_seconds))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Original Segment duration must be positive and finite.") from error
    if not duration.is_finite() or duration <= 0:
        raise ValueError("Original Segment duration must be positive and finite.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Vietnamese translation must not be empty.")
    # Keep Vietnamese diacritics and punctuation intact; whitespace splitting is
    # intentionally the same WPS heuristic used by the pre-TTS readiness check.
    wps = Decimal(len(text.strip().split())) / duration
    if wps > Decimal("4.2"):
        return 20
    if wps > Decimal("3.5"):
        return 12
    if wps > Decimal("2.8"):
        return 6
    return 0


OPTIMIZATION_RATE_TIERS = (0, 6, 14, 22, 35)


def next_optimization_rate(current_rate_percent: int, maximum_rate_percent: int) -> int | None:
    """Choose the next bounded legacy-inspired tier above the stored TTS rate."""
    tiers = (*OPTIMIZATION_RATE_TIERS, maximum_rate_percent)
    return next(
        (rate for rate in sorted(set(tiers)) if current_rate_percent < rate <= maximum_rate_percent),
        None,
    )


def measured_audio_duration_ms(path: Path) -> int:
    """Ask FFprobe for real audio duration and reject missing/unusable output."""
    try:
        return measure_decoded_audio_duration_ms(path)
    except AudioNormalizationError as error:
        raise TTSError(str(error)) from None


def _is_transient(error: Exception) -> bool:
    status_code = getattr(error, "status_code", getattr(error, "status", None))
    if isinstance(error, WebSocketError):
        status_code = getattr(error, "status", status_code)
    if isinstance(status_code, int) and 400 <= status_code < 500:
        return False
    return isinstance(
        error,
        (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            TimeoutError,
            OSError,
            WebSocketError,
            SkewAdjustmentError,
            NoAudioReceived,
        ),
    )


async def synthesize_segment(
    text: str,
    destination: Path,
    *,
    voice: str,
    rate_percent: int,
    semaphore: asyncio.Semaphore,
    communicate_factory: Callable[..., Any] | None = None,
    retry_sleep: Callable[[float], Any] = asyncio.sleep,
    segment_id: UUID | None = None,
    artifact_id: UUID | None = None,
    attempt_callback: Callable[[int], None] | None = None,
) -> int:
    """Synthesize one complete Segment with bounded retries and concurrency."""
    if not text.strip():
        raise TTSError("Vietnamese translation must not be empty.")
    communicate_factory = communicate_factory or edge_tts.Communicate
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw_destination = destination.with_name(f"{destination.stem}.original.mp3")
    metadata_path = destination.with_name(f"{destination.stem}.normalization.json")
    async with semaphore:
        for attempt in range(MAX_ATTEMPTS):
            destination.unlink(missing_ok=True)
            raw_destination.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            try:
                communicate = communicate_factory(
                    text, voice, rate=f"+{rate_percent}%", connect_timeout=10,
                    receive_timeout=SYNTHESIS_TIMEOUT_SECONDS,
                )
                if attempt_callback is not None:
                    attempt_callback(attempt + 1)
                await asyncio.wait_for(communicate.save(str(raw_destination)), timeout=SYNTHESIS_TIMEOUT_SECONDS)
                original_duration_ms = measured_audio_duration_ms(raw_destination)
                normalized = normalize_audio_file(raw_destination, destination)
                metadata = normalized.as_metadata()
                metadata.update({
                    "voice": voice,
                    "rate_percent": rate_percent,
                    "translation_fingerprint": translation_fingerprint(text, voice, rate_percent),
                    "original_file": raw_destination.name,
                })
                write_normalization_metadata(destination, metadata)
                if normalized.original_duration_ms != original_duration_ms:
                    raise TTSError("Generated Segment audio measurement changed during normalization.")
                logger.info(
                    "Edge-TTS synthesis succeeded (segment_id=%s, artifact_id=%s, rate_percent=%d, attempt=%d).",
                    segment_id,
                    artifact_id,
                    rate_percent,
                    attempt + 1,
                )
                return measured_audio_duration_ms(destination)
            except Exception as error:
                destination.unlink(missing_ok=True)
                raw_destination.unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)
                status_code = getattr(error, "status_code", getattr(error, "status", None))
                if not isinstance(status_code, int):
                    status_code = None
                logger.warning(
                    "Edge-TTS synthesis attempt failed (segment_id=%s, artifact_id=%s, rate_percent=%d, attempt=%d/%d, exception_class=%s, http_status=%s).",
                    segment_id,
                    artifact_id,
                    rate_percent,
                    attempt + 1,
                    MAX_ATTEMPTS,
                    type(error).__name__,
                    status_code,
                )
                if not _is_transient(error) or attempt + 1 >= MAX_ATTEMPTS:
                    if isinstance(error, TTSError):
                        raise
                    raise TTSError("Vietnamese voice generation failed for a Segment.") from None
                await retry_sleep(BASE_RETRY_DELAY_SECONDS * (2**attempt))
    raise TTSError("Vietnamese voice generation failed for a Segment.")


def _safe_tts_dir(project_id: UUID, job_id: UUID, *, temporary: bool) -> Path:
    relative = PurePosixPath("projects") / str(project_id)
    if temporary:
        relative = relative / "tts-temp" / str(job_id)
    else:
        relative = relative / "jobs" / str(job_id) / "tts"
    return resolve_storage_path(relative)


def _segment_snapshot(segments: list[Segment]) -> list[tuple]:
    return [
        (item.id, item.project_id, item.position, item.start_seconds, item.end_seconds,
         item.source_text, item.translated_text, item.revision)
        for item in segments
    ]


def _artifact_snapshot(artifacts: list[Artifact]) -> dict[UUID, tuple]:
    return {
        item.id: (item.project_id, item.segment_id, item.job_id, item.revision, item.media_type,
                  item.storage_reference, item.duration_ms, item.provenance_fingerprint,
                  item.voice, item.rate_percent, item.is_current)
        for item in artifacts
    }


def _artifacts_by_segment(artifacts: list[Artifact]) -> dict[UUID | None, list[Artifact]]:
    grouped: dict[UUID | None, list[Artifact]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.segment_id, []).append(artifact)
    return grouped


def generate_project_tts(
    engine: Engine,
    *,
    project_id: UUID,
    job_id: UUID,
    input_revision: int,
    stage_callback: Callable[[str], None],
) -> int:
    """Reuse strictly valid audio and atomically publish only required replacements."""
    voice = get_edge_tts_voice()
    with Session(engine) as session:
        project = session.get(Project, project_id)
        job = session.get(Job, job_id)
        if (
            project is None or job is None or job.project_id != project_id
            or job.operation_type != "tts" or job.status != JobStatus.RUNNING.value
            or job.input_revision != input_revision or project.current_revision != input_revision
        ):
            raise TTSError("TTS Job is not valid for the current Project revision.")
        readiness = validate_project_tts_readiness(session, project_id, ignore_active_job_id=job_id)
        if not readiness.ready:
            raise TTSError("Project is no longer ready for Vietnamese voice generation.")
        segments = session.scalars(select(Segment).where(
            Segment.project_id == project_id,
            Segment.revision == input_revision,
        ).order_by(Segment.position, Segment.id)).all()
        snapshots = _segment_snapshot(segments)
        artifacts = session.scalars(select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.media_type == TTS_MEDIA_TYPE,
            Artifact.is_current.is_(True),
        )).all()
        artifact_snapshot = _artifact_snapshot(artifacts)
        grouped = _artifacts_by_segment(artifacts)
        if set(grouped) - {segment.id for segment in segments}:
            raise TTSError("Current TTS audio has an unknown Segment association; regeneration was stopped.")
        required: list[Segment] = []
        reused: dict[UUID, UUID] = {}
        for segment in segments:
            try:
                valid = validate_segment_tts_artifact(
                    session, project, segment, grouped.get(segment.id, []), voice
                )
                reused[segment.id] = valid.artifact.id
            except TTSArtifactError as error:
                required.append(segment)
                logger.info("TTS regeneration required (job_id=%s, segment_id=%s, reason=%s).",
                            job_id, segment.id, error.code)

    concurrency = get_edge_tts_concurrency()
    temporary_dir = _safe_tts_dir(project_id, job_id, temporary=True)
    final_dir = _safe_tts_dir(project_id, job_id, temporary=False)
    generated: list[tuple[UUID, UUID, int, int, str]] = []
    temporary_created = final_created = False
    logger.info("TTS selection (job_id=%s, regenerate=%d, reuse=%d).", job_id, len(required), len(reused))

    async def synthesize_all() -> None:
        semaphore = asyncio.Semaphore(concurrency)

        async def synthesize_one(segment: Segment):
            stage_callback("generating_tts")
            text = segment.translated_text or ""
            rate = adaptive_rate_percent(text, Decimal(segment.end_seconds) - Decimal(segment.start_seconds))
            artifact_id = uuid4()
            duration_ms = await synthesize_segment(
                text, temporary_dir / f"{segment.id}.mp3", voice=voice, rate_percent=rate,
                semaphore=semaphore, segment_id=segment.id, artifact_id=artifact_id,
            )
            return segment.id, artifact_id, duration_ms, rate, translation_fingerprint(text, voice, rate)

        generated.extend(await asyncio.gather(*(synthesize_one(segment) for segment in required)))

    try:
        if required:
            temporary_dir.mkdir(parents=True, exist_ok=False)
            temporary_created = True
            asyncio.run(synthesize_all())
        stage_callback("validating_tts")
        if required:
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            if final_dir.exists():
                raise TTSError("TTS output directory already exists for this Job.")
            temporary_dir.rename(final_dir)
            temporary_created = False
            final_created = True
        with Session(engine) as session, session.begin():
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            current_segments = session.scalars(select(Segment).where(
                Segment.project_id == project_id
            ).order_by(Segment.position, Segment.id).with_for_update()).all()
            current_artifacts = session.scalars(select(Artifact).where(
                Artifact.project_id == project_id, Artifact.media_type == TTS_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            ).with_for_update()).all()
            if (
                project is None or job is None or job.project_id != project_id
                or job.operation_type != "tts" or job.status != JobStatus.RUNNING.value
                or job.input_revision != input_revision or project.current_revision != input_revision
                or _segment_snapshot(current_segments) != snapshots
                or _artifact_snapshot(current_artifacts) != artifact_snapshot
                or get_edge_tts_voice() != voice
            ):
                raise TTSError("Project translations or TTS inputs changed; generated audio was discarded.")
            if not validate_project_tts_readiness(session, project_id, ignore_active_job_id=job_id).ready:
                raise TTSError("Project is no longer ready for TTS publication.")
            # Lock producer rows and revalidate reuse in this fresh transaction.
            producer_jobs = session.scalars(select(Job).where(Job.id.in_(
                [item.job_id for item in current_artifacts if item.id in reused.values()]
            )).with_for_update()).all()
            current_grouped = _artifacts_by_segment(current_artifacts)
            for segment in current_segments:
                if segment.id in reused:
                    try:
                        valid = validate_segment_tts_artifact(
                            session, project, segment, current_grouped.get(segment.id, []), voice
                        )
                        if valid.artifact.id != reused[segment.id]:
                            raise ValueError
                    except ValueError:
                        raise TTSError("Reusable TTS audio changed or became invalid; generated audio was discarded.") from None
            regenerated_ids = {segment.id for segment in required}
            for artifact in current_artifacts:
                if artifact.segment_id in regenerated_ids:
                    artifact.is_current = False
            for segment_id, artifact_id, duration_ms, rate, fingerprint in generated:
                session.add(Artifact(
                    id=artifact_id, project_id=project_id, job_id=job_id, segment_id=segment_id,
                    revision=input_revision, media_type=TTS_MEDIA_TYPE,
                    storage_reference=f"projects/{project_id}/jobs/{job_id}/tts/{segment_id}.mp3",
                    duration_ms=duration_ms, provenance_fingerprint=fingerprint,
                    voice=voice, rate_percent=rate, is_current=True,
                ))
            job.status = JobStatus.SUCCEEDED.value
            job.stage = "tts_ready"
            job.safe_error = None
            job.completed_at = session.scalar(select(func.now()))
            session.flush()
            published = session.scalars(select(Artifact).where(
                Artifact.project_id == project_id, Artifact.media_type == TTS_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            )).all()
            published_grouped = _artifacts_by_segment(published)
            for segment in current_segments:
                try:
                    validate_segment_tts_artifact(
                        session, project, segment, published_grouped.get(segment.id, []), voice
                    )
                except TTSArtifactError:
                    raise TTSError("TTS output could not be validated; no replacement audio was published.") from None
    except Exception:
        if temporary_created:
            shutil.rmtree(temporary_dir, ignore_errors=True)
        if final_created:
            shutil.rmtree(final_dir, ignore_errors=True)
        raise
    logger.info("TTS completed (job_id=%s, generated=%d, reused=%d).", job_id, len(generated), len(reused))
    return len(generated)
