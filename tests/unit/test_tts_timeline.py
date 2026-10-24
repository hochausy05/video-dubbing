"""Deterministic TTS output timeline planning and read-only API tests."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Artifact, Job, Project, Segment
from app.models.base import Base
from app.services.tts import adaptive_rate_percent, translation_fingerprint
from app.services.tts_timeline import TimelineSegmentInput, compute_timeline_plan


PROJECT_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e11")
TRANSLATION_JOB_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e12")
TTS_JOB_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e13")
SEGMENT_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e14")
VOICE = "vi-VN-HoaiMyNeural"


def row(number: int, start_ms: int, end_ms: int, audio_ms: int, position: int | None = None):
    return TimelineSegmentInput(
        segment_id=uuid.UUID(f"00000000-0000-0000-0000-{number:012d}"),
        position=number if position is None else position,
        original_start_ms=start_ms,
        original_end_ms=end_ms,
        tts_audio_duration_ms=audio_ms,
    )


class TimelineCalculationTests(unittest.TestCase):
    def test_existing_silent_gap_fits_audio_without_stretch(self) -> None:
        plan = compute_timeline_plan(PROJECT_ID, 5_000, [row(1, 1_000, 2_000, 2_500)])
        self.assertEqual(plan.total_added_duration_ms, 0)
        self.assertEqual(plan.stretch_segment_count, 0)
        self.assertEqual(plan.planned_output_video_duration_ms, 5_000)
        segment = plan.segments[0]
        self.assertEqual((segment.output_audio_start_ms, segment.output_audio_end_ms), (1_000, 3_500))
        self.assertEqual(segment.stretch_factor, None)
        self.assertTrue(plan.renderable)

    def test_stretch_below_cap_uses_only_required_addition(self) -> None:
        plan = compute_timeline_plan(PROJECT_ID, 1_600, [row(1, 0, 1_000, 1_500)])
        self.assertEqual(plan.total_added_duration_ms, 0)  # source end gap supplies 600 ms
        self.assertEqual(plan.stretch_segment_count, 0)
        self.assertTrue(plan.renderable)

        cramped = compute_timeline_plan(PROJECT_ID, 1_100, [row(1, 0, 1_000, 1_050)])
        self.assertEqual(cramped.total_added_duration_ms, 0)  # 100 ms remains after the audio
        self.assertEqual(cramped.stretch_segment_count, 0)
        stretch = compute_timeline_plan(PROJECT_ID, 1_000, [row(1, 0, 1_000, 1_200)])
        self.assertEqual(stretch.total_added_duration_ms, 200)
        self.assertEqual(stretch.stretch_operations[0].stretch_factor, 1.2)
        self.assertEqual(stretch.stretch_operations[0].expected_output_duration_ms, 1_200)

    def test_exact_1_4_cap_is_renderable(self) -> None:
        plan = compute_timeline_plan(PROJECT_ID, 1_000, [row(1, 0, 1_000, 1_400)])
        operation = plan.stretch_operations[0]
        self.assertEqual(operation.stretch_factor, 1.4)
        self.assertEqual(operation.added_duration_ms, 400)
        self.assertEqual(plan.planned_output_video_duration_ms, 1_400)
        self.assertEqual(plan.blocking_issue_count, 0)
        self.assertTrue(plan.renderable)

    def test_over_cap_reports_conflict_and_shifts_by_actual_capped_addition(self) -> None:
        plan = compute_timeline_plan(
            PROJECT_ID,
            2_000,
            [row(1, 0, 1_000, 1_600), row(2, 1_000, 1_500, 200)],
        )
        self.assertEqual(plan.stretch_operations[0].added_duration_ms, 400)
        self.assertEqual(plan.total_added_duration_ms, 400)
        self.assertEqual(plan.planned_output_video_duration_ms, 2_400)
        # Using the uncapped 600 ms request here would incorrectly produce 1,600.
        self.assertEqual(plan.segments[1].cumulative_shift_ms, 400)
        self.assertEqual(plan.segments[1].output_audio_start_ms, 1_400)
        self.assertEqual(plan.segments[0].unresolved_overlap_ms, 200)
        self.assertFalse(plan.renderable)
        self.assertEqual(plan.issues[0].code, "stretch_limit_exceeded")

    def test_consecutive_stretches_cumulate_exact_integer_milliseconds(self) -> None:
        plan = compute_timeline_plan(
            PROJECT_ID,
            2_000,
            [row(1, 0, 1_000, 1_400), row(2, 1_000, 2_000, 1_400)],
        )
        self.assertEqual([operation.added_duration_ms for operation in plan.stretch_operations], [400, 400])
        self.assertEqual([segment.cumulative_shift_ms for segment in plan.segments], [0, 400])
        self.assertEqual([segment.output_audio_start_ms for segment in plan.segments], [0, 1_400])
        self.assertEqual(plan.total_added_duration_ms, 800)
        self.assertEqual(plan.planned_output_video_duration_ms, 2_800)

    def test_original_overlap_is_explicit_and_never_stretched(self) -> None:
        plan = compute_timeline_plan(
            PROJECT_ID,
            2_500,
            [row(1, 0, 1_200, 1_300), row(2, 1_000, 1_500, 800)],
        )
        self.assertEqual(plan.stretch_operations, [])
        self.assertFalse(plan.renderable)
        self.assertEqual(plan.issues[0].code, "source_timestamp_overlap")
        self.assertEqual(plan.issues[0].severity, "warning")
        self.assertIn("stretch_interval_overlaps_dialogue", {issue.code for issue in plan.issues})
        self.assertEqual(plan.blocking_issue_count, 1)

    def test_overlapping_source_windows_that_need_no_stretch_are_only_a_warning(self) -> None:
        plan = compute_timeline_plan(
            PROJECT_ID,
            2_500,
            [row(1, 0, 1_200, 1_000), row(2, 1_000, 1_500, 800)],
        )
        self.assertEqual(plan.stretch_operations, [])
        self.assertTrue(plan.renderable)
        self.assertEqual(plan.blocking_issue_count, 0)
        self.assertEqual(plan.issues[0].code, "source_timestamp_overlap")
        self.assertEqual(plan.issues[0].severity, "warning")

    def test_final_segment_near_video_end_and_invalid_inputs(self) -> None:
        final = compute_timeline_plan(PROJECT_ID, 1_000, [row(1, 900, 950, 120)])
        self.assertEqual(final.stretch_operations[0].source_start_ms, 900)
        self.assertEqual(final.stretch_operations[0].source_end_ms, 950)
        self.assertEqual(final.stretch_operations[0].added_duration_ms, 20)
        self.assertEqual(final.segments[0].output_audio_end_ms, 1_020)
        self.assertEqual(final.planned_output_video_duration_ms, 1_020)

        invalid = compute_timeline_plan(PROJECT_ID, 1_000, [row(2, -1, 0, 0)])
        self.assertFalse(invalid.renderable)
        self.assertIsNone(invalid.planned_output_video_duration_ms)
        self.assertEqual(
            {issue.code for issue in invalid.issues},
            {"audio_duration_invalid", "source_timestamp_invalid"},
        )

    def test_repeated_calculation_is_deterministic(self) -> None:
        inputs = [row(1, 0, 1_000, 1_600), row(2, 1_000, 2_000, 1_400)]
        first = compute_timeline_plan(PROJECT_ID, 2_000, inputs).model_dump(mode="json")
        second = compute_timeline_plan(PROJECT_ID, 2_000, inputs).model_dump(mode="json")
        self.assertEqual(first, second)


class TimelinePlanApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.engine = create_engine(f"sqlite+pysqlite:///{self.root / 'timeline.sqlite'}")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session, session.begin():
            session.add(Project(
                id=PROJECT_ID, name="timeline test",
                source_media_reference=f"projects/{PROJECT_ID}/source/video.mp4",
                current_revision=0,
            ))
            session.add(Job(
                id=TRANSLATION_JOB_ID, project_id=PROJECT_ID,
                operation_type="transcribe_translate", input_revision=0,
                status="succeeded", stage="translation_ready",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ))
            session.add(Job(
                id=TTS_JOB_ID, project_id=PROJECT_ID, operation_type="tts",
                input_revision=0, status="succeeded", stage="tts_ready",
            ))
            session.add(Segment(
                id=SEGMENT_ID, project_id=PROJECT_ID, position=0,
                start_seconds=Decimal("0.000"), end_seconds=Decimal("1.000"),
                source_text="Source.", translated_text="Xin chào.", revision=0,
            ))
            session.flush()
            session.add(Artifact(
                project_id=PROJECT_ID, job_id=TTS_JOB_ID, segment_id=SEGMENT_ID,
                revision=0, media_type="audio/mpeg",
                storage_reference=f"projects/{PROJECT_ID}/jobs/{TTS_JOB_ID}/tts/{SEGMENT_ID}.mp3",
                duration_ms=1_200, provenance_fingerprint=translation_fingerprint("Xin chào.", VOICE, 0),
                voice=VOICE, rate_percent=0, is_current=True,
            ))
        self.engine_patch = patch("app.api.projects.create_database_engine", return_value=self.engine)
        self.factory_patch = patch(
            "app.api.projects.create_session_factory",
            side_effect=lambda engine: sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
        )
        self.engine_patch.start()
        self.factory_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.engine_patch.stop()
        self.factory_patch.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_api_uses_persisted_audio_and_performs_no_database_writes(self) -> None:
        statements: list[str] = []

        def record_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement.lstrip().split(None, 1)[0].upper())

        event.listen(self.engine, "before_cursor_execute", record_statement)
        with patch("app.services.tts_timeline._probe_source_video_duration_ms", return_value=1_000), \
                patch("app.services.tts_timeline.get_edge_tts_voice", return_value=VOICE), \
                patch("app.services.tts_timeline.resolve_storage_path", return_value=self.root / "audio.mp3"):
            (self.root / "audio.mp3").write_bytes(b"already-persisted-audio")
            response = self.client.get(f"/projects/{PROJECT_ID}/tts-timeline-plan")
        event.remove(self.engine, "before_cursor_execute", record_statement)

        self.assertEqual(response.status_code, 200)
        plan = response.json()
        self.assertEqual(plan["original_video_duration_ms"], 1_000)
        self.assertEqual(plan["planned_output_video_duration_ms"], 1_200)
        self.assertEqual(plan["stretch_operations"][0]["added_duration_ms"], 200)
        self.assertTrue(plan["renderable"])
        self.assertFalse(any(statement in {"INSERT", "UPDATE", "DELETE"} for statement in statements))
        with Session(self.engine) as session:
            self.assertEqual(len(session.scalars(select(Artifact)).all()), 1)
            self.assertEqual(session.get(Segment, SEGMENT_ID).start_seconds, Decimal("0.000"))

    def test_stale_artifact_returns_structured_blocker(self) -> None:
        with Session(self.engine) as session, session.begin():
            artifact = session.scalar(select(Artifact).where(Artifact.segment_id == SEGMENT_ID))
            artifact.provenance_fingerprint = "stale"
        audio_path = self.root / "audio.mp3"
        audio_path.write_bytes(b"already-persisted-audio")
        with patch("app.services.tts_timeline._probe_source_video_duration_ms", return_value=1_000), \
                patch("app.services.tts_timeline.get_edge_tts_voice", return_value=VOICE), \
                patch("app.services.tts_timeline.resolve_storage_path", return_value=audio_path):
            response = self.client.get(f"/projects/{PROJECT_ID}/tts-timeline-plan")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["renderable"])
        self.assertIsNone(payload["planned_output_video_duration_ms"])
        self.assertIn("tts_artifact_stale", {issue["code"] for issue in payload["issues"]})

    def test_missing_artifact_returns_structured_blocker(self) -> None:
        with Session(self.engine) as session, session.begin():
            artifact = session.scalar(select(Artifact).where(Artifact.segment_id == SEGMENT_ID))
            session.delete(artifact)
        with patch("app.services.tts_timeline._probe_source_video_duration_ms", return_value=1_000), \
                patch("app.services.tts_timeline.get_edge_tts_voice", return_value=VOICE):
            response = self.client.get(f"/projects/{PROJECT_ID}/tts-timeline-plan")
        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["renderable"])
        self.assertIn("tts_artifact_missing", {issue["code"] for issue in payload["issues"]})


if __name__ == "__main__":
    unittest.main()
