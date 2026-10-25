"""Timeline-driven MP4 rendering with verified, atomic Artifact publication."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_render_original_audio_gain
from app.models import Artifact, Job, JobStatus, Project, Segment
from app.schemas import JobCreated, RenderArtifactRead
from app.schemas.render import RenderAudioSettings
from app.services.audio_mixing import write_ducking_envelope
from app.schemas.timeline import TTSTimelinePlan
from app.services.audio_normalization import measured_audio_duration_ms
from app.services.tts import TTS_MEDIA_TYPE
from app.services.tts_readiness import ProjectNotFoundError
from app.services.tts_timeline import build_project_timeline_plan
from app.services.uploads import UploadStorageError, resolve_storage_path, source_relative_path


logger = logging.getLogger("autodub.render")
RENDER_MEDIA_TYPE = "video/mp4"
RENDER_DURATION_TOLERANCE_MS = 100
FFMPEG_TIMEOUT_SECONDS = 1800
FFPROBE_TIMEOUT_SECONDS = 30
MAX_VIDEO_STRETCH_FACTOR = Decimal("1.4")


class RenderError(ValueError):
    """Safe render-domain failure handled by the existing Job lifecycle."""


@dataclass(frozen=True)
class _SpeechInput:
    segment_id: UUID
    artifact_id: UUID
    path: Path
    output_start_ms: int
    duration_ms: int
    rate_percent: int
    sha256: str


@dataclass(frozen=True)
class _RenderSnapshot:
    project_id: UUID
    revision: int
    source_path: Path
    source_sha256: str
    source_has_audio: bool
    original_audio_start_ms: int
    plan: TTSTimelinePlan
    segments: tuple[tuple[object, ...], ...]
    artifacts: tuple[tuple[object, ...], ...]
    speech_inputs: tuple[_SpeechInput, ...]
    audio_settings: RenderAudioSettings
    fingerprint: str


@dataclass(frozen=True)
class _SourceProbe:
    duration_ms: int
    has_video: bool
    has_audio: bool
    audio_start_ms: int


@dataclass(frozen=True)
class _VideoInterval:
    start_ms: int
    end_ms: int
    factor: Decimal


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as media:
            for chunk in iter(lambda: media.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise RenderError("A required media file is unavailable.") from error
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _legacy_render_fingerprint(snapshot: _RenderSnapshot, original_audio_gain: float) -> str:
    """Reproduce RENDER-01 identity for already-published v1 renders during upgrade."""
    payload = {
        "project_id": str(snapshot.project_id),
        "revision": snapshot.revision,
        "source_sha256": snapshot.source_sha256,
        "source_has_audio": snapshot.source_has_audio,
        "source_audio_start_ms": snapshot.original_audio_start_ms,
        "segments": [
            [str(value) if isinstance(value, UUID) else str(value) for value in row]
            for row in snapshot.segments
        ],
        "artifacts": [[str(value) if isinstance(value, UUID) else value for value in row]
                      for row in snapshot.artifacts],
        "timeline": snapshot.plan.model_dump(mode="json"),
        "settings": {
            "original_audio_gain": original_audio_gain,
            "video_encoder": "libx264",
            "audio_encoder": "aac",
            "duration_tolerance_ms": RENDER_DURATION_TOLERANCE_MS,
            "normalization": "timeline-render-v1",
        },
    }
    return _sha256_json(payload)


def _safe_render_dir(project_id: UUID, job_id: UUID, *, temporary: bool = False) -> Path:
    suffix = "render-temp" if temporary else "render"
    return resolve_storage_path(PurePosixPath("projects") / str(project_id) / "jobs" / str(job_id) / suffix)


def _probe_source(path: Path) -> _SourceProbe:
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,start_time", "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=FFPROBE_TIMEOUT_SECONDS, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RenderError("The source video could not be inspected.") from error
    if result.returncode:
        raise RenderError("The source video could not be inspected.")
    try:
        payload = json.loads(result.stdout)
        duration = Decimal(str(payload["format"]["duration"]))
        if not duration.is_finite() or duration <= 0:
            raise ValueError
        streams = payload.get("streams", [])
        video = [stream for stream in streams if stream.get("codec_type") == "video"]
        audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
        start_ms = 0
        if audio:
            raw_audio_start = audio[0].get("start_time")
            audio_start = Decimal(str(raw_audio_start if raw_audio_start is not None else "0"))
            if not audio_start.is_finite():
                raise ValueError
            start_ms = max(0, int((audio_start * 1000).to_integral_value()))
        duration_ms = int((duration * 1000).to_integral_value(rounding="ROUND_HALF_UP"))
        if duration_ms <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError, ArithmeticError, json.JSONDecodeError) as error:
        raise RenderError("The source video has invalid media metadata.") from error
    return _SourceProbe(duration_ms, bool(video), bool(audio), start_ms)


def _validate_plan(plan: TTSTimelinePlan) -> tuple[_VideoInterval, ...]:
    if (
        not plan.renderable or plan.blocking_issue_count != 0
        or plan.original_video_duration_ms is None or plan.original_video_duration_ms <= 0
        or plan.planned_output_video_duration_ms is None
        or plan.planned_output_video_duration_ms <= 0
    ):
        raise RenderError(f"The current timeline plan has {plan.blocking_issue_count} blocking issue(s).")
    if plan.planned_output_video_duration_ms != plan.original_video_duration_ms + plan.total_added_duration_ms:
        raise RenderError("The timeline plan duration is inconsistent.")

    ordered = sorted(plan.stretch_operations, key=lambda operation: operation.operation_order)
    if len(ordered) != plan.stretch_segment_count:
        raise RenderError("The timeline plan stretch operation count is inconsistent.")
    intervals: list[_VideoInterval] = []
    cursor = 0
    for expected_order, operation in enumerate(ordered, start=1):
        start, end = operation.source_start_ms, operation.source_end_ms
        factor = Decimal(str(operation.stretch_factor))
        if (
            operation.operation_order != expected_order
            or start < cursor or end <= start or end > plan.original_video_duration_ms
            or not factor.is_finite() or factor < 1 or factor > MAX_VIDEO_STRETCH_FACTOR
        ):
            raise RenderError("The timeline plan contains an invalid or overlapping stretch operation.")
        interval_ms = end - start
        if operation.expected_output_duration_ms != interval_ms + operation.added_duration_ms:
            raise RenderError("The timeline plan contains an inconsistent stretch duration.")
        if abs((Decimal(interval_ms) * factor) - Decimal(operation.expected_output_duration_ms)) > 2:
            raise RenderError("The timeline plan stretch factor does not match its duration.")
        if start > cursor:
            intervals.append(_VideoInterval(cursor, start, Decimal(1)))
        intervals.append(_VideoInterval(start, end, factor))
        cursor = end
    if cursor < plan.original_video_duration_ms:
        intervals.append(_VideoInterval(cursor, plan.original_video_duration_ms, Decimal(1)))
    if not intervals or intervals[0].start_ms != 0 or intervals[-1].end_ms != plan.original_video_duration_ms:
        raise RenderError("The timeline operations do not cover the complete source video.")
    if any(left.end_ms != right.start_ms for left, right in zip(intervals, intervals[1:])):
        raise RenderError("The timeline operations contain a gap or duplicate source interval.")

    speech = sorted(plan.segments, key=lambda row: row.output_audio_start_ms)
    for index, row in enumerate(speech):
        if (
            row.output_audio_start_ms < 0
            or row.output_audio_end_ms != row.output_audio_start_ms + row.tts_audio_duration_ms
            or row.output_audio_end_ms > plan.planned_output_video_duration_ms
            or row.unresolved_overlap_ms > 0
        ):
            raise RenderError("The timeline contains an invalid or overlapping dubbing interval.")
        if index and speech[index - 1].output_audio_end_ms > row.output_audio_start_ms:
            raise RenderError("The timeline contains overlapping Vietnamese speech.")
    if len(speech) != plan.segment_count:
        raise RenderError("The timeline plan does not include every TTS Segment.")
    return tuple(intervals)


def _load_render_snapshot(
    session: Session,
    project_id: UUID,
    *,
    ignore_active_job_id: UUID | None = None,
    audio_settings_override: RenderAudioSettings | None = None,
) -> _RenderSnapshot:
    project = session.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError
    try:
        source_relative = source_relative_path(project_id)
        if project.source_media_reference != source_relative.as_posix():
            raise RenderError("The Project has no valid original video.")
        source_path = resolve_storage_path(source_relative)
        if not source_path.is_file():
            raise RenderError("The Project original video is unavailable.")
        plan = build_project_timeline_plan(
            session, project_id, ignore_active_job_id=ignore_active_job_id
        )
    except (UploadStorageError, OSError, ValueError) as error:
        if isinstance(error, RenderError):
            raise
        raise RenderError("The Project media or timeline could not be validated.") from error
    intervals = _validate_plan(plan)
    probe = _probe_source(source_path)
    if not probe.has_video:
        raise RenderError("The original video has no decodable video stream.")
    if abs(probe.duration_ms - int(plan.original_video_duration_ms or 0)) > RENDER_DURATION_TOLERANCE_MS:
        raise RenderError("The source video duration changed after timeline analysis.")

    segments = session.scalars(select(Segment).where(
        Segment.project_id == project_id,
        Segment.revision == project.current_revision,
    ).order_by(Segment.position, Segment.id)).all()
    segment_snapshot = tuple((
        segment.id, segment.position, segment.start_seconds, segment.end_seconds,
        segment.source_text, _sha256_json(segment.translated_text or ""), segment.revision,
    ) for segment in segments)
    current_artifacts = session.scalars(select(Artifact).where(
        Artifact.project_id == project_id,
        Artifact.media_type == TTS_MEDIA_TYPE,
        Artifact.is_current.is_(True),
    )).all()
    artifact_by_segment: dict[UUID, Artifact] = {}
    for artifact in current_artifacts:
        if artifact.segment_id is None or artifact.segment_id in artifact_by_segment:
            raise RenderError("The Project does not have exactly one current audio Artifact per Segment.")
        artifact_by_segment[artifact.segment_id] = artifact
    if set(artifact_by_segment) != {segment.id for segment in segments}:
        raise RenderError("The Project does not have a complete current TTS Artifact set.")

    plan_segment_by_id = {row.segment_id: row for row in plan.segments}
    speech_inputs: list[_SpeechInput] = []
    artifact_snapshot_rows: list[tuple[object, ...]] = []
    for segment in segments:
        artifact = artifact_by_segment[segment.id]
        job = session.get(Job, artifact.job_id)
        expected_reference = f"projects/{project_id}/jobs/{artifact.job_id}/tts/{segment.id}.mp3"
        if (
            artifact.storage_reference != expected_reference or artifact.revision != project.current_revision
            or artifact.duration_ms is None or artifact.duration_ms <= 0
            or artifact.rate_percent is None or job is None
            or job.status != JobStatus.SUCCEEDED.value
        ):
            raise RenderError("A current TTS Artifact has invalid provenance.")
        path = resolve_storage_path(PurePosixPath(expected_reference))
        if not path.is_file():
            raise RenderError("A current TTS audio file is unavailable.")
        try:
            measured_duration = measured_audio_duration_ms(path)
        except ValueError as error:
            raise RenderError("A current TTS audio file is invalid or unreadable.") from error
        if measured_duration != artifact.duration_ms:
            raise RenderError("A TTS Artifact duration does not match its published audio file.")
        row = plan_segment_by_id.get(segment.id)
        if row is None or row.tts_audio_duration_ms != artifact.duration_ms:
            raise RenderError("The timeline plan does not match the current TTS Artifacts.")
        digest = _sha256_file(path)
        speech_inputs.append(_SpeechInput(
            segment_id=segment.id,
            artifact_id=artifact.id,
            path=path,
            output_start_ms=row.output_audio_start_ms,
            duration_ms=artifact.duration_ms,
            rate_percent=int(artifact.rate_percent),
            sha256=digest,
        ))
        artifact_snapshot_rows.append((
            artifact.id, artifact.segment_id, artifact.revision, artifact.storage_reference,
            artifact.duration_ms, artifact.provenance_fingerprint, artifact.voice,
            artifact.rate_percent, artifact.is_current, artifact.job_id, digest,
        ))

    source_digest = _sha256_file(source_path)
    artifact_snapshot = tuple(sorted(artifact_snapshot_rows, key=lambda row: str(row[0])))
    active_job = session.scalar(select(Job).where(
        Job.project_id == project_id,
        Job.operation_type == "render",
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    ).order_by(Job.created_at.desc(), Job.id.desc()).limit(1))
    settings_data = (
        audio_settings_override.model_dump(mode="json") if audio_settings_override is not None
        else active_job.audio_settings if active_job is not None else None
    )
    try:
        audio_settings = RenderAudioSettings.model_validate(settings_data) if settings_data else RenderAudioSettings(
            mode="fixed", background_gain=get_render_original_audio_gain()
        )
    except ValueError as error:
        raise RenderError("The queued render audio settings are invalid.") from error
    fingerprint_payload = {
        "project_id": str(project_id),
        "revision": project.current_revision,
        "source_sha256": source_digest,
        "source_has_audio": probe.has_audio,
        "source_audio_start_ms": probe.audio_start_ms,
        "segments": [
            [str(value) if isinstance(value, UUID) else str(value) for value in row]
            for row in segment_snapshot
        ],
        "artifacts": [[str(value) if isinstance(value, UUID) else value for value in row]
                      for row in artifact_snapshot],
        "timeline": plan.model_dump(mode="json"),
        "settings": {
            "audio_settings": audio_settings.model_dump(mode="json"),
            "video_encoder": "libx264",
            "audio_encoder": "aac",
            "duration_tolerance_ms": RENDER_DURATION_TOLERANCE_MS,
            "normalization": "timeline-render-v1",
        },
    }
    fingerprint = _sha256_json(fingerprint_payload)
    # Keep validation explicit even when there are no operations (the full interval is still rendered).
    if not intervals:
        raise RenderError("The timeline plan has no renderable source interval.")
    return _RenderSnapshot(
        project_id=project_id,
        revision=project.current_revision,
        source_path=source_path,
        source_sha256=source_digest,
        source_has_audio=probe.has_audio,
        original_audio_start_ms=probe.audio_start_ms,
        plan=plan,
        segments=segment_snapshot,
        artifacts=artifact_snapshot,
        speech_inputs=tuple(speech_inputs),
        audio_settings=audio_settings,
        fingerprint=fingerprint,
    )


def _format_seconds(milliseconds: int | Decimal) -> str:
    return f"{Decimal(milliseconds) / Decimal(1000):.6f}".rstrip("0").rstrip(".") or "0"


def build_render_filtergraph(snapshot: _RenderSnapshot) -> str:
    """Build an ordered interval partition exclusively from the validated planner output."""
    plan = snapshot.plan
    intervals = _validate_plan(plan)
    lines: list[str] = []
    video_labels = "".join(f"[vsrc{i}]" for i in range(len(intervals)))
    lines.append(f"[0:v:0]setpts=PTS-STARTPTS,split={len(intervals)}{video_labels};")
    for index, interval in enumerate(intervals):
        lines.append(
            f"[vsrc{index}]trim=start={_format_seconds(interval.start_ms)}:"
            f"end={_format_seconds(interval.end_ms)},"
            f"setpts=(PTS-STARTPTS)*{interval.factor:.9f}[v{index}];"
        )
    lines.append("".join(f"[v{i}]" for i in range(len(intervals)))
                 + f"concat=n={len(intervals)}:v=1:a=0[vout];")

    planned_ms = plan.planned_output_video_duration_ms or 0
    planned_seconds = _format_seconds(planned_ms)
    dub_labels: list[str] = []
    for index, speech in enumerate(snapshot.speech_inputs):
        lines.append(
            f"[{index + 1}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"asetpts=PTS-STARTPTS,volume={snapshot.audio_settings.tts_gain:.6f},"
            f"adelay=delays={speech.output_start_ms}:all=1[dub{index}];"
        )
        dub_labels.append(f"[dub{index}]")

    mix_labels = []
    if snapshot.source_has_audio:
        lines.append(
            f"[0:a:0]aresample=48000:async=1:first_pts=0,"
            f"aformat=sample_fmts=fltp:channel_layouts=stereo,asplit={len(intervals)}"
            + "".join(f"[asrc{i}]" for i in range(len(intervals))) + ";"
        )
        for index, interval in enumerate(intervals):
            atempo = Decimal(1) / interval.factor
            lines.append(
                f"[asrc{index}]atrim=start={_format_seconds(interval.start_ms)}:"
                f"end={_format_seconds(interval.end_ms)},asetpts=PTS-STARTPTS,"
                f"atempo={atempo:.9f}[a{index}];"
            )
        lines.append("".join(f"[a{i}]" for i in range(len(intervals)))
                     + f"concat=n={len(intervals)}:v=0:a=1[bgraw];")
        if snapshot.audio_settings.mode == "fixed":
            lines.append(
                f"[bgraw]volume={snapshot.audio_settings.background_gain:.6f}[bg];"
            )
        else:
            envelope_input_index = 1 + len(snapshot.speech_inputs)
            lines.append(
                f"[{envelope_input_index}:a:0]aresample=48000:async=0:first_pts=0,"
                "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                "asetpts=PTS-STARTPTS[duckenv];"
            )
            lines.append("[bgraw][duckenv]amultiply[bg];")
        mix_labels.append("[bg]")
    mix_labels.extend(dub_labels)
    lines.append(
        "".join(mix_labels)
        + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0:dropout_transition=0,"
        + f"alimiter=limit=0.95:attack=5:release=50,apad=whole_dur={planned_seconds},"
        + f"atrim=duration={planned_seconds}[aout]"
    )
    return "\n".join(lines)


def _run(command: list[str], *, timeout: int, failure_message: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RenderError("Video rendering exceeded its time limit.") from error
    except OSError as error:
        raise RenderError("FFmpeg could not be started.") from error
    if result.returncode:
        diagnostic = next((line.strip() for line in result.stderr.splitlines() if line.strip()), "")
        raise RenderError(f"{failure_message} {diagnostic}".strip())
    return result


def _probe_rendered_media(path: Path) -> int:
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,pix_fmt,duration", "-of", "json", str(path),
    ]
    result = _run(command, timeout=FFPROBE_TIMEOUT_SECONDS, failure_message="Rendered MP4 could not be inspected.")
    try:
        payload = json.loads(result.stdout)
        duration = Decimal(str(payload["format"]["duration"]))
        streams = payload.get("streams", [])
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
        audio = next(stream for stream in streams if stream.get("codec_type") == "audio")
        video_duration = Decimal(str(video["duration"]))
        audio_duration = Decimal(str(audio["duration"]))
        duration_ms = int((duration * 1000).to_integral_value())
        if (
            not duration.is_finite() or not video_duration.is_finite() or not audio_duration.is_finite()
            or duration_ms <= 0 or video_duration <= 0 or audio_duration <= 0
            or abs(video_duration - duration) * 1000 > RENDER_DURATION_TOLERANCE_MS
            or abs(audio_duration - duration) * 1000 > RENDER_DURATION_TOLERANCE_MS
            or video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p"
            or audio.get("codec_name") != "aac"
        ):
            raise ValueError
    except (KeyError, StopIteration, TypeError, ValueError, ArithmeticError, json.JSONDecodeError) as error:
        raise RenderError("Rendered output is missing a usable H.264/AAC media stream.") from error
    return duration_ms


def render_media(
    snapshot: _RenderSnapshot,
    output_path: Path,
    *,
    filter_script_path: Path | None = None,
    envelope_path: Path | None = None,
) -> int:
    """Render and verify an MP4 from a prepared, authoritative timeline snapshot."""
    if not output_path.parent.is_dir():
        raise RenderError("Render output directory is unavailable.")
    script_path = filter_script_path or output_path.with_suffix(".filter.txt")
    graph = build_render_filtergraph(snapshot)
    script_path.write_text(graph, encoding="utf-8")
    command = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(snapshot.source_path)]
    for speech in snapshot.speech_inputs:
        command.extend(["-i", str(speech.path)])
    generated_envelope = False
    if snapshot.source_has_audio and snapshot.audio_settings.mode == "ducking":
        envelope_path = envelope_path or output_path.with_name(f"{output_path.stem}-ducking.wav")
        write_ducking_envelope(
            envelope_path,
            ((item.output_start_ms, item.output_start_ms + item.duration_ms)
             for item in snapshot.speech_inputs),
            duration_ms=snapshot.plan.planned_output_video_duration_ms or 0,
            settings=snapshot.audio_settings,
        )
        generated_envelope = True
        command.extend(["-i", str(envelope_path)])
    command.extend([
        "-filter_complex_script", str(script_path), "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-fps_mode", "vfr",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_path),
    ])
    _run(command, timeout=FFMPEG_TIMEOUT_SECONDS, failure_message="FFmpeg could not render this Project.")
    if generated_envelope:
        envelope_path.unlink(missing_ok=True)
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RenderError("FFmpeg did not produce a non-empty MP4.")
    actual_duration_ms = _probe_rendered_media(output_path)
    planned_duration_ms = snapshot.plan.planned_output_video_duration_ms or 0
    if abs(actual_duration_ms - planned_duration_ms) > RENDER_DURATION_TOLERANCE_MS:
        raise RenderError("Rendered MP4 duration differs from the authoritative plan by more than 100 ms.")
    _run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error", "-i", str(output_path), "-f", "null", "-"],
        timeout=FFMPEG_TIMEOUT_SECONDS,
        failure_message="Rendered MP4 failed full-stream decode verification.",
    )
    return actual_duration_ms


def enqueue_render_job(
    session: Session, project_id: UUID, audio_settings: RenderAudioSettings | None = None
) -> JobCreated:
    project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise ProjectNotFoundError
    active_job = session.scalar(select(Job.id).where(
        Job.project_id == project_id,
        Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
    ).limit(1))
    if active_job is not None:
        raise RenderError("Another Project Job is active; wait for it to finish before rendering.")
    settings = audio_settings or RenderAudioSettings(
        mode="fixed", background_gain=get_render_original_audio_gain()
    )
    _load_render_snapshot(session, project_id)
    job = Job(
        project_id=project_id,
        operation_type="render",
        input_revision=project.current_revision,
        status=JobStatus.QUEUED.value,
        stage="queued",
        audio_settings=settings.model_dump(mode="json"),
    )
    session.add(job)
    session.flush()
    return JobCreated(id=job.id, project_id=project_id, status=job.status)


def render_project(
    engine: Engine,
    *,
    project_id: UUID,
    job_id: UUID,
    input_revision: int,
    stage_callback: Callable[[str], None],
) -> int:
    """Run FFmpeg outside FastAPI and atomically publish a verified video Artifact."""
    with Session(engine) as session:
        job = session.get(Job, job_id)
        if job is None or job.status != JobStatus.RUNNING.value or job.operation_type != "render":
            raise RenderError("Render Job is no longer available.")
        try:
            job_settings = RenderAudioSettings.model_validate(job.audio_settings)
        except ValueError as error:
            raise RenderError("The queued render audio settings are invalid.") from error
        snapshot = _load_render_snapshot(
            session, project_id, ignore_active_job_id=job_id,
            audio_settings_override=job_settings,
        )
        if job.input_revision != input_revision or snapshot.revision != input_revision:
            raise RenderError("Project revision changed before rendering started.")

    temporary_dir = _safe_render_dir(project_id, job_id, temporary=True)
    final_dir = _safe_render_dir(project_id, job_id)
    temporary_dir.mkdir(parents=True, exist_ok=False)
    output = temporary_dir / "rendered.mp4"
    filter_script = temporary_dir / "filter-graph.txt"
    try:
        stage_callback("rendering_video")
        actual_duration_ms = render_media(snapshot, output, filter_script_path=filter_script)
        stage_callback("verifying_render")
        metadata = {
            "version": "timeline-render-v2",
            "project_id": str(project_id),
            "job_id": str(job_id),
            "input_revision": input_revision,
            "input_fingerprint": snapshot.fingerprint,
            "source_sha256": snapshot.source_sha256,
            "planned_duration_ms": snapshot.plan.planned_output_video_duration_ms,
            "actual_duration_ms": actual_duration_ms,
            "render_sha256": _sha256_file(output),
            "duration_tolerance_ms": RENDER_DURATION_TOLERANCE_MS,
            "original_audio_included": snapshot.source_has_audio,
            "audio_settings": snapshot.audio_settings.model_dump(mode="json"),
            "video_encoder": "libx264",
            "audio_encoder": "aac",
            "stretch_operations": [operation.model_dump(mode="json") for operation in snapshot.plan.stretch_operations],
            "speech_artifacts": [
                {"segment_id": str(item.segment_id), "artifact_id": str(item.artifact_id),
                 "sha256": item.sha256, "output_start_ms": item.output_start_ms,
                 "duration_ms": item.duration_ms, "rate_percent": item.rate_percent}
                for item in snapshot.speech_inputs
            ],
        }
        metadata_path = temporary_dir / "render.json"
        metadata_path.write_text(json.dumps(metadata, sort_keys=True, indent=2), encoding="utf-8")
        stage_callback("publishing_render")
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        if final_dir.exists():
            raise RenderError("Render output already exists for this Job.")
        shutil.move(str(temporary_dir), str(final_dir))
        final_output = final_dir / "rendered.mp4"
        with Session(engine) as session, session.begin():
            project = session.scalar(select(Project).where(Project.id == project_id).with_for_update())
            job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
            current_segments = session.scalars(select(Segment).where(
                Segment.project_id == project_id,
                Segment.revision == input_revision,
            ).order_by(Segment.position, Segment.id).with_for_update()).all()
            current_audio = session.scalars(select(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.media_type == TTS_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            ).order_by(Artifact.id).with_for_update()).all()
            current_snapshot = _load_render_snapshot(
                session, project_id, ignore_active_job_id=job_id,
                audio_settings_override=job_settings,
            )
            if (
                project is None or job is None or job.status != JobStatus.RUNNING.value
                or project.current_revision != input_revision
                or current_snapshot.fingerprint != snapshot.fingerprint
                or current_snapshot.segments != snapshot.segments
                or current_snapshot.artifacts != snapshot.artifacts
                or len(current_segments) != len(snapshot.segments)
                or len(current_audio) != len(snapshot.artifacts)
                or not final_output.is_file()
                or final_output.stat().st_size <= 0
                or metadata["render_sha256"] != _sha256_file(final_output)
            ):
                raise RenderError("Project inputs changed while rendering; output was discarded.")
            session.execute(update(Artifact).where(
                Artifact.project_id == project_id,
                Artifact.media_type == RENDER_MEDIA_TYPE,
                Artifact.is_current.is_(True),
            ).values(is_current=False))
            session.add(Artifact(
                project_id=project_id,
                job_id=job_id,
                revision=input_revision,
                media_type=RENDER_MEDIA_TYPE,
                storage_reference=f"projects/{project_id}/jobs/{job_id}/render/rendered.mp4",
                is_current=True,
                duration_ms=actual_duration_ms,
                provenance_fingerprint=snapshot.fingerprint,
            ))
            job.status = JobStatus.SUCCEEDED.value
            job.stage = "render_complete"
            job.safe_error = None
            job.completed_at = session.scalar(select(func.now()))
        logger.info("Render Job %s published a verified MP4 Artifact.", job_id)
        return actual_duration_ms
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        shutil.rmtree(final_dir, ignore_errors=True)
        raise


def _read_render_metadata(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.with_name("render.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload.get("version") in {"timeline-render-v1", "timeline-render-v2"} else None


def get_current_render(
    session: Session, project_id: UUID
) -> tuple[RenderArtifactRead, Path]:
    """Return a render only if the current persisted inputs still match its provenance."""
    if session.get(Project, project_id) is None:
        raise ProjectNotFoundError
    rows = session.scalars(select(Artifact).where(
        Artifact.project_id == project_id,
        Artifact.media_type == RENDER_MEDIA_TYPE,
        Artifact.is_current.is_(True),
    ).order_by(Artifact.created_at.desc(), Artifact.id.desc())).all()
    if len(rows) != 1:
        raise LookupError
    artifact = rows[0]
    job = session.get(Job, artifact.job_id)
    expected = f"projects/{project_id}/jobs/{artifact.job_id}/render/rendered.mp4"
    if (
        artifact.segment_id is not None or artifact.storage_reference != expected
        or artifact.duration_ms is None or artifact.duration_ms <= 0
        or job is None or job.operation_type != "render"
        or job.status != JobStatus.SUCCEEDED.value or job.stage != "render_complete"
    ):
        raise LookupError
    try:
        path = resolve_storage_path(PurePosixPath(expected))
    except (UploadStorageError, OSError, ValueError):
        raise LookupError from None
    if not path.is_file():
        raise LookupError
    metadata = _read_render_metadata(path)
    try:
        actual_digest = _sha256_file(path)
    except RenderError:
        raise LookupError from None
    if (
        metadata is None or metadata.get("project_id") != str(project_id)
        or metadata.get("job_id") != str(job.id)
        or metadata.get("actual_duration_ms") != artifact.duration_ms
        or metadata.get("input_fingerprint") != artifact.provenance_fingerprint
        or metadata.get("render_sha256") != actual_digest
    ):
        raise LookupError
    try:
        audio_settings = RenderAudioSettings.model_validate(
            metadata.get("audio_settings") or {
                "mode": "fixed",
                "background_gain": metadata.get("original_audio_gain", 0),
            }
        )
    except ValueError:
        raise LookupError from None
    try:
        published_settings = RenderAudioSettings.model_validate(
            job.audio_settings if job.audio_settings else {
                "mode": "fixed", "background_gain": metadata.get("original_audio_gain", 0.10),
            }
        )
        current = _load_render_snapshot(
            session, project_id, audio_settings_override=published_settings,
        )
    except (ProjectNotFoundError, RenderError):
        raise LookupError from None
    if metadata.get("version") == "timeline-render-v1":
        try:
            expected_fingerprint = _legacy_render_fingerprint(
                current, float(metadata.get("original_audio_gain", 0.10))
            )
        except (TypeError, ValueError):
            raise LookupError from None
    else:
        expected_fingerprint = current.fingerprint
    if expected_fingerprint != artifact.provenance_fingerprint:
        raise LookupError
    planned = metadata.get("planned_duration_ms")
    if not isinstance(planned, int) or planned <= 0:
        raise LookupError
    return RenderArtifactRead(
        id=artifact.id,
        project_id=project_id,
        job_id=job.id,
        planned_duration_ms=planned,
        duration_ms=artifact.duration_ms,
        created_at=artifact.created_at,
        preview_url=f"/api/projects/{project_id}/rendered-video/preview",
        download_url=f"/api/projects/{project_id}/rendered-video/download",
        current=True,
        audio_settings=audio_settings,
    ), path

