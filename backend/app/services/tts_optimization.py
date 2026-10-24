"""Bounded Edge-TTS rate optimization using the authoritative TTS-02 planner."""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import (
    get_edge_tts_concurrency,
    get_edge_tts_voice,
    get_tts_optimization_max_attempts,
    get_tts_optimization_max_rate_percent,
)
from app.models import Artifact, Job, JobStatus, Project, Segment
from app.schemas import JobCreated
from app.schemas.tts_optimization import (
    OptimizedSegmentRead,
    RemainingTTSConflict,
    TTSOptimizationResult,
)
from app.services.audio_normalization import read_normalization_metadata, write_normalization_metadata
from app.services.tts import (
    TTS_MEDIA_TYPE,
    TTSError,
    _safe_tts_dir,
    adaptive_rate_percent,
    next_optimization_rate,
    synthesize_segment,
    translation_fingerprint,
)
from app.services.tts_readiness import ProjectNotFoundError, validate_project_tts_readiness
from app.services.tts_timeline import build_project_timeline_plan
from app.services.uploads import UploadStorageError, resolve_storage_path


logger = logging.getLogger("autodub.tts_optimization")
_OPTIMIZABLE_ISSUES = {"stretch_limit_exceeded", "stretch_interval_overlaps_dialogue"}


@dataclass(frozen=True)
class _Candidate:
    path: Path | None
    duration_ms: int
    rate_percent: int


def enqueue_tts_optimization(
    session: Session,
    project_id: UUID,
    *,
    maximum_rate_percent: int,
) -> JobCreated:
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise ProjectNotFoundError
    active_job_id = session.scalar(select(Job.id).where(
        Job.project_id == project_id,
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    ).limit(1))
    if active_job_id is not None:
        raise ValueError("Another Job is already active for this Project.")
    readiness = validate_project_tts_readiness(session, project_id)
    if not readiness.ready:
        raise ValueError("Project is not ready for TTS duration optimization.")
    plan = build_project_timeline_plan(session, project_id)
    if plan.blocking_issue_count == 0:
        raise ValueError("No blocking timeline conflicts need optimization.")
    if any(issue.code not in _OPTIMIZABLE_ISSUES for issue in plan.issues if issue.severity == "blocking"):
        raise ValueError("Timeline inputs are not safe for TTS duration optimization.")
    if not any(issue.segment_ids for issue in plan.issues if issue.severity == "blocking"):
        raise ValueError("Timeline conflicts could not be associated with Segments.")
    blocking_ids = {
        segment_id
        for issue in plan.issues if issue.severity == "blocking"
        for segment_id in issue.segment_ids
    }
    current_rates = session.execute(select(Artifact.segment_id, Artifact.rate_percent).where(
        Artifact.project_id == project_id,
        Artifact.media_type == TTS_MEDIA_TYPE,
        Artifact.is_current.is_(True),
        Artifact.segment_id.in_(blocking_ids),
    )).all()
    if not any(
        next_optimization_rate(int(rate or 0), maximum_rate_percent) is not None
        for _segment_id, rate in current_rates
    ):
        raise ValueError("No faster TTS rate is available under the configured maximum.")
    for artifact in session.scalars(select(Artifact).where(
        Artifact.project_id == project_id,
        Artifact.media_type == TTS_MEDIA_TYPE,
        Artifact.is_current.is_(True),
    )).all():
        try:
            audio_path = resolve_storage_path(PurePosixPath(artifact.storage_reference))
        except (UploadStorageError, OSError, ValueError):
            raise ValueError("Current TTS audio is unavailable for optimization.") from None
        metadata = read_normalization_metadata(audio_path)
        if metadata is None or metadata.get("final_duration_ms") != artifact.duration_ms:
            raise ValueError("Normalize current TTS audio before optimizing its duration.")
    job = Job(
        project_id=project_id,
        operation_type="tts_optimize",
        input_revision=project.current_revision,
        status=JobStatus.QUEUED.value,
        stage="queued",
    )
    session.add(job)
    session.flush()
    return JobCreated(id=job.id, project_id=job.project_id, status=job.status)


def _blocking_ids(plan) -> set[UUID]:
    return {
        segment_id
        for issue in plan.issues
        if issue.severity == "blocking"
        for segment_id in issue.segment_ids
    }


def optimize_project_tts(
    engine: Engine,
    *,
    project_id: UUID,
    job_id: UUID,
    input_revision: int,
    stage_callback: Callable[[str], None],
    synthesizer: Callable[..., int] | None = None,
    max_rate_percent: int | None = None,
    max_attempts: int | None = None,
) -> int:
    """Try progressively faster measured TTS for only current blocking Segments.

    New files remain in a Job-scoped temporary directory until the final rate and
    duration-aware timeline have been selected. Replacements publish as one DB
    transaction; unaffected current Artifacts stay usable and current.
    """
    max_rate_percent = max_rate_percent or get_tts_optimization_max_rate_percent()
    max_attempts = max_attempts or get_tts_optimization_max_attempts()
    synthesizer = synthesizer or synthesize_segment
    with Session(engine) as session:
        project = session.get(Project, project_id)
        job = session.get(Job, job_id)
        if project is None or job is None or job.status != JobStatus.RUNNING.value:
            raise TTSError("TTS optimization Job or Project is no longer available.")
        if job.operation_type != "tts_optimize" or project.current_revision != input_revision:
            raise TTSError("TTS optimization Job is not valid for the current Project revision.")
        readiness = validate_project_tts_readiness(
            session, project_id, ignore_active_job_id=job_id
        )
        if not readiness.ready:
            raise TTSError("Project translations changed or are no longer ready for optimization.")
        segments = session.scalars(select(Segment).where(
            Segment.project_id == project_id,
            Segment.revision == input_revision,
        ).order_by(Segment.position, Segment.id)).all()
        artifacts = session.scalars(select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.media_type == TTS_MEDIA_TYPE,
            Artifact.is_current.is_(True),
        )).all()
        artifacts_by_segment = {item.segment_id: item for item in artifacts if item.segment_id is not None}
        if len(artifacts_by_segment) != len(segments):
            raise TTSError("Every current Segment must have one valid TTS Artifact before optimization.")
        snapshots = [
            (item.id, item.position, item.start_seconds, item.end_seconds, item.source_text,
             item.translated_text, item.revision)
            for item in segments
        ]
        original_artifacts = {
            item.id: (item.segment_id, item.duration_ms, item.rate_percent,
                      item.provenance_fingerprint, item.storage_reference, item.is_current)
            for item in artifacts
        }
        original_plan = build_project_timeline_plan(
            session, project_id, ignore_active_job_id=job_id
        )
        if original_plan.blocking_issue_count == 0:
            job.status = JobStatus.SUCCEEDED.value
            job.stage = "tts_optimization_complete"
            job.safe_error = None
            job.completed_at = session.scalar(select(func.now()))
            session.commit()
            return 0
        for artifact in artifacts:
            audio_path = resolve_storage_path(PurePosixPath(artifact.storage_reference))
            metadata = read_normalization_metadata(audio_path)
            if metadata is None or metadata.get("final_duration_ms") != artifact.duration_ms:
                raise TTSError("Normalize current TTS audio before optimizing its duration.")
        if any(issue.code not in _OPTIMIZABLE_ISSUES for issue in original_plan.issues if issue.severity == "blocking"):
            raise TTSError("Current TTS inputs cannot be safely optimized.")

    voice = get_edge_tts_voice()
    concurrency = get_edge_tts_concurrency()
    segment_by_id = {item.id: item for item in segments}
    temporary_dir = _safe_tts_dir(project_id, job_id, temporary=True)
    final_dir = _safe_tts_dir(project_id, job_id, temporary=False)
    temporary_dir.mkdir(parents=True, exist_ok=False)
    best: dict[UUID, _Candidate] = {}
    attempts: dict[UUID, int] = {}
    last_rate = {segment_id: int(artifact.rate_percent or 0) for segment_id, artifact in artifacts_by_segment.items()}
    current_plan = original_plan
    final_dir_created = False
    try:
        for _round in range(max_attempts):
            with Session(engine) as planning_session:
                current_plan = build_project_timeline_plan(
                    planning_session, project_id,
                    ignore_active_job_id=job_id,
                    duration_overrides_ms={key: value.duration_ms for key, value in best.items()},
                )
            if current_plan.renderable:
                break
            blocking_segment_ids = _blocking_ids(current_plan)
            selected: list[tuple[UUID, int, str]] = []
            for segment_id in sorted(blocking_segment_ids, key=lambda item: (segment_by_id[item].position, str(item))):
                segment = segment_by_id.get(segment_id)
                artifact = artifacts_by_segment.get(segment_id)
                if segment is None or artifact is None or attempts.get(segment_id, 0) >= max_attempts:
                    continue
                previous_rate = last_rate[segment_id]
                rate = next_optimization_rate(previous_rate, max_rate_percent)
                if rate is None:
                    continue
                selected.append((segment_id, rate, segment.translated_text or ""))
            if not selected:
                break

            async def synthesize_round() -> list[tuple[UUID, int, Path, int]]:
                semaphore = asyncio.Semaphore(concurrency)

                async def one(segment_id: UUID, rate: int, text: str):
                    path = temporary_dir / f"{segment_id}-{rate}.mp3"
                    stage_callback("optimizing_tts")
                    duration_ms = await synthesizer(
                        text, path, voice=voice, rate_percent=rate, semaphore=semaphore
                    )
                    return segment_id, rate, path, duration_ms

                return await asyncio.gather(*(one(*item) for item in selected))

            generated = asyncio.run(synthesize_round())
            for segment_id, rate, path, duration_ms in generated:
                attempts[segment_id] = attempts.get(segment_id, 0) + 1
                last_rate[segment_id] = rate
                previous_duration = best.get(segment_id)
                if previous_duration is None:
                    previous_duration = _Candidate(
                        None, int(artifacts_by_segment[segment_id].duration_ms),
                        int(artifacts_by_segment[segment_id].rate_percent or 0),
                    )
                if duration_ms < previous_duration.duration_ms:
                    if previous_duration.path is not None and previous_duration.path.exists():
                        previous_duration.path.unlink(missing_ok=True)
                    best[segment_id] = _Candidate(path, duration_ms, rate)
                else:
                    path.unlink(missing_ok=True)
            stage_callback("reanalyzing_timeline")

        with Session(engine) as planning_session:
            current_plan = build_project_timeline_plan(
                planning_session, project_id,
                ignore_active_job_id=job_id,
                duration_overrides_ms={key: value.duration_ms for key, value in best.items()},
            )
        stage_callback("publishing_tts_optimization")
        if best:
            if final_dir.exists():
                raise TTSError("TTS optimization output directory already exists for this Job.")
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            final_dir.mkdir()
            final_dir_created = True
            for segment_id, candidate in best.items():
                assert candidate.path is not None
                output_path = final_dir / f"{segment_id}.mp3"
                metadata = read_normalization_metadata(candidate.path)
                shutil.move(str(candidate.path), str(output_path))
                original_path = candidate.path.with_name(f"{candidate.path.stem}.original.mp3")
                if original_path.is_file():
                    shutil.move(str(original_path), str(final_dir / f"{segment_id}.original.mp3"))
                if metadata is not None:
                    metadata["original_file"] = f"{segment_id}.original.mp3"
                    write_normalization_metadata(output_path, metadata)

        with Session(engine) as session, session.begin():
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            current_segments = session.scalars(select(Segment).where(
                Segment.project_id == project_id,
            ).order_by(Segment.position, Segment.id).with_for_update()).all()
            current_snapshot = [
                (item.id, item.position, item.start_seconds, item.end_seconds, item.source_text,
                 item.translated_text, item.revision)
                for item in current_segments
            ]
            current_artifacts = session.scalars(select(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.media_type == TTS_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            ).with_for_update()).all()
            current_artifact_snapshot = {
                item.id: (item.segment_id, item.duration_ms, item.rate_percent,
                          item.provenance_fingerprint, item.storage_reference, item.is_current)
                for item in current_artifacts
            }
            if (
                project is None or job is None or job.status != JobStatus.RUNNING.value
                or project.current_revision != input_revision or current_snapshot != snapshots
                or current_artifact_snapshot != original_artifacts
            ):
                raise TTSError("Project transcript or TTS inputs changed; optimized audio was discarded.")
            current_artifacts_by_segment = {
                item.segment_id: item for item in current_artifacts if item.segment_id is not None
            }
            for segment_id, candidate in best.items():
                artifact = current_artifacts_by_segment[segment_id]
                artifact.is_current = False
                segment = segment_by_id[segment_id]
                session.add(Artifact(
                    project_id=project_id,
                    job_id=job_id,
                    segment_id=segment_id,
                    revision=input_revision,
                    media_type=TTS_MEDIA_TYPE,
                    storage_reference=f"projects/{project_id}/jobs/{job_id}/tts/{segment_id}.mp3",
                    duration_ms=candidate.duration_ms,
                    provenance_fingerprint=translation_fingerprint(
                        segment.translated_text or "", voice, candidate.rate_percent
                    ),
                    voice=voice,
                    rate_percent=candidate.rate_percent,
                    is_current=True,
                ))
            job.status = JobStatus.SUCCEEDED.value
            job.stage = "tts_optimization_complete"
            job.safe_error = None
            job.completed_at = session.scalar(select(func.now()))
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        if final_dir_created:
            shutil.rmtree(final_dir, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)
    logger.info(
        "TTS optimization Job %s published %d improved Segment Artifact(s); renderable=%s.",
        job_id, len(best), current_plan.renderable,
    )
    return len(best)


def read_tts_optimization_result(
    session: Session,
    project_id: UUID,
    job_id: UUID,
) -> TTSOptimizationResult:
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError
    job = session.get(Job, job_id)
    if job is None or job.project_id != project_id or job.operation_type != "tts_optimize":
        raise LookupError
    updated = session.scalars(select(Artifact).where(
        Artifact.project_id == project_id,
        Artifact.job_id == job_id,
        Artifact.media_type == TTS_MEDIA_TYPE,
        Artifact.is_current.is_(True),
    ).order_by(Artifact.created_at, Artifact.id)).all()
    if job.status not in {JobStatus.SUCCEEDED.value, JobStatus.FAILED.value, JobStatus.INTERRUPTED.value}:
        return TTSOptimizationResult(
            job_id=job_id, project_id=project_id, status=job.status, stage=job.stage,
            error=job.safe_error, updated_segments=[], resolved_conflict_segment_ids=[],
            remaining_conflicts=[], renderable=False, stale=False, recommendation=None,
        )
    plan = build_project_timeline_plan(session, project_id)
    newer_successful_job = session.scalar(select(Job.id).where(
        Job.project_id == project_id,
        Job.operation_type.in_(["tts", "tts_optimize", "tts_normalize"]),
        Job.id != job_id,
        Job.status == JobStatus.SUCCEEDED.value,
        Job.created_at >= job.completed_at,
    ).limit(1)) if job.completed_at is not None else None
    stale = (
        job.status == JobStatus.SUCCEEDED.value
        and (
            newer_successful_job is not None
            or any(
                issue.severity == "blocking" and issue.code not in _OPTIMIZABLE_ISSUES
                for issue in plan.issues
            )
        )
    )
    if stale:
        return TTSOptimizationResult(
            job_id=job_id,
            project_id=project_id,
            status=job.status,
            stage=job.stage,
            error=job.safe_error,
            updated_segments=[],
            resolved_conflict_segment_ids=[],
            remaining_conflicts=[],
            renderable=False,
            stale=True,
            recommendation="This optimization result is stale because current Project inputs no longer match it. Analyze the current timeline before relying on optimization details.",
        )
    remaining_ids = _blocking_ids(plan)
    updated_segments = [
        OptimizedSegmentRead(
            segment_id=artifact.segment_id,
            rate_percent=int(artifact.rate_percent or 0),
            duration_ms=int(artifact.duration_ms or 0),
            resolved=artifact.segment_id not in remaining_ids,
        )
        for artifact in updated if artifact.segment_id is not None
    ]
    resolved_ids = [item.segment_id for item in updated_segments if item.resolved]
    timings = {row.segment_id: row for row in plan.segments}
    remaining_conflicts = [
        RemainingTTSConflict(
            code=issue.code,
            message=issue.message,
            segment_id=segment_id,
            remaining_excess_ms=timings[segment_id].unresolved_overlap_ms if segment_id in timings else 0,
        )
        for issue in plan.issues if issue.severity == "blocking"
        for segment_id in issue.segment_ids
    ]
    recommendation = None if plan.renderable else (
        "Shorten the affected Vietnamese translations in the existing editor, then regenerate TTS."
    )
    return TTSOptimizationResult(
        job_id=job_id,
        project_id=project_id,
        status=job.status,
        stage=job.stage,
        error=job.safe_error,
        updated_segments=updated_segments,
        resolved_conflict_segment_ids=resolved_ids,
        remaining_conflicts=remaining_conflicts,
        renderable=plan.renderable,
        stale=False,
        recommendation=recommendation,
    )
