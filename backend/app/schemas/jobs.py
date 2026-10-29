"""Job API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.render import RenderAudioSettings
from app.schemas.timeline import JointTimelinePlan


class JobCreated(BaseModel):
    """Public identifiers and queue state returned after enqueue."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    status: str


class JobDetail(BaseModel):
    """Persisted job lifecycle fields exposed to API clients."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    job_type: str
    status: Literal["queued", "running", "succeeded", "failed", "interrupted"]
    stage: str | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    audio_settings: RenderAudioSettings | None = None


class JointOptimizationJobResult(BaseModel):
    """Persisted result for AV-SYNC-02; never implies renderer support."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    project_id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "interrupted"]
    stage: str | None
    error: str | None
    plan: JointTimelinePlan | None
