"""Deterministic, read-only validation of persisted translation input for future TTS."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import MAX_TRANSLATION_TEXT_CHARACTERS
from app.models import Job, JobStatus, Project, Segment
from app.schemas.readiness import ReadinessIssue, TTSReadiness


# Conservative pre-TTS heuristics; these produce warnings only.
VERY_SHORT_WINDOW_MILLISECONDS = 250
HIGH_ESTIMATED_WORDS_PER_SECOND = Decimal("8.0")


class ProjectNotFoundError(LookupError):
    """The requested Project does not exist."""


def _milliseconds(value: Any) -> int | None:
    """Convert persisted seconds to exact integer milliseconds or reject the value."""
    try:
        seconds = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not seconds.is_finite() or seconds < 0:
        return None
    milliseconds = seconds * 1000
    if milliseconds != milliseconds.to_integral_value():
        return None
    return int(milliseconds)


def _issue(
    code: str,
    severity: str,
    message: str,
    segment_id: UUID | None = None,
) -> ReadinessIssue:
    return ReadinessIssue(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        message=message,
        segment_id=segment_id,
    )


def _evaluate_segments(
    project_id: UUID,
    project_revision: int,
    segments: list[Any],
) -> list[ReadinessIssue]:
    """Evaluate ordered Segment-like rows without modifying the rows or database."""
    issues_with_order: list[tuple[tuple[int, str, int, str], ReadinessIssue]] = []
    id_counts: dict[Any, int] = {}
    for segment in segments:
        segment_id = getattr(segment, "id", None)
        if isinstance(segment_id, UUID):
            id_counts[segment_id] = id_counts.get(segment_id, 0) + 1

    timestamps: list[tuple[int, int, int, str, UUID | None, Any]] = []

    def add(segment: Any | None, issue: ReadinessIssue) -> None:
        if segment is None:
            order = -1
            segment_key = ""
        else:
            raw_position = getattr(segment, "position", -1)
            order = raw_position if isinstance(raw_position, int) else -1
            raw_id = getattr(segment, "id", None)
            segment_key = str(raw_id) if isinstance(raw_id, UUID) else ""
        severity_order = 0 if issue.severity == "error" else 1
        issues_with_order.append(
            ((order, segment_key, severity_order, issue.code), issue)
        )

    for segment in segments:
        raw_id = getattr(segment, "id", None)
        segment_id = raw_id if isinstance(raw_id, UUID) else None
        position = getattr(segment, "position", None)
        if segment_id is None:
            add(segment, _issue("segment_id_invalid", "error", "Segment ID is invalid."))
        elif id_counts.get(segment_id, 0) > 1:
            add(
                segment,
                _issue(
                    "segment_id_duplicate",
                    "error",
                    "Segment ID is duplicated in the Project transcript.",
                    segment_id,
                ),
            )
        if not isinstance(position, int) or position < 0:
            add(
                segment,
                _issue(
                    "segment_position_invalid",
                    "error",
                    "Segment ordering position is invalid.",
                    segment_id,
                ),
            )
        if getattr(segment, "project_id", project_id) != project_id:
            add(
                segment,
                _issue(
                    "segment_project_mismatch",
                    "error",
                    "Segment does not belong to the requested Project.",
                    segment_id,
                ),
            )
        if not isinstance(getattr(segment, "source_text", None), str) or not segment.source_text.strip():
            add(
                segment,
                _issue(
                    "source_text_missing",
                    "error",
                    "Source transcription text is missing or empty.",
                    segment_id,
                ),
            )
        if getattr(segment, "revision", project_revision) != project_revision:
            add(
                segment,
                _issue(
                    "segment_revision_stale",
                    "error",
                    "Segment is not part of the current Project revision.",
                    segment_id,
                ),
            )

        start_ms = _milliseconds(getattr(segment, "start_seconds", None))
        end_ms = _milliseconds(getattr(segment, "end_seconds", None))
        if start_ms is None or end_ms is None:
            add(
                segment,
                _issue(
                    "timestamps_invalid",
                    "error",
                    "Segment timestamps must be non-negative integer milliseconds.",
                    segment_id,
                ),
            )
        elif end_ms <= start_ms:
            add(
                segment,
                _issue(
                    "timestamp_range_invalid",
                    "error",
                    "Segment end time must be later than its start time.",
                    segment_id,
                ),
            )
        else:
            order = position if isinstance(position, int) else -1
            timestamps.append(
                (start_ms, end_ms, order, str(segment_id or ""), segment_id, segment)
            )
            duration_ms = end_ms - start_ms
            if duration_ms < VERY_SHORT_WINDOW_MILLISECONDS:
                add(
                    segment,
                    _issue(
                        "short_speaking_window",
                        "warning",
                        "Original speaking window is under 250 ms; later TTS pacing may need review.",
                        segment_id,
                    ),
                )

        translation = getattr(segment, "translated_text", None)
        translation_valid = isinstance(translation, str) and bool(translation.strip())
        if translation is None:
            add(
                segment,
                _issue(
                    "translation_missing",
                    "error",
                    "Vietnamese translation is missing.",
                    segment_id,
                ),
            )
        elif not isinstance(translation, str):
            add(
                segment,
                _issue(
                    "translation_invalid",
                    "error",
                    "Vietnamese translation must be text.",
                    segment_id,
                ),
            )
        elif not translation.strip():
            add(
                segment,
                _issue(
                    "translation_empty",
                    "error",
                    "Vietnamese translation is empty or contains only whitespace.",
                    segment_id,
                ),
            )
        elif len(translation.strip()) > MAX_TRANSLATION_TEXT_CHARACTERS:
            translation_valid = False
            add(
                segment,
                _issue(
                    "translation_too_long",
                    "error",
                    f"Vietnamese translation exceeds {MAX_TRANSLATION_TEXT_CHARACTERS} characters.",
                    segment_id,
                ),
            )

        if translation_valid and start_ms is not None and end_ms is not None and end_ms > start_ms:
            duration_seconds = Decimal(end_ms - start_ms) / 1000
            estimated_wps = Decimal(len(translation.strip().split())) / duration_seconds
            if estimated_wps > HIGH_ESTIMATED_WORDS_PER_SECOND:
                add(
                    segment,
                    _issue(
                        "high_estimated_wps",
                        "warning",
                        "Estimated translation density exceeds 8 whitespace-delimited tokens per second; this is a pre-TTS heuristic, not measured audio duration.",
                        segment_id,
                    ),
                )

    previous_max_end = -1
    for start_ms, end_ms, _position, _id_text, segment_id, segment in sorted(
        timestamps, key=lambda item: item[:4]
    ):
        if start_ms < previous_max_end:
            # Overlap is informational only; source timing is never rewritten.
            add(
                segment,
                _issue(
                    "original_timestamps_overlap",
                    "warning",
                    "This original timestamp window overlaps an earlier Segment; review timing during later TTS/render work.",
                    segment_id,
                ),
            )
        previous_max_end = max(previous_max_end, end_ms)

    return [issue for _key, issue in sorted(issues_with_order, key=lambda item: item[0])]


def validate_project_tts_readiness(session: Session, project_id: UUID) -> TTSReadiness:
    """Read persisted project/job/segment data and return deterministic TTS readiness."""
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError

    active_job_id = session.scalar(
        select(Job.id)
        .where(
            Job.project_id == project_id,
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
        .limit(1)
    )
    latest_job = session.scalar(
        select(Job)
        .where(Job.project_id == project_id)
        .order_by(desc(Job.created_at), desc(Job.id))
        .limit(1)
    )
    segments = session.scalars(
        select(Segment)
        .where(Segment.project_id == project_id)
        .order_by(Segment.position, Segment.id)
    ).all()

    issues = _evaluate_segments(project_id, project.current_revision, list(segments))
    project_issues: list[ReadinessIssue] = []
    if active_job_id is not None:
        project_issues.append(
            _issue(
                "project_job_active",
                "error",
                "A queued or running Job may still modify this Project.",
            )
        )
    elif (
        latest_job is None
        or latest_job.status != JobStatus.SUCCEEDED.value
        or latest_job.stage != "translation_ready"
        or latest_job.input_revision != project.current_revision
    ):
        project_issues.append(
            _issue(
                "project_translation_not_ready",
                "error",
                "The current Project revision has no succeeded translation Job.",
            )
        )
    if not segments:
        project_issues.append(
            _issue("project_transcript_empty", "error", "Project has no transcript Segments.")
        )

    issues = project_issues + issues
    blocking_error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    return TTSReadiness(
        project_id=project_id,
        ready=blocking_error_count == 0,
        segment_count=len(segments),
        blocking_error_count=blocking_error_count,
        warning_count=warning_count,
        issues=issues,
    )
