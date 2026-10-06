"""faster-whisper transcription and transactional Segment persistence."""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Job, JobStatus, Project, Segment
from app.services.uploads import UploadStorageError, resolve_storage_path, source_relative_path


logger = logging.getLogger("autodub.asr")
MODEL_NAME = "small"
_TIMESTAMP_QUANTUM = Decimal("0.001")
_MODEL_LOCK = threading.Lock()
_MODEL_RUNTIME: _ModelRuntime | None = None
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s,;]+")
_URL_RE = re.compile(r"(?i)\b(?:postgres(?:ql)?|https?)://\S+")


class ASRInputError(ValueError):
    """The Project does not have a usable, controlled source video."""


class TranscriptConflictError(RuntimeError):
    """Persisted transcript data cannot be safely replaced by a new ASR run."""


class ASRDataError(ValueError):
    """Whisper returned timestamps or text that cannot be safely persisted."""


@dataclass(frozen=True)
class NormalizedSegment:
    position: int
    start_seconds: Decimal
    end_seconds: Decimal
    source_text: str


@dataclass(frozen=True)
class ASRResult:
    segment_count: int
    language: str | None
    device: str
    compute_type: str
    stage: str


@dataclass(frozen=True)
class _ModelRuntime:
    model: Any
    device: str
    compute_type: str


def normalize_segments(segments: Iterable[Any]) -> tuple[NormalizedSegment, ...]:
    """Trim text and validate Whisper's chronological, millisecond-resolution output."""
    normalized: list[NormalizedSegment] = []
    previous_start: Decimal | None = None

    for raw_segment in segments:
        text = raw_segment.text
        if not isinstance(text, str):
            raise ASRDataError("Whisper returned segment text in an unsupported format.")
        source_text = text.strip()
        if not source_text:
            continue

        try:
            raw_start = Decimal(str(raw_segment.start))
            raw_end = Decimal(str(raw_segment.end))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ASRDataError("Whisper returned an invalid segment timestamp.") from error

        if not raw_start.is_finite() or not raw_end.is_finite():
            raise ASRDataError("Whisper returned a non-finite segment timestamp.")
        if raw_start < 0 or raw_end <= raw_start:
            raise ASRDataError("Whisper returned an invalid segment time range.")
        if previous_start is not None and raw_start < previous_start:
            raise ASRDataError("Whisper returned segments outside chronological order.")

        start_seconds = raw_start.quantize(_TIMESTAMP_QUANTUM, rounding=ROUND_HALF_UP)
        end_seconds = raw_end.quantize(_TIMESTAMP_QUANTUM, rounding=ROUND_HALF_UP)
        if end_seconds <= start_seconds:
            raise ASRDataError("A segment time range is shorter than the database precision.")

        normalized.append(
            NormalizedSegment(
                position=len(normalized),
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                source_text=source_text,
            )
        )
        previous_start = raw_start

    return tuple(normalized)


def resolve_project_video(engine: Engine, project_id: uuid.UUID) -> tuple[Path, str | None, int]:
    """Resolve only the server-generated Project path under the managed storage root."""
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise ASRInputError("The Project was not found.")
        if project.source_media_reference is None:
            raise ASRInputError("The Project has no source video.")

        expected_relative_path = source_relative_path(project.id)
        stored_relative_path = PurePosixPath(project.source_media_reference)
        if stored_relative_path != expected_relative_path:
            raise ASRInputError("The Project source video reference is invalid.")
        try:
            video_path = resolve_storage_path(stored_relative_path)
        except UploadStorageError as error:
            raise ASRInputError("The Project source video reference is invalid.") from error
        if not video_path.is_file():
            raise ASRInputError("The Project source video is missing from server storage.")
        if project.current_revision < 0:
            raise ASRInputError("The Project revision is invalid.")
        return video_path, project.source_language, project.current_revision


def _gpu_failure_reason(error: Exception) -> str:
    message = str(error).splitlines()[0] if str(error).splitlines() else type(error).__name__
    message = _URL_RE.sub("[connection details omitted]", message)
    message = _WINDOWS_PATH_RE.sub("[path omitted]", message)
    return f"{type(error).__name__}: {message[:220]}"


def _create_model(device: str, compute_type: str) -> _ModelRuntime:
    from faster_whisper import WhisperModel

    model = WhisperModel(MODEL_NAME, device=device, compute_type=compute_type)
    return _ModelRuntime(model=model, device=device, compute_type=compute_type)


def _get_model_runtime() -> _ModelRuntime:
    global _MODEL_RUNTIME
    with _MODEL_LOCK:
        if _MODEL_RUNTIME is not None:
            return _MODEL_RUNTIME
        try:
            _MODEL_RUNTIME = _create_model("cuda", "float16")
        except Exception as error:
            reason = _gpu_failure_reason(error)
            logger.warning("CUDA Whisper initialization failed (%s); falling back to CPU int8.", reason)
            _MODEL_RUNTIME = _create_model("cpu", "int8")
        return _MODEL_RUNTIME


def _run_inference(
    runtime: _ModelRuntime, video_path: Path, language: str | None
) -> tuple[list[Any], Any]:
    segments, info = runtime.model.transcribe(
        str(video_path),
        language=language,
        beam_size=5,
        vad_filter=True,
    )
    return list(segments), info


def _transcribe(
    video_path: Path, language: str | None
) -> tuple[tuple[NormalizedSegment, ...], Any, _ModelRuntime]:
    global _MODEL_RUNTIME
    runtime = _get_model_runtime()
    try:
        raw_segments, info = _run_inference(runtime, video_path, language)
    except Exception as error:
        if runtime.device != "cuda":
            raise
        reason = _gpu_failure_reason(error)
        logger.warning("CUDA Whisper inference failed (%s); falling back to CPU int8.", reason)
        with _MODEL_LOCK:
            if _MODEL_RUNTIME is runtime:
                _MODEL_RUNTIME = _create_model("cpu", "int8")
            runtime = _MODEL_RUNTIME
        raw_segments, info = _run_inference(runtime, video_path, language)

    return normalize_segments(raw_segments), info, runtime


def _persist_transcript(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    input_revision: int,
    segments: tuple[NormalizedSegment, ...],
    job_id: uuid.UUID,
    stage: str,
) -> None:
    with Session(engine) as session, session.begin():
        project = session.scalar(
            select(Project).where(Project.id == project_id).with_for_update()
        )
        if project is None:
            raise ASRInputError("The Project was not found.")
        if project.current_revision != input_revision:
            raise TranscriptConflictError(
                "The Project changed while transcription was running; existing transcript was preserved."
            )

        job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None or job.project_id != project_id:
            raise ASRInputError("The Job is not associated with this Project.")
        if job.status != JobStatus.RUNNING.value:
            raise TranscriptConflictError("The Job is no longer running; transcript was not changed.")

        existing_segments = session.scalars(
            select(Segment)
            .where(Segment.project_id == project_id)
            .order_by(Segment.position)
            .with_for_update()
        ).all()
        if any(
            segment.translated_text is not None
            or segment.revision != input_revision
            or segment.warnings is not None
            for segment in existing_segments
        ):
            raise TranscriptConflictError(
                "Existing transcript edits or revision data prevent safe replacement."
            )

        session.execute(delete(Segment).where(Segment.project_id == project_id))
        session.add_all(
            [
                Segment(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    position=segment.position,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    source_text=segment.source_text,
                    translated_text=None,
                    revision=input_revision,
                )
                for segment in segments
            ]
        )
        job.stage = stage


def transcribe_project(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    input_revision: int,
    stage_callback: Callable[[str], None],
) -> ASRResult:
    """Run real faster-whisper inference and atomically replace only safe ASR rows."""
    video_path, language, current_revision = resolve_project_video(engine, project_id)
    if current_revision != input_revision:
        raise TranscriptConflictError("The Job references an outdated Project revision.")

    stage_callback("transcribing")
    segments, info, runtime = _transcribe(video_path, language)
    final_stage = "transcript_ready" if segments else "no_speech"
    _persist_transcript(
        engine,
        project_id=project_id,
        input_revision=input_revision,
        segments=segments,
        job_id=job_id,
        stage=final_stage,
    )
    logger.info(
        "faster-whisper model=%s device=%s compute_type=%s language=%s segments=%d",
        MODEL_NAME,
        runtime.device,
        runtime.compute_type,
        getattr(info, "language", None) or "undetected",
        len(segments),
    )
    return ASRResult(
        segment_count=len(segments),
        language=getattr(info, "language", None),
        device=runtime.device,
        compute_type=runtime.compute_type,
        stage=final_stage,
    )
