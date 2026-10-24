"""Read-only output timeline planning response schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TimelinePlanningIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["blocking", "warning"]
    message: str
    segment_ids: list[UUID]


class PlannedSegmentTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: UUID
    position: int
    original_start_ms: int
    original_end_ms: int
    tts_audio_duration_ms: int
    output_audio_start_ms: int
    output_audio_end_ms: int
    cumulative_shift_ms: int
    stretch_factor: float | None
    added_duration_ms: int
    unresolved_overlap_ms: int


class TimelineStretchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_order: int
    segment_id: UUID
    source_start_ms: int
    source_end_ms: int
    stretch_factor: float
    expected_output_duration_ms: int
    added_duration_ms: int


class TTSTimelinePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    original_video_duration_ms: int | None
    planned_output_video_duration_ms: int | None
    segment_count: int
    stretch_segment_count: int
    total_added_duration_ms: int
    renderable: bool
    blocking_issue_count: int
    issues: list[TimelinePlanningIssue]
    segments: list[PlannedSegmentTiming]
    stretch_operations: list[TimelineStretchOperation]
