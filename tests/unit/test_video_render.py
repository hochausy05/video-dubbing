"""Synthetic FFmpeg and SQLite coverage for timeline-based MP4 rendering."""

from __future__ import annotations

import subprocess
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
from app.services.audio_normalization import measured_audio_duration_ms
from app.services.tts import TTS_MEDIA_TYPE, translation_fingerprint
from app.services.tts_timeline import TimelineSegmentInput, compute_timeline_plan
from app.schemas.timeline import TimelineStretchOperation
from app.services.video_render import (
    RENDER_MEDIA_TYPE,
    RenderError,
    _probe_rendered_media,
    _RenderSnapshot,
    _SpeechInput,
    _probe_source,
    _validate_plan,
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

    def _snapshot(self, *, with_audio: bool = True, one_stretch: bool = True) -> _RenderSnapshot:
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
            original_audio_gain=0.1,
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
        ), 0.1, "x")
        result = self.root / "rendered.mp4"
        actual = render_media(snapshot, result)
        self.assertLessEqual(abs(actual - 2000), 100)
        self.assertGreater(result.stat().st_size, 0)

    def test_source_probe_keeps_fractional_duration_in_milliseconds(self) -> None:
        fractional = self.root / "fractional-duration.mp4"
        _make_video(fractional, audio=False, duration=Decimal("1.375"))
        self.assertEqual(_probe_source(fractional).duration_ms, 1375)

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
        snapshot = _RenderSnapshot(PROJECT_ID, 0, self.source, "x", True, 0, plan, (), (), speeches, 0.1, "x")
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
        snapshot = _RenderSnapshot(PROJECT_ID, 0, source, "x", True, 0, plan, (), (), speeches, 0.1, "x")
        output = self.root / "separated-stretches.mp4"
        actual = render_media(snapshot, output)
        self.assertLessEqual(abs(actual - (plan.planned_output_video_duration_ms or 0)), 100)

    def test_no_original_audio_still_produces_mixed_dubbing_audio_track(self) -> None:
        source_no_audio = self.root / "without-audio.mp4"
        _make_video(source_no_audio, audio=False)
        original = self._snapshot(with_audio=False)
        snapshot = _RenderSnapshot(
            original.project_id, original.revision, source_no_audio, original.source_sha256, False,
            0, original.plan, original.segments, original.artifacts, original.speech_inputs,
            original.original_audio_gain, original.fingerprint,
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
        queued = self.client.post(f"/projects/{PROJECT_ID}/render-jobs")
        self.assertEqual(queued.status_code, 202, queued.text)
        self.assertEqual(self.client.post(f"/projects/{PROJECT_ID}/render-jobs").status_code, 409)
        job_id = uuid.UUID(queued.json()["id"])
        with Session(self.engine) as session:
            job = session.get(Job, job_id)
            self.assertEqual((job.operation_type, job.status), ("render", "queued"))
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

    def test_failed_render_keeps_previously_published_current_artifact(self) -> None:
        queued = self.client.post(f"/projects/{PROJECT_ID}/render-jobs")
        first_job_id = uuid.UUID(queued.json()["id"])
        self._claim_and_run(first_job_id)
        first_artifact = self.client.get(f"/projects/{PROJECT_ID}/rendered-video").json()["id"]
        second = self.client.post(f"/projects/{PROJECT_ID}/render-jobs")
        second_job_id = uuid.UUID(second.json()["id"])
        with patch("app.services.video_render.render_media", side_effect=RenderError("synthetic encoder failure")):
            self._claim_and_run(second_job_id)
        with Session(self.engine) as session:
            self.assertEqual(session.get(Job, second_job_id).status, "failed")
            current = session.scalar(select(Artifact).where(Artifact.project_id == PROJECT_ID, Artifact.media_type == RENDER_MEDIA_TYPE, Artifact.is_current.is_(True)))
            self.assertEqual(str(current.id), first_artifact)
            self.assertTrue((self.storage / Path(current.storage_reference)).is_file())

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
