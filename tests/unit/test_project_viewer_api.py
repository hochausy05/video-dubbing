"""Read-only Project viewer APIs over an isolated local test database."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.models import Project, Segment
from app.models.base import Base
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


if __name__ == "__main__":
    unittest.main()
