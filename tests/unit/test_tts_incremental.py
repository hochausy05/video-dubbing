"""Incremental TTS selection/publication with isolated SQLite and fake synthesis."""

from contextlib import ExitStack
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Artifact, Job, Project, Segment
from app.models.base import Base
from app.services.audio_normalization import write_normalization_metadata
from app.services.tts import TTSError, translation_fingerprint
from app.services.tts_timeline import build_project_timeline_plan
from app.workers.job_worker import process_claimed_job, _set_running_job_stage


VOICE = "vi-VN-HoaiMyNeural"


class IncrementalTtsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.storage = self.root / "storage"
        self.engine = create_engine(f"sqlite+pysqlite:///{self.root / 'db.sqlite'}")
        Base.metadata.create_all(self.engine)
        self.pid, self.jid = uuid.uuid4(), uuid.uuid4()
        self.translation_job = uuid.uuid4()
        self.producers = [uuid.uuid4() for _ in range(3)]
        self.ids = []
        self._seed(6)

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def _seed(self, count):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.ids = [uuid.uuid5(self.pid, str(index)) for index in range(count)]
        with Session(self.engine) as s, s.begin():
            s.add(Project(id=self.pid, name="isolated fixture", current_revision=0,
                          source_media_reference=f"projects/{self.pid}/source/video.mp4"))
            s.add(Job(id=self.translation_job, project_id=self.pid, input_revision=0,
                      operation_type="transcribe_translate", status="succeeded", stage="translation_ready",
                      created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
            for jid, kind, stage in zip(self.producers,
                    ["tts", "tts_optimize", "tts_normalize"],
                    ["tts_ready", "tts_optimization_complete", "tts_normalization_complete"]):
                s.add(Job(id=jid, project_id=self.pid, input_revision=0,
                          operation_type=kind, status="succeeded", stage=stage))
            s.add(Job(id=self.jid, project_id=self.pid, input_revision=0,
                      operation_type="tts", status="running", stage="claimed"))
            s.flush()
            for i, sid in enumerate(self.ids):
                text = f"Xin chào {i}."
                s.add(Segment(id=sid, project_id=self.pid, position=i,
                              start_seconds=Decimal(i * 2), end_seconds=Decimal(i * 2 + 2),
                              source_text=f"Source {i}", translated_text=text, revision=0))
                s.flush()
                producer = self.producers[i % 3]
                rate = 0 if i % 3 == 0 else 35
                ref = f"projects/{self.pid}/jobs/{producer}/tts/{sid}.mp3"
                path = self.storage / ref
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"original audio {i}".encode())
                fingerprint = translation_fingerprint(text, VOICE, rate)
                write_normalization_metadata(path, {
                    "version": "boundary-silence-v1", "final_duration_ms": 900,
                    "original_duration_ms": 1100, "voice": VOICE, "rate_percent": rate,
                    "translation_fingerprint": fingerprint,
                })
                s.add(Artifact(project_id=self.pid, job_id=producer, segment_id=sid, revision=0,
                               media_type="audio/mpeg", storage_reference=ref, duration_ms=900,
                               provenance_fingerprint=fingerprint, voice=VOICE, rate_percent=rate,
                               is_current=True))

    def _patches(self):
        stack = ExitStack()
        stack.enter_context(patch("app.services.uploads.get_storage_root", return_value=self.storage))
        stack.enter_context(patch("app.services.tts.get_edge_tts_voice", return_value=VOICE))
        stack.enter_context(patch("app.services.tts.get_edge_tts_concurrency", return_value=2))
        stack.enter_context(patch("app.services.tts_timeline.get_edge_tts_voice", return_value=VOICE))
        stack.enter_context(patch("app.services.tts_timeline._probe_source_video_duration_ms",
                                  return_value=len(self.ids) * 2000))
        stack.enter_context(patch("app.api.projects.get_edge_tts_voice", return_value=VOICE))
        stack.enter_context(patch("app.api.projects.create_database_engine", return_value=self.engine))
        stack.enter_context(patch("app.api.projects.create_session_factory",
                                  side_effect=lambda e: sessionmaker(bind=e, expire_on_commit=False)))
        return stack

    def _artifact_rows(self):
        with Session(self.engine) as s:
            return {a.id: (a.segment_id, a.job_id, a.revision, a.storage_reference, a.duration_ms,
                           a.provenance_fingerprint, a.voice, a.rate_percent, a.is_current,
                           a.created_at, a.updated_at)
                    for a in s.scalars(select(Artifact).where(Artifact.project_id == self.pid))}

    def _segment_rows(self):
        with Session(self.engine) as s:
            return [(x.id, x.position, x.start_seconds, x.end_seconds, x.source_text,
                     x.translated_text, x.revision) for x in s.scalars(
                         select(Segment).where(Segment.project_id == self.pid).order_by(Segment.position))]

    def _edit(self, indices):
        with Session(self.engine) as s, s.begin():
            for index in indices:
                s.get(Segment, self.ids[index]).translated_text = f"Nội dung mới {index}."

    def _run(self, *, fail_at=None, before_publish=None):
        self.calls = []
        self.stages = []
        self.before_artifacts = self._artifact_rows()
        self.before_segments = self._segment_rows()
        self.before_files = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                             for p in self.storage.rglob("*") if p.is_file()}

        async def fake(text, destination, **kwargs):
            self.calls.append(kwargs["segment_id"])
            if len(self.calls) == fail_at:
                raise TTSError("Vietnamese voice generation failed for a Segment.")
            destination.write_bytes(b"complete fake speech")
            write_normalization_metadata(destination, {
                "version": "boundary-silence-v1", "final_duration_ms": 900,
                "translation_fingerprint": translation_fingerprint(text, VOICE, kwargs["rate_percent"]),
            })
            return 900

        def stage(engine, jid, value):
            self.stages.append(value)
            _set_running_job_stage(engine, jid, value)
            if value == "validating_tts" and before_publish:
                before_publish()

        with self._patches() as stack:
            stack.enter_context(patch("app.services.tts.synthesize_segment", side_effect=fake))
            stack.enter_context(patch("app.workers.job_worker._set_running_job_stage", side_effect=stage))
            process_claimed_job(self.engine, self.jid)
        with Session(self.engine) as s:
            job = s.get(Job, self.jid)
            self.result = (job.status, job.stage, job.safe_error)

    def _assert_replaced(self, indices):
        expected = {self.ids[i] for i in indices}
        self.assertEqual(set(self.calls), expected)
        self.assertEqual(len(self.calls), len(expected))
        self.assertEqual(self.result[:2], ("succeeded", "tts_ready"))
        self.assertEqual(self._segment_rows(), self.before_segments)
        after = self._artifact_rows()
        for aid, row in self.before_artifacts.items():
            if row[0] not in expected:
                self.assertEqual(after[aid], row)
            else:
                self.assertFalse(after[aid][8])
        current = [row for row in after.values() if row[8]]
        self.assertEqual(len(current), len(self.ids))
        self.assertEqual(sum(row[1] == self.jid for row in current), len(expected))
        for path, snapshot in self.before_files.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), snapshot)
        with self._patches(), Session(self.engine) as s:
            plan = build_project_timeline_plan(s, self.pid)
        self.assertTrue(plan.renderable, plan.issues)

    def test_one_edit_in_272_reuses_271_exact_artifacts_and_accepts_mixed_jobs(self):
        self._seed(272)
        self._edit([4])
        self._run()
        self._assert_replaced([4])

    def test_three_edits_generate_three_audio_files(self):
        self._edit([0, 2, 5])
        self._run()
        self._assert_replaced([0, 2, 5])

    def test_272_unchanged_rows_make_zero_calls_and_no_output_directory(self):
        self._seed(272)
        self._run()
        self._assert_replaced([])
        self.assertNotIn("generating_tts", self.stages)
        self.assertEqual(self._artifact_rows(), self.before_artifacts)
        self.assertFalse((self.storage / f"projects/{self.pid}/jobs/{self.jid}").exists())
        self.assertFalse((self.storage / f"projects/{self.pid}/tts-temp/{self.jid}").exists())

    def test_unchanged_optimized_35_percent_artifact_is_reused(self):
        self._edit([0])
        self._run()
        self._assert_replaced([0])
        optimized = [a for a in self._artifact_rows().values() if a[0] == self.ids[1] and a[8]]
        self.assertEqual(optimized[0][7], 35)

    def _invalidate(self, index, **changes):
        with Session(self.engine) as s, s.begin():
            a = s.scalar(select(Artifact).where(Artifact.segment_id == self.ids[index]))
            for key, value in changes.items():
                setattr(a, key, value)

    def test_only_missing_file_is_regenerated(self):
        with Session(self.engine) as s:
            a = s.scalar(select(Artifact).where(Artifact.segment_id == self.ids[1]))
            (self.storage / a.storage_reference).unlink()
        self._run()
        self._assert_replaced([1])

    def test_only_stale_fingerprint_is_regenerated(self):
        self._invalidate(1, provenance_fingerprint="stale")
        self._run()
        self._assert_replaced([1])

    def test_only_incompatible_voice_is_regenerated(self):
        self._invalidate(1, voice="vi-VN-NamMinhNeural")
        self._run()
        self._assert_replaced([1])

    def test_only_invalid_producer_is_regenerated(self):
        bad = uuid.uuid4()
        with Session(self.engine) as s, s.begin():
            s.add(Job(id=bad, project_id=self.pid, input_revision=0,
                      operation_type="tts", status="failed", stage="failed"))
        self._invalidate(1, job_id=bad)
        self._run()
        self._assert_replaced([1])

    def test_successful_producer_from_another_project_is_not_reused(self):
        other, bad = uuid.uuid4(), uuid.uuid4()
        with Session(self.engine) as s, s.begin():
            s.add(Project(id=other, name="other fixture", current_revision=0))
            s.flush()
            s.add(Job(id=bad, project_id=other, input_revision=0,
                      operation_type="tts", status="succeeded", stage="tts_ready"))
        self._invalidate(1, job_id=bad)
        self._run()
        self._assert_replaced([1])
        with Session(self.engine) as s:
            self.assertEqual(s.get(Job, bad).status, "succeeded")

    def test_old_revision_producer_is_not_reused(self):
        bad = uuid.uuid4()
        with Session(self.engine) as s, s.begin():
            s.add(Job(id=bad, project_id=self.pid, input_revision=1,
                      operation_type="tts", status="succeeded", stage="tts_ready"))
        self._invalidate(1, job_id=bad)
        self._run()
        self._assert_replaced([1])

    def test_noncanonical_path_is_not_reused(self):
        self._invalidate(1, storage_reference="projects/unsafe/audio.mp3")
        self._run()
        self._assert_replaced([1])

    def test_invalid_duration_is_not_reused(self):
        self._invalidate(1, duration_ms=None)
        self._run()
        self._assert_replaced([1])

    def test_only_ambiguous_mapping_is_regenerated_and_all_duplicates_are_superseded(self):
        with Session(self.engine) as s, s.begin():
            a = s.scalar(select(Artifact).where(Artifact.segment_id == self.ids[1]))
            s.add(Artifact(project_id=a.project_id, job_id=a.job_id, segment_id=a.segment_id,
                           revision=a.revision, media_type=a.media_type, storage_reference=a.storage_reference,
                           duration_ms=a.duration_ms, provenance_fingerprint=a.provenance_fingerprint,
                           voice=a.voice, rate_percent=a.rate_percent, is_current=True))
        self._run()
        self._assert_replaced([1])

    def test_missing_required_normalization_metadata_is_not_reused(self):
        with Session(self.engine) as s:
            a = s.scalar(select(Artifact).where(Artifact.segment_id == self.ids[2]))
            (self.storage / a.storage_reference).with_suffix(".normalization.json").unlink()
        self._run()
        self._assert_replaced([2])

    def test_old_revision_audio_is_never_reused(self):
        with Session(self.engine) as s, s.begin():
            s.get(Project, self.pid).current_revision = 1
            s.get(Job, self.translation_job).input_revision = 1
            s.get(Job, self.jid).input_revision = 1
            for segment in s.scalars(select(Segment)):
                segment.revision = 1
        self._run()
        self._assert_replaced(range(6))
        with Session(self.engine) as s:
            self.assertEqual({a.revision for a in s.scalars(select(Artifact).where(Artifact.is_current.is_(True)))}, {1})

    def test_failed_second_synthesis_publishes_nothing(self):
        self._edit([0, 1])
        self._run(fail_at=2)
        self.assertEqual(self.result[0], "failed")
        self.assertEqual(self._artifact_rows(), self.before_artifacts)
        self.assertEqual(self._segment_rows(), self.before_segments)
        self.assertFalse((self.storage / f"projects/{self.pid}/jobs/{self.jid}").exists())
        self.assertFalse((self.storage / f"projects/{self.pid}/tts-temp/{self.jid}").exists())

    def test_database_insert_failure_rolls_back_superseded_artifacts(self):
        self._edit([0, 1])
        def reject(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("INSERT INTO AUTODUB_ARTIFACTS"):
                raise RuntimeError("synthetic TTS publication rejection")
        event.listen(self.engine, "before_cursor_execute", reject)
        try:
            self._run()
        finally:
            event.remove(self.engine, "before_cursor_execute", reject)
        self.assertEqual(self.result[0], "failed")
        self.assertEqual(self._artifact_rows(), self.before_artifacts)
        self.assertFalse((self.storage / f"projects/{self.pid}/jobs/{self.jid}/tts").exists())

    def test_concurrent_segment_edit_discards_all_candidates(self):
        self._edit([0])
        self._run(before_publish=lambda: self._edit([1]))
        self.assertEqual(self.result[0], "failed")
        self.assertEqual(self._artifact_rows(), self.before_artifacts)

    def test_revision_change_before_publication_discards_candidates(self):
        self._edit([0])
        def mutate():
            with Session(self.engine) as s, s.begin():
                s.get(Project, self.pid).current_revision = 1
        self._run(before_publish=mutate)
        self.assertEqual(self.result[0], "failed")
        self.assertEqual(self._artifact_rows(), self.before_artifacts)

    def test_reused_file_disappearing_before_commit_aborts_publication(self):
        self._edit([0])
        with Session(self.engine) as s:
            a = s.scalar(select(Artifact).where(Artifact.segment_id == self.ids[1]))
            path = self.storage / a.storage_reference
        self._run(before_publish=path.unlink)
        self.assertEqual(self.result[0], "failed")
        self.assertEqual(self._artifact_rows(), self.before_artifacts)

    def test_reused_producer_becoming_failed_is_rechecked(self):
        self._edit([0])
        def mutate():
            with Session(self.engine) as s, s.begin():
                s.get(Job, self.producers[1]).status = "failed"
        self._run(before_publish=mutate)
        self.assertEqual(self.result[0], "failed")
        self.assertEqual(self._artifact_rows(), self.before_artifacts)

    def test_artifact_snapshot_change_before_commit_aborts_publication(self):
        self._edit([0])
        self._run(before_publish=lambda: self._invalidate(1, provenance_fingerprint="concurrent"))
        self.assertEqual(self.result[0], "failed")
        with Session(self.engine) as s:
            self.assertIsNone(s.scalar(select(Artifact.id).where(Artifact.job_id == self.jid)))
            self.assertTrue(all(a.is_current for a in s.scalars(select(Artifact))))

    def test_conflicting_job_before_publication_aborts(self):
        self._edit([0])
        def mutate():
            with Session(self.engine) as s, s.begin():
                s.add(Job(project_id=self.pid, operation_type="tts", input_revision=0,
                          status="queued", stage="queued"))
        self._run(before_publish=mutate)
        self.assertEqual(self.result[0], "failed")
        self.assertEqual(self._artifact_rows(), self.before_artifacts)

    def test_audio_api_and_timeline_share_strict_producer_validation(self):
        self._run()
        with Session(self.engine) as s, s.begin():
            s.get(Job, self.producers[1]).stage = "render_complete"
        with self._patches():
            client = TestClient(app)
            listing = client.get(f"/projects/{self.pid}/tts-audio")
            audio = client.get(f"/projects/{self.pid}/segments/{self.ids[1]}/audio")
            plan = client.get(f"/projects/{self.pid}/tts-timeline-plan")
        self.assertFalse(next(x for x in listing.json() if x["segment_id"] == str(self.ids[1]))["current"])
        self.assertEqual(audio.status_code, 404)
        self.assertIn("tts_job_incomplete", {x["code"] for x in plan.json()["issues"]})

    def test_audio_api_refuses_ambiguous_current_artifacts(self):
        self._run()
        with Session(self.engine) as s, s.begin():
            a = s.scalar(select(Artifact).where(Artifact.segment_id == self.ids[1]))
            s.add(Artifact(project_id=a.project_id, job_id=a.job_id, segment_id=a.segment_id,
                           revision=a.revision, media_type=a.media_type, storage_reference=a.storage_reference,
                           duration_ms=a.duration_ms, provenance_fingerprint=a.provenance_fingerprint,
                           voice=a.voice, rate_percent=a.rate_percent, is_current=True))
        with self._patches():
            client = TestClient(app)
            listing = client.get(f"/projects/{self.pid}/tts-audio")
            audio = client.get(f"/projects/{self.pid}/segments/{self.ids[1]}/audio")
        self.assertFalse(any(x["current"] for x in listing.json() if x["segment_id"] == str(self.ids[1])))
        self.assertEqual(audio.status_code, 404)


if __name__ == "__main__":
    unittest.main()
