"""Project API response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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


class SegmentRead(BaseModel):
    """Read-only persisted transcript row used by the Project viewer."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    position: int
    start_seconds: Decimal
    end_seconds: Decimal
    source_text: str
    translated_text: str | None
