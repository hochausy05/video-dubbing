"""Read-only Project viewer APIs over an isolated local test database."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Job, Project, Segment
from app.models.base import Base
from app.services.translation import TranslationConflictError, translate_project
from app.services.uploads import source_relative_path


PROJECT_ID = uuid.UUID("bdfe8938-083c-49b8-b12a-71f4da86d702")


class ProjectViewerApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.storage_root = Path(self.temp_directory.name)
        self.engine = create_engine(
            f"sqlite+pysqlite:///{self.storage_root / 'test.sqlite'}"
        )
        Base.metadata.create_all(self.engine)
        self.project = Project(
            id=PROJECT_ID,
            name="viewer test",
            source_media_reference=source_relative_path(PROJECT_ID).as_posix(),
        )
        with Session(self.engine) as session, session.begin():
            session.add(self.project)
            session.add(
                Job(
                    id=uuid.UUID("30000000-0000-0000-0000-000000000001"),
                    project_id=PROJECT_ID,
                    operation_type="transcribe_translate",
                    input_revision=0,
                    status="succeeded",
                    stage="translation_ready",
                )
            )
            session.add_all(
                [
                    Segment(
                        id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                        project_id=PROJECT_ID,
                        position=1,
                        start_seconds=1,
                        end_seconds=2,
                        source_text="second",
                        translated_text="thứ hai",
                        revision=0,
                    ),
                    Segment(
                        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                        project_id=PROJECT_ID,
                        position=0,
                        start_seconds=0,
                        end_seconds=1,
                        source_text="first",
                        translated_text=None,
                        revision=0,
                    ),
                ]
            )
        self.engine_patch = patch("app.api.projects.create_database_engine", return_value=self.engine)
        self.factory_patch = patch(
            "app.api.projects.create_session_factory",
            side_effect=lambda engine: sessionmaker(
                bind=engine, autoflush=False, expire_on_commit=False
            ),
        )
        self.storage_patch = patch("app.services.uploads.get_storage_root", return_value=self.storage_root)
        self.engine_patch.start()
        self.factory_patch.start()
        self.storage_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.engine_patch.stop()
        self.factory_patch.stop()
        self.storage_patch.stop()
        self.engine.dispose()
        self.temp_directory.cleanup()

    def test_segments_are_project_scoped_ordered_and_include_real_translation(self) -> None:
        response = self.client.get(f"/projects/{PROJECT_ID}/segments")
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual([row["position"] for row in rows], [0, 1])
        self.assertEqual([row["source_text"] for row in rows], ["first", "second"])
        self.assertEqual([row["translated_text"] for row in rows], [None, "thứ hai"])
        self.assertEqual([row["id"] for row in rows], [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ])

    def test_missing_project_is_404_for_transcript_and_video(self) -> None:
        missing_id = uuid.uuid4()
        self.assertEqual(self.client.get(f"/projects/{missing_id}/segments").status_code, 404)
        self.assertEqual(self.client.get(f"/projects/{missing_id}/video").status_code, 404)

    def test_video_is_canonical_and_supports_http_range(self) -> None:
        source = self.storage_root.joinpath(*source_relative_path(PROJECT_ID).parts)
        source.parent.mkdir(parents=True)
        source.write_bytes(b"0123456789")
        response = self.client.get(
            f"/projects/{PROJECT_ID}/video", headers={"Range": "bytes=2-5"}
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"2345")
        self.assertEqual(response.headers["content-range"], "bytes 2-5/10")
        self.assertNotIn(str(self.storage_root), response.text)

    def test_noncanonical_stored_reference_cannot_serve_an_arbitrary_file(self) -> None:
        arbitrary = self.storage_root / "private.txt"
        arbitrary.write_text("private", encoding="utf-8")
        with Session(self.engine) as session, session.begin():
            session.get(Project, PROJECT_ID).source_media_reference = "../../private.txt"
        response = self.client.get(f"/projects/{PROJECT_ID}/video")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("private", response.text)

    def test_translation_update_persists_only_translation_and_returns_segment(self) -> None:
        segment_id = "00000000-0000-0000-0000-000000000001"
        response = self.client.patch(
            f"/projects/{PROJECT_ID}/segments/{segment_id}",
            json={"translated_text": "  Xin chào bằng tiếng Việt.  "},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["translated_text"], "Xin chào bằng tiếng Việt.")
        self.assertEqual(body["source_text"], "first")
        self.assertEqual(body["position"], 0)
        self.assertEqual((body["start_seconds"], body["end_seconds"]), ("0.000", "1.000"))
        reloaded = self.client.get(f"/projects/{PROJECT_ID}/segments")
        self.assertEqual(reloaded.status_code, 200)
        self.assertEqual(reloaded.json()[0]["translated_text"], "Xin chào bằng tiếng Việt.")
        with Session(self.engine) as session, session.begin():
            persisted = session.get(Segment, uuid.UUID(segment_id))
            self.assertEqual(persisted.translated_text, "Xin chào bằng tiếng Việt.")
            self.assertEqual(persisted.source_text, "first")
            self.assertEqual((persisted.start_seconds, persisted.end_seconds), (0, 1))
            self.assertEqual(persisted.position, 0)
            self.assertEqual(persisted.id, uuid.UUID(segment_id))
            all_segments = session.scalars(
                select(Segment).where(Segment.project_id == PROJECT_ID).order_by(Segment.position)
            ).all()
            self.assertEqual(
                [item.id for item in all_segments],
                [
                    uuid.UUID(segment_id),
                    uuid.UUID("00000000-0000-0000-0000-000000000002"),
                ],
            )
            session.add(
                Job(
                    id=uuid.UUID("30000000-0000-0000-0000-000000000004"),
                    project_id=PROJECT_ID,
                    operation_type="transcribe_translate",
                    input_revision=0,
                    status="running",
                    stage="translating",
                )
            )

        def forbidden_client_factory() -> object:
            raise AssertionError(
                "A transcript containing an edited translation must not be retranslated."
            )

        with self.assertRaises(TranslationConflictError):
            translate_project(
                self.engine,
                project_id=PROJECT_ID,
                job_id=uuid.UUID("30000000-0000-0000-0000-000000000004"),
                input_revision=0,
                stage_callback=lambda _stage: None,
                client_factory=forbidden_client_factory,
                model="test-model",
            )
        with Session(self.engine) as session:
            self.assertEqual(
                session.get(Segment, uuid.UUID(segment_id)).translated_text,
                "Xin chào bằng tiếng Việt.",
            )

    def test_update_returns_404_for_missing_project_or_segment_from_another_project(self) -> None:
        segment_id = "00000000-0000-0000-0000-000000000001"
        missing_project = self.client.patch(
            f"/projects/{uuid.uuid4()}/segments/{segment_id}",
            json={"translated_text": "Bản dịch."},
        )
        self.assertEqual(missing_project.status_code, 404)

        other_project_id = uuid.UUID("bdfe8938-083c-49b8-b12a-71f4da86d703")
        with Session(self.engine) as session, session.begin():
            session.add(
                Project(id=other_project_id, name="other project", current_revision=0)
            )
            session.add(
                Job(
                    id=uuid.UUID("30000000-0000-0000-0000-000000000002"),
                    project_id=other_project_id,
                    operation_type="transcribe_translate",
                    input_revision=0,
                    status="succeeded",
                    stage="translation_ready",
                )
            )
        cross_project = self.client.patch(
            f"/projects/{other_project_id}/segments/{segment_id}",
            json={"translated_text": "Không được lưu."},
        )
        self.assertEqual(cross_project.status_code, 404)

    def test_update_rejects_missing_empty_wrong_type_extra_and_oversized_payload(self) -> None:
        segment_id = "00000000-0000-0000-0000-000000000001"
        invalid_payloads = [
            {},
            {"translated_text": "  \n "},
            {"translated_text": 123},
            {"translated_text": "Bản dịch", "source_text": "changed"},
            {"translated_text": "x" * 10_001},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=str(payload)[:50]):
                result = self.client.patch(
                    f"/projects/{PROJECT_ID}/segments/{segment_id}", json=payload
                )
                self.assertEqual(result.status_code, 422)

        missing_segment = self.client.patch(
            f"/projects/{PROJECT_ID}/segments/{uuid.uuid4()}",
            json={"translated_text": "Bản dịch."},
        )
        self.assertEqual(missing_segment.status_code, 404)

    def test_active_job_prevents_translation_edit_without_mutation(self) -> None:
        segment_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        with Session(self.engine) as session, session.begin():
            session.add(
                Job(
                    id=uuid.UUID("30000000-0000-0000-0000-000000000003"),
                    project_id=PROJECT_ID,
                    operation_type="transcribe_translate",
                    input_revision=0,
                    status="running",
                    stage="translating",
                )
            )
        result = self.client.patch(
            f"/projects/{PROJECT_ID}/segments/{segment_id}",
            json={"translated_text": "Bản dịch mới."},
        )
        self.assertEqual(result.status_code, 409)
        with Session(self.engine) as session:
            self.assertIsNone(session.get(Segment, segment_id).translated_text)


if __name__ == "__main__":
    unittest.main()
