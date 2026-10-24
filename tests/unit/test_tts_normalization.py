"""Normalization Job integration tests with local SQLite and synthetic MP3 media."""

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
from app.services.audio_normalization import measured_audio_duration_ms
from app.services.audio_normalization import AudioNormalizationError
from app.services.tts import translation_fingerprint
from app.workers.job_worker import process_claimed_job
from test_audio_normalization import make_mp3


PROJECT_ID = uuid.UUID("a75f0fb4-c706-4770-a259-65f424c08101")
SEGMENT_ID = uuid.UUID("a75f0fb4-c706-4770-a259-65f424c08102")
TRANSLATION_JOB_ID = uuid.UUID("a75f0fb4-c706-4770-a259-65f424c08103")
TTS_JOB_ID = uuid.UUID("a75f0fb4-c706-4770-a259-65f424c08104")
NORMALIZE_JOB_ID = uuid.UUID("a75f0fb4-c706-4770-a259-65f424c08105")
VOICE = "vi-VN-HoaiMyNeural"


class TTSNormalizationJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.storage = self.root / "storage"
        self.engine = create_engine(f"sqlite+pysqlite:///{self.root / 'normalization.sqlite'}")
        Base.metadata.create_all(self.engine)
        self.audio_reference = f"projects/{PROJECT_ID}/jobs/{TTS_JOB_ID}/tts/{SEGMENT_ID}.mp3"
        self.audio_path = self.storage / Path(self.audio_reference)
        self.audio_path.parent.mkdir(parents=True, exist_ok=True)
        make_mp3(self.audio_path, [("speech", 0.3), ("silence", 1.0)])
        self.old_audio = self.audio_path.read_bytes()
        self.original_duration_ms = measured_audio_duration_ms(self.audio_path)
        with Session(self.engine) as session, session.begin():
            session.add(Project(
                id=PROJECT_ID, name="normalization test", current_revision=0,
                source_media_reference=f"projects/{PROJECT_ID}/source/video.mp4",
            ))
            session.add(Job(
                id=TRANSLATION_JOB_ID, project_id=PROJECT_ID,
                operation_type="transcribe_translate", input_revision=0,
                status="succeeded", stage="translation_ready",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ))
            session.add(Job(
                id=TTS_JOB_ID, project_id=PROJECT_ID, operation_type="tts_optimize",
                input_revision=0, status="succeeded", stage="tts_optimization_complete",
            ))
            session.add(Segment(
                id=SEGMENT_ID, project_id=PROJECT_ID, position=0,
                start_seconds=Decimal("0.000"), end_seconds=Decimal("0.200"),
                source_text="Hello", translated_text="Xin chào", revision=0,
            ))
            session.add(Artifact(
                project_id=PROJECT_ID, job_id=TTS_JOB_ID, segment_id=SEGMENT_ID,
                revision=0, media_type="audio/mpeg", storage_reference=self.audio_reference,
                duration_ms=self.original_duration_ms,
                provenance_fingerprint=translation_fingerprint("Xin chào", VOICE, 35),
                voice=VOICE, rate_percent=35, is_current=True,
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

    def _patch_storage(self):
        return (
            patch("app.services.uploads.get_storage_root", return_value=self.storage),
            patch("app.api.projects.get_edge_tts_voice", return_value=VOICE),
            patch("app.services.tts_timeline.get_edge_tts_voice", return_value=VOICE),
            patch("app.services.tts_timeline._probe_source_video_duration_ms", return_value=250),
        )

    def _run_job(self, job_id: uuid.UUID = NORMALIZE_JOB_ID) -> None:
        with Session(self.engine) as session, session.begin():
            session.get(Job, job_id).status = "running"
        process_claimed_job(self.engine, job_id)

    def test_existing_optimized_audio_is_normalized_without_edge_tts_and_reanalyzed(self) -> None:
        client = TestClient(app)
        patches = self._patch_storage()
        for item in patches:
            item.start()
        try:
            queued = client.post(f"/projects/{PROJECT_ID}/tts-normalization-jobs")
            duplicate = client.post(f"/projects/{PROJECT_ID}/tts-normalization-jobs")
            self.assertEqual(queued.status_code, 202)
            self.assertEqual(duplicate.status_code, 409)
            job_id = uuid.UUID(queued.json()["id"])
            with Session(self.engine) as session:
                self.assertEqual(session.get(Job, job_id).operation_type, "tts_normalize")
                self.assertEqual(session.get(Artifact, session.scalar(select(Artifact.id))).rate_percent, 35)
            with patch("app.services.tts.edge_tts.Communicate", side_effect=AssertionError("Edge-TTS must not run")):
                self._run_job(job_id)

            with Session(self.engine) as session:
                job = session.get(Job, job_id)
                old = session.get(Artifact, session.scalar(select(Artifact.id).where(Artifact.job_id == TTS_JOB_ID)))
                current = session.scalar(select(Artifact).where(Artifact.job_id == job_id))
                segment = session.get(Segment, SEGMENT_ID)
                self.assertEqual((job.status, job.stage), ("succeeded", "tts_normalization_complete"))
                self.assertFalse(old.is_current)
                self.assertTrue(current.is_current)
                self.assertEqual((current.rate_percent, current.provenance_fingerprint), (35, translation_fingerprint("Xin chào", VOICE, 35)))
                self.assertEqual((segment.start_seconds, segment.end_seconds, segment.translated_text), (Decimal("0.000"), Decimal("0.200"), "Xin chào"))
                self.assertTrue(self.audio_path.is_file())
                self.assertEqual(self.audio_path.read_bytes(), self.old_audio)
            normalized_path = self.storage / Path(f"projects/{PROJECT_ID}/jobs/{job_id}/tts/{SEGMENT_ID}.mp3")
            normalized_ms = measured_audio_duration_ms(normalized_path)
            self.assertLess(normalized_ms, self.original_duration_ms)
            audio_response = client.get(f"/projects/{PROJECT_ID}/segments/{SEGMENT_ID}/audio")
            listed = client.get(f"/projects/{PROJECT_ID}/tts-audio")
            plan = client.get(f"/projects/{PROJECT_ID}/tts-timeline-plan")
            result = client.get(f"/projects/{PROJECT_ID}/tts-normalization-jobs/{job_id}")
            self.assertEqual(audio_response.content, normalized_path.read_bytes())
            self.assertEqual(listed.json()[0]["duration_ms"], normalized_ms)
            self.assertEqual(plan.status_code, 200)
            self.assertFalse(plan.json()["renderable"])
            self.assertGreater(plan.json()["blocking_issue_count"], 0)
            self.assertEqual(plan.json()["segments"][0]["tts_audio_duration_ms"], normalized_ms)
            self.assertEqual(result.status_code, 200)
            report = result.json()
            self.assertEqual((report["files_processed"], report["files_shortened"]), (1, 1))
            self.assertEqual(report["segments"][0]["final_duration_ms"], normalized_ms)
            self.assertEqual(report["segments"][0]["rate_percent"], 35)
        finally:
            for item in reversed(patches):
                item.stop()

    def test_repeated_normalization_is_idempotent_and_preserves_optimized_rate(self) -> None:
        client = TestClient(app)
        patches = self._patch_storage()
        for item in patches:
            item.start()
        try:
            first_job = uuid.UUID(client.post(f"/projects/{PROJECT_ID}/tts-normalization-jobs").json()["id"])
            self._run_job(first_job)
            first_path = self.storage / Path(f"projects/{PROJECT_ID}/jobs/{first_job}/tts/{SEGMENT_ID}.mp3")
            first_bytes = first_path.read_bytes()
            first_duration = measured_audio_duration_ms(first_path)

            second_job = uuid.UUID(client.post(f"/projects/{PROJECT_ID}/tts-normalization-jobs").json()["id"])
            self._run_job(second_job)
            second_path = self.storage / Path(f"projects/{PROJECT_ID}/jobs/{second_job}/tts/{SEGMENT_ID}.mp3")
            result = client.get(f"/projects/{PROJECT_ID}/tts-normalization-jobs/{second_job}").json()
            with Session(self.engine) as session:
                current = session.scalar(select(Artifact).where(
                    Artifact.job_id == second_job, Artifact.is_current.is_(True)
                ))
            self.assertEqual(second_path.read_bytes(), first_bytes)
            self.assertEqual(measured_audio_duration_ms(second_path), first_duration)
            self.assertEqual((current.rate_percent, current.duration_ms), (35, first_duration))
            self.assertEqual((result["files_processed"], result["files_shortened"], result["total_recovered_ms"]), (1, 0, 0))
            self.assertFalse(result["segments"][0]["trimmed"])
        finally:
            for item in reversed(patches):
                item.stop()

    def test_artifact_snapshot_order_does_not_cause_false_stale_failure(self) -> None:
        # Segment order differs from UUID order, matching the ordering of the two DB queries.
        second_segment_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        second_reference = f"projects/{PROJECT_ID}/jobs/{TTS_JOB_ID}/tts/{second_segment_id}.mp3"
        second_path = self.storage / Path(second_reference)
        second_path.write_bytes(self.old_audio)
        with Session(self.engine) as session, session.begin():
            session.add(Segment(
                id=second_segment_id, project_id=PROJECT_ID, position=1,
                start_seconds=Decimal("0.300"), end_seconds=Decimal("0.500"),
                source_text="World", translated_text="Thế giới", revision=0,
            ))
            session.add(Artifact(
                project_id=PROJECT_ID, job_id=TTS_JOB_ID, segment_id=second_segment_id,
                revision=0, media_type="audio/mpeg", storage_reference=second_reference,
                duration_ms=self.original_duration_ms,
                provenance_fingerprint=translation_fingerprint("Thế giới", VOICE, 35),
                voice=VOICE, rate_percent=35, is_current=True,
            ))

        patches = self._patch_storage()
        for item in patches:
            item.start()
        try:
            client = TestClient(app)
            response = client.post(f"/projects/{PROJECT_ID}/tts-normalization-jobs")
            self.assertEqual(response.status_code, 202)
            job_id = uuid.UUID(response.json()["id"])
            with patch("app.services.tts.edge_tts.Communicate", side_effect=AssertionError("Edge-TTS must not run")):
                self._run_job(job_id)
            with Session(self.engine) as session:
                job = session.get(Job, job_id)
                current = session.scalars(select(Artifact).where(Artifact.is_current.is_(True))).all()
            self.assertEqual((job.status, job.stage), ("succeeded", "tts_normalization_complete"))
            self.assertEqual(len(current), 2)
            self.assertEqual({artifact.job_id for artifact in current}, {job_id})
            self.assertTrue(all(artifact.rate_percent == 35 for artifact in current))
        finally:
            for item in reversed(patches):
                item.stop()

    def test_translation_change_before_worker_claim_fails_without_replacing_old_audio(self) -> None:
        client = TestClient(app)
        patches = self._patch_storage()
        for item in patches:
            item.start()
        try:
            response = client.post(f"/projects/{PROJECT_ID}/tts-normalization-jobs")
            job_id = uuid.UUID(response.json()["id"])
            with Session(self.engine) as session, session.begin():
                session.get(Segment, SEGMENT_ID).translated_text = "Bản dịch đã đổi"
            self._run_job(job_id)
            with Session(self.engine) as session:
                job = session.get(Job, job_id)
                current = session.scalar(select(Artifact).where(Artifact.is_current.is_(True)))
            self.assertEqual(job.status, "failed")
            self.assertTrue(current.is_current)
            self.assertEqual(current.job_id, TTS_JOB_ID)
            self.assertEqual(self.audio_path.read_bytes(), self.old_audio)
        finally:
            for item in reversed(patches):
                item.stop()

    def test_normalization_failure_rolls_back_staged_generation(self) -> None:
        client = TestClient(app)
        patches = self._patch_storage()
        for item in patches:
            item.start()
        try:
            job_id = uuid.UUID(client.post(f"/projects/{PROJECT_ID}/tts-normalization-jobs").json()["id"])

            def fail_after_staging(source: Path, destination: Path):
                destination.write_bytes(b"partial candidate must not publish")
                raise AudioNormalizationError("Audio boundaries could not be analyzed.")

            with patch("app.services.tts_normalization.normalize_audio_file", side_effect=fail_after_staging):
                self._run_job(job_id)
            final_dir = self.storage / Path(f"projects/{PROJECT_ID}/jobs/{job_id}/tts")
            temporary_dir = self.storage / Path(f"projects/{PROJECT_ID}/tts-temp/{job_id}")
            with Session(self.engine) as session:
                job = session.get(Job, job_id)
                current = session.scalar(select(Artifact).where(Artifact.is_current.is_(True)))
            self.assertEqual(job.status, "failed")
            self.assertTrue(current.is_current)
            self.assertEqual(current.job_id, TTS_JOB_ID)
            self.assertEqual(self.audio_path.read_bytes(), self.old_audio)
            self.assertFalse(final_dir.exists())
            self.assertFalse(temporary_dir.exists())
        finally:
            for item in reversed(patches):
                item.stop()

