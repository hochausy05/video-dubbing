"""Job API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
