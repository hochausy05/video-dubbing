from __future__ import annotations

import tempfile
import hashlib
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.models import Artifact, Job, Project, Segment
from app.models.base import Base
from app.services.audio_normalization import AudioNormalizationResult, write_normalization_metadata
from app.services.av_sync_optimization import process_joint_optimization
from app.services.tts_artifacts import TTS_MEDIA_TYPE, translation_fingerprint
from app.services.uploads import source_relative_path


PROJECT_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")
SEGMENT_ID = uuid.UUID("40000000-0000-0000-0000-000000000002")
SOURCE_JOB_ID = uuid.UUID("40000000-0000-0000-0000-000000000003")
JOINT_JOB_ID = uuid.UUID("40000000-0000-0000-0000-000000000004")
VOICE = "vi-VN-HoaiMyNeural"


class JointOptimizationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.engine = create_engine(f"sqlite+pysqlite:///{self.root / 'test.sqlite'}")
        Base.metadata.create_all(self.engine)
        self.source = self.root.joinpath(*source_relative_path(PROJECT_ID).parts)
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b"source-video")
        self.old_reference = f"projects/{PROJECT_ID}/jobs/{SOURCE_JOB_ID}/tts/{SEGMENT_ID}.mp3"
        old_audio = self.root.joinpath(*Path(self.old_reference).parts)
        old_audio.parent.mkdir(parents=True)
        old_audio.write_bytes(b"valid-old-audio")
        with Session(self.engine) as session, session.begin():
            session.add(Project(
                id=PROJECT_ID, name="joint test", selected_voice=VOICE,
                source_media_reference=source_relative_path(PROJECT_ID).as_posix(),
            ))
            session.add_all([
                Job(id=SOURCE_JOB_ID, project_id=PROJECT_ID, operation_type="tts",
                    input_revision=0, status="succeeded", stage="tts_ready"),
                Job(id=JOINT_JOB_ID, project_id=PROJECT_ID, operation_type="av_sync_optimize",
                    input_revision=0, status="running", stage="claimed"),
            ])
            session.add(Segment(
                id=SEGMENT_ID, project_id=PROJECT_ID, position=0,
                start_seconds=Decimal("0.000"), end_seconds=Decimal("0.400"),
                source_text="source", translated_text="Xin chào", revision=0,
            ))
            session.add(Artifact(
                id=uuid.UUID("40000000-0000-0000-0000-000000000005"),
                project_id=PROJECT_ID, job_id=SOURCE_JOB_ID, segment_id=SEGMENT_ID,
                revision=0, media_type=TTS_MEDIA_TYPE, storage_reference=self.old_reference,
                duration_ms=600, provenance_fingerprint=translation_fingerprint("Xin chào", VOICE, 35),
                voice=VOICE, rate_percent=35, is_current=True,
            ))
        self.storage_patch = patch("app.services.uploads.get_storage_root", return_value=self.root)
        self.storage_patch.start()
        self.probe_patch = patch(
            "app.services.av_sync_optimization._probe_source_timing",
            return_value=(500_000, 10_000),
        )
        self.probe_patch.start()
        self.duration_us_patch = patch(
            "app.services.av_sync_optimization.measured_audio_duration_us",
            side_effect=self._duration_us,
        )
        self.duration_us_patch.start()
        self.duration_ms_patch = patch(
            "app.services.av_sync_optimization.measured_audio_duration_ms", return_value=400,
        )
        self.duration_ms_patch.start()

    def tearDown(self) -> None:
        self.duration_ms_patch.stop()
        self.duration_us_patch.stop()
        self.probe_patch.stop()
        self.storage_patch.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def _duration_us(self, path: Path) -> int:
        if "-25.mp3" in path.name:
            return 400_000
        if "-0.mp3" in path.name:
            return 1_010_000
        return 600_000

    @staticmethod
    def _synthesizer(*, fail_rate: int | None = None, calls: list[int]):
        async def synthesize(_text, path, *, rate_percent, attempt_callback, **_kwargs):
            calls.append(rate_percent)
            attempt_callback(1)
            if rate_percent == fail_rate:
                raise RuntimeError("synthetic provider failure")
            path.write_bytes(b"new-complete-audio")
            path.with_name(f"{path.stem}.original.mp3").write_bytes(b"original-audio")
            write_normalization_metadata(path, AudioNormalizationResult(
                original_duration_ms=400, final_duration_ms=400, removed_silence_ms=0,
                trimmed=False, skipped_reason="synthetic fixture",
            ).as_metadata())
            return 400
        return synthesize

    def test_selects_measured_25_percent_candidate_and_publishes_atomically(self) -> None:
        calls: list[int] = []
        process_joint_optimization(
            self.engine, project_id=PROJECT_ID, job_id=JOINT_JOB_ID, input_revision=0,
            synthesizer=self._synthesizer(calls=calls),
        )
        with Session(self.engine) as session:
            rows = session.scalars(select(Artifact).where(Artifact.segment_id == SEGMENT_ID)).all()
            current = [row for row in rows if row.is_current]
            job = session.get(Job, JOINT_JOB_ID)
            self.assertEqual(calls, [25, 0])
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0].rate_percent, 25)
            self.assertEqual(current[0].job_id, JOINT_JOB_ID)
            self.assertEqual(job.status, "succeeded")
            self.assertEqual(job.stage, "joint_optimization_complete")
            self.assertTrue(job.result_json["renderable"])
            self.assertTrue(job.result_json["renderer_supported"])
            self.assertTrue(job.result_json["coverage_precision_verified"])
            self.assertEqual(job.result_json["source_video_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
            self.assertEqual(job.result_json["segments"][0]["artifact_id"], str(current[0].id))
            self.assertTrue((self.root / "projects" / str(PROJECT_ID) / "jobs" / str(JOINT_JOB_ID)
                             / "tts" / f"{SEGMENT_ID}.mp3").is_file())

    def test_failed_candidate_preserves_existing_artifact_and_cleans_staging(self) -> None:
        calls: list[int] = []
        with self.assertRaisesRegex(RuntimeError, "synthetic provider failure"):
            process_joint_optimization(
                self.engine, project_id=PROJECT_ID, job_id=JOINT_JOB_ID, input_revision=0,
                synthesizer=self._synthesizer(fail_rate=0, calls=calls),
            )
        with Session(self.engine) as session:
            rows = session.scalars(select(Artifact).where(Artifact.segment_id == SEGMENT_ID)).all()
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0].is_current)
            self.assertEqual(rows[0].job_id, SOURCE_JOB_ID)
        self.assertFalse((self.root / "projects" / str(PROJECT_ID) / "tts-temp" / str(JOINT_JOB_ID)).exists())
        self.assertFalse((self.root / "projects" / str(PROJECT_ID) / "jobs" / str(JOINT_JOB_ID) / "tts").exists())

    def test_stale_translation_during_candidate_generation_discards_plan(self) -> None:
        async def edit_during_generation(_text, path, *, attempt_callback, **_kwargs):
            attempt_callback(1)
            path.write_bytes(b"candidate")
            path.with_name(f"{path.stem}.original.mp3").write_bytes(b"original-audio")
            write_normalization_metadata(path, AudioNormalizationResult(
                original_duration_ms=400, final_duration_ms=400, removed_silence_ms=0,
                trimmed=False, skipped_reason="synthetic fixture",
            ).as_metadata())
            with Session(self.engine) as session, session.begin():
                segment = session.get(Segment, SEGMENT_ID)
                segment.translated_text = "changed during work"
            return 400

        with self.assertRaisesRegex(ValueError, "inputs changed"):
            process_joint_optimization(
                self.engine, project_id=PROJECT_ID, job_id=JOINT_JOB_ID, input_revision=0,
                synthesizer=edit_during_generation,
            )
        with Session(self.engine) as session:
            rows = session.scalars(select(Artifact).where(Artifact.segment_id == SEGMENT_ID)).all()
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0].is_current)

    def test_database_publication_failure_rolls_back_and_cleans_files(self) -> None:
        def reject_joint_artifact(session, _flush_context, _instances):
            if any(isinstance(row, Artifact) and row.job_id == JOINT_JOB_ID for row in session.new):
                raise RuntimeError("synthetic publication failure")

        event.listen(Session, "before_flush", reject_joint_artifact)
        calls: list[int] = []
        try:
            with self.assertRaisesRegex(RuntimeError, "synthetic publication failure"):
                process_joint_optimization(
                    self.engine, project_id=PROJECT_ID, job_id=JOINT_JOB_ID, input_revision=0,
                    synthesizer=self._synthesizer(calls=calls),
                )
        finally:
            event.remove(Session, "before_flush", reject_joint_artifact)
        with Session(self.engine) as session:
            rows = session.scalars(select(Artifact).where(Artifact.segment_id == SEGMENT_ID)).all()
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0].is_current)
        self.assertFalse((self.root / "projects" / str(PROJECT_ID) / "jobs" / str(JOINT_JOB_ID) / "tts").exists())


if __name__ == "__main__":
    unittest.main()
