"""Public metadata for verified rendered MP4 Artifacts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
