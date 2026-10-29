from __future__ import annotations

import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Job, Project, Segment
from app.models.base import Base
from app.services.translation import TranslationProviderError, TranslationResult
from app.workers.job_worker import process_claimed_job


PROJECT_ID = uuid.UUID("db7dc46e-42ea-4ffb-9f22-8c60f277f9e8")
JOB_ID = uuid.UUID("e14a75cf-cc84-4fa5-a87f-7962aee15bd3")
SEGMENT_ID = uuid.UUID("a69a7139-9347-4ea4-a6ca-d9027ba2c2f9")


class TranslationOnlyWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session, session.begin():
            session.add(Project(id=PROJECT_ID, name="retry", current_revision=0))
            session.add(Job(
                id=JOB_ID, project_id=PROJECT_ID, operation_type="translate_existing",
                input_revision=0, status="running", stage="claimed",
            ))
            session.add(Segment(
                id=SEGMENT_ID, project_id=PROJECT_ID, position=0,
                start_seconds=1, end_seconds=2, source_text="Hello", revision=0,
            ))

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_translation_retry_skips_whisper_and_completes_only_after_translation(self) -> None:
        result = TranslationResult(segment_count=1, batch_count=1, model="selected-model")
        with (
            patch("app.workers.job_worker.verify_gemini_model_listed", return_value="selected-model"),
            patch("app.workers.job_worker.transcribe_project") as transcribe,
            patch("app.workers.job_worker.translate_project", return_value=result) as translate,
        ):
            process_claimed_job(self.engine, JOB_ID)
        transcribe.assert_not_called()
        translate.assert_called_once()
        with Session(self.engine) as session:
            job = session.get(Job, JOB_ID)
            segment = session.get(Segment, SEGMENT_ID)
            self.assertEqual((job.status, job.stage), ("succeeded", "translation_ready"))
            self.assertEqual((segment.id, segment.source_text, segment.start_seconds, segment.end_seconds),
                             (SEGMENT_ID, "Hello", 1, 2))
            self.assertIsNone(segment.translated_text)

    def test_unavailable_model_fails_before_expensive_asr(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.get(Job, JOB_ID).operation_type = "transcribe_translate"
        with (
            patch(
                "app.workers.job_worker.verify_gemini_model_listed",
                side_effect=TranslationProviderError(
                    "Configured Gemini model missing-model is unavailable for generateContent.",
                    status_code=404, model="missing-model",
                ),
            ),
            patch("app.workers.job_worker.transcribe_project") as transcribe,
        ):
            process_claimed_job(self.engine, JOB_ID)
        transcribe.assert_not_called()
        with Session(self.engine) as session:
            job = session.get(Job, JOB_ID)
            self.assertEqual(job.status, "failed")
            self.assertIn("missing-model", job.safe_error)
            self.assertIn("generateContent", job.safe_error)


if __name__ == "__main__":
    unittest.main()
