"""Stable API response schemas."""

from app.schemas.jobs import JobCreated, JobDetail, JointOptimizationJobResult
from app.schemas.projects import ProjectListItem, SegmentRead, SegmentTranslationUpdate
from app.schemas.readiness import ReadinessIssue, TTSReadiness
from app.schemas.render import RenderArtifactRead
from app.schemas.tts import TTSArtifactRead
from app.schemas.tts_optimization import (
    OptimizedSegmentRead,
    RemainingTTSConflict,
    TTSOptimizationResult,
)
from app.schemas.tts_normalization import TTSNormalizationResult, TTSNormalizedSegmentRead
from app.schemas.timeline import (
    JointSegmentTiming,
    JointTimelinePlan,
    JointVideoInterval,
    PlannedSegmentTiming,
    TimelinePlanningIssue,
    TimelineStretchOperation,
    TTSTimelinePlan,
)

__all__ = [
    "JobCreated",
    "JobDetail",
    "JointOptimizationJobResult",
    "ProjectListItem",
    "SegmentRead",
    "SegmentTranslationUpdate",
    "ReadinessIssue",
    "TTSReadiness",
    "RenderArtifactRead",
    "TTSArtifactRead",
    "OptimizedSegmentRead",
    "RemainingTTSConflict",
    "TTSOptimizationResult",
    "TTSNormalizationResult",
    "TTSNormalizedSegmentRead",
    "PlannedSegmentTiming",
    "TimelinePlanningIssue",
    "TimelineStretchOperation",
    "TTSTimelinePlan",
    "JointSegmentTiming",
    "JointTimelinePlan",
    "JointVideoInterval",
]
