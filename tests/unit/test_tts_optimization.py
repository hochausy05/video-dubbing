"""Deterministic duration-optimization worker and API service tests."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
import uuid
from decimal import Decimal
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from fastapi.testclient import TestClient
from edge_tts.exceptions import NoAudioReceived
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Artifact, Job, Project, Segment
from app.models.base import Base
from app.services.tts import TTSError, synthesize_segment, translation_fingerprint
from app.services.audio_normalization import write_normalization_metadata
from app.services.tts_optimization import (
    enqueue_tts_optimization,
    optimize_project_tts,
    read_tts_optimization_result,
)
from app.services.uploads import source_relative_path
from app.workers.job_worker import cleanup_interrupted_tts_optimization_files, process_claimed_job


PROJECT_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e21")
TRANSLATION_JOB_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e22")
TTS_JOB_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e23")
OPTIMIZATION_JOB_ID = uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e24")
SEGMENT_IDS = [
    uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e25"),
    uuid.UUID("6c232d83-296c-4d33-8b6b-81f7bd092e26"),
]
VOICE = "vi-VN-HoaiMyNeural"


class TtsOptimizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.storage = self.root / "storage"
        self.video_duration_ms = 1_000
        self.engine = create_engine(f"sqlite+pysqlite:///{self.root / 'optimization.sqlite'}")
        Base.metadata.create_all(self.engine)
        self._seed([1_800])

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _seed(self, durations: list[int], *, base_rates: list[int] | None = None) -> None:
        base_rates = base_rates or [0] * len(durations)
        source_reference = source_relative_path(PROJECT_ID).as_posix()
        with Session(self.engine) as session, session.begin():
            session.add(Project(
                id=PROJECT_ID, name="optimization test", source_media_reference=source_reference,
                current_revision=0,
            ))
            session.add(Job(
                id=TRANSLATION_JOB_ID, project_id=PROJECT_ID,
                operation_type="transcribe_translate", input_revision=0,
                status="succeeded", stage="translation_ready",
            ))
            session.add(Job(
                id=TTS_JOB_ID, project_id=PROJECT_ID, operation_type="tts", input_revision=0,
                status="succeeded", stage="tts_ready",
            ))
            session.add(Job(
                id=OPTIMIZATION_JOB_ID, project_id=PROJECT_ID, operation_type="tts_optimize",
                input_revision=0, status="running", stage="claimed",
            ))
            for index, duration_ms in enumerate(durations):
                segment_id = SEGMENT_IDS[index]
                start = Decimal(index)
                end = Decimal(index + 1)
                text = f"Xin chào {index}."
                session.add(Segment(
                    id=segment_id, project_id=PROJECT_ID, position=index,
                    start_seconds=start, end_seconds=end, source_text=f"Source {index}.",
                    translated_text=text, revision=0,
                ))
                session.flush()
                reference = f"projects/{PROJECT_ID}/jobs/{TTS_JOB_ID}/tts/{segment_id}.mp3"
                session.add(Artifact(
                    project_id=PROJECT_ID, job_id=TTS_JOB_ID, segment_id=segment_id,
                    revision=0, media_type="audio/mpeg", storage_reference=reference,
                    duration_ms=duration_ms,
                    provenance_fingerprint=translation_fingerprint(text, VOICE, base_rates[index]),
                    voice=VOICE, rate_percent=base_rates[index], is_current=True,
                ))
                audio_path = self.storage / Path(reference)
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                audio_path.write_bytes(b"valid fixture audio")
                write_normalization_metadata(audio_path, {
                    "version": "boundary-silence-v1",
                    "original_duration_ms": duration_ms,
                    "final_duration_ms": duration_ms,
                    "removed_silence_ms": 0,
                    "trimmed": False,
                    "skipped_reason": "Fixture already normalized.",
                })

    def _patches(self):
        return (
            patch("app.services.uploads.get_storage_root", return_value=self.storage),
            patch("app.services.tts_optimization.get_edge_tts_voice", return_value=VOICE),
            patch("app.services.tts_timeline.get_edge_tts_voice", return_value=VOICE),
            patch(
                "app.services.tts_timeline.resolve_storage_path",
                side_effect=lambda relative: self.storage / Path(str(relative)),
            ),
            patch("app.services.tts_timeline._probe_source_video_duration_ms", return_value=self.video_duration_ms),
        )

    def _run(
        self,
        measured_durations: dict[int, int],
        *,
        max_rate: int = 35,
        attempts: int = 4,
        provider_attempts_per_operation: int = 1,
    ):
        requested_rates: list[tuple[uuid.UUID, int]] = []
        self.synthesis_operations: list[tuple[uuid.UUID, uuid.UUID, int]] = []
        self.synthesis_attempt_events: list[tuple[uuid.UUID, uuid.UUID, int, int]] = []
        self.maximum_active_syntheses = 0
        active_syntheses = 0

        async def synthesize(
            text: str,
            destination: Path,
            *,
            rate_percent: int,
            segment_id: uuid.UUID,
            artifact_id: uuid.UUID,
            attempt_callback,
            **_kwargs,
        ) -> int:
            nonlocal active_syntheses
            active_syntheses += 1
            self.maximum_active_syntheses = max(self.maximum_active_syntheses, active_syntheses)
            self.synthesis_operations.append((segment_id, artifact_id, rate_percent))
            requested_rates.append((segment_id, rate_percent))
            for attempt_number in range(1, provider_attempts_per_operation + 1):
                attempt_callback(attempt_number)
                self.synthesis_attempt_events.append((segment_id, artifact_id, rate_percent, attempt_number))
            await asyncio.sleep(0.001)
            destination.write_bytes(b"new measured audio")
            write_normalization_metadata(destination, {
                "version": "boundary-silence-v1",
                "original_duration_ms": measured_durations[rate_percent],
                "final_duration_ms": measured_durations[rate_percent],
                "removed_silence_ms": 0,
                "trimmed": False,
                "skipped_reason": "Synthetic optimizer fixture.",
            })
            active_syntheses -= 1
            return measured_durations[rate_percent]

        patches = self._patches()
        for item in patches:
            item.start()
        try:
            count = optimize_project_tts(
                self.engine, project_id=PROJECT_ID, job_id=OPTIMIZATION_JOB_ID,
                input_revision=0, stage_callback=lambda _stage: None, synthesizer=synthesize,
                max_rate_percent=max_rate, max_attempts=attempts,
            )
        finally:
            for item in reversed(patches):
                item.stop()
        return count, requested_rates

    def _read_result(self):
        patches = self._patches()
        for item in patches:
            item.start()
        try:
            with Session(self.engine) as session:
                return read_tts_optimization_result(session, PROJECT_ID, OPTIMIZATION_JOB_ID)
        finally:
            for item in reversed(patches):
                item.stop()

    def test_no_blocking_conflicts_finish_without_synthesizing(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.scalar(select(Artifact).where(Artifact.segment_id == SEGMENT_IDS[0])).duration_ms = 800
        count, requested = self._run({})
        self.assertEqual(count, 0)
        self.assertEqual(requested, [])
        with Session(self.engine) as session:
            job = session.get(Job, OPTIMIZATION_JOB_ID)
            self.assertEqual((job.status, job.stage), ("succeeded", "tts_optimization_complete"))

    def test_no_blocking_conflicts_do_not_enqueue_an_optimization_job(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.get(Job, OPTIMIZATION_JOB_ID).status = "failed"
            session.scalar(select(Artifact).where(Artifact.segment_id == SEGMENT_IDS[0])).duration_ms = 800
        patches = self._patches()
        for item in patches:
            item.start()
        try:
            with Session(self.engine) as session, session.begin():
                with self.assertRaisesRegex(ValueError, "No blocking"):
                    enqueue_tts_optimization(session, PROJECT_ID, maximum_rate_percent=35)
        finally:
            for item in reversed(patches):
                item.stop()
        with Session(self.engine) as session:
            queued = session.scalars(select(Job).where(
                Job.project_id == PROJECT_ID, Job.operation_type == "tts_optimize",
                Job.status == "queued",
            )).all()
            self.assertEqual(queued, [])

    def test_one_conflict_resolves_and_artifact_is_published_with_real_rate(self) -> None:
        count, requested = self._run({6: 1_300})
        self.assertEqual(count, 1)
        self.assertEqual(requested, [(SEGMENT_IDS[0], 6)])
        with Session(self.engine) as session:
            artifact = session.scalar(select(Artifact).where(
                Artifact.segment_id == SEGMENT_IDS[0], Artifact.is_current.is_(True)
            ))
            self.assertEqual((artifact.job_id, artifact.rate_percent, artifact.duration_ms),
                             (OPTIMIZATION_JOB_ID, 6, 1_300))
            original = session.get(Segment, SEGMENT_IDS[0])
            self.assertEqual((original.start_seconds, original.end_seconds, original.translated_text),
                             (Decimal("0"), Decimal("1"), "Xin chào 0."))
        result = self._read_result()
        self.assertTrue(result.renderable)
        self.assertFalse(result.stale)
        self.assertEqual(result.resolved_conflict_segment_ids, [SEGMENT_IDS[0]])

    def test_translation_edit_hides_stale_optimization_result_after_reload(self) -> None:
        self._run({6: 1_300})
        with Session(self.engine) as session, session.begin():
            session.get(Segment, SEGMENT_IDS[0]).translated_text = "Bản dịch đã được chỉnh sửa."
        result = self._read_result()
        self.assertTrue(result.stale)
        self.assertFalse(result.renderable)
        self.assertEqual(result.updated_segments, [])
        self.assertEqual(result.remaining_conflicts, [])
        self.assertIn("stale", result.recommendation or "")

    def test_repeated_reanalysis_uses_measured_durations_not_rate_expectations(self) -> None:
        count, requested = self._run({6: 1_650, 14: 1_350})
        self.assertEqual(count, 1)
        self.assertEqual(requested, [(SEGMENT_IDS[0], 6), (SEGMENT_IDS[0], 14)])
        with Session(self.engine) as session:
            current = session.scalar(select(Artifact).where(
                Artifact.segment_id == SEGMENT_IDS[0], Artifact.is_current.is_(True)
            ))
            self.assertEqual((current.rate_percent, current.duration_ms), (14, 1_350))

    def test_multiple_conflicts_are_reanalyzed_and_tuned_progressively(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(delete(Artifact).where(Artifact.project_id == PROJECT_ID))
            session.execute(delete(Segment).where(Segment.project_id == PROJECT_ID))
            session.execute(delete(Job).where(Job.project_id == PROJECT_ID))
            session.execute(delete(Project).where(Project.id == PROJECT_ID))
        self._seed([1_800, 1_800], base_rates=[0, 0])
        self.video_duration_ms = 2_000
        count, requested = self._run({6: 1_650, 14: 1_350})
        self.assertEqual(count, 2)
        self.assertEqual(requested, [
            (SEGMENT_IDS[0], 6), (SEGMENT_IDS[1], 6),
            (SEGMENT_IDS[0], 14), (SEGMENT_IDS[1], 14),
        ])
        self.assertEqual(self.maximum_active_syntheses, 1)
        self.assertEqual(len(self.synthesis_attempt_events), 4)
        self.assertEqual(len({artifact_id for _, artifact_id, _ in self.synthesis_operations}), 4)
        with Session(self.engine) as session:
            for segment_id in SEGMENT_IDS:
                artifact = session.scalar(select(Artifact).where(
                    Artifact.segment_id == segment_id, Artifact.is_current.is_(True)
                ))
                published_candidate = next(
                    artifact_id
                    for candidate_segment_id, artifact_id, rate in reversed(self.synthesis_operations)
                    if candidate_segment_id == segment_id and rate == 14
                )
                self.assertEqual(artifact.id, published_candidate)

    def test_retry_request_budget_is_capped_by_remaining_rates_and_three_attempts(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(delete(Artifact).where(Artifact.project_id == PROJECT_ID))
            session.execute(delete(Segment).where(Segment.project_id == PROJECT_ID))
            session.execute(delete(Job).where(Job.project_id == PROJECT_ID))
            session.execute(delete(Project).where(Project.id == PROJECT_ID))
        self._seed([1_800, 1_800], base_rates=[20, 20])
        self.video_duration_ms = 2_000

        count, requested = self._run(
            {22: 1_800, 35: 1_800}, provider_attempts_per_operation=3
        )

        self.assertEqual(count, 0)
        self.assertEqual(requested, [
            (SEGMENT_IDS[0], 22), (SEGMENT_IDS[1], 22),
            (SEGMENT_IDS[0], 35), (SEGMENT_IDS[1], 35),
        ])
        self.assertEqual(len(self.synthesis_operations), 4)
        self.assertEqual(len(self.synthesis_attempt_events), 12)
        self.assertEqual(self.maximum_active_syntheses, 1)
        with Session(self.engine) as session:
            artifacts = session.scalars(select(Artifact).where(
                Artifact.project_id == PROJECT_ID, Artifact.is_current.is_(True)
            )).all()
            self.assertEqual(len(artifacts), 2)
            self.assertEqual({artifact.job_id for artifact in artifacts}, {TTS_JOB_ID})

    def test_maximum_rate_may_leave_reported_excess_without_rendering(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.get(Artifact, session.scalar(select(Artifact.id).where(Artifact.segment_id == SEGMENT_IDS[0]))).rate_percent = 22
        # Keep the base artifact's provenance aligned with its stored rate.
        with Session(self.engine) as session, session.begin():
            artifact = session.scalar(select(Artifact).where(Artifact.segment_id == SEGMENT_IDS[0]))
            artifact.provenance_fingerprint = translation_fingerprint("Xin chào 0.", VOICE, 22)
        count, requested = self._run({35: 1_500}, max_rate=35, attempts=4)
        self.assertEqual(count, 1)
        self.assertEqual(requested, [(SEGMENT_IDS[0], 35)])
        with Session(self.engine) as session:
            optimized = session.scalar(select(Artifact).where(
                Artifact.segment_id == SEGMENT_IDS[0], Artifact.is_current.is_(True)
            ))
            self.assertEqual((optimized.rate_percent, optimized.duration_ms), (35, 1_500))
        result = self._read_result()
        self.assertFalse(result.renderable)
        self.assertEqual(result.remaining_conflicts[0].remaining_excess_ms, 100)
        self.assertIn("Shorten", result.recommendation)

    def test_missing_audio_is_rejected_without_fallback(self) -> None:
        (self.storage / "projects" / str(PROJECT_ID) / "jobs" / str(TTS_JOB_ID) / "tts" / f"{SEGMENT_IDS[0]}.mp3").unlink()
        patches = self._patches()
        for item in patches:
            item.start()
        try:
            with Session(self.engine) as session:
                from app.services.tts_timeline import build_project_timeline_plan
                plan = build_project_timeline_plan(session, PROJECT_ID, ignore_active_job_id=OPTIMIZATION_JOB_ID)
                self.assertFalse(plan.renderable)
                self.assertIn("tts_audio_missing", {issue.code for issue in plan.issues})
            with self.assertRaisesRegex(TTSError, "cannot be safely optimized"):
                optimize_project_tts(
                    self.engine, project_id=PROJECT_ID, job_id=OPTIMIZATION_JOB_ID,
                    input_revision=0, stage_callback=lambda _stage: None,
                    synthesizer=lambda *_args, **_kwargs: self.fail("must not synthesize without source audio"),
                )
        finally:
            for item in reversed(patches):
                item.stop()
        with Session(self.engine) as session:
            current = session.scalar(select(Artifact).where(Artifact.is_current.is_(True)))
            self.assertEqual((current.job_id, current.duration_ms), (TTS_JOB_ID, 1_800))

    def test_no_audio_after_retry_limit_preserves_current_artifact_and_fails_job(self) -> None:
        provider_attempts = 0

        class Communicate:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            async def save(self, _destination: str) -> None:
                nonlocal provider_attempts
                provider_attempts += 1
                raise NoAudioReceived("provider response body must not be logged")

        async def no_sleep(_delay: float) -> None:
            return None

        async def synthesize_without_backoff(*args, **kwargs) -> int:
            return await synthesize_segment(*args, retry_sleep=no_sleep, **kwargs)

        patches = self._patches()
        for item in patches:
            item.start()
        try:
            with (
                patch("app.services.tts_optimization.synthesize_segment", side_effect=synthesize_without_backoff),
                patch("app.services.tts.edge_tts.Communicate", Communicate),
            ):
                process_claimed_job(self.engine, OPTIMIZATION_JOB_ID)
        finally:
            for item in reversed(patches):
                item.stop()
        with Session(self.engine) as session:
            job = session.get(Job, OPTIMIZATION_JOB_ID)
            artifacts = session.scalars(select(Artifact).where(Artifact.project_id == PROJECT_ID)).all()
            self.assertEqual(job.status, "failed")
            self.assertEqual(provider_attempts, 3)
            self.assertEqual(len(artifacts), 1)
            self.assertTrue(artifacts[0].is_current)

    def test_transcript_change_during_synthesis_discards_staged_audio(self) -> None:
        async def edit_during_synthesis(_text: str, destination: Path, **_kwargs) -> int:
            destination.write_bytes(b"staged candidate")
            with Session(self.engine) as session, session.begin():
                session.get(Segment, SEGMENT_IDS[0]).translated_text = "Edited while optimizing."
            return 1_000

        patches = self._patches()
        for item in patches:
            item.start()
        try:
            with self.assertRaisesRegex(TTSError, "changed"):
                optimize_project_tts(
                    self.engine, project_id=PROJECT_ID, job_id=OPTIMIZATION_JOB_ID,
                    input_revision=0, stage_callback=lambda _stage: None,
                    synthesizer=edit_during_synthesis,
                )
        finally:
            for item in reversed(patches):
                item.stop()
        with Session(self.engine) as session:
            artifacts = session.scalars(select(Artifact)).all()
            self.assertEqual(len(artifacts), 1)
            self.assertTrue(artifacts[0].is_current)

    def test_duplicate_active_project_job_is_rejected_by_api(self) -> None:
        engine_patch = patch("app.api.projects.create_database_engine", return_value=self.engine)
        factory_patch = patch(
            "app.api.projects.create_session_factory",
            side_effect=lambda engine: sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
        )
        engine_patch.start()
        factory_patch.start()
        patches = self._patches()
        for item in patches:
            item.start()
        try:
            response = TestClient(app).post(f"/projects/{PROJECT_ID}/tts-optimization-jobs")
        finally:
            for item in reversed(patches):
                item.stop()
            factory_patch.stop()
            engine_patch.stop()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Another Job is already active for this Project.")

    def test_enqueue_persists_optimization_job_and_rejects_a_second_submission(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.get(Job, OPTIMIZATION_JOB_ID).status = "failed"
        engine_patch = patch("app.api.projects.create_database_engine", return_value=self.engine)
        factory_patch = patch(
            "app.api.projects.create_session_factory",
            side_effect=lambda engine: sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
        )
        engine_patch.start()
        factory_patch.start()
        patches = self._patches()
        for item in patches:
            item.start()
        try:
            client = TestClient(app)
            response = client.post(f"/projects/{PROJECT_ID}/tts-optimization-jobs")
            second_response = client.post(f"/projects/{PROJECT_ID}/tts-optimization-jobs")
        finally:
            for item in reversed(patches):
                item.stop()
            factory_patch.stop()
            engine_patch.stop()
        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(second_response.status_code, 409)
        with Session(self.engine) as session:
            persisted = session.get(Job, uuid.UUID(payload["id"]))
            self.assertEqual((persisted.operation_type, persisted.status), ("tts_optimize", "queued"))

    def test_worker_interruption_during_optimization_preserves_old_audio(self) -> None:
        async def interrupt_during_synthesis(_text: str, destination: Path, **_kwargs) -> int:
            destination.write_bytes(b"staged candidate")
            with Session(self.engine) as session, session.begin():
                job = session.get(Job, OPTIMIZATION_JOB_ID)
                job.status = "interrupted"
                job.stage = "interrupted"
            return 1_000

        patches = self._patches()
        for item in patches:
            item.start()
        try:
            with self.assertRaises(TTSError):
                optimize_project_tts(
                    self.engine, project_id=PROJECT_ID, job_id=OPTIMIZATION_JOB_ID,
                    input_revision=0, stage_callback=lambda _stage: None,
                    synthesizer=interrupt_during_synthesis,
                )
        finally:
            for item in reversed(patches):
                item.stop()
        with Session(self.engine) as session:
            job = session.get(Job, OPTIMIZATION_JOB_ID)
            artifact = session.scalar(select(Artifact).where(Artifact.is_current.is_(True)))
            self.assertEqual(job.status, "interrupted")
            self.assertEqual((artifact.job_id, artifact.duration_ms), (TTS_JOB_ID, 1_800))

    def test_interrupted_unpublished_optimization_files_are_cleaned(self) -> None:
        temporary_dir = self.storage / "projects" / str(PROJECT_ID) / "tts-temp" / str(OPTIMIZATION_JOB_ID)
        job_audio_dir = self.storage / "projects" / str(PROJECT_ID) / "jobs" / str(OPTIMIZATION_JOB_ID) / "tts"
        for directory in (temporary_dir, job_audio_dir):
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "staged.mp3").write_bytes(b"staged audio")
        with self.engine.begin() as connection:
            connection.execute(
                Job.__table__.update()
                .where(Job.id == OPTIMIZATION_JOB_ID)
                .values(status="interrupted", stage="interrupted")
            )
        with patch(
            "app.services.tts.resolve_storage_path",
            side_effect=lambda relative: self.storage / Path(str(relative)),
        ):
            cleanup_interrupted_tts_optimization_files(self.engine, (OPTIMIZATION_JOB_ID,))
        self.assertFalse(temporary_dir.exists())
        self.assertFalse(job_audio_dir.exists())
        current_audio = self.storage / Path(
            f"projects/{PROJECT_ID}/jobs/{TTS_JOB_ID}/tts/{SEGMENT_IDS[0]}.mp3"
        )
        self.assertTrue(current_audio.exists())


if __name__ == "__main__":
    unittest.main()
