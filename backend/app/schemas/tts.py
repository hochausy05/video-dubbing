"""Vietnamese TTS enqueue and persisted audio response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TTSArtifactRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    segment_id: UUID
    duration_ms: int
    voice: str
    rate_percent: int
    audio_url: str
    current: bool
