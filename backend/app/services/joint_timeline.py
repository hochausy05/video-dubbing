"""Deterministic joint TTS-rate/video-speed planner (not an FFmpeg renderer)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Sequence
from uuid import UUID

from app.schemas.timeline import (
    JointSegmentTiming,
    JointTimelinePlan,
    JointVideoInterval,
    TimelinePlanningIssue,
)

MAX_TTS_RATE = 35
MIN_VIDEO_SPEED = Decimal("0.5")
MAX_VIDEO_SPEED = Decimal("1.0")


@dataclass(frozen=True)
class MeasuredAudioCandidate:
    artifact_id: UUID
    rate_percent: int
    duration_us: int


@dataclass(frozen=True)
class JointInputSegment:
    segment_id: UUID
    position: int
    start_us: int
    end_us: int
    candidates: tuple[MeasuredAudioCandidate, ...]


def seconds_to_us(value: Decimal | str | float) -> int:
    """Convert persisted decimal seconds without rounding a positive tail down."""
    return int((Decimal(str(value)) * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def _speed_choices(window_us: int, audio_us: int, margin_us: int, precision_verified: bool) -> tuple[Decimal, ...]:
    required = audio_us + margin_us
    if required > window_us * 2:
        return ()
    threshold = Decimal(window_us) / Decimal(required) if required else Decimal(1)
    threshold = min(Decimal(1), threshold)
    # Include the exact limiting speed as well as coarser quality choices. The
    # exact boundary is retained only when precision is verified (margin=0).
    speeds = {Decimal(1), Decimal("0.5"), threshold}
    speeds.update(Decimal(step) / 100 for step in range(50, 101))
    return tuple(sorted(
        (speed for speed in speeds if Decimal("0.5") <= speed <= threshold),
        reverse=True,
    ))


def _distortions(rate: int, speed: Decimal) -> tuple[Decimal, Decimal]:
    audio = Decimal(rate) / Decimal(MAX_TTS_RATE)
    video = (Decimal(1) - speed) / Decimal("0.5")
    return audio, video


def _choose_joint_options(
    segments: Sequence[JointInputSegment], windows: Sequence[int], margin_us: int, precision_verified: bool,
) -> tuple[tuple[MeasuredAudioCandidate, Decimal], ...] | None:
    options: list[list[tuple[MeasuredAudioCandidate, Decimal, Decimal, Decimal]]] = []
    for segment, window in zip(segments, windows, strict=True):
        local = []
        for candidate in segment.candidates:
            if not 0 <= candidate.rate_percent <= MAX_TTS_RATE or candidate.duration_us <= 0:
                continue
            for speed in _speed_choices(window, candidate.duration_us, margin_us, precision_verified):
                audio_dist, video_dist = _distortions(candidate.rate_percent, speed)
                local.append((candidate, speed, max(audio_dist, video_dist), audio_dist**2 + video_dist**2))
        if not local:
            if not any(0 <= candidate.rate_percent <= MAX_TTS_RATE and candidate.duration_us > 0
                       for candidate in segment.candidates):
                raise ValueError("Candidate rate and measured duration must satisfy the supported bounds.")
            return None
        options.append(local)

    threshold_values = sorted({row[2] for group in options for row in group})
    for threshold in threshold_values:
        # Dynamic programming minimizes squared distortion, then adjacent video
        # speed changes, with stable rate/Artifact tie-breaking.
        states: dict[int, tuple[Decimal, Decimal, tuple[tuple[MeasuredAudioCandidate, Decimal], ...], tuple]] = {}
        for index, group in enumerate(options):
            next_states = {}
            for option_index, (candidate, speed, worst, squared) in enumerate(group):
                if worst > threshold:
                    continue
                if index == 0:
                    tie = ((candidate.rate_percent, str(candidate.artifact_id)),)
                    next_states[option_index] = (squared, Decimal(0), ((candidate, speed),), tie)
                    continue
                for previous_index, state in states.items():
                    previous_speed = state[2][-1][1]
                    cost = (state[0] + squared,
                            state[1] + ((Decimal(1) - speed) - (Decimal(1) - previous_speed)) ** 2)
                    chosen = state[2] + ((candidate, speed),)
                    tie = state[3] + ((candidate.rate_percent, str(candidate.artifact_id)),)
                    value = (*cost, chosen, tie)
                    old = next_states.get(option_index)
                    if old is None or value[:2] + (value[3],) < old[:2] + (old[3],):
                        next_states[option_index] = value
            states = next_states
        if states:
            return min(states.values(), key=lambda item: (item[0], item[1], item[3]))[2]
    return None


def build_joint_timeline_plan(
    *,
    project_id: UUID,
    project_revision: int,
    video_duration_us: int,
    segments: Sequence[JointInputSegment],
    coverage_precision_verified: bool,
    coverage_margin_us: int,
) -> JointTimelinePlan:
    """Build one continuous source/output mapping using measured audio options.

    Source is partitioned at ordered Segment start times; no source interval can
    be duplicated. Overlapping dialogue is reported as a blocker when a slowdown
    would alter either overlapping dialogue window.
    """
    ordered = tuple(sorted(segments, key=lambda row: (row.position, str(row.segment_id))))
    if not ordered:
        raise ValueError("At least one measured Segment is required for a joint plan.")
    if any(not row.candidates for row in ordered):
        raise ValueError("Every planned Segment requires at least one measured Artifact candidate.")
    issues: list[TimelinePlanningIssue] = []
    if video_duration_us <= 0 or coverage_margin_us < 0:
        raise ValueError("Video duration and coverage margin must be valid.")
    if not coverage_precision_verified and coverage_margin_us == 0:
        issues.append(TimelinePlanningIssue(
            code="coverage_precision_unverified", severity="blocking",
            message="Exact-boundary audio coverage cannot be accepted without verified frame/sample precision.",
            segment_ids=[row.segment_id for row in ordered],
        ))
    starts = [row.start_us for row in ordered]
    if (
        len({row.position for row in ordered}) != len(ordered)
        or any(left.start_us > right.start_us for left, right in zip(ordered, ordered[1:]))
        or any(row.start_us < 0 or row.end_us <= row.start_us or row.end_us > video_duration_us for row in ordered)
    ):
        raise ValueError("Segment timestamps must be valid and inside the source video.")
    windows = [
        (ordered[i + 1].start_us if i + 1 < len(ordered) else video_duration_us) - row.start_us
        for i, row in enumerate(ordered)
    ]
    if any(window <= 0 for window in windows):
        raise ValueError("Ordered Segment starts must define positive timeline windows.")

    selected = _choose_joint_options(ordered, windows, coverage_margin_us, coverage_precision_verified)
    if selected is None:
        issues.append(TimelinePlanningIssue(
            code="joint_duration_deficit", severity="blocking",
            message="No measured TTS rate and video speed combination satisfies coverage within the 0.5× speed limit.",
            segment_ids=[row.segment_id for row in ordered],
        ))
        chosen = tuple((row.candidates[0], Decimal(1)) for row in ordered if row.candidates)
    else:
        chosen = selected

    # When dialogue timestamp intervals overlap, slowdown on either involved
    # partition would stretch frames occupied by both lines. Block explicitly.
    for i, left in enumerate(ordered):
        for j in range(i + 1, len(ordered)):
            right = ordered[j]
            if right.start_us >= left.end_us:
                break
            if chosen[i][1] < 1 or chosen[j][1] < 1:
                issues.append(TimelinePlanningIssue(
                    code="joint_overlap_unsafe", severity="blocking",
                    message="Overlapping source dialogue cannot be slowed safely by this planner.",
                    segment_ids=[left.segment_id, right.segment_id],
                ))
    speeds = [item[1] for item in chosen]
    intervals: list[JointVideoInterval] = []
    mapped_starts: dict[int, int] = {}
    output_cursor = 0
    # Partition the full source video at Segment starts, retaining silent lead-in.
    boundaries = sorted({0, video_duration_us, *starts})
    for start, end in zip(boundaries, boundaries[1:]):
        owner_index = next((i for i, row in enumerate(ordered) if row.start_us <= start < (ordered[i + 1].start_us if i + 1 < len(ordered) else video_duration_us)), None)
        speed = speeds[owner_index] if owner_index is not None and owner_index < len(speeds) else Decimal(1)
        out_start = output_cursor
        output_cursor += int((Decimal(end - start) / speed).to_integral_value(rounding=ROUND_CEILING))
        intervals.append(JointVideoInterval(
            source_start_us=start, source_end_us=end,
            output_start_us=out_start, output_end_us=output_cursor,
            speed=float(speed),
        ))
        if owner_index is not None:
            mapped_starts[owner_index] = out_start

    timings = []
    for index, (row, (candidate, speed)) in enumerate(zip(ordered, chosen, strict=True)):
        window = windows[index]
        window_end = row.start_us + window
        available = int((Decimal(window) / speed).to_integral_value(rounding=ROUND_CEILING))
        slack = available - candidate.duration_us
        if slack < 0 or (slack == 0 and not coverage_precision_verified):
            issues.append(TimelinePlanningIssue(
                code="joint_negative_slack" if slack < 0 else "coverage_precision_unverified",
                severity="blocking",
                message="Selected audio does not have verified nonnegative video coverage.",
                segment_ids=[row.segment_id],
            ))
        out_start = mapped_starts.get(index, 0)
        timings.append(JointSegmentTiming(
            segment_id=row.segment_id, position=row.position, artifact_id=candidate.artifact_id,
            source_start_us=row.start_us, source_end_us=row.end_us,
            source_window_end_us=window_end,
            rate_percent=candidate.rate_percent, measured_audio_duration_us=candidate.duration_us,
            output_audio_start_us=out_start, output_audio_end_us=out_start + candidate.duration_us,
            video_speed=float(speed), signed_slack_us=slack,
        ))
    feasible = not issues and len(timings) == len(ordered)
    return JointTimelinePlan(
        project_id=project_id, project_revision=project_revision,
        source_video_duration_us=video_duration_us, planned_output_duration_us=output_cursor,
        segments=timings, video_intervals=intervals, blocking_issues=issues,
        joint_feasible=feasible, coverage_precision_verified=coverage_precision_verified,
        coverage_margin_us=coverage_margin_us, renderer_supported=False, renderable=False,
    )
