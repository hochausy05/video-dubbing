"""Synthetic FFmpeg and SQLite coverage for timeline-based MP4 rendering."""

from __future__ import annotations

import subprocess
import json
import hashlib
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import event

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Artifact, Job, Project, Segment
from app.models.base import Base
from app.services.audio_normalization import measured_audio_duration_ms, measured_audio_duration_us
from app.services.audio_mixing import write_ducking_envelope
from app.services.tts import TTS_MEDIA_TYPE, translation_fingerprint
from app.services.tts_timeline import TimelineSegmentInput, compute_timeline_plan
from app.schemas.timeline import JointSegmentTiming, JointTimelinePlan, JointVideoInterval, TimelineStretchOperation
from app.schemas.render import RenderAudioSettings
from app.services.video_render import (
    RENDER_MEDIA_TYPE,
    RenderError,
    _probe_rendered_media,
    _RenderSnapshot,
    _SpeechInput,
    _probe_source,
    _probe_joint_source_timing,
    _sha256_file,
    _validate_plan,
    _load_render_snapshot,
    _legacy_render_fingerprint,
    build_render_filtergraph,
    render_media,
)
from app.services.uploads import source_relative_path
from app.workers.job_worker import process_claimed_job


PROJECT_ID = uuid.UUID("26b4b050-9019-4f7f-92c2-0ac274ea3a10")
SEGMENT_ID = uuid.UUID("26b4b050-9019-4f7f-92c2-0ac274ea3a11")
TRANSLATION_JOB_ID = uuid.UUID("26b4b050-9019-4f7f-92c2-0ac274ea3a12")
TTS_JOB_ID = uuid.UUID("26b4b050-9019-4f7f-92c2-0ac274ea3a13")
VOICE = "vi-VN-HoaiMyNeural"


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(f"Synthetic media command failed: {result.stderr}")


def _make_video(path: Path, *, audio: bool, duration: Decimal = Decimal("2.0")) -> None:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "lavfi", "-i", f"testsrc2=size=160x90:rate=24:duration={duration}"]
    if audio:
        command.extend(["-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}:sample_rate=48000"])
    command.extend(["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"])
    if audio:
        command.extend(["-c:a", "aac", "-shortest"])
    command.append(str(path))
    _run(command)


def _make_speech(path: Path, duration: Decimal) -> int:
    _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=660:duration={duration}:sample_rate=24000",
        "-codec:a", "libmp3lame", "-q:a", "3", str(path),
    ])
    return measured_audio_duration_ms(path)


class RenderFilterAndMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "Unicode source video.mp4"
        self.speech_paths = [self.root / "speech one.mp3", self.root / "speech two.mp3"]
        _make_video(self.source, audio=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _snapshot(
        self, *, with_audio: bool = True, one_stretch: bool = True,
        audio_settings: RenderAudioSettings | None = None,
    ) -> _RenderSnapshot:
        durations = [_make_speech(self.speech_paths[0], Decimal("1.08"))]
        segment_inputs = [TimelineSegmentInput(SEGMENT_ID, 0, 0, 500, durations[0])]
        speech_ids = [SEGMENT_ID]
        if not one_stretch:
            second_id = uuid.UUID("26b4b050-9019-4f7f-92c2-0ac274ea3a14")
            durations.append(_make_speech(self.speech_paths[1], Decimal("0.30")))
            segment_inputs.append(TimelineSegmentInput(second_id, 1, 1000, 1200, durations[1]))
            speech_ids.append(second_id)
        plan = compute_timeline_plan(PROJECT_ID, 2000, segment_inputs)
        if not plan.renderable:
            raise AssertionError(f"Test plan unexpectedly blocked: {plan.issues}")
        speeches = tuple(_SpeechInput(
            segment_id=segment_id,
            artifact_id=uuid.uuid4(),
            path=self.speech_paths[index],
            output_start_ms=plan.segments[index].output_audio_start_ms,
            duration_ms=durations[index],
            rate_percent=20,
            sha256="synthetic",
        ) for index, segment_id in enumerate(speech_ids))
        return _RenderSnapshot(
            project_id=PROJECT_ID,
            revision=0,
            source_path=self.source,
            source_sha256="synthetic-source",
            source_has_audio=with_audio,
            original_audio_start_ms=0,
            plan=plan,
            segments=(),
            artifacts=(),
            speech_inputs=speeches,
            audio_settings=audio_settings or RenderAudioSettings(mode="fixed", background_gain=0.1),
            fingerprint="synthetic-plan",
        )

    def test_no_stretch_preserves_timeline_and_emits_browser_compatible_streams(self) -> None:
        speech = self.root / "short.mp3"
        duration = _make_speech(speech, Decimal("0.30"))
        plan = compute_timeline_plan(PROJECT_ID, 2000, [TimelineSegmentInput(SEGMENT_ID, 0, 200, 400, duration)])
        self.assertTrue(plan.renderable)
        self.assertEqual(plan.stretch_operations, [])
        snapshot = _RenderSnapshot(PROJECT_ID, 0, self.source, "x", True, 0, plan, (), (), (
            _SpeechInput(SEGMENT_ID, uuid.uuid4(), speech, plan.segments[0].output_audio_start_ms, duration, 0, "x"),
        ), RenderAudioSettings(mode="fixed", background_gain=0.1), "x")
        result = self.root / "rendered.mp4"
        actual = render_media(snapshot, result)
        self.assertLessEqual(abs(actual - 2000), 100)
        self.assertGreater(result.stat().st_size, 0)

    def test_source_probe_keeps_fractional_duration_in_milliseconds(self) -> None:
        fractional = self.root / "fractional-duration.mp4"
        _make_video(fractional, audio=False, duration=Decimal("1.375"))
        self.assertEqual(_probe_source(fractional).duration_ms, 1375)

    def test_joint_optimizer_source_probe_measures_frame_coverage_and_half_speed_margin(self) -> None:
        from app.services.av_sync_optimization import _probe_source_timing

        duration_us, margin_us = _probe_source_timing(self.source)
        self.assertEqual(duration_us, 2_000_000)
        self.assertGreaterEqual(margin_us, 4 * 41_667 + 21)

    def test_one_stretch_places_following_speech_at_planner_output_timestamp(self) -> None:
        snapshot = self._snapshot(one_stretch=False)
        self.assertEqual(len(snapshot.plan.stretch_operations), 1)
        self.assertGreater(snapshot.speech_inputs[1].output_start_ms, 1000)
        self.assertIn(f"delays={snapshot.speech_inputs[1].output_start_ms}:all=1", build_render_filtergraph(snapshot))
        output = self.root / "stretched.mp4"
        actual = render_media(snapshot, output)
        self.assertLessEqual(abs(actual - snapshot.plan.planned_output_video_duration_ms), 100)
        frames = subprocess.run([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(output),
        ], capture_output=True, text=True, check=True).stdout.strip()
        source_frames = subprocess.run([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(self.source),
        ], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(frames, source_frames)

    def test_adjacent_stretches_render_without_dropping_source_frames(self) -> None:
        first_duration = _make_speech(self.speech_paths[0], Decimal("0.55"))
        second_duration = _make_speech(self.speech_paths[1], Decimal("1.55"))
        second_id = uuid.uuid4()
        plan = compute_timeline_plan(PROJECT_ID, 2000, [
            TimelineSegmentInput(SEGMENT_ID, 0, 0, 500, first_duration),
            TimelineSegmentInput(second_id, 1, 500, 1000, second_duration),
        ])
        self.assertTrue(plan.renderable)
        self.assertEqual(len(plan.stretch_operations), 2)
        self.assertEqual(plan.stretch_operations[0].source_end_ms, plan.stretch_operations[1].source_start_ms)
        speeches = tuple(_SpeechInput(
            segment_id=item.segment_id, artifact_id=uuid.uuid4(), path=self.speech_paths[index],
            output_start_ms=plan.segments[index].output_audio_start_ms,
            duration_ms=(first_duration, second_duration)[index], rate_percent=20, sha256="synthetic",
        ) for index, item in enumerate(plan.segments))
        snapshot = _RenderSnapshot(PROJECT_ID, 0, self.source, "x", True, 0, plan, (), (), speeches, RenderAudioSettings(mode="fixed", background_gain=0.1), "x")
        output = self.root / "adjacent-stretches.mp4"
        actual = render_media(snapshot, output)
        self.assertLessEqual(abs(actual - (plan.planned_output_video_duration_ms or 0)), 100)
        output_frames = subprocess.run([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(output),
        ], capture_output=True, text=True, check=True).stdout.strip()
        source_frames = subprocess.run([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(self.source),
        ], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(output_frames, source_frames)

    def test_separated_stretches_keep_intervening_and_trailing_source_intervals(self) -> None:
        source = self.root / "three-second source.mp4"
        _make_video(source, audio=True, duration=Decimal("3.0"))
        first_duration = _make_speech(self.speech_paths[0], Decimal("1.30"))
        second_duration = _make_speech(self.speech_paths[1], Decimal("1.90"))
        second_id = uuid.uuid4()
        plan = compute_timeline_plan(PROJECT_ID, 3000, [
            TimelineSegmentInput(SEGMENT_ID, 0, 0, 400, first_duration),
            TimelineSegmentInput(second_id, 1, 1200, 1600, second_duration),
        ])
        self.assertTrue(plan.renderable)
        self.assertEqual(len(plan.stretch_operations), 2)
        intervals = _validate_plan(plan)
        self.assertIn((400, 1200), [(item.start_ms, item.end_ms) for item in intervals])
        self.assertEqual(intervals[-1].end_ms, 3000)
        speeches = tuple(_SpeechInput(
            segment_id=item.segment_id, artifact_id=uuid.uuid4(), path=self.speech_paths[index],
            output_start_ms=item.output_audio_start_ms,
            duration_ms=(first_duration, second_duration)[index], rate_percent=20, sha256="synthetic",
        ) for index, item in enumerate(plan.segments))
        snapshot = _RenderSnapshot(PROJECT_ID, 0, source, "x", True, 0, plan, (), (), speeches, RenderAudioSettings(mode="fixed", background_gain=0.1), "x")
        output = self.root / "separated-stretches.mp4"
        actual = render_media(snapshot, output)
        self.assertLessEqual(abs(actual - (plan.planned_output_video_duration_ms or 0)), 100)

    def test_no_original_audio_still_produces_mixed_dubbing_audio_track(self) -> None:
        source_no_audio = self.root / "without-audio.mp4"
        _make_video(source_no_audio, audio=False)
        original = self._snapshot(with_audio=False, audio_settings=RenderAudioSettings(mode="ducking"))
        snapshot = _RenderSnapshot(
            original.project_id, original.revision, source_no_audio, original.source_sha256, False,
            0, original.plan, original.segments, original.artifacts, original.speech_inputs,
            original.audio_settings, original.fingerprint,
        )
        output = self.root / "no-background.mp4"
        render_media(snapshot, output)
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
            "-of", "csv=p=0", str(output),
        ], capture_output=True, text=True, check=True).stdout
        self.assertIn("h264,video", probe)
        self.assertIn("aac,audio", probe)

    def test_multiple_tts_inputs_are_mixed_into_one_audio_stream(self) -> None:
        snapshot = self._snapshot(one_stretch=False)
        output = self.root / "two-voices.mp4"
        render_media(snapshot, output)
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
            "stream=codec_name", "-of", "csv=p=0", str(output),
        ], capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertEqual(probe, ["aac"])

    def test_timeline_ducking_reduces_background_and_keeps_planned_duration(self) -> None:
        settings = RenderAudioSettings(
            mode="ducking", background_gain=0.7, ducked_gain=0.06,
            tts_gain=0, attack_ms=80, release_ms=250, bridge_gap_ms=350,
        )
        snapshot = self._snapshot(audio_settings=settings)
        graph = build_render_filtergraph(snapshot)
        self.assertIn("amultiply[bg]", graph)
        self.assertIn("[2:a:0]aresample=48000", graph)
        output = self.root / "ducked.mp4"
        duration = render_media(snapshot, output)
        pcm = subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(output), "-map", "0:a:0",
            "-ac", "1", "-ar", "48000", "-f", "s16le", "-",
        ], capture_output=True, check=True).stdout
        def rms(start_ms: int, end_ms: int) -> float:
            first = start_ms * 48 * 2
            last = end_ms * 48 * 2
            samples = [int.from_bytes(pcm[index:index + 2], "little", signed=True)
                       for index in range(first, last, 2)]
            return (sum(sample * sample for sample in samples) / len(samples)) ** 0.5
        speech_start = snapshot.speech_inputs[0].output_start_ms
        during = rms(speech_start + 100, speech_start + 300)
        outside = rms(1600, 1850)
        self.assertGreater(outside, during * 2)
        self.assertLessEqual(abs(duration - snapshot.plan.planned_output_video_duration_ms), 100)

    def test_fixed_mix_keeps_background_volume_compatibility(self) -> None:
        snapshot = self._snapshot(audio_settings=RenderAudioSettings(
            mode="fixed", background_gain=0.1, tts_gain=0.9,
        ))
        graph = build_render_filtergraph(snapshot)
        self.assertIn("[bgraw]volume=0.100000[bg]", graph)
        self.assertIn("volume=0.900000", graph)
        self.assertNotIn("amultiply[bg]", graph)

    def test_av_sync_joint_plan_executes_selected_speed_and_sample_aligned_speech(self) -> None:
        speech = self.root / "joint-selected.mp3"
        _make_speech(speech, Decimal("1.10"))
        duration_us = measured_audio_duration_us(speech)
        source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        planned_end = 500_000 + int((Decimal(1_500_000) / Decimal("0.7")).to_integral_value(rounding="ROUND_CEILING"))
        plan = JointTimelinePlan(
            project_id=PROJECT_ID, project_revision=0, source_video_sha256=source_hash,
            source_video_duration_us=2_000_000, planned_output_duration_us=planned_end,
            segments=[JointSegmentTiming(
                segment_id=SEGMENT_ID, position=0, artifact_id=uuid.uuid4(),
                source_start_us=500_000, source_end_us=600_000, source_window_end_us=2_000_000,
                rate_percent=25, measured_audio_duration_us=duration_us,
                output_audio_start_us=500_000, output_audio_end_us=500_000 + duration_us,
                video_speed=0.7, signed_slack_us=(planned_end - 500_000) - duration_us,
            )],
            video_intervals=[
                JointVideoInterval(source_start_us=0, source_end_us=500_000,
                                   output_start_us=0, output_end_us=500_000, speed=1.0),
                JointVideoInterval(source_start_us=500_000, source_end_us=2_000_000,
                                   output_start_us=500_000, output_end_us=planned_end, speed=0.7),
            ], blocking_issues=[], joint_feasible=True, coverage_precision_verified=True,
            coverage_margin_us=200_000, renderer_supported=True, renderable=True,
        )
        snapshot = _RenderSnapshot(
            PROJECT_ID, 0, self.source, source_hash, True, 0, plan, (), (),
            (_SpeechInput(
                SEGMENT_ID, plan.segments[0].artifact_id, speech, 500, (duration_us + 999) // 1000,
                25, "synthetic", output_start_us=500_000, duration_us=duration_us,
            ),), RenderAudioSettings(mode="fixed", background_gain=0.1), "synthetic-joint",
        )
        graph = build_render_filtergraph(snapshot)
        self.assertIn("setpts=(PTS-STARTPTS)*1.428571429", graph)
        self.assertIn("adelay=delays=24000S:all=1", graph)
        self.assertIn("atempo=0.700000000", graph)
        output = self.root / "joint-render.mp4"
        rendered_ms = render_media(snapshot, output)
        self.assertLessEqual(abs(rendered_ms * 1000 - planned_end), 42_000)
        decoded_frames = subprocess.run([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(output),
        ], capture_output=True, text=True, check=True).stdout.strip()
        source_frames = subprocess.run([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(self.source),
        ], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(decoded_frames, source_frames)

    def test_av_sync_joint_plan_rejects_negative_slack_and_unsupported_version(self) -> None:
        speech = self.root / "joint-validation.mp3"
        _make_speech(speech, Decimal("0.20"))
        duration_us = measured_audio_duration_us(speech)
        interval = JointVideoInterval(source_start_us=0, source_end_us=2_000_000,
                                      output_start_us=0, output_end_us=2_000_000, speed=1.0)
        base = JointTimelinePlan(
            project_id=PROJECT_ID, project_revision=0, source_video_sha256="a" * 64,
            source_video_duration_us=2_000_000, planned_output_duration_us=2_000_000,
            segments=[JointSegmentTiming(
                segment_id=SEGMENT_ID, position=0, artifact_id=uuid.uuid4(),
                source_start_us=0, source_end_us=100_000, source_window_end_us=2_000_000,
                rate_percent=0, measured_audio_duration_us=duration_us,
                output_audio_start_us=0, output_audio_end_us=duration_us, video_speed=1.0,
                signed_slack_us=2_000_000 - duration_us,
            )], video_intervals=[interval], blocking_issues=[], joint_feasible=True,
            coverage_precision_verified=True, coverage_margin_us=1,
            renderer_supported=True, renderable=True,
        )
        base.segments[0].signed_slack_us = -1_000
        with self.assertRaises(RenderError):
            _validate_plan(base)
        base.segments[0].signed_slack_us = 2_000_000 - duration_us
        base.video_intervals[0].speed = 1.01
        with self.assertRaises(RenderError):
            _validate_plan(base)
        base.video_intervals[0].speed = 1.0
        base = base.model_copy(update={"plan_version": "av-sync-v2"})
        with self.assertRaises(RenderError):
            _validate_plan(base)

    def test_av_sync_supports_minimum_and_normal_video_speed(self) -> None:
        speech = self.root / "speed-boundary.mp3"
        _make_speech(speech, Decimal("0.10"))
        duration_us = measured_audio_duration_us(speech)
        source_hash = _sha256_file(self.source)
        for speed in (Decimal("0.5"), Decimal("1.0")):
            with self.subTest(speed=speed):
                planned_end = int((Decimal(2_000_000) / speed).to_integral_value(rounding="ROUND_CEILING"))
                plan = JointTimelinePlan(
                    project_id=PROJECT_ID, project_revision=0, source_video_sha256=source_hash,
                    source_video_duration_us=2_000_000, planned_output_duration_us=planned_end,
                    segments=[JointSegmentTiming(
                        segment_id=SEGMENT_ID, position=0, artifact_id=uuid.uuid4(),
                        source_start_us=0, source_end_us=100_000, source_window_end_us=2_000_000,
                        rate_percent=0, measured_audio_duration_us=duration_us,
                        output_audio_start_us=0, output_audio_end_us=duration_us,
                        video_speed=float(speed), signed_slack_us=planned_end - duration_us,
                    )], video_intervals=[JointVideoInterval(
                        source_start_us=0, source_end_us=2_000_000, output_start_us=0,
                        output_end_us=planned_end, speed=float(speed),
                    )], blocking_issues=[], joint_feasible=True, coverage_precision_verified=True,
                    coverage_margin_us=200_000, renderer_supported=True, renderable=True,
                )
                snapshot = _RenderSnapshot(
                    PROJECT_ID, 0, self.source, source_hash, True, 0, plan, (), (),
                    (_SpeechInput(
                        SEGMENT_ID, plan.segments[0].artifact_id, speech, 0,
                        (duration_us + 999) // 1000, 0, "synthetic",
                        output_start_us=0, duration_us=duration_us,
                    ),), RenderAudioSettings(mode="fixed", background_gain=0.1), "synthetic-boundary",
                )
                self.assertIn(f"setpts=(PTS-STARTPTS)*{(Decimal(1) / speed):.9f}",
                              build_render_filtergraph(snapshot))
                output = self.root / f"speed-{str(speed).replace('.', '-')}.mp4"
                render_media(snapshot, output)

    def test_truncated_output_is_rejected_by_ffprobe_verification(self) -> None:
        truncated = self.root / "truncated.mp4"
        truncated.write_bytes(b"not an mp4")
        with self.assertRaises(RenderError):
            _probe_rendered_media(truncated)

    def test_adjacent_and_separated_operations_form_complete_partition(self) -> None:
        adjacent = compute_timeline_plan(PROJECT_ID, 2000, [
            TimelineSegmentInput(SEGMENT_ID, 0, 0, 500, 600),
            TimelineSegmentInput(uuid.uuid4(), 1, 500, 1000, 1600),
        ])
        self.assertTrue(adjacent.renderable)
        intervals = _validate_plan(adjacent)
        self.assertEqual(len(adjacent.stretch_operations), 2)
        self.assertEqual([(row.start_ms, row.end_ms) for row in intervals], [(0, 500), (500, 1000), (1000, 2000)])
        separated = compute_timeline_plan(PROJECT_ID, 3000, [
            TimelineSegmentInput(SEGMENT_ID, 0, 0, 400, 1300),
            TimelineSegmentInput(uuid.uuid4(), 1, 1200, 1600, 1900),
        ])
        self.assertTrue(separated.renderable)
        parts = _validate_plan(separated)
        self.assertEqual(len(separated.stretch_operations), 2)
        self.assertEqual(parts[0].start_ms, 0)
        self.assertEqual(parts[-1].end_ms, 3000)
        self.assertTrue(all(left.end_ms == right.start_ms for left, right in zip(parts, parts[1:])))
        self.assertTrue(all(row.factor <= Decimal("1.4") for row in parts))

    def test_blocked_plan_and_factor_above_cap_are_rejected(self) -> None:
        blocked = compute_timeline_plan(PROJECT_ID, 1000, [TimelineSegmentInput(SEGMENT_ID, 0, 0, 100, 2000)])
        with self.assertRaises(RenderError):
            _validate_plan(blocked)
        plan = compute_timeline_plan(PROJECT_ID, 1000, [TimelineSegmentInput(SEGMENT_ID, 0, 0, 100, 100)])
        plan.stretch_operations.append(TimelineStretchOperation(
            operation_order=1, segment_id=SEGMENT_ID, source_start_ms=0, source_end_ms=100,
            stretch_factor=1.41, expected_output_duration_ms=141, added_duration_ms=41,
        ))
        plan.stretch_segment_count = 1
        with self.assertRaises(RenderError):
            _validate_plan(plan)


class RenderJobAndApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.storage = self.root / "storage"
        self.db_path = self.root / "render.sqlite"
        self.engine = create_engine(f"sqlite+pysqlite:///{self.db_path}")
        self.engines = [self.engine]
        Base.metadata.create_all(self.engine)
        self.source = self.storage.joinpath(*source_relative_path(PROJECT_ID).parts)
        self.source.parent.mkdir(parents=True)
        _make_video(self.source, audio=True)
        self.audio_reference = f"projects/{PROJECT_ID}/jobs/{TTS_JOB_ID}/tts/{SEGMENT_ID}.mp3"
        self.audio_path = self.storage / Path(self.audio_reference)
        self.audio_path.parent.mkdir(parents=True)
        self.audio_duration = _make_speech(self.audio_path, Decimal("0.30"))
        with Session(self.engine) as session, session.begin():
            session.add(Project(
                id=PROJECT_ID, name="render integration", current_revision=0,
                source_media_reference=source_relative_path(PROJECT_ID).as_posix(),
                selected_voice=VOICE,
            ))
            session.add(Job(
                id=TRANSLATION_JOB_ID, project_id=PROJECT_ID, operation_type="transcribe_translate",
                input_revision=0, status="succeeded", stage="translation_ready",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ))
            session.add(Job(
                id=TTS_JOB_ID, project_id=PROJECT_ID, operation_type="tts", input_revision=0,
                status="succeeded", stage="tts_ready",
            ))
            session.add(Segment(
                id=SEGMENT_ID, project_id=PROJECT_ID, position=0,
                start_seconds=Decimal("0.200"), end_seconds=Decimal("0.600"),
                source_text="Source", translated_text="Xin chào", revision=0,
            ))
            session.add(Artifact(
                project_id=PROJECT_ID, job_id=TTS_JOB_ID, segment_id=SEGMENT_ID,
                revision=0, media_type=TTS_MEDIA_TYPE, storage_reference=self.audio_reference,
                duration_ms=self.audio_duration,
                provenance_fingerprint=translation_fingerprint("Xin chào", VOICE, 0),
                voice=VOICE, rate_percent=0, is_current=True,
            ))
        self.patches = [
            patch("app.api.projects.create_database_engine", return_value=self.engine),
            patch("app.api.projects.create_session_factory", side_effect=lambda engine: sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)),
            patch("app.services.uploads.get_storage_root", return_value=self.storage),
            patch("app.services.tts_timeline.get_edge_tts_voice", return_value=VOICE),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        for item in reversed(self.patches):
            item.stop()
        for engine in self.engines:
            engine.dispose()
        self.temp.cleanup()

    def _claim_and_run(self, job_id: uuid.UUID) -> None:
        with Session(self.engine) as session, session.begin():
            session.get(Job, job_id).status = "running"
        process_claimed_job(self.engine, job_id)

    def test_enqueue_worker_publication_range_download_and_persistence(self) -> None:
        chosen_settings = {
            "mode": "ducking", "background_gain": 0.42, "ducked_gain": 0.07,
            "tts_gain": 0.92, "attack_ms": 80, "release_ms": 250,
            "bridge_gap_ms": 350,
        }
        queued = self.client.post(f"/projects/{PROJECT_ID}/render-jobs", json=chosen_settings)
        self.assertEqual(queued.status_code, 202, queued.text)
        self.assertEqual(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").status_code, 409)
        job_id = uuid.UUID(queued.json()["id"])
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            self.assertEqual((job.operation_type, job.status), ("render", "queued"))
            self.assertEqual(job.audio_settings, chosen_settings)
        self._claim_and_run(job_id)
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            artifact = session.scalar(select(Artifact).where(Artifact.job_id == job_id))
            self.assertEqual((job.status, job.stage), ("succeeded", "render_complete"))
            self.assertEqual(artifact.media_type, RENDER_MEDIA_TYPE)
            output_path = self.storage / Path(artifact.storage_reference)
            self.assertTrue(output_path.is_file())
        self.engine.dispose()
        self.engine = create_engine(f"sqlite+pysqlite:///{self.db_path}")
        self.engines.append(self.engine)
        self.patches[0].stop()
        self.patches[1].stop()
        self.patches[0] = patch("app.api.projects.create_database_engine", return_value=self.engine)
        self.patches[1] = patch("app.api.projects.create_session_factory", side_effect=lambda engine: sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))
        self.patches[0].start()
        self.patches[1].start()
        metadata = self.client.get(f"/projects/{PROJECT_ID}/rendered-video")
        self.assertEqual(metadata.status_code, 200, metadata.text)
        self.assertEqual(metadata.json()["audio_settings"], chosen_settings)
        preview_url = metadata.json()["preview_url"].removeprefix("/api")
        download_url = metadata.json()["download_url"].removeprefix("/api")
        preview = self.client.get(preview_url, headers={"Range": "bytes=0-31"})
        self.assertEqual(preview.status_code, 206)
        self.assertEqual(len(preview.content), 32)
        self.assertEqual(preview.headers["content-type"], "video/mp4")
        download = self.client.get(download_url)
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers["content-disposition"])
        self.assertNotIn(str(self.storage), metadata.text)

    def test_unsupported_joint_plan_is_rejected_instead_of_using_legacy_timeline(self) -> None:
        joint_job_id = uuid.UUID("50000000-0000-0000-0000-000000000001")
        with Session(self.engine) as session, session.begin():
            session.add(Job(
                id=joint_job_id, project_id=PROJECT_ID, operation_type="av_sync_optimize",
                input_revision=0, status="succeeded", stage="joint_optimization_complete",
                result_json={
                    "plan_version": "av-sync-v1", "project_id": str(PROJECT_ID), "project_revision": 0,
                    "source_video_duration_us": 2_000_000, "planned_output_duration_us": 2_000_000,
                    "source_video_sha256": "a" * 64, "segments": [],
                    "video_intervals": [], "blocking_issues": [], "joint_feasible": True,
                    "coverage_precision_verified": False, "coverage_margin_us": 0,
                    "renderer_supported": False, "renderable": False,
                },
            ))
        response = self.client.post(f"/projects/{PROJECT_ID}/render-jobs")
        self.assertEqual(response.status_code, 409)
        self.assertIn("blocked or unsupported", response.json()["detail"])

    def test_joint_plan_renders_and_publishes_versioned_result_atomically(self) -> None:
        from app.services.joint_timeline import seconds_to_us

        duration_us = measured_audio_duration_us(self.audio_path)
        source_duration_us, margin_us, _frame_pts = _probe_joint_source_timing(self.source)
        with Session(self.engine) as session:
            artifact = session.scalar(select(Artifact).where(Artifact.segment_id == SEGMENT_ID))
        start_us = seconds_to_us(Decimal("0.200"))
        end_us = seconds_to_us(Decimal("0.600"))
        plan = JointTimelinePlan(
            project_id=PROJECT_ID, project_revision=0, source_video_sha256=_sha256_file(self.source),
            source_video_duration_us=source_duration_us, planned_output_duration_us=source_duration_us,
            segments=[JointSegmentTiming(
                segment_id=SEGMENT_ID, position=0, artifact_id=artifact.id,
                source_start_us=start_us, source_end_us=end_us, source_window_end_us=source_duration_us,
                rate_percent=0, measured_audio_duration_us=duration_us,
                output_audio_start_us=start_us, output_audio_end_us=start_us + duration_us,
                video_speed=1.0, signed_slack_us=source_duration_us - start_us - duration_us,
            )], video_intervals=[
                JointVideoInterval(source_start_us=0, source_end_us=start_us,
                                   output_start_us=0, output_end_us=start_us, speed=1.0),
                JointVideoInterval(source_start_us=start_us, source_end_us=source_duration_us,
                                   output_start_us=start_us, output_end_us=source_duration_us, speed=1.0),
            ], blocking_issues=[], joint_feasible=True, coverage_precision_verified=True,
            coverage_margin_us=max(margin_us, 1), renderer_supported=True, renderable=True,
        )
        joint_job_id = uuid.uuid4()
        with Session(self.engine) as session, session.begin():
            session.add(Job(
                id=joint_job_id, project_id=PROJECT_ID, operation_type="av_sync_optimize",
                input_revision=0, status="succeeded", stage="joint_optimization_complete",
                result_json=plan.model_dump(mode="json"),
            ))
        settings = {
            "mode": "ducking", "background_gain": 0.35, "ducked_gain": 0.08,
            "tts_gain": 1.0, "attack_ms": 80, "release_ms": 250, "bridge_gap_ms": 350,
        }
        queued = self.client.post(f"/projects/{PROJECT_ID}/render-jobs", json=settings)
        self.assertEqual(queued.status_code, 202, queued.text)
        render_job_id = uuid.UUID(queued.json()["id"])
        ducking_intervals: list[tuple[int, int]] = []

        def record_ducking(path, intervals, *, duration_ms, settings):
            ducking_intervals.extend(intervals)
            write_ducking_envelope(path, ducking_intervals, duration_ms=duration_ms, settings=settings)

        with patch("app.services.video_render.write_ducking_envelope", side_effect=record_ducking):
            self._claim_and_run(render_job_id)
        self.assertEqual(ducking_intervals, [(start_us // 1000, (start_us + duration_us + 999) // 1000)])
        with Session(self.engine) as session:
            render_job = session.get(Job, render_job_id)
            render_artifact = session.scalar(select(Artifact).where(Artifact.job_id == render_job_id))
            self.assertEqual((render_job.status, render_job.stage), ("succeeded", "render_complete"))
            output = self.storage / Path(render_artifact.storage_reference)
            metadata = json.loads(output.with_name("render.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["version"], "timeline-render-v3")
            self.assertEqual(metadata["plan_version"], "av-sync-v1")
            self.assertEqual(metadata["speech_artifacts"][0]["artifact_id"], str(artifact.id))
            self.assertEqual(metadata["joint_video_intervals"][1]["speed"], 1.0)
            self.assertEqual(metadata["audio_settings"], settings)
        result = self.client.get(f"/projects/{PROJECT_ID}/rendered-video")
        self.assertEqual(result.status_code, 200, result.text)

    def test_joint_render_rejects_a_plan_selecting_a_stale_artifact_id(self) -> None:
        from app.services.joint_timeline import seconds_to_us

        duration_us = measured_audio_duration_us(self.audio_path)
        source_duration_us, margin_us, _frame_pts = _probe_joint_source_timing(self.source)
        stale_artifact_id = uuid.uuid4()
        plan = JointTimelinePlan(
            project_id=PROJECT_ID, project_revision=0, source_video_sha256=_sha256_file(self.source),
            source_video_duration_us=source_duration_us, planned_output_duration_us=source_duration_us,
            segments=[JointSegmentTiming(
                segment_id=SEGMENT_ID, position=0, artifact_id=stale_artifact_id,
                source_start_us=seconds_to_us(Decimal("0.200")),
                source_end_us=seconds_to_us(Decimal("0.600")),
                source_window_end_us=source_duration_us, rate_percent=0,
                measured_audio_duration_us=duration_us, output_audio_start_us=seconds_to_us(Decimal("0.200")),
                output_audio_end_us=seconds_to_us(Decimal("0.200")) + duration_us,
                video_speed=1.0, signed_slack_us=source_duration_us - seconds_to_us(Decimal("0.200")) - duration_us,
            )], video_intervals=[
                JointVideoInterval(source_start_us=0, source_end_us=200_000,
                                   output_start_us=0, output_end_us=200_000, speed=1.0),
                JointVideoInterval(source_start_us=200_000, source_end_us=source_duration_us,
                                   output_start_us=200_000, output_end_us=source_duration_us, speed=1.0),
            ], blocking_issues=[], joint_feasible=True, coverage_precision_verified=True,
            coverage_margin_us=max(margin_us, 1), renderer_supported=True, renderable=True,
        )
        joint_job_id = uuid.uuid4()
        with Session(self.engine) as session, session.begin():
            session.add(Job(
                id=joint_job_id, project_id=PROJECT_ID, operation_type="av_sync_optimize",
                input_revision=0, status="succeeded", stage="joint_optimization_complete",
                result_json=plan.model_dump(mode="json"),
            ))
        response = self.client.post(f"/projects/{PROJECT_ID}/render-jobs")
        self.assertEqual(response.status_code, 409)
        self.assertIn("different current TTS Artifact", response.json()["detail"])

    def test_failed_render_keeps_previously_published_current_artifact(self) -> None:
        queued = self.client.post(f"/projects/{PROJECT_ID}/render-jobs")
        first_job_id = uuid.UUID(queued.json()["id"])
        self._claim_and_run(first_job_id)
        first_artifact = self.client.get(f"/projects/{PROJECT_ID}/rendered-video").json()["id"]
        second = self.client.post(f"/projects/{PROJECT_ID}/render-jobs", json={
            "mode": "ducking", "background_gain": 0.35, "ducked_gain": 0.08,
            "tts_gain": 1.0, "attack_ms": 80, "release_ms": 250, "bridge_gap_ms": 350,
        })
        second_job_id = uuid.UUID(second.json()["id"])
        with patch("app.services.video_render.render_media", side_effect=RenderError("synthetic encoder failure")):
            self._claim_and_run(second_job_id)
        with Session(self.engine) as session:
            self.assertEqual(session.get(Job, second_job_id).status, "failed")
            current = session.scalar(select(Artifact).where(Artifact.project_id == PROJECT_ID, Artifact.media_type == RENDER_MEDIA_TYPE, Artifact.is_current.is_(True)))
            self.assertEqual(str(current.id), first_artifact)
            self.assertTrue((self.storage / Path(current.storage_reference)).is_file())

    def test_existing_v1_render_remains_available_after_schema_upgrade(self) -> None:
        job_id = uuid.UUID(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").json()["id"])
        self._claim_and_run(job_id)
        with Session(self.engine) as session, session.begin():
            job = session.get(Job, job_id)
            artifact = session.scalar(select(Artifact).where(Artifact.job_id == job_id))
            snapshot = _load_render_snapshot(
                session, PROJECT_ID,
                audio_settings_override=RenderAudioSettings(mode="fixed", background_gain=0.1),
            )
            fingerprint = _legacy_render_fingerprint(snapshot, 0.1)
            job.audio_settings = None
            artifact.provenance_fingerprint = fingerprint
            render_path = self.storage / Path(artifact.storage_reference)
            metadata_path = render_path.with_name("render.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["version"] = "timeline-render-v1"
            metadata["input_fingerprint"] = fingerprint
            metadata["original_audio_gain"] = 0.1
            metadata.pop("audio_settings", None)
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        response = self.client.get(f"/projects/{PROJECT_ID}/rendered-video")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["audio_settings"]["mode"], "fixed")

    def test_invalid_render_audio_settings_are_rejected(self) -> None:
        response = self.client.post(
            f"/projects/{PROJECT_ID}/render-jobs",
            json={"mode": "ducking", "background_gain": 0.2, "ducked_gain": 0.4},
        )
        self.assertEqual(response.status_code, 422)

    def test_database_publication_failure_rolls_back_artifact_and_keeps_previous(self) -> None:
        first_job_id = uuid.UUID(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").json()["id"])
        self._claim_and_run(first_job_id)
        with Session(self.engine) as session:
            previous = session.scalar(select(Artifact).where(Artifact.job_id == first_job_id))
            previous_id = previous.id
            previous_path = self.storage / Path(previous.storage_reference)
        next_job_id = uuid.UUID(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").json()["id"])

        def reject_render_commit(session):
            if any(isinstance(item, Artifact) and item.media_type == RENDER_MEDIA_TYPE for item in session.new):
                raise RuntimeError("synthetic database commit rejection")

        event.listen(Session, "before_commit", reject_render_commit)
        try:
            self._claim_and_run(next_job_id)
        finally:
            event.remove(Session, "before_commit", reject_render_commit)
        with Session(self.engine) as session:
            job = session.get(Job, next_job_id)
            renders = session.scalars(select(Artifact).where(
                Artifact.project_id == PROJECT_ID, Artifact.media_type == RENDER_MEDIA_TYPE,
            )).all()
            self.assertEqual(job.status, "failed")
            self.assertEqual([item.id for item in renders], [previous_id])
            self.assertTrue(renders[0].is_current)
            self.assertTrue(previous_path.is_file())
        self.assertFalse((self.storage / "projects" / str(PROJECT_ID) / "jobs" / str(next_job_id) / "render").exists())

    def test_translation_change_hides_stale_render_and_does_not_change_media(self) -> None:
        job_id = uuid.UUID(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").json()["id"])
        self._claim_and_run(job_id)
        with Session(self.engine) as session:
            artifact = session.scalar(select(Artifact).where(Artifact.job_id == job_id))
            artifact_path = self.storage / Path(artifact.storage_reference)
            original_bytes = artifact_path.read_bytes()
            session.get(Segment, SEGMENT_ID).translated_text = "Bản dịch mới"
            session.commit()
        response = self.client.get(f"/projects/{PROJECT_ID}/rendered-video")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(artifact_path.read_bytes(), original_bytes)

    def test_render_result_endpoints_reject_wrong_project_or_revision_provenance(self) -> None:
        job_id = uuid.UUID(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").json()["id"])
        self._claim_and_run(job_id)
        other_project_id = uuid.uuid4()
        with Session(self.engine) as session, session.begin():
            session.add(Project(id=other_project_id, name="unrelated project"))

        endpoints = (
            f"/projects/{PROJECT_ID}/rendered-video",
            f"/projects/{PROJECT_ID}/rendered-video/preview",
            f"/projects/{PROJECT_ID}/rendered-video/download",
        )

        def assert_all_result_routes_hide_render() -> None:
            for endpoint in endpoints:
                with self.subTest(endpoint=endpoint):
                    response = self.client.get(endpoint)
                    self.assertEqual(response.status_code, 404)

        with Session(self.engine) as session, session.begin():
            session.get(Job, job_id).project_id = other_project_id
        assert_all_result_routes_hide_render()

        with Session(self.engine) as session, session.begin():
            session.get(Job, job_id).project_id = PROJECT_ID
            session.get(Job, job_id).input_revision = 1
        assert_all_result_routes_hide_render()

        with Session(self.engine) as session, session.begin():
            session.get(Job, job_id).input_revision = 0
            session.scalar(select(Artifact).where(Artifact.job_id == job_id)).revision = 1
        assert_all_result_routes_hide_render()

        with Session(self.engine) as session, session.begin():
            session.scalar(select(Artifact).where(Artifact.job_id == job_id)).revision = 0
            session.get(Job, job_id).status = "failed"
        assert_all_result_routes_hide_render()

        with Session(self.engine) as session, session.begin():
            session.get(Job, job_id).status = "succeeded"
            session.get(Job, job_id).stage = "rendering_video"
        assert_all_result_routes_hide_render()

    def test_missing_or_stale_tts_artifact_blocks_enqueue(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.scalar(select(Artifact).where(
                Artifact.project_id == PROJECT_ID, Artifact.media_type == TTS_MEDIA_TYPE,
            )).is_current = False
        response = self.client.post(f"/projects/{PROJECT_ID}/render-jobs")
        self.assertEqual(response.status_code, 409)
        with Session(self.engine) as session, session.begin():
            session.scalar(select(Artifact).where(
                Artifact.project_id == PROJECT_ID, Artifact.media_type == TTS_MEDIA_TYPE,
            )).is_current = True
            session.get(Segment, SEGMENT_ID).translated_text = "Stale source translation"
        stale = self.client.post(f"/projects/{PROJECT_ID}/render-jobs")
        self.assertEqual(stale.status_code, 409)

    def test_input_change_during_render_discards_unpublished_output(self) -> None:
        first_job_id = uuid.UUID(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").json()["id"])
        self._claim_and_run(first_job_id)
        first_artifact = self.client.get(f"/projects/{PROJECT_ID}/rendered-video").json()["id"]
        second_job_id = uuid.UUID(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").json()["id"])
        from app.services import video_render

        actual_render = video_render.render_media

        def render_then_edit(snapshot, output_path, *, filter_script_path=None):
            actual_duration = actual_render(snapshot, output_path, filter_script_path=filter_script_path)
            with Session(self.engine) as session, session.begin():
                session.get(Segment, SEGMENT_ID).translated_text = "Changed during rendering"
            return actual_duration

        with patch("app.services.video_render.render_media", side_effect=render_then_edit):
            self._claim_and_run(second_job_id)
        with Session(self.engine) as session:
            self.assertEqual(session.get(Job, second_job_id).status, "failed")
            artifacts = session.scalars(select(Artifact).where(
                Artifact.project_id == PROJECT_ID, Artifact.media_type == RENDER_MEDIA_TYPE,
            )).all()
            self.assertEqual({str(item.id) for item in artifacts}, {first_artifact})
            self.assertTrue((self.storage / Path(artifacts[0].storage_reference)).is_file())
        self.assertFalse((self.storage / "projects" / str(PROJECT_ID) / "jobs" / str(second_job_id) / "render").exists())


if __name__ == "__main__":
    unittest.main()
