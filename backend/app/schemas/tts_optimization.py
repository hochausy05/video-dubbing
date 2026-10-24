"""Tracked TTS duration optimization response schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OptimizedSegmentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: UUID
    rate_percent: int
    duration_ms: int
    resolved: bool


class RemainingTTSConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    segment_id: UUID
    remaining_excess_ms: int


class TTSOptimizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    project_id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "interrupted"]
    stage: str | None
    error: str | None
    updated_segments: list[OptimizedSegmentRead]
    resolved_conflict_segment_ids: list[UUID]
    remaining_conflicts: list[RemainingTTSConflict]
    renderable: bool
    recommendation: str | None
