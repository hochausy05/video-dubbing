"""Read-only deterministic planning for a future TTS-aware video render."""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path, PurePosixPath
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_edge_tts_voice
from app.models import Artifact, Job, JobStatus, Project, Segment
from app.schemas.readiness import TTSReadiness
from app.schemas.timeline import (
    PlannedSegmentTiming,
    TimelinePlanningIssue,
    TimelineStretchOperation,
    TTSTimelinePlan,
)
from app.services.tts import TTS_MEDIA_TYPE, adaptive_rate_percent, translation_fingerprint
from app.services.tts_readiness import ProjectNotFoundError, validate_project_tts_readiness
from app.services.uploads import UploadStorageError, resolve_storage_path, source_relative_path


MAX_VIDEO_STRETCH_FACTOR = Decimal("1.4")
MAX_STRETCH_ADDITION_RATIO = MAX_VIDEO_STRETCH_FACTOR - Decimal("1")
FFPROBE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class TimelineSegmentInput:
    segment_id: UUID
    position: int
    original_start_ms: int
    original_end_ms: int
    tts_audio_duration_ms: int


def _issue(code: str, message: str, *segment_ids: UUID, severity: str = "blocking") -> TimelinePlanningIssue:
    return TimelinePlanningIssue(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        segment_ids=list(segment_ids),
    )


def _empty_plan(
    project_id: UUID,
    *,
    segment_count: int,
    original_video_duration_ms: int | None,
    issues: list[TimelinePlanningIssue],
) -> TTSTimelinePlan:
    blocking_count = sum(issue.severity == "blocking" for issue in issues)
    return TTSTimelinePlan(
        project_id=project_id,
        original_video_duration_ms=original_video_duration_ms,
        planned_output_video_duration_ms=None,
        segment_count=segment_count,
        stretch_segment_count=0,
        total_added_duration_ms=0,
        renderable=False,
        blocking_issue_count=blocking_count,
        issues=issues,
        segments=[],
        stretch_operations=[],
    )


def _factor_number(interval_ms: int, added_ms: int) -> float:
    """Describe the exact integer-ms ratio rounded to six decimal places."""
    factor = (Decimal(interval_ms + added_ms) / Decimal(interval_ms)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    return float(factor)


def compute_timeline_plan(
    project_id: UUID,
    original_video_duration_ms: int,
    segments: Iterable[TimelineSegmentInput],
    *,
    issues: list[TimelinePlanningIssue] | None = None,
) -> TTSTimelinePlan:
    """Compute output timings; all positions and shifts remain integer milliseconds.

    For each chronologically ordered Segment, available time is the distance from
    its source start to the next source start, or to video end for the last row.
    This includes existing source silence. A needed insertion is made by stretching
    only that Segment's non-overlapping [source start, source end] interval. Added
    time is floor(interval_ms * 0.4), capped at the exact 1.4x maximum. Later
    Segment output positions shift by the actual capped insertion, never the
    unconstrained request. FFprobe durations are rounded to nearest millisecond
    using half-up rounding; all subsequent arithmetic is integer-only.
    """
    segment_rows = list(segments)
    plan_issues = list(issues or [])
    if original_video_duration_ms <= 0:
        plan_issues.append(_issue("video_duration_invalid", "Original video duration must be positive."))
    if not segment_rows:
        plan_issues.append(_issue("transcript_empty", "Project has no current transcript Segments."))
    if any(row.tts_audio_duration_ms <= 0 for row in segment_rows):
        plan_issues.extend(
            _issue("audio_duration_invalid", "Measured TTS duration must be positive.", row.segment_id)
            for row in segment_rows if row.tts_audio_duration_ms <= 0
        )
    if any(
        row.original_start_ms < 0
        or row.original_end_ms <= row.original_start_ms
        or row.original_end_ms > original_video_duration_ms
        for row in segment_rows
    ):
        plan_issues.extend(
            _issue("source_timestamp_invalid", "Source timestamps must be valid and within the original video.", row.segment_id)
            for row in segment_rows
            if row.original_start_ms < 0
            or row.original_end_ms <= row.original_start_ms
            or row.original_end_ms > original_video_duration_ms
        )
    if len({row.segment_id for row in segment_rows}) != len(segment_rows):
        plan_issues.append(_issue("segment_id_duplicate", "Current transcript contains duplicate Segment IDs."))
    if any(issue.severity == "blocking" for issue in plan_issues):
        return _empty_plan(
            project_id,
            segment_count=len(segment_rows),
            original_video_duration_ms=original_video_duration_ms if original_video_duration_ms > 0 else None,
            issues=plan_issues,
        )

    ordered = sorted(
        segment_rows,
        key=lambda row: (row.original_start_ms, row.original_end_ms, row.position, str(row.segment_id)),
    )
    overlap_ids: set[UUID] = set()
    for right_index, right in enumerate(ordered):
        for left in ordered[:right_index]:
            if left.original_end_ms > right.original_start_ms:
                overlap_ids.update((left.segment_id, right.segment_id))
                plan_issues.append(_issue(
                    "source_timestamp_overlap",
                    "Original dialogue intervals overlap; stretch operations in this region require conflict checks.",
                    left.segment_id,
                    right.segment_id,
                    severity="warning",
                ))

    output_rows: list[PlannedSegmentTiming] = []
    operations: list[TimelineStretchOperation] = []
    shift_ms = 0
    for index, row in enumerate(ordered):
        next_start_ms = (
            ordered[index + 1].original_start_ms
            if index + 1 < len(ordered)
            else original_video_duration_ms
        )
        available_ms = max(0, next_start_ms - row.original_start_ms)
        needed_ms = max(0, row.tts_audio_duration_ms - available_ms)
        interval_ms = row.original_end_ms - row.original_start_ms
        added_ms = 0
        factor: float | None = None
        if needed_ms and row.segment_id in overlap_ids:
            plan_issues.append(_issue(
                "stretch_interval_overlaps_dialogue",
                f"This Segment needs {needed_ms} ms more time, but its source interval overlaps another dialogue interval and cannot be stretched safely.",
                row.segment_id,
            ))
        elif needed_ms:
            maximum_add_ms = int(
                (Decimal(interval_ms) * MAX_STRETCH_ADDITION_RATIO).to_integral_value(rounding=ROUND_FLOOR)
            )
            added_ms = min(needed_ms, maximum_add_ms)
            if added_ms > 0:
                factor = _factor_number(interval_ms, added_ms)
                operations.append(TimelineStretchOperation(
                    operation_order=len(operations) + 1,
                    segment_id=row.segment_id,
                    source_start_ms=row.original_start_ms,
                    source_end_ms=row.original_end_ms,
                    stretch_factor=factor,
                    expected_output_duration_ms=interval_ms + added_ms,
                    added_duration_ms=added_ms,
                ))
        unresolved_ms = max(0, needed_ms - added_ms)
        if unresolved_ms and row.segment_id not in overlap_ids:
            plan_issues.append(_issue(
                "stretch_limit_exceeded",
                f"Audio needs {unresolved_ms} ms more than the safe timeline can provide under the 1.4x stretch cap.",
                row.segment_id,
            ))
        output_start_ms = row.original_start_ms + shift_ms
        output_rows.append(PlannedSegmentTiming(
            segment_id=row.segment_id,
            position=row.position,
            original_start_ms=row.original_start_ms,
            original_end_ms=row.original_end_ms,
            tts_audio_duration_ms=row.tts_audio_duration_ms,
            output_audio_start_ms=output_start_ms,
            output_audio_end_ms=output_start_ms + row.tts_audio_duration_ms,
            cumulative_shift_ms=shift_ms,
            stretch_factor=factor,
            added_duration_ms=added_ms,
            unresolved_overlap_ms=unresolved_ms,
        ))
        shift_ms += added_ms

    # Report any remaining audio-to-audio overlap in addition to cap/source issues.
    for index in range(len(output_rows) - 1):
        current = output_rows[index]
        following = output_rows[index + 1]
        overlap_ms = max(0, current.output_audio_end_ms - following.output_audio_start_ms)
        if overlap_ms:
            current.unresolved_overlap_ms = max(current.unresolved_overlap_ms, overlap_ms)
            following.unresolved_overlap_ms = max(following.unresolved_overlap_ms, overlap_ms)

    blocking_count = sum(issue.severity == "blocking" for issue in plan_issues)
    return TTSTimelinePlan(
        project_id=project_id,
        original_video_duration_ms=original_video_duration_ms,
        planned_output_video_duration_ms=original_video_duration_ms + shift_ms,
        segment_count=len(ordered),
        stretch_segment_count=len(operations),
        total_added_duration_ms=shift_ms,
        renderable=blocking_count == 0,
        blocking_issue_count=blocking_count,
        issues=plan_issues,
        segments=output_rows,
        stretch_operations=operations,
    )


def _seconds_to_ms(value: Decimal) -> int | None:
    milliseconds = Decimal(value) * 1000
    if not milliseconds.is_finite() or milliseconds < 0 or milliseconds != milliseconds.to_integral_value():
        return None
    return int(milliseconds)


def _probe_source_video_duration_ms(project: Project) -> int:
    canonical = source_relative_path(project.id)
    if project.source_media_reference != canonical.as_posix():
        raise ValueError("Project source reference is not canonical.")
    path = resolve_storage_path(canonical)
    if not path.is_file():
        raise ValueError("Project source video is unavailable.")
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=codec_type,duration",
        "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=FFPROBE_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("Original video duration could not be measured.") from error
    if result.returncode:
        raise ValueError("Original video duration could not be measured.")
    try:
        probe = json.loads(result.stdout)
        duration_value = probe["format"]["duration"]
        duration = Decimal(str(duration_value))
        if not duration.is_finite() or duration <= 0:
            raise ValueError
        if not any(stream.get("codec_type") == "video" for stream in probe.get("streams", [])):
            raise ValueError
        duration_ms = int((duration * 1000).to_integral_value(rounding=ROUND_HALF_UP))
    except (KeyError, TypeError, ValueError, ArithmeticError, json.JSONDecodeError) as error:
        raise ValueError("Original video duration is invalid.") from error
    if duration_ms <= 0:
        raise ValueError("Original video duration is invalid.")
    return duration_ms


def _readiness_issues(readiness: TTSReadiness) -> list[TimelinePlanningIssue]:
    return [
        _issue(
            issue.code,
            issue.message,
            *((issue.segment_id,) if issue.segment_id else ()),
            severity="blocking" if issue.severity == "error" else "warning",
        )
        for issue in readiness.issues
    ]


def build_project_timeline_plan(
    session: Session,
    project_id: UUID,
    *,
    ignore_active_job_id: UUID | None = None,
    duration_overrides_ms: dict[UUID, int] | None = None,
) -> TTSTimelinePlan:
    """Validate persisted TTS provenance and calculate a plan without DB writes."""
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError

    issues: list[TimelinePlanningIssue] = []
    try:
        video_duration_ms = _probe_source_video_duration_ms(project)
    except (UploadStorageError, OSError, ValueError):
        video_duration_ms = None
        issues.append(_issue("source_video_unavailable", "Original source video is missing or its duration cannot be verified."))

    readiness = validate_project_tts_readiness(
        session, project_id, ignore_active_job_id=ignore_active_job_id
    )
    issues.extend(_readiness_issues(readiness))
    segments = session.scalars(
        select(Segment).where(
            Segment.project_id == project_id,
            Segment.revision == project.current_revision,
        ).order_by(Segment.position, Segment.id)
    ).all()
    if not segments:
        if not any(issue.code == "project_transcript_empty" for issue in issues):
            issues.append(_issue("transcript_empty", "Project has no current transcript Segments."))
        return _empty_plan(
            project_id, segment_count=0, original_video_duration_ms=video_duration_ms, issues=issues
        )

    artifacts = session.scalars(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.media_type == TTS_MEDIA_TYPE,
            Artifact.is_current.is_(True),
        ).order_by(Artifact.created_at, Artifact.id)
    ).all()
    artifacts_by_segment: dict[UUID, list[Artifact]] = {}
    for artifact in artifacts:
        if artifact.segment_id is None:
            issues.append(_issue("artifact_segment_missing", "A current TTS Artifact is not associated with a Segment."))
        else:
            artifacts_by_segment.setdefault(artifact.segment_id, []).append(artifact)

    try:
        configured_voice = get_edge_tts_voice()
    except RuntimeError:
        configured_voice = None
        issues.append(_issue("tts_voice_invalid", "Configured Vietnamese voice cannot be verified."))

    timeline_inputs: list[TimelineSegmentInput] = []
    for segment in segments:
        candidates = artifacts_by_segment.get(segment.id, [])
        if len(candidates) != 1:
            code = "tts_artifact_missing" if not candidates else "tts_artifact_ambiguous"
            issues.append(_issue(code, "Exactly one current TTS Artifact is required for every Segment.", segment.id))
            continue
        artifact = candidates[0]
        if artifact.project_id != segment.project_id or artifact.revision != project.current_revision:
            issues.append(_issue("tts_artifact_association_invalid", "TTS Artifact Project, Segment, or revision association is invalid.", segment.id))
            continue
        if artifact.duration_ms is None or artifact.duration_ms <= 0:
            issues.append(_issue("tts_duration_invalid", "Persisted TTS duration must be positive milliseconds.", segment.id))
            continue
        job = session.get(Job, artifact.job_id)
        if (
            job is None or job.project_id != project_id
            or job.operation_type not in {"tts", "tts_optimize"}
            or job.status != JobStatus.SUCCEEDED.value
            or job.stage not in {"tts_ready", "tts_optimization_complete"}
            or job.input_revision != project.current_revision
        ):
            issues.append(_issue("tts_job_incomplete", "TTS Artifact must belong to a completed current-revision TTS Job.", segment.id))
            continue
        expected_reference = f"projects/{project_id}/jobs/{job.id}/tts/{segment.id}.mp3"
        if artifact.storage_reference != expected_reference:
            issues.append(_issue("tts_artifact_path_invalid", "TTS Artifact storage association is invalid.", segment.id))
            continue
        try:
            if not resolve_storage_path(PurePosixPath(expected_reference)).is_file():
                raise ValueError
        except (UploadStorageError, OSError, ValueError):
            issues.append(_issue("tts_audio_missing", "Generated audio file is unavailable for a Segment.", segment.id))
            continue

        if (
            configured_voice is None or not segment.translated_text
            or artifact.voice != configured_voice
        ):
            issues.append(_issue("tts_artifact_stale", "TTS Artifact does not match the current translation or voice.", segment.id))
            continue
        try:
            start_ms = _seconds_to_ms(segment.start_seconds)
            end_ms = _seconds_to_ms(segment.end_seconds)
            rate = artifact.rate_percent
            adaptive_rate_percent(
                segment.translated_text,
                Decimal(segment.end_seconds) - Decimal(segment.start_seconds),
            )
        except (ValueError, ArithmeticError):
            start_ms = end_ms = None
            rate = -1
        if (
            start_ms is None or end_ms is None or end_ms <= start_ms
            or rate not in {0, 6, 12, 14, 20, 22, 35}
            or artifact.provenance_fingerprint != translation_fingerprint(
                segment.translated_text, configured_voice, rate
            )
        ):
            issues.append(_issue("tts_artifact_stale", "TTS Artifact does not match the current translation, timestamps, voice, and rate.", segment.id))
            continue

        timeline_inputs.append(TimelineSegmentInput(
            segment_id=segment.id,
            position=segment.position,
            original_start_ms=start_ms,
            original_end_ms=end_ms,
            tts_audio_duration_ms=(duration_overrides_ms or {}).get(segment.id, artifact.duration_ms),
        ))

    known_segment_ids = {segment.id for segment in segments}
    for artifact_segment_id in artifacts_by_segment.keys() - known_segment_ids:
        issues.append(_issue(
            "tts_artifact_segment_mismatch",
            "A current TTS Artifact refers to a Segment outside the current Project revision.",
            artifact_segment_id,
        ))

    if any(issue.severity == "blocking" for issue in issues):
        return _empty_plan(
            project_id,
            segment_count=len(segments),
            original_video_duration_ms=video_duration_ms,
            issues=issues,
        )
    assert video_duration_ms is not None
    return compute_timeline_plan(
        project_id, video_duration_ms, timeline_inputs, issues=issues
    )
