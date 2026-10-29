"""Queue and persist a measured joint AV plan without activating rendering."""

from __future__ import annotations

import subprocess
import asyncio
import json
import logging
import shutil
import hashlib
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Artifact, Job, JobStatus, Project, Segment
from app.schemas import JobCreated, JointOptimizationJobResult
from app.services.audio_normalization import (
    measured_audio_duration_ms, measured_audio_duration_us,
    read_normalization_metadata, write_normalization_metadata,
)
from app.services.tts import MAX_ATTEMPTS, _safe_tts_dir, synthesize_segment, translation_fingerprint
from app.services.joint_timeline import JointInputSegment, MeasuredAudioCandidate, build_joint_timeline_plan, seconds_to_us
from app.schemas.timeline import TimelinePlanningIssue
from app.services.tts_artifacts import TTS_MEDIA_TYPE, validate_segment_tts_artifact
from app.services.tts_readiness import ProjectNotFoundError, validate_project_tts_readiness
from app.services.uploads import resolve_storage_path, source_relative_path


VIDEO_SAMPLE_RATE_HZ = 48_000
JOINT_TTS_CANDIDATE_RATES = (0, 25, 35)
MAX_SYNTHESIS_CANDIDATES_PER_SEGMENT = 3
MAX_SYNTHESIS_CANDIDATES_PER_JOB = 32
logger = logging.getLogger("autodub.av_sync")


class JointOptimizationError(ValueError):
    pass


def enqueue_joint_optimization(session: Session, project_id: UUID) -> JobCreated:
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise ProjectNotFoundError
    if session.scalar(select(Job.id).where(
        Job.project_id == project_id,
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    ).limit(1)) is not None:
        raise JointOptimizationError("Another Job is already active for this Project.")
    readiness = validate_project_tts_readiness(session, project_id)
    if not readiness.ready:
        raise JointOptimizationError("Project is not ready for joint timeline planning.")
    job = Job(project_id=project_id, operation_type="av_sync_optimize", input_revision=project.current_revision,
              status=JobStatus.QUEUED.value, stage="queued")
    session.add(job)
    session.flush()
    return JobCreated(id=job.id, project_id=project_id, status=job.status)


def _probe_source_timing(path: Path) -> tuple[int, int] | None:
    """Return decoded video-frame coverage and a margin for a maximum 0.5x slowdown."""
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time,pkt_duration_time,duration_time", "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=120, check=False)
        if result.returncode:
            return None
        payload = json.loads(result.stdout)
        frames = payload.get("frames", [])
        frame_pts = [Decimal(str(row["best_effort_timestamp_time"])) for row in frames]
        frame_durations = [Decimal(str(row.get("pkt_duration_time") or row["duration_time"])) for row in frames]
        if not frame_pts or len(frame_pts) != len(frame_durations):
            return None
        first_pts = min(frame_pts)
        normalized_pts = [timestamp - first_pts for timestamp in frame_pts]
        max_frame = max(frame_durations)
        coverage_duration = max(timestamp + duration for timestamp, duration
                                 in zip(normalized_pts, frame_durations, strict=True))
        if (not coverage_duration.is_finite() or coverage_duration <= 0
                or not max_frame.is_finite() or max_frame <= 0):
            return None
        duration_us = int((coverage_duration * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
        frame_us = int((max_frame * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
        sample_us = (1_000_000 + VIDEO_SAMPLE_RATE_HZ - 1) // VIDEO_SAMPLE_RATE_HZ
        # A source frame can occupy twice its normal time at 0.5x. Reserve two
        # such output frames plus one 48 kHz sample for conservative coverage.
        return duration_us, frame_us * 4 + sample_us
    except (OSError, subprocess.TimeoutExpired, KeyError, TypeError, ValueError, ArithmeticError,
            json.JSONDecodeError):
        return None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as media:
        for chunk in iter(lambda: media.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_joint_optimization(
    engine, *, project_id: UUID, job_id: UUID, input_revision: int,
    stage_callback=lambda _stage: None, synthesizer=None,
) -> None:
    """Evaluate bounded measured candidates and atomically publish only a feasible selection."""
    from app.services.tts import synthesize_segment as default_synthesizer

    measure_us = measured_audio_duration_us
    synthesizer = synthesizer or default_synthesizer
    temporary_dir = _safe_tts_dir(project_id, job_id, temporary=True)
    final_dir = _safe_tts_dir(project_id, job_id, temporary=False)
    generated: dict[UUID, tuple[MeasuredAudioCandidate, Path]] = {}
    final_dir_created = False
    try:
        with Session(engine) as session:
            project = session.get(Project, project_id)
            job = session.get(Job, job_id)
            if project is None or job is None or job.project_id != project_id or job.status != JobStatus.RUNNING.value:
                raise JointOptimizationError("Joint optimization Job is no longer active.")
            if job.operation_type != "av_sync_optimize" or project.current_revision != input_revision:
                raise JointOptimizationError("Joint optimization Job revision is stale.")
            segments = session.scalars(select(Segment).where(
                Segment.project_id == project_id, Segment.revision == input_revision,
            ).order_by(Segment.position, Segment.id)).all()
            artifacts = session.scalars(select(Artifact).where(
                Artifact.project_id == project_id, Artifact.media_type == TTS_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            )).all()
            by_segment: dict[UUID, list[Artifact]] = {}
            for item in artifacts:
                if item.segment_id is not None:
                    by_segment.setdefault(item.segment_id, []).append(item)
            if project.source_media_reference is None:
                raise JointOptimizationError("Project source video is unavailable.")
            stage_callback("measuring_joint_inputs")
            source_path = resolve_storage_path(source_relative_path(project_id))
            probe = _probe_source_timing(source_path)
            if probe is None:
                raise JointOptimizationError("Source video frame timing could not be verified safely.")
            video_duration_us, safety_margin_us = probe
            source_video_sha256 = _file_sha256(source_path)
            voice = project.selected_voice
            joint_segments: list[JointInputSegment] = []
            validated_by_id = {}
            for segment in segments:
                validated = validate_segment_tts_artifact(
                    session, project, segment, by_segment.get(segment.id, []), voice,
                )
                validated_by_id[segment.id] = validated
                measured = measure_us(validated.path)
                joint_segments.append(JointInputSegment(
                    segment_id=segment.id, position=segment.position,
                    start_us=seconds_to_us(segment.start_seconds), end_us=seconds_to_us(segment.end_seconds),
                    candidates=(MeasuredAudioCandidate(
                        artifact_id=validated.artifact.id,
                        rate_percent=int(validated.artifact.rate_percent or 0), duration_us=measured,
                    ),),
                ))
            segment_snapshot = tuple(
                (row.id, row.position, row.start_seconds, row.end_seconds, row.source_text,
                 row.translated_text, row.revision) for row in segments
            )
            artifact_snapshot = tuple(sorted((
                str(row.id), row.segment_id, row.revision, row.storage_reference, row.duration_ms,
                row.provenance_fingerprint, row.voice, row.rate_percent, row.is_current,
            ) for row in artifacts))
            baseline = build_joint_timeline_plan(
                project_id=project_id, project_revision=input_revision, video_duration_us=video_duration_us,
                segments=joint_segments, coverage_precision_verified=False, coverage_margin_us=safety_margin_us,
            )
            targets = {row.segment_id for row in baseline.segments if row.video_speed < 1.0}
            targets.update(
                segment_id for issue in baseline.blocking_issues for segment_id in issue.segment_ids
            )
            if safety_margin_us == 0:
                targets.clear()
            operations = []
            for item in joint_segments:
                if item.segment_id not in targets:
                    continue
                current_rate = item.candidates[0].rate_percent
                rates = [rate for rate in JOINT_TTS_CANDIDATE_RATES if rate != current_rate]
                rates.sort(key=lambda rate: (abs(rate - current_rate), -rate))
                for rate in rates[:MAX_SYNTHESIS_CANDIDATES_PER_SEGMENT - 1]:
                    operations.append((item, rate))
            budget_exhausted = len(operations) > MAX_SYNTHESIS_CANDIDATES_PER_JOB
            operations = operations[:MAX_SYNTHESIS_CANDIDATES_PER_JOB]
            temporary_dir.mkdir(parents=True, exist_ok=False) if operations else None
            if operations:
                stage_callback("generating_joint_tts_candidates")
            candidate_sets = {item.segment_id: list(item.candidates) for item in joint_segments}
            total_requests = 0
            for operation_number, (item, rate) in enumerate(operations, start=1):
                segment = next(row for row in segments if row.id == item.segment_id)
                artifact_id = uuid4()
                destination = temporary_dir / f"{segment.id}-{rate}.mp3"
                logger.info(
                    "Joint TTS candidate started (job_id=%s, segment_id=%s, artifact_id=%s, rate_percent=%d, candidate=%d/%d).",
                    job_id, segment.id, artifact_id, rate, operation_number, len(operations),
                )

                def count_attempt(attempt: int) -> None:
                    nonlocal total_requests
                    if not 1 <= attempt <= MAX_ATTEMPTS or total_requests >= MAX_SYNTHESIS_CANDIDATES_PER_JOB * MAX_ATTEMPTS:
                        raise JointOptimizationError("Joint TTS synthesis request budget was exceeded.")
                    total_requests += 1

                duration_ms = asyncio.run(synthesizer(
                    segment.translated_text or "", destination, voice=voice,
                    rate_percent=rate, semaphore=asyncio.Semaphore(1),
                    segment_id=segment.id, artifact_id=artifact_id, attempt_callback=count_attempt,
                ))
                measured = measure_us(destination)
                if duration_ms <= 0 or measured <= 0:
                    raise JointOptimizationError("Generated TTS candidate has no valid measured duration.")
                candidate = MeasuredAudioCandidate(artifact_id, rate, measured)
                candidate_sets[item.segment_id].append(candidate)
                generated[artifact_id] = (candidate, destination)

            optimized_segments = [JointInputSegment(
                segment_id=item.segment_id, position=item.position, start_us=item.start_us, end_us=item.end_us,
                candidates=tuple(candidate_sets[item.segment_id]),
            ) for item in joint_segments]
            plan = build_joint_timeline_plan(
                project_id=project_id, project_revision=input_revision, video_duration_us=video_duration_us,
                segments=optimized_segments, coverage_precision_verified=False,
                coverage_margin_us=safety_margin_us,
            )
            if plan.joint_feasible and safety_margin_us > 0:
                plan = plan.model_copy(update={
                    "source_video_sha256": source_video_sha256,
                    "coverage_precision_verified": True,
                    "renderer_supported": True,
                    "renderable": True,
                })
            if budget_exhausted:
                plan = baseline.model_copy(update={
                    "joint_feasible": False,
                    "blocking_issues": [*baseline.blocking_issues, TimelinePlanningIssue(
                        code="candidate_budget_exhausted", severity="blocking",
                        message="The bounded TTS candidate budget was exhausted before every affected Segment could be evaluated.",
                        segment_ids=sorted(targets, key=str),
                    )],
                })
            stage_callback("joint_plan_validating")
            selected_ids = {row.artifact_id for row in plan.segments}
            selected_generated = {key: value for key, value in generated.items() if key in selected_ids}
            if plan.joint_feasible and selected_generated:
                if final_dir.exists():
                    raise JointOptimizationError("Joint optimization output already exists for this Job.")
                final_dir.parent.mkdir(parents=True, exist_ok=True)
                final_dir.mkdir()
                final_dir_created = True
                for segment_id in {next(row.segment_id for row in plan.segments if row.artifact_id == key) for key in selected_generated}:
                    selected = next((value for key, value in selected_generated.items()
                                     if next(row.segment_id for row in plan.segments if row.artifact_id == key) == segment_id), None)
                    if selected is None:
                        continue
                    candidate, source = selected
                    target = final_dir / f"{segment_id}.mp3"
                    raw = source.with_name(f"{source.stem}.original.mp3")
                    metadata = read_normalization_metadata(source)
                    if metadata is None:
                        raise JointOptimizationError("Generated candidate normalization provenance is unavailable.")
                    shutil.move(str(source), str(target))
                    if raw.is_file():
                        shutil.move(str(raw), str(final_dir / f"{segment_id}.original.mp3"))
                    metadata["original_file"] = f"{segment_id}.original.mp3"
                    write_normalization_metadata(target, metadata)

            session.commit()
            session.expire_all()
            current_project = session.scalar(select(Project).where(Project.id == project_id)
                                             .with_for_update().execution_options(populate_existing=True))
            current_job = session.scalar(select(Job).where(Job.id == job_id)
                                         .with_for_update().execution_options(populate_existing=True))
            current_segments = session.scalars(select(Segment).where(
                Segment.project_id == project_id,
            ).order_by(Segment.position, Segment.id).with_for_update()
              .execution_options(populate_existing=True)).all()
            current_artifacts = session.scalars(select(Artifact).where(
                Artifact.project_id == project_id, Artifact.media_type == TTS_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            ).with_for_update().execution_options(populate_existing=True)).all()
            current_segment_snapshot = tuple(
                (row.id, row.position, row.start_seconds, row.end_seconds, row.source_text,
                 row.translated_text, row.revision) for row in current_segments
            )
            current_artifact_snapshot = tuple(sorted((
                str(row.id), row.segment_id, row.revision, row.storage_reference, row.duration_ms,
                row.provenance_fingerprint, row.voice, row.rate_percent, row.is_current,
            ) for row in current_artifacts))
            if (
                current_project is None or current_project.current_revision != input_revision
                or current_job is None or current_job.status != JobStatus.RUNNING.value
                or current_job.operation_type != "av_sync_optimize"
                or segment_snapshot != current_segment_snapshot
                or artifact_snapshot != current_artifact_snapshot
                or _file_sha256(source_path) != source_video_sha256
            ):
                raise JointOptimizationError("Project transcript or TTS inputs changed; joint plan was discarded.")
            for row in current_segments:
                current_for_segment = [item for item in current_artifacts if item.segment_id == row.id]
                validate_segment_tts_artifact(session, current_project, row, current_for_segment,
                                              current_project.selected_voice)
            current_by_segment = {item.segment_id: item for item in current_artifacts}
            if plan.joint_feasible:
                for timing in plan.segments:
                    if timing.artifact_id not in selected_ids:
                        raise JointOptimizationError("Joint plan contains an unknown selected Artifact.")
                    if timing.artifact_id in generated:
                        candidate, _path = generated[timing.artifact_id]
                        segment = next(row for row in current_segments if row.id == timing.segment_id)
                        old = current_by_segment[segment.id]
                        old.is_current = False
                        session.add(Artifact(
                            id=candidate.artifact_id, project_id=project_id, job_id=job_id,
                            segment_id=segment.id, revision=input_revision, media_type=TTS_MEDIA_TYPE,
                            storage_reference=f"projects/{project_id}/jobs/{job_id}/tts/{segment.id}.mp3",
                            duration_ms=measured_audio_duration_ms(final_dir / f"{segment.id}.mp3"),
                            provenance_fingerprint=translation_fingerprint(
                                segment.translated_text or "", voice, candidate.rate_percent,
                            ), voice=voice, rate_percent=candidate.rate_percent, is_current=True,
                        ))
            current_job = current_job
            current_job.result_json = plan.model_dump(mode="json")
            current_job.status = JobStatus.SUCCEEDED.value
            current_job.stage = "joint_optimization_complete" if plan.joint_feasible else "joint_optimization_blocked"
            current_job.safe_error = None
            current_job.completed_at = session.scalar(select(func.now()))
            session.flush()
            if plan.joint_feasible:
                final_artifacts = session.scalars(select(Artifact).where(
                    Artifact.project_id == project_id, Artifact.media_type == TTS_MEDIA_TYPE,
                    Artifact.is_current.is_(True),
                )).all()
                final_by_segment = {item.segment_id: item for item in final_artifacts if item.segment_id is not None}
                for row in current_segments:
                    validate_segment_tts_artifact(session, current_project, row,
                                                  [final_by_segment.get(row.id)] if row.id in final_by_segment else [], voice)
            session.commit()
    except Exception:
        shutil.rmtree(final_dir, ignore_errors=True) if final_dir_created else None
        raise
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)


def read_joint_optimization_result(session: Session, project_id: UUID, job_id: UUID) -> JointOptimizationJobResult:
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError
    job = session.get(Job, job_id)
    if job is None or job.project_id != project_id or job.operation_type != "av_sync_optimize":
        raise LookupError
    plan = None
    current = job.input_revision == project.current_revision
    if job.result_json is not None and current:
        from app.schemas.timeline import JointTimelinePlan
        plan = JointTimelinePlan.model_validate(job.result_json)
        if plan.project_id != project_id or plan.project_revision != job.input_revision:
            plan = None
            current = False
    return JointOptimizationJobResult(
        job_id=job.id, project_id=project_id, status=job.status, stage=job.stage,
        error=job.safe_error if current else "Stored joint plan is stale for the current Project revision.",
        plan=plan,
    )
