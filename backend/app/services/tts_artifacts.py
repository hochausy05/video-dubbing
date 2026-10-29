"""Shared current TTS provenance contract for reuse, playback, and timeline planning."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Callable, Sequence

from sqlalchemy.orm import Session

from app.models import Artifact, Job, JobStatus, Project, Segment
from app.services.audio_normalization import read_normalization_metadata
from app.services.uploads import UploadStorageError, resolve_storage_path


TTS_MEDIA_TYPE = "audio/mpeg"
VALID_TTS_RATES = {0, 6, 12, 14, 20, 22, 25, 35}
_PRODUCER_STAGES = {
    "tts": "tts_ready",
    "tts_optimize": "tts_optimization_complete",
    "tts_normalize": "tts_normalization_complete",
    "av_sync_optimize": "joint_optimization_complete",
}


def translation_fingerprint(text: str, voice: str, rate_percent: int) -> str:
    material = json.dumps(
        {"text": text, "voice": voice, "rate_percent": rate_percent, "format": "mp3"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


class TTSArtifactError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ValidatedTTSArtifact:
    artifact: Artifact
    path: Path
    start_ms: int
    end_ms: int


def validate_segment_tts_artifact(
    session: Session,
    project: Project,
    segment: Segment,
    candidates: Sequence[Artifact],
    configured_voice: str | None,
    *,
    resolve_audio: Callable[[PurePosixPath], Path] = resolve_storage_path,
) -> ValidatedTTSArtifact:
    """Reject missing/ambiguous, stale, or incorrectly associated audio.

    Stored optimized rates are valid inputs; they must not be compared with a
    newly computed adaptive rate. Historical tts/tts_optimize media remains
    compatible; tts_normalize requires its existing normalization sidecar.
    """
    if len(candidates) != 1:
        raise TTSArtifactError(
            "tts_artifact_missing" if not candidates else "tts_artifact_ambiguous",
            "Exactly one current TTS Artifact is required for every Segment.",
        )
    artifact = candidates[0]
    if (
        segment.project_id != project.id or segment.revision != project.current_revision
        or artifact.project_id != project.id or artifact.segment_id != segment.id
        or artifact.revision != project.current_revision
        or artifact.media_type != TTS_MEDIA_TYPE or not artifact.is_current
    ):
        raise TTSArtifactError("tts_artifact_association_invalid", "TTS Artifact Project, Segment, or revision association is invalid.")
    if not isinstance(artifact.duration_ms, int) or artifact.duration_ms <= 0:
        raise TTSArtifactError("tts_duration_invalid", "Persisted TTS duration must be positive milliseconds.")
    job = session.get(Job, artifact.job_id)
    if (
        job is None or job.project_id != project.id
        or job.status != JobStatus.SUCCEEDED.value
        or job.operation_type not in _PRODUCER_STAGES
        or job.stage != _PRODUCER_STAGES.get(job.operation_type)
        or job.input_revision != project.current_revision
    ):
        raise TTSArtifactError("tts_job_incomplete", "TTS Artifact must belong to a completed current-revision TTS Job.")
    expected = f"projects/{project.id}/jobs/{job.id}/tts/{segment.id}.mp3"
    if artifact.storage_reference != expected:
        raise TTSArtifactError("tts_artifact_path_invalid", "TTS Artifact storage association is invalid.")
    try:
        audio_path = resolve_audio(PurePosixPath(expected))
        if not audio_path.is_file() or audio_path.stat().st_size == 0:
            raise ValueError
    except (UploadStorageError, OSError, ValueError):
        raise TTSArtifactError("tts_audio_missing", "Generated audio file is unavailable for a Segment.") from None
    if job.operation_type in {"tts_normalize", "av_sync_optimize"}:
        metadata = read_normalization_metadata(audio_path)
        if metadata is None or metadata.get("final_duration_ms") != artifact.duration_ms:
            raise TTSArtifactError("tts_artifact_normalization_invalid", "Normalized TTS media metadata is unavailable or inconsistent.")
    if configured_voice is None or artifact.voice != configured_voice or not segment.translated_text:
        raise TTSArtifactError("tts_artifact_stale", "TTS Artifact does not match the current translation or voice.")
    try:
        start = Decimal(segment.start_seconds) * 1000
        end = Decimal(segment.end_seconds) * 1000
        if (
            not start.is_finite() or not end.is_finite() or start < 0 or end <= start
            or start != start.to_integral_value() or end != end.to_integral_value()
            or not segment.translated_text.strip() or artifact.rate_percent not in VALID_TTS_RATES
            or artifact.provenance_fingerprint != translation_fingerprint(
                segment.translated_text, configured_voice, artifact.rate_percent
            )
        ):
            raise ValueError
    except (ValueError, TypeError, ArithmeticError):
        raise TTSArtifactError("tts_artifact_stale", "TTS Artifact does not match the current translation, timestamps, voice, and rate.") from None
    return ValidatedTTSArtifact(artifact, audio_path, int(start), int(end))
