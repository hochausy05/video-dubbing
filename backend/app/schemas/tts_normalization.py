"""Safe public result for a tracked TTS normalization Job."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TTSNormalizedSegmentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: UUID
    rate_percent: int
    original_duration_ms: int
    final_duration_ms: int
    removed_silence_ms: int
    trimmed: bool
    skipped_reason: str | None


class TTSNormalizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    project_id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "interrupted"]
    stage: str | None
    error: str | None
    files_processed: int
    files_shortened: int
    total_recovered_ms: int
    segments: list[TTSNormalizedSegmentRead]
