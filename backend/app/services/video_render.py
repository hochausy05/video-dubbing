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
from app.schemas.timeline import JointTimelinePlan, TTSTimelinePlan
from app.services.audio_normalization import measured_audio_duration_ms, measured_audio_duration_us
from app.services.tts import TTS_MEDIA_TYPE
from app.services.tts_readiness import ProjectNotFoundError
from app.services.tts_timeline import build_project_timeline_plan
from app.services.joint_timeline import seconds_to_us
from app.services.tts_artifacts import validate_segment_tts_artifact
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
    output_start_us: int | None = None
    duration_us: int | None = None


@dataclass(frozen=True)
class _RenderSnapshot:
    project_id: UUID
    revision: int
    source_path: Path
    source_sha256: str
    source_has_audio: bool
    original_audio_start_ms: int
    plan: TTSTimelinePlan | JointTimelinePlan
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
    start_us: int
    end_us: int
    factor: Decimal

    @property
    def start_ms(self) -> int:
        return self.start_us // 1000

    @property
    def end_ms(self) -> int:
        return self.end_us // 1000


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


def _probe_joint_source_timing(path: Path) -> tuple[int, int, tuple[Decimal, ...]]:
    """Read normalized source-frame PTS, frame coverage duration and safe margin."""
    result = _run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time,pkt_duration_time,duration_time", "-of", "json", str(path),
    ], timeout=FFPROBE_TIMEOUT_SECONDS * 4,
       failure_message="Source frame timing could not be verified for joint rendering.")
    try:
        payload = json.loads(result.stdout)
        frames = payload.get("frames", [])
        raw_pts = [Decimal(str(row["best_effort_timestamp_time"])) for row in frames]
        frame_durations = [Decimal(str(row.get("pkt_duration_time") or row["duration_time"])) for row in frames]
        if not raw_pts or len(raw_pts) != len(frame_durations):
            raise ValueError
        first_pts = min(raw_pts)
        normalized_pts = [timestamp - first_pts for timestamp in raw_pts]
        maximum_frame = max(frame_durations)
        final_coverage = max(timestamp + frame_duration for timestamp, frame_duration
                             in zip(normalized_pts, frame_durations, strict=True))
        if (not final_coverage.is_finite() or final_coverage <= 0
                or not maximum_frame.is_finite() or maximum_frame <= 0):
            raise ValueError
        duration_us = int((final_coverage * 1_000_000).to_integral_value(rounding="ROUND_CEILING"))
        frame_us = int((maximum_frame * 1_000_000).to_integral_value(rounding="ROUND_CEILING"))
        sample_us = (1_000_000 + 48_000 - 1) // 48_000
        return duration_us, frame_us * 2 + sample_us, tuple(timestamp * 1_000_000 for timestamp in normalized_pts)
    except (KeyError, TypeError, ValueError, ArithmeticError, json.JSONDecodeError) as error:
        raise RenderError("Source frame timing is insufficient for strict joint coverage.") from error


def _load_current_joint_plan(session: Session, project_id: UUID, revision: int) -> JointTimelinePlan | None:
    jobs = session.scalars(select(Job).where(
        Job.project_id == project_id,
        Job.operation_type == "av_sync_optimize",
        Job.status == JobStatus.SUCCEEDED.value,
        Job.input_revision == revision,
    ).order_by(Job.created_at.desc(), Job.id.desc())).all()
    for job in jobs:
        if job.result_json is None:
            raise RenderError("The latest successful joint optimization Job has no persisted plan.")
        if not isinstance(job.result_json, dict) or job.result_json.get("plan_version") != "av-sync-v1":
            raise RenderError("The current joint plan uses an unsupported version.")
        try:
            plan = JointTimelinePlan.model_validate(job.result_json)
        except ValueError as error:
            raise RenderError("The persisted joint plan is malformed and cannot be rendered.") from error
        if plan.project_id != project_id or plan.project_revision != revision:
            raise RenderError("The persisted joint plan belongs to a stale Project revision.")
        if not plan.joint_feasible or not plan.renderer_supported or not plan.renderable:
            raise RenderError("The current joint plan is blocked or unsupported by the renderer.")
        return plan
    return None


def _validate_legacy_plan(plan: TTSTimelinePlan) -> tuple[_VideoInterval, ...]:
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
            intervals.append(_VideoInterval(cursor * 1000, start * 1000, Decimal(1)))
        intervals.append(_VideoInterval(start * 1000, end * 1000, factor))
        cursor = end
    if cursor < plan.original_video_duration_ms:
        intervals.append(_VideoInterval(cursor * 1000, plan.original_video_duration_ms * 1000, Decimal(1)))
    if not intervals or intervals[0].start_us != 0 or intervals[-1].end_us != plan.original_video_duration_ms * 1000:
        raise RenderError("The timeline operations do not cover the complete source video.")
    if any(left.end_us != right.start_us for left, right in zip(intervals, intervals[1:])):
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


def _validate_joint_plan(plan: JointTimelinePlan) -> tuple[_VideoInterval, ...]:
    if (
        plan.plan_version != "av-sync-v1" or not plan.renderer_supported or not plan.renderable
        or not plan.joint_feasible or plan.blocking_issues
        or not plan.coverage_precision_verified or plan.coverage_margin_us < 0
        or plan.source_video_duration_us <= 0 or plan.planned_output_duration_us <= 0
        or not plan.source_video_sha256 or len(plan.source_video_sha256) != 64
    ):
        raise RenderError("The av-sync-v1 plan is blocked or unsupported by the active renderer.")
    intervals: list[_VideoInterval] = []
    source_cursor = output_cursor = 0
    source_ranges = []
    for row in plan.video_intervals:
        speed = Decimal(str(row.speed))
        if (
            row.source_start_us != source_cursor or row.source_end_us <= row.source_start_us
            or row.output_start_us != output_cursor or row.output_end_us <= row.output_start_us
            or not speed.is_finite() or speed < Decimal("0.5") or speed > Decimal(1)
        ):
            raise RenderError("The joint plan contains an invalid or discontinuous source/output interval.")
        source_duration = row.source_end_us - row.source_start_us
        expected_output_duration = int((Decimal(source_duration) / speed).to_integral_value(rounding="ROUND_CEILING"))
        if row.output_end_us - row.output_start_us != expected_output_duration:
            raise RenderError("A joint video interval duration does not match its selected playback speed.")
        intervals.append(_VideoInterval(row.source_start_us, row.source_end_us, Decimal(1) / speed))
        source_ranges.append((row.source_start_us, row.source_end_us))
        source_cursor = row.source_end_us
        output_cursor = row.output_end_us
    if (
        not intervals or source_cursor != plan.source_video_duration_us
        or output_cursor != plan.planned_output_duration_us
        or any(left[1] != right[0] for left, right in zip(source_ranges, source_ranges[1:]))
    ):
        raise RenderError("The joint plan does not cover the complete source video exactly once.")
    if len(plan.segments) == 0 or len({row.segment_id for row in plan.segments}) != len(plan.segments):
        raise RenderError("The joint plan must contain unique Segment identities.")

    def map_time(source_time_us: int) -> int:
        if source_time_us == plan.source_video_duration_us:
            return plan.planned_output_duration_us
        interval = next((row for row in plan.video_intervals
                         if row.source_start_us <= source_time_us < row.source_end_us), None)
        if interval is None:
            raise RenderError("A Segment timestamp is outside the joint source mapping.")
        speed = Decimal(str(interval.speed))
        delta = int((Decimal(source_time_us - interval.source_start_us) / speed)
                    .to_integral_value(rounding="ROUND_CEILING"))
        return interval.output_start_us + delta

    for row in plan.segments:
        if (
            not 0 <= row.rate_percent <= 35 or row.measured_audio_duration_us <= 0
            or row.source_start_us < 0 or row.source_end_us <= row.source_start_us
            or row.source_window_end_us <= row.source_start_us
            or row.source_window_end_us > plan.source_video_duration_us
            or row.output_audio_end_us != row.output_audio_start_us + row.measured_audio_duration_us
            or row.signed_slack_us < 0
            or (row.signed_slack_us == 0 and not plan.coverage_precision_verified)
        ):
            raise RenderError("A joint Segment has invalid rate, timing, or negative duration slack.")
        mapped_start = map_time(row.source_start_us)
        mapped_end = map_time(row.source_window_end_us)
        slack = mapped_end - mapped_start - row.measured_audio_duration_us
        if (
            row.output_audio_start_us != mapped_start or row.signed_slack_us != slack
            or row.output_audio_end_us > mapped_end or slack < 0
        ):
            raise RenderError("A joint Segment exceeds its transformed video coverage window.")
        selected_interval = next((item for item in plan.video_intervals
                                  if item.source_start_us == row.source_start_us), None)
        if selected_interval is None or Decimal(str(row.video_speed)) != Decimal(str(selected_interval.speed)):
            raise RenderError("The Segment's selected video speed disagrees with the global mapping.")
    if any(
        left.output_audio_end_us > right.output_audio_start_us
        for left, right in zip(sorted(plan.segments, key=lambda item: item.output_audio_start_us),
                               sorted(plan.segments, key=lambda item: item.output_audio_start_us)[1:])
    ):
        raise RenderError("The joint plan contains overlapping dubbed speech intervals.")
    return tuple(intervals)


def _validate_plan(plan: TTSTimelinePlan | JointTimelinePlan) -> tuple[_VideoInterval, ...]:
    if isinstance(plan, JointTimelinePlan):
        return _validate_joint_plan(plan)
    return _validate_legacy_plan(plan)


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
        plan = _load_current_joint_plan(session, project_id, project.current_revision)
        if plan is None:
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
    source_digest = _sha256_file(source_path)
    if isinstance(plan, JointTimelinePlan):
        exact_duration_us, measured_margin_us, source_frame_pts = _probe_joint_source_timing(source_path)
        if exact_duration_us != plan.source_video_duration_us or source_digest != plan.source_video_sha256:
            raise RenderError("The source video changed after joint timeline analysis.")
        if plan.coverage_margin_us < measured_margin_us:
            raise RenderError("Joint plan coverage margin is smaller than measured frame/sample precision.")
        frames_per_interval = [
            sum(Decimal(interval.source_start_us) <= frame_pts < Decimal(interval.source_end_us)
                for frame_pts in source_frame_pts)
            for interval in plan.video_intervals
        ]
        if not frames_per_interval or any(count == 0 for count in frames_per_interval) \
                or sum(frames_per_interval) != len(source_frame_pts):
            raise RenderError("A joint source partition contains no complete source video frame.")
    elif abs(probe.duration_ms - int(plan.original_video_duration_ms or 0)) > RENDER_DURATION_TOLERANCE_MS:
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
    if isinstance(plan, JointTimelinePlan) and set(plan_segment_by_id) != {segment.id for segment in segments}:
        raise RenderError("The joint plan does not include the exact current Segment set.")
    speech_inputs: list[_SpeechInput] = []
    artifact_snapshot_rows: list[tuple[object, ...]] = []
    for segment_index, segment in enumerate(segments):
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
        if isinstance(plan, JointTimelinePlan):
            if row is None or row.artifact_id != artifact.id or row.rate_percent != artifact.rate_percent:
                raise RenderError("The joint plan selected a different current TTS Artifact.")
            try:
                validated = validate_segment_tts_artifact(session, project, segment, [artifact], project.selected_voice)
                measured_us = measured_audio_duration_us(validated.path)
            except (ValueError, OSError) as error:
                raise RenderError("The selected joint-plan audio Artifact is invalid.") from error
            expected_start_us = seconds_to_us(Decimal(str(segment.start_seconds)))
            expected_end_us = seconds_to_us(Decimal(str(segment.end_seconds)))
            expected_window_end_us = (
                seconds_to_us(Decimal(str(segments[segment_index + 1].start_seconds)))
                if segment_index + 1 < len(segments) else plan.source_video_duration_us
            )
            if (
                measured_us != row.measured_audio_duration_us
                or row.source_start_us != expected_start_us
                or row.source_end_us != expected_end_us
                or row.source_window_end_us != expected_window_end_us
                or row.position != segment.position
            ):
                raise RenderError("The persisted joint plan does not match current Segment or audio data.")
            output_start_us = row.output_audio_start_us
            duration_us = measured_us
            output_start_ms = (output_start_us + 999) // 1000
            duration_for_ms = (duration_us + 999) // 1000
        else:
            if row is None or row.tts_audio_duration_ms != artifact.duration_ms:
                raise RenderError("The timeline plan does not match the current TTS Artifacts.")
            output_start_us = duration_us = None
            output_start_ms = row.output_audio_start_ms
            duration_for_ms = artifact.duration_ms
        digest = _sha256_file(path)
        speech_inputs.append(_SpeechInput(
            segment_id=segment.id,
            artifact_id=artifact.id,
            path=path,
            output_start_ms=output_start_ms,
            duration_ms=duration_for_ms,
            rate_percent=int(artifact.rate_percent),
            sha256=digest,
            output_start_us=output_start_us,
            duration_us=duration_us,
        ))
        artifact_snapshot_rows.append((
            artifact.id, artifact.segment_id, artifact.revision, artifact.storage_reference,
            artifact.duration_ms, artifact.provenance_fingerprint, artifact.voice,
            artifact.rate_percent, artifact.is_current, artifact.job_id, digest,
        ))

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


def _format_microseconds(microseconds: int) -> str:
    return f"{Decimal(microseconds) / Decimal(1_000_000):.6f}".rstrip("0").rstrip(".") or "0"


def _planned_duration_us(plan: TTSTimelinePlan | JointTimelinePlan) -> int:
    if isinstance(plan, JointTimelinePlan):
        return plan.planned_output_duration_us
    return int(plan.planned_output_video_duration_ms or 0) * 1000


def _speech_interval_us(speech: _SpeechInput) -> tuple[int, int]:
    if speech.output_start_us is not None and speech.duration_us is not None:
        return speech.output_start_us, speech.output_start_us + speech.duration_us
    return speech.output_start_ms * 1000, (speech.output_start_ms + speech.duration_ms) * 1000


def build_render_filtergraph(snapshot: _RenderSnapshot) -> str:
    """Build an ordered interval partition exclusively from the validated planner output."""
    plan = snapshot.plan
    intervals = _validate_plan(plan)
    if isinstance(plan, JointTimelinePlan):
        speech_by_id = {speech.segment_id: speech for speech in snapshot.speech_inputs}
        if len(speech_by_id) != len(snapshot.speech_inputs) or set(speech_by_id) != {row.segment_id for row in plan.segments}:
            raise RenderError("Render inputs do not contain the exact joint-plan Segment set.")
        for row in plan.segments:
            speech = speech_by_id[row.segment_id]
            if (
                speech.artifact_id != row.artifact_id or speech.rate_percent != row.rate_percent
                or speech.output_start_us != row.output_audio_start_us
                or speech.duration_us != row.measured_audio_duration_us
            ):
                raise RenderError("Render inputs do not match the joint plan's selected Artifact and timing.")
    lines: list[str] = []
    video_labels = "".join(f"[vsrc{i}]" for i in range(len(intervals)))
    lines.append(f"[0:v:0]setpts=PTS-STARTPTS,split={len(intervals)}{video_labels};")
    for index, interval in enumerate(intervals):
        start, end = _format_microseconds(interval.start_us), _format_microseconds(interval.end_us)
        lines.append(
            f"[vsrc{index}]trim=start={start}:end={end},settb=AVTB,"
            f"setpts=(PTS-STARTPTS)*{interval.factor:.9f}[v{index}];"
        )
    lines.append("".join(f"[v{i}]" for i in range(len(intervals)))
                 + f"concat=n={len(intervals)}:v=1:a=0[vout];")

    planned_us = _planned_duration_us(plan)
    planned_seconds = _format_microseconds(planned_us)
    dub_labels: list[str] = []
    for index, speech in enumerate(snapshot.speech_inputs):
        if isinstance(plan, JointTimelinePlan):
            sample = (speech.output_start_us * 48_000 + 999_999) // 1_000_000
            delay = f"{sample}S:all=1"
        else:
            delay = f"{speech.output_start_ms}:all=1"
        lines.append(
            f"[{index + 1}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"asetpts=PTS-STARTPTS,volume={snapshot.audio_settings.tts_gain:.6f},"
            f"adelay=delays={delay}[dub{index}];"
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
                f"[asrc{index}]atrim=start={_format_microseconds(interval.start_us)}:"
                f"end={_format_microseconds(interval.end_us)},asetpts=PTS-STARTPTS,"
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


def _verify_joint_render_timing(path: Path, snapshot: _RenderSnapshot) -> None:
    """Validate decoded frame/sample coverage with conservative integer bounds."""
    plan = snapshot.plan
    if not isinstance(plan, JointTimelinePlan):
        raise RenderError("Strict timing verification requires an av-sync-v1 plan.")
    result = _run([
        "ffprobe", "-v", "error", "-show_frames", "-show_streams", "-show_format",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,pix_fmt,start_time,duration,sample_rate:"
        "frame=media_type,best_effort_timestamp_time,pkt_duration_time,duration_time,nb_samples,sample_rate",
        "-of", "json", str(path),
    ], timeout=FFPROBE_TIMEOUT_SECONDS * 4,
       failure_message="Rendered frame/sample timing could not be verified.")
    try:
        payload = json.loads(result.stdout)
        streams = payload["streams"]
        video_stream = next(row for row in streams if row.get("codec_type") == "video")
        audio_stream = next(row for row in streams if row.get("codec_type") == "audio")
        if (video_stream.get("codec_name") != "h264" or video_stream.get("pix_fmt") != "yuv420p"
                or audio_stream.get("codec_name") != "aac"):
            raise ValueError
        video_frames_raw: list[tuple[int, int, int]] = []
        audio_frames: list[tuple[int, int]] = []
        for frame in payload["frames"]:
            timestamp = Decimal(str(frame["best_effort_timestamp_time"]))
            if frame.get("media_type") == "video":
                duration = Decimal(str(frame.get("pkt_duration_time") or frame["duration_time"]))
                start = int((timestamp * 1_000_000).to_integral_value(rounding="ROUND_CEILING"))
                duration_us = int((duration * 1_000_000).to_integral_value(rounding="ROUND_FLOOR"))
                end = start + duration_us
                if end <= start:
                    raise ValueError
                video_frames_raw.append((start, end, duration_us))
            elif frame.get("media_type") == "audio":
                samples = int(frame["nb_samples"])
                rate = int(frame.get("sample_rate") or audio_stream.get("sample_rate"))
                if samples <= 0 or rate <= 0:
                    raise ValueError
                start_sample = int((timestamp * rate).to_integral_value(rounding="ROUND_CEILING"))
                audio_frames.append((start_sample, start_sample + samples))
        if not video_frames_raw or not audio_frames:
            raise ValueError
        _source_duration_us, _source_margin_us, source_frame_pts = _probe_joint_source_timing(snapshot.source_path)
        if len(video_frames_raw) != len(source_frame_pts):
            raise RenderError("Rendered output omitted or duplicated a source video frame.")
        video_frames_raw.sort()
        audio_frames.sort()
        # For VFR output, each decoded picture remains displayed until the next
        # presentation timestamp. Packet duration metadata may retain the source
        # frame duration after setpts; derive interior coverage from adjacent PTS.
        video_frames = [
            (start, max(start + 1, video_frames_raw[index + 1][0]) if index + 1 < len(video_frames_raw) else end)
            for index, (start, end, _duration) in enumerate(video_frames_raw)
        ]
        max_frame_us = max(end - start for start, end in video_frames)
        max_sample_frame_us = max(
            int((Decimal(end - start) * 1_000_000 / Decimal(48_000)).to_integral_value(rounding="ROUND_CEILING"))
            for start, end in audio_frames
        )
        video_coverage: list[list[int]] = []
        for start, end in video_frames:
            if video_coverage and start <= video_coverage[-1][1]:
                video_coverage[-1][1] = max(video_coverage[-1][1], end)
            else:
                video_coverage.append([start, end])

        audio_coverage_samples: list[list[int]] = []
        for start, end in audio_frames:
            if audio_coverage_samples and start <= audio_coverage_samples[-1][1] + 1:
                audio_coverage_samples[-1][1] = max(audio_coverage_samples[-1][1], end)
            else:
                audio_coverage_samples.append([start, end])

        def is_covered(coverage: list[list[int]], start: int, end: int) -> bool:
            return any(left <= start and right >= end for left, right in coverage)

        required_ends = []
        for speech in snapshot.speech_inputs:
            start, end = _speech_interval_us(speech)
            sample_start = (start * 48_000 + 999_999) // 1_000_000
            sample_end = (end * 48_000 + 999_999) // 1_000_000
            start_us = (sample_start * 1_000_000 + 47_999) // 48_000
            end_us = (sample_end * 1_000_000 + 47_999) // 48_000
            if not is_covered(video_coverage, start_us, end_us):
                raise RenderError("Rendered video frames do not cover a complete dubbed Segment interval.")
            if not any(left <= sample_start and right >= sample_end
                       for left, right in audio_coverage_samples):
                raise RenderError("Rendered audio samples do not cover a complete dubbed Segment interval.")
            required_ends.append(end_us)
        final_required_audio_us = max(required_ends, default=0)
        actual_video_end_us = video_coverage[-1][1]
        actual_audio_end_us = int((Decimal(audio_frames[-1][1]) * 1_000_000 / Decimal(48_000))
                                  .to_integral_value(rounding="ROUND_FLOOR"))
        planned_us = plan.planned_output_duration_us
        format_duration = Decimal(str(payload["format"]["duration"]))
        format_end_us = int((format_duration * 1_000_000).to_integral_value(rounding="ROUND_FLOOR"))
        if (
            actual_video_end_us < final_required_audio_us
            or actual_audio_end_us < final_required_audio_us
            or actual_video_end_us < format_end_us - max_frame_us
            or abs(actual_video_end_us - planned_us) > max_frame_us
            or abs(format_end_us - actual_video_end_us) > max_frame_us
            or abs(format_end_us - planned_us) > max_frame_us
            or max_sample_frame_us <= 0
        ):
            raise RenderError("Rendered frame/sample coverage is shorter than the authoritative joint timeline.")
    except RenderError:
        raise
    except (KeyError, StopIteration, TypeError, ValueError, ArithmeticError, json.JSONDecodeError) as error:
        raise RenderError("Rendered output has incomplete frame/sample timing metadata.") from error


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
            ((start_us // 1000, (end_us + 999) // 1000)
             for item in snapshot.speech_inputs
             for start_us, end_us in [_speech_interval_us(item)]),
            duration_ms=(_planned_duration_us(snapshot.plan) + 999) // 1000,
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
    if isinstance(snapshot.plan, JointTimelinePlan):
        _verify_joint_render_timing(output_path, snapshot)
    else:
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
        planned_duration_ms = (_planned_duration_us(snapshot.plan) + 999) // 1000
        is_joint = isinstance(snapshot.plan, JointTimelinePlan)
        metadata = {
            "version": "timeline-render-v3" if is_joint else "timeline-render-v2",
            "plan_version": snapshot.plan.plan_version if is_joint else "timeline-v1",
            "project_id": str(project_id),
            "job_id": str(job_id),
            "input_revision": input_revision,
            "input_fingerprint": snapshot.fingerprint,
            "source_sha256": snapshot.source_sha256,
            "planned_duration_ms": planned_duration_ms,
            "planned_duration_us": _planned_duration_us(snapshot.plan),
            "actual_duration_ms": actual_duration_ms,
            "render_sha256": _sha256_file(output),
            "duration_tolerance_ms": RENDER_DURATION_TOLERANCE_MS,
            "original_audio_included": snapshot.source_has_audio,
            "audio_settings": snapshot.audio_settings.model_dump(mode="json"),
            "video_encoder": "libx264",
            "audio_encoder": "aac",
            "stretch_operations": (
                [interval.model_dump(mode="json") for interval in snapshot.plan.video_intervals]
                if is_joint else [operation.model_dump(mode="json") for operation in snapshot.plan.stretch_operations]
            ),
            "joint_video_intervals": (
                [interval.model_dump(mode="json") for interval in snapshot.plan.video_intervals]
                if is_joint else None
            ),
            "speech_artifacts": [
                {"segment_id": str(item.segment_id), "artifact_id": str(item.artifact_id),
                 "sha256": item.sha256, "output_start_ms": item.output_start_ms,
                 "duration_ms": item.duration_ms, "rate_percent": item.rate_percent,
                 "output_start_us": item.output_start_us, "duration_us": item.duration_us}
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
    return payload if isinstance(payload, dict) and payload.get("version") in {
        "timeline-render-v1", "timeline-render-v2", "timeline-render-v3"
    } else None


def get_current_render(
    session: Session, project_id: UUID
) -> tuple[RenderArtifactRead, Path]:
    """Return a render only if the current persisted inputs still match its provenance."""
    project = session.get(Project, project_id)
    if project is None:
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
        artifact.project_id != project_id
        or artifact.revision != project.current_revision
        or artifact.segment_id is not None
        or artifact.storage_reference != expected
        or artifact.duration_ms is None or artifact.duration_ms <= 0
        or job is None
        or job.project_id != project_id
        or job.input_revision != project.current_revision
        or job.operation_type != "render"
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

