"""Read-only TTS readiness response schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReadinessIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["error", "warning"]
    message: str
    segment_id: UUID | None


class TTSReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    ready: bool
    segment_count: int
    blocking_error_count: int
    warning_count: int
    issues: list[ReadinessIssue]
