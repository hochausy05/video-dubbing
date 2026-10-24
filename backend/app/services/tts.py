"""Edge-TTS synthesis, adaptive pacing, provenance, and measured media duration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from uuid import UUID

import aiohttp
import edge_tts
from edge_tts.exceptions import SkewAdjustmentError, WebSocketError
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import (
    get_edge_tts_concurrency,
    get_edge_tts_voice,
)
from app.models import Artifact, Job, JobStatus, Project, Segment
from app.services.uploads import resolve_storage_path
from app.services.tts_readiness import validate_project_tts_readiness


logger = logging.getLogger("autodub.tts")
MAX_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 0.5
SYNTHESIS_TIMEOUT_SECONDS = 90
FFPROBE_TIMEOUT_SECONDS = 30
TTS_MEDIA_TYPE = "audio/mpeg"


class TTSError(ValueError):
    """Safe TTS failure suitable for existing bounded Job failure handling."""


def adaptive_rate_percent(text: str, original_duration_seconds: Decimal | float) -> int:
    """Legacy v3.4.1 whitespace-token WPS policy; Vietnamese syllables are tokens."""
    try:
        duration = Decimal(str(original_duration_seconds))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Original Segment duration must be positive and finite.") from error
    if not duration.is_finite() or duration <= 0:
        raise ValueError("Original Segment duration must be positive and finite.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Vietnamese translation must not be empty.")
    # Keep Vietnamese diacritics and punctuation intact; whitespace splitting is
    # intentionally the same WPS heuristic used by the pre-TTS readiness check.
    wps = Decimal(len(text.strip().split())) / duration
    if wps > Decimal("4.2"):
        return 20
    if wps > Decimal("3.5"):
        return 12
    if wps > Decimal("2.8"):
        return 6
    return 0


def translation_fingerprint(text: str, voice: str, rate_percent: int) -> str:
    material = json.dumps(
        {"text": text, "voice": voice, "rate_percent": rate_percent, "format": "mp3"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def measured_audio_duration_ms(path: Path) -> int:
    """Ask FFprobe for real audio duration and reject missing/unusable output."""
    if not path.is_file() or path.stat().st_size == 0:
        raise TTSError("Edge-TTS did not produce usable audio for a Segment.")
    command = [
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "format=duration:stream=duration", "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=FFPROBE_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TTSError("Generated Segment audio could not be measured.") from error
    if result.returncode:
        raise TTSError("Generated Segment audio is invalid or unreadable.")
    try:
        probe = json.loads(result.stdout)
        raw_duration = probe.get("format", {}).get("duration")
        if raw_duration in (None, ""):
            raw_duration = next(stream["duration"] for stream in probe["streams"] if stream.get("duration"))
        duration_seconds = float(raw_duration)
    except (KeyError, TypeError, ValueError, StopIteration, json.JSONDecodeError) as error:
        raise TTSError("Generated Segment audio has no valid duration.") from error
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise TTSError("Generated Segment audio has no valid duration.")
    duration_ms = round(duration_seconds * 1000)
    if duration_ms <= 0:
        raise TTSError("Generated Segment audio duration is below one millisecond.")
    return duration_ms


def _is_transient(error: Exception) -> bool:
    status_code = getattr(error, "status_code", getattr(error, "status", None))
    if isinstance(error, WebSocketError):
        status_code = getattr(error, "status", status_code)
    if isinstance(status_code, int) and 400 <= status_code < 500:
        return False
    return isinstance(
        error,
        (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError, OSError, WebSocketError, SkewAdjustmentError),
    )


async def synthesize_segment(
    text: str,
    destination: Path,
    *,
    voice: str,
    rate_percent: int,
    semaphore: asyncio.Semaphore,
    communicate_factory: Callable[..., Any] | None = None,
    retry_sleep: Callable[[float], Any] = asyncio.sleep,
) -> int:
    """Synthesize one complete Segment with bounded retries and concurrency."""
    if not text.strip():
        raise TTSError("Vietnamese translation must not be empty.")
    communicate_factory = communicate_factory or edge_tts.Communicate
    destination.parent.mkdir(parents=True, exist_ok=True)
    async with semaphore:
        for attempt in range(MAX_ATTEMPTS):
            destination.unlink(missing_ok=True)
            try:
                communicate = communicate_factory(
                    text, voice, rate=f"+{rate_percent}%", connect_timeout=10,
                    receive_timeout=SYNTHESIS_TIMEOUT_SECONDS,
                )
                await asyncio.wait_for(communicate.save(str(destination)), timeout=SYNTHESIS_TIMEOUT_SECONDS)
                return measured_audio_duration_ms(destination)
            except Exception as error:
                destination.unlink(missing_ok=True)
                if not _is_transient(error) or attempt + 1 >= MAX_ATTEMPTS:
                    if isinstance(error, TTSError):
                        raise
                    raise TTSError("Vietnamese voice generation failed for a Segment.") from None
                await retry_sleep(BASE_RETRY_DELAY_SECONDS * (2**attempt))
    raise TTSError("Vietnamese voice generation failed for a Segment.")


def _safe_tts_dir(project_id: UUID, job_id: UUID, *, temporary: bool) -> Path:
    relative = PurePosixPath("projects") / str(project_id)
    if temporary:
        relative = relative / "tts-temp" / str(job_id)
    else:
        relative = relative / "jobs" / str(job_id) / "tts"
    return resolve_storage_path(relative)


def generate_project_tts(
    engine: Engine,
    *,
    project_id: UUID,
    job_id: UUID,
    input_revision: int,
    stage_callback: Callable[[str], None],
) -> int:
    """Generate all required audio, then publish artifacts in one DB transaction."""
    with Session(engine) as session:
        project = session.get(Project, project_id)
        job = session.get(Job, job_id)
        if project is None or job is None or job.status != JobStatus.RUNNING.value:
            raise TTSError("TTS Job or Project is no longer available.")
        readiness = validate_project_tts_readiness(
            session, project_id, ignore_active_job_id=job_id
        )
        if not readiness.ready:
            raise TTSError("Project is no longer ready for Vietnamese voice generation.")
        segments = session.scalars(
            select(Segment).where(
                Segment.project_id == project_id,
                Segment.revision == input_revision,
            ).order_by(Segment.position, Segment.id)
        ).all()
        if not segments or any(not item.translated_text or not item.translated_text.strip() for item in segments):
            raise TTSError("Every current Segment must have a Vietnamese translation.")
        snapshots = [
            (item.id, item.position, item.start_seconds, item.end_seconds, item.translated_text)
            for item in segments
        ]

    voice = get_edge_tts_voice()
    concurrency = get_edge_tts_concurrency()
    temporary_dir = _safe_tts_dir(project_id, job_id, temporary=True)
    final_dir = _safe_tts_dir(project_id, job_id, temporary=False)
    temporary_dir.mkdir(parents=True, exist_ok=False)
    generated: list[tuple[UUID, Path, int, int, str]] = []

    async def synthesize_all() -> None:
        semaphore = asyncio.Semaphore(concurrency)

        async def synthesize_one(index: int, snapshot: tuple[UUID, int, Decimal, Decimal, str]):
            segment_id, _position, start, end, text = snapshot
            stage_callback("generating_tts")
            duration_seconds = Decimal(end) - Decimal(start)
            rate = adaptive_rate_percent(text, duration_seconds)
            fingerprint = translation_fingerprint(text, voice, rate)
            output = temporary_dir / f"{segment_id}.mp3"
            duration_ms = await synthesize_segment(
                text, output, voice=voice, rate_percent=rate, semaphore=semaphore
            )
            logger.info("Generated TTS for Segment %s (%d/%d).", segment_id, index, len(snapshots))
            return segment_id, output, duration_ms, rate, fingerprint

        generated.extend(await asyncio.gather(*(
            synthesize_one(index, snapshot)
            for index, snapshot in enumerate(snapshots, start=1)
        )))

    try:
        asyncio.run(synthesize_all())
        stage_callback("validating_tts")
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        if final_dir.exists():
            raise TTSError("TTS output directory already exists for this Job.")
        shutil.move(str(temporary_dir), str(final_dir))
        relative_final = PurePosixPath("projects") / str(project_id) / "jobs" / str(job_id) / "tts"
        with Session(engine) as session, session.begin():
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            current_segments = session.scalars(
                select(Segment).where(Segment.project_id == project_id)
                .order_by(Segment.position, Segment.id).with_for_update()
            ).all()
            current_snapshot = [
                (item.id, item.position, item.start_seconds, item.end_seconds, item.translated_text)
                for item in current_segments
            ]
            if (
                project is None or job is None or job.status != JobStatus.RUNNING.value
                or project.current_revision != input_revision or current_snapshot != snapshots
            ):
                raise TTSError("Project translations changed while TTS was running; generated audio was discarded.")
            session.execute(
                update(Artifact).where(
                    Artifact.project_id == project_id,
                    Artifact.media_type == TTS_MEDIA_TYPE,
                    Artifact.is_current.is_(True),
                ).values(is_current=False)
            )
            for segment_id, _path, duration_ms, rate, fingerprint in generated:
                storage_reference = (
                    relative_final / f"{segment_id}.mp3"
                ).as_posix()
                session.add(Artifact(
                    project_id=project_id,
                    job_id=job_id,
                    segment_id=segment_id,
                    revision=input_revision,
                    media_type=TTS_MEDIA_TYPE,
                    storage_reference=storage_reference,
                    duration_ms=duration_ms,
                    provenance_fingerprint=fingerprint,
                    voice=voice,
                    rate_percent=rate,
                    is_current=True,
                ))
            job.status = JobStatus.SUCCEEDED.value
            job.stage = "tts_ready"
            job.safe_error = None
            job.completed_at = session.scalar(select(func.now()))
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        shutil.rmtree(final_dir, ignore_errors=True)
        raise
    return len(generated)
