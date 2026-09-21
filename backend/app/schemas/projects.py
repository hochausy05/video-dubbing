"""Project API response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectListItem(BaseModel):
    """The persisted project fields required by the project list UI."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    status: str
    source_media_reference: str | None
    created_at: datetime
