"""Job API response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobCreated(BaseModel):
    """Public identifiers and queue state returned after enqueue."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    status: str
