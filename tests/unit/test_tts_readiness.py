"""Persisted Project TTS readiness API and deterministic validation tests."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Job, Project, Segment
from app.models.base import Base
from app.services.tts_readiness import _evaluate_segments


PROJECT_ID = uuid.UUID("ce2a1a28-dfc6-46cc-8494-02829cc9ca01")
JOB_ID = uuid.UUID("ce2a1a28-dfc6-46cc-8494-02829cc9ca02")
SEGMENT_ID = uuid.UUID("ce2a1a28-dfc6-46cc-8494-02829cc9ca03")


class TTSReadinessApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "readiness.sqlite"
        self.engine = create_engine(f"sqlite+pysqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session, session.begin():
            session.add(
                Project(id=PROJECT_ID, name="readiness test", current_revision=0)
            )
            session.add(
                Job(
                    id=JOB_ID,
                    project_id=PROJECT_ID,
                    operation_type="transcribe_translate",
                    input_revision=0,
                    status="succeeded",
                    stage="translation_ready",
                    created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                )
            )
            session.add(
                Segment(
                    id=SEGMENT_ID,
                    project_id=PROJECT_ID,
                    position=0,
                    start_seconds=0,
                    end_seconds=1,
                    source_text="Hello there.",
                    translated_text="Xin chào.",
                    revision=0,
                )
            )
        self.engine_patch = patch(
            "app.api.projects.create_database_engine", return_value=self.engine
        )
        self.factory_patch = patch(
            "app.api.projects.create_session_factory",
            side_effect=lambda engine: sessionmaker(
                bind=engine, autoflush=False, expire_on_commit=False
            ),
        )
        self.engine_patch.start()
        self.factory_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.engine_patch.stop()
        self.factory_patch.stop()
        self.engine.dispose()
        self.temp_directory.cleanup()

    def check(self, project_id: uuid.UUID = PROJECT_ID):
        return self.client.get(f"/projects/{project_id}/tts-readiness")

    def add_segment(
        self,
        *,
        segment_id: uuid.UUID,
        position: int,
        start: float,
        end: float,
        source: str | None = "Source.",
        translated: str | None = "Bản dịch.",
        revision: int = 0,
    ) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(
                Segment(
                    id=segment_id,
                    project_id=PROJECT_ID,
                    position=position,
                    start_seconds=start,
                    end_seconds=end,
                    source_text=source,
                    translated_text=translated,
                    revision=revision,
                )
            )

    def test_fully_valid_project_is_ready(self) -> None:
        response = self.check()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["project_id"], str(PROJECT_ID))
        self.assertTrue(body["ready"])
        self.assertEqual(body["segment_count"], 1)
        self.assertEqual(body["blocking_error_count"], 0)
        self.assertEqual(body["warning_count"], 0)
        self.assertEqual(body["issues"], [])

    def test_missing_project_returns_404(self) -> None:
        self.assertEqual(self.check(uuid.uuid4()).status_code, 404)

    def test_project_without_segments_is_blocked(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(Segment.__table__.delete())
        body = self.check().json()
        self.assertFalse(body["ready"])
        self.assertEqual(body["segment_count"], 0)
        self.assertIn("project_transcript_empty", [issue["code"] for issue in body["issues"]])

    def test_missing_and_whitespace_translation_are_blocking(self) -> None:
        for value, code in ((None, "translation_missing"), (" \n ", "translation_empty")):
            with self.subTest(value=value):
                with Session(self.engine) as session, session.begin():
                    session.get(Segment, SEGMENT_ID).translated_text = value
                body = self.check().json()
                self.assertFalse(body["ready"])
                self.assertIn(code, [issue["code"] for issue in body["issues"]])

    def test_invalid_source_and_oversized_translation_are_blocking(self) -> None:
        with Session(self.engine) as session, session.begin():
            segment = session.get(Segment, SEGMENT_ID)
            segment.source_text = "   "
            segment.translated_text = "你" * 10_001
        body = self.check().json()
        codes = [issue["code"] for issue in body["issues"]]
        self.assertIn("source_text_missing", codes)
        self.assertIn("translation_too_long", codes)
        self.assertFalse(body["ready"])

    def test_invalid_timestamp_range_is_reported_by_segment_validator(self) -> None:
        row = SimpleNamespace(
            id=SEGMENT_ID,
            project_id=PROJECT_ID,
            position=0,
            start_seconds=Decimal("1.000"),
            end_seconds=Decimal("0.500"),
            source_text="Source.",
            translated_text="Bản dịch.",
            revision=0,
        )
        issues = _evaluate_segments(PROJECT_ID, 0, [row])
        self.assertIn("timestamp_range_invalid", [issue.code for issue in issues])

    def test_invalid_millisecond_precision_and_duplicate_ids_are_blocking(self) -> None:
        rows = [
            SimpleNamespace(
                id=SEGMENT_ID,
                project_id=PROJECT_ID,
                position=0,
                start_seconds=Decimal("0.0005"),
                end_seconds=Decimal("1.000"),
                source_text="Source.",
                translated_text="Bản dịch.",
                revision=0,
            ),
            SimpleNamespace(
                id=SEGMENT_ID,
                project_id=PROJECT_ID,
                position=1,
                start_seconds=Decimal("1.000"),
                end_seconds=Decimal("2.000"),
                source_text="Source 2.",
                translated_text="Bản dịch 2.",
                revision=0,
            ),
        ]
        issues = _evaluate_segments(PROJECT_ID, 0, rows)
        codes = [issue.code for issue in issues]
        self.assertIn("timestamps_invalid", codes)
        self.assertEqual(codes.count("segment_id_duplicate"), 2)

    def test_active_job_blocks_readiness_but_old_terminal_jobs_do_not(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.add_all(
                [
                    Job(
                        id=uuid.UUID("ce2a1a28-dfc6-46cc-8494-02829cc9ca04"),
                        project_id=PROJECT_ID,
                        operation_type="transcribe_translate",
                        input_revision=0,
                        status="failed",
                        stage="failed",
                        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    ),
                    Job(
                        id=uuid.UUID("ce2a1a28-dfc6-46cc-8494-02829cc9ca05"),
                        project_id=PROJECT_ID,
                        operation_type="transcribe_translate",
                        input_revision=0,
                        status="interrupted",
                        stage="interrupted",
                        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    ),
                ]
            )
        self.assertTrue(self.check().json()["ready"])

        with Session(self.engine) as session, session.begin():
            session.add(
                Job(
                    id=uuid.UUID("ce2a1a28-dfc6-46cc-8494-02829cc9ca06"),
                    project_id=PROJECT_ID,
                    operation_type="transcribe_translate",
                    input_revision=0,
                    status="running",
                    stage="transcribing",
                )
            )
        body = self.check().json()
        self.assertFalse(body["ready"])
        self.assertIn("project_job_active", [issue["code"] for issue in body["issues"]])

    def test_latest_failed_job_makes_workflow_not_ready(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.add(
                Job(
                    id=uuid.UUID("ce2a1a28-dfc6-46cc-8494-02829cc9ca07"),
                    project_id=PROJECT_ID,
                    operation_type="transcribe_translate",
                    input_revision=0,
                    status="failed",
                    stage="failed",
                    created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
                )
            )
        body = self.check().json()
        self.assertFalse(body["ready"])
        self.assertIn("project_translation_not_ready", [issue["code"] for issue in body["issues"]])

    def test_timing_warnings_do_not_block_and_include_overlap_and_high_wps(self) -> None:
        self.add_segment(
            segment_id=uuid.UUID("ce2a1a28-dfc6-46cc-8494-02829cc9ca08"),
            position=1,
            start=0.9,
            end=1.1,
            translated="Xin chào bạn hôm nay chúng ta cùng bắt đầu.",
        )
        body = self.check().json()
        self.assertTrue(body["ready"])
        self.assertEqual(body["blocking_error_count"], 0)
        codes = {issue["code"] for issue in body["issues"]}
        self.assertIn("short_speaking_window", codes)
        self.assertIn("high_estimated_wps", codes)
        self.assertIn("original_timestamps_overlap", codes)

    def test_issue_order_is_deterministic_and_validation_performs_no_writes(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.get(Segment, SEGMENT_ID).translated_text = None
        with self.engine.connect() as connection:
            before = connection.execute(
                select(
                    Segment.id,
                    Segment.source_text,
                    Segment.start_seconds,
                    Segment.end_seconds,
                    Segment.translated_text,
                    Segment.position,
                ).where(Segment.project_id == PROJECT_ID)
            ).all()
        statements: list[str] = []

        def record_statement(_connection, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
                statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", record_statement)
        try:
            first = self.check().json()
            second = self.check().json()
        finally:
            event.remove(self.engine, "before_cursor_execute", record_statement)
        with self.engine.connect() as connection:
            after = connection.execute(
                select(
                    Segment.id,
                    Segment.source_text,
                    Segment.start_seconds,
                    Segment.end_seconds,
                    Segment.translated_text,
                    Segment.position,
                ).where(Segment.project_id == PROJECT_ID)
            ).all()
        self.assertEqual(first["issues"], second["issues"])
        self.assertEqual(before, after)
        self.assertEqual(statements, [])

if __name__ == "__main__":
    unittest.main()
