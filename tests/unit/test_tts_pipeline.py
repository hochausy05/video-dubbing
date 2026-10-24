"""TTS artifact publication and enqueue API tests using isolated SQLite storage."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Artifact, Job, Project, Segment
from app.models.base import Base
from app.services.tts import TTSError, generate_project_tts
from app.workers.job_worker import process_claimed_job


PROJECT_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e01")
TRANSLATION_JOB_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e02")
TTS_JOB_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e03")
SEGMENT_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e04")


class TtsPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.engine = create_engine(f"sqlite+pysqlite:///{self.root / 'tts.sqlite'}")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session, session.begin():
            session.add(Project(id=PROJECT_ID, name="tts test", current_revision=0))
            session.add(Job(
                id=TRANSLATION_JOB_ID, project_id=PROJECT_ID,
                operation_type="transcribe_translate", input_revision=0,
                status="succeeded", stage="translation_ready",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ))
            session.add(Segment(
                id=SEGMENT_ID, project_id=PROJECT_ID, position=0,
                start_seconds=Decimal("2.000"), end_seconds=Decimal("4.000"),
                source_text="你好", translated_text="Xin chào Việt Nam.", revision=0,
            ))
            session.add(Job(
                id=TTS_JOB_ID, project_id=PROJECT_ID, operation_type="tts",
                input_revision=0, status="running", stage="generating_tts",
            ))
        self.engine_patch = patch("app.api.projects.create_database_engine", return_value=self.engine)
        self.factory_patch = patch(
            "app.api.projects.create_session_factory",
            side_effect=lambda engine: sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
        )
        self.engine_patch.start()
        self.factory_patch.start()

    def tearDown(self) -> None:
        self.engine_patch.stop()
        self.factory_patch.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_enqueue_requires_readiness_and_persists_tts_job(self) -> None:
        client = TestClient(app)
        blocked = client.post(f"/projects/{PROJECT_ID}/tts-jobs")
        self.assertEqual(blocked.status_code, 409)
        with Session(self.engine) as session, session.begin():
            session.get(Job, TTS_JOB_ID).status = "failed"
            session.add(Job(
                project_id=PROJECT_ID, operation_type="transcribe_translate", input_revision=0,
                status="succeeded", stage="translation_ready",
            ))
        accepted = client.post(f"/projects/{PROJECT_ID}/tts-jobs")
        self.assertEqual(accepted.status_code, 202)
        payload = accepted.json()
        self.assertEqual(payload["status"], "queued")
        with Session(self.engine) as session:
            persisted = session.get(Job, uuid.UUID(payload["id"]))
            self.assertEqual(persisted.operation_type, "tts")
            self.assertEqual(persisted.status, "queued")

    def test_all_audio_is_published_transactionally_and_segment_data_is_unchanged(self) -> None:
        async def fake_synthesis(text: str, path: Path, **kwargs) -> int:
            self.assertEqual(text, "Xin chào Việt Nam.")
            self.assertEqual(kwargs["voice"], "vi-VN-HoaiMyNeural")
            path.write_bytes(b"mock valid audio bytes")
            return 1_234

        stages: list[str] = []
        with patch("app.services.uploads.get_storage_root", return_value=self.root / "storage"), \
                patch("app.services.tts.get_edge_tts_voice", return_value="vi-VN-HoaiMyNeural"), \
                patch("app.services.tts.get_edge_tts_concurrency", return_value=2), \
                patch("app.services.tts.synthesize_segment", side_effect=fake_synthesis), \
                patch("app.workers.job_worker._set_running_job_stage", side_effect=lambda _engine, _job, stage: stages.append(stage)):
            process_claimed_job(self.engine, TTS_JOB_ID)
        with Session(self.engine) as session:
            job = session.get(Job, TTS_JOB_ID)
            artifact = session.scalar(select(Artifact).where(Artifact.segment_id == SEGMENT_ID))
            segment = session.get(Segment, SEGMENT_ID)
            self.assertEqual((job.status, job.stage), ("succeeded", "tts_ready"))
            self.assertEqual(artifact.duration_ms, 1_234)
            self.assertEqual(artifact.rate_percent, 0)
            self.assertEqual(artifact.voice, "vi-VN-HoaiMyNeural")
            self.assertTrue(artifact.is_current)
            self.assertEqual(segment.translated_text, "Xin chào Việt Nam.")
            self.assertEqual(segment.start_seconds, Decimal("2.000"))
            self.assertEqual(segment.end_seconds, Decimal("4.000"))
        self.assertIn("preparing_tts", stages)
        self.assertIn("generating_tts", stages)
        self.assertIn("validating_tts", stages)

        client = TestClient(app)
        readiness = client.get(f"/projects/{PROJECT_ID}/tts-readiness")
        self.assertEqual(readiness.status_code, 200)
        self.assertTrue(readiness.json()["ready"])
        with patch(
            "app.api.projects.resolve_storage_path",
            side_effect=lambda relative: self.root / "storage" / Path(relative),
        ), patch("app.api.projects.get_edge_tts_voice", return_value="vi-VN-HoaiMyNeural"):
            current_audio = client.get(f"/projects/{PROJECT_ID}/segments/{SEGMENT_ID}/audio")
            self.assertEqual(current_audio.status_code, 200)
            self.assertEqual(current_audio.content, b"mock valid audio bytes")
            current_list = client.get(f"/projects/{PROJECT_ID}/tts-audio")
            self.assertTrue(current_list.json()[0]["current"])
        edited = client.patch(
            f"/projects/{PROJECT_ID}/segments/{SEGMENT_ID}",
            json={"translated_text": "Xin chào Việt Nam mới."},
        )
        self.assertEqual(edited.status_code, 200)
        with patch(
            "app.api.projects.resolve_storage_path",
            side_effect=lambda relative: self.root / "storage" / Path(relative),
        ), patch("app.api.projects.get_edge_tts_voice", return_value="vi-VN-HoaiMyNeural"):
            audio = client.get(f"/projects/{PROJECT_ID}/tts-audio")
        self.assertEqual(audio.status_code, 200)
        self.assertFalse(audio.json()[0]["current"])

    def test_failed_regeneration_preserves_previous_current_artifact(self) -> None:
        prior_job_id = uuid.uuid4()
        with Session(self.engine) as session, session.begin():
            session.add(Job(
                id=prior_job_id, project_id=PROJECT_ID, operation_type="tts", input_revision=0,
                status="succeeded", stage="tts_ready",
            ))
            session.add(Artifact(
                project_id=PROJECT_ID, job_id=prior_job_id, segment_id=SEGMENT_ID,
                revision=0, media_type="audio/mpeg", storage_reference="projects/prior.mp3",
                duration_ms=900, provenance_fingerprint="old", voice="vi-VN-HoaiMyNeural",
                rate_percent=0, is_current=True,
            ))

        async def failed_synthesis(*_args, **_kwargs) -> int:
            raise TTSError("synthesis failed")

        with patch("app.services.uploads.get_storage_root", return_value=self.root / "storage"), \
                patch("app.services.tts.get_edge_tts_voice", return_value="vi-VN-HoaiMyNeural"), \
                patch("app.services.tts.get_edge_tts_concurrency", return_value=2), \
                patch("app.services.tts.synthesize_segment", side_effect=failed_synthesis):
            with self.assertRaises(TTSError):
                generate_project_tts(
                    self.engine, project_id=PROJECT_ID, job_id=TTS_JOB_ID, input_revision=0,
                    stage_callback=lambda _stage: None,
                )
        with Session(self.engine) as session:
            artifacts = session.scalars(select(Artifact).where(Artifact.project_id == PROJECT_ID)).all()
            self.assertEqual(len(artifacts), 1)
            self.assertTrue(artifacts[0].is_current)
            self.assertEqual(artifacts[0].duration_ms, 900)
        self.assertFalse((self.root / "storage" / "projects" / str(PROJECT_ID) / "tts-temp" / str(TTS_JOB_ID)).exists())


if __name__ == "__main__":
    unittest.main()
