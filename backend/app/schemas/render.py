"""Public metadata for verified rendered MP4 Artifacts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RenderAudioSettings(BaseModel):
    """Validated per-render mixing options persisted with the render Job."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed", "ducking"] = "ducking"
    background_gain: float = Field(default=0.35, ge=0, le=1, strict=True, allow_inf_nan=False)
    ducked_gain: float = Field(default=0.08, ge=0, le=1, strict=True, allow_inf_nan=False)
    tts_gain: float = Field(default=1.0, ge=0, le=1, strict=True, allow_inf_nan=False)
    attack_ms: int = Field(default=80, ge=10, le=500, strict=True)
    release_ms: int = Field(default=250, ge=20, le=2000, strict=True)
    bridge_gap_ms: int = Field(default=350, ge=0, le=2000, strict=True)

    @model_validator(mode="after")
    def duck_level_below_background(self) -> "RenderAudioSettings":
        if self.mode == "ducking" and self.ducked_gain > self.background_gain:
            raise ValueError("Ducked gain must not exceed background gain.")
        return self


class RenderArtifactRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    job_id: UUID
    planned_duration_ms: int
    duration_ms: int
    created_at: datetime
    preview_url: str
    download_url: str
    current: bool
    audio_settings: RenderAudioSettings
