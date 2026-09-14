"""DATA-01 PostgreSQL metadata entities; media bytes remain in server-managed storage."""

from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_REVIEW = "awaiting_review"
    READY = "ready"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class TimestampedModel:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Project(TimestampedModel, Base):
    __tablename__ = "autodub_projects"
    __table_args__ = (
        CheckConstraint("current_revision >= 0", name="ck_autodub_projects_current_revision"),
        CheckConstraint("name <> ''", name="ck_autodub_projects_name_not_empty"),
        CheckConstraint(
            "business_status IN ('draft', 'awaiting_review', 'ready')",
            name="ck_autodub_projects_business_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_media_reference: Mapped[str | None] = mapped_column(String(1024))
    source_language: Mapped[str | None] = mapped_column(String(16))
    target_language: Mapped[str] = mapped_column(String(16), nullable=False, default="vi")
    selected_voice: Mapped[str | None] = mapped_column(String(255))
    business_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ProjectStatus.DRAFT.value
    )
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    jobs: Mapped[list["Job"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Job(TimestampedModel, Base):
    __tablename__ = "autodub_jobs"
    __table_args__ = (
        CheckConstraint("input_revision >= 0", name="ck_autodub_jobs_input_revision"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'interrupted')",
            name="ck_autodub_jobs_status",
        ),
        Index("ix_autodub_jobs_project_status", "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("autodub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    input_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JobStatus.QUEUED.value)
    stage: Mapped[str | None] = mapped_column(String(128))
    safe_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="jobs")
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Segment(TimestampedModel, Base):
    __tablename__ = "autodub_segments"
    __table_args__ = (
        UniqueConstraint("project_id", "position", name="uq_autodub_segments_project_position"),
        CheckConstraint("position >= 0", name="ck_autodub_segments_position"),
        CheckConstraint("end_seconds > start_seconds", name="ck_autodub_segments_time_range"),
        CheckConstraint("source_text <> ''", name="ck_autodub_segments_source_text_not_empty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("autodub_projects.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    start_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    end_seconds: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="segments")


class Artifact(TimestampedModel, Base):
    __tablename__ = "autodub_artifacts"
    __table_args__ = (
        CheckConstraint("revision >= 0", name="ck_autodub_artifacts_revision"),
        CheckConstraint("media_type <> ''", name="ck_autodub_artifacts_media_type_not_empty"),
        CheckConstraint(
            "storage_reference <> ''", name="ck_autodub_artifacts_storage_reference_not_empty"
        ),
        Index("ix_autodub_artifacts_project_revision", "project_id", "revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("autodub_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("autodub_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project: Mapped[Project] = relationship(back_populates="artifacts")
    job: Mapped[Job] = relationship(back_populates="artifacts")
