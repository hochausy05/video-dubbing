"""Strict Gemini response and transactional translation behavior tests."""

from __future__ import annotations

import json
import unittest
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Job, Project, Segment
from app.models.base import Base
from app.services.translation import (
    TranslationConflictError,
    TranslationValidationError,
    translate_project,
    validate_translation_response,
)


SEGMENT_ID = uuid.UUID("1052b4b7-310a-49f5-905c-552961d23f2f")
SECOND_SEGMENT_ID = uuid.UUID("46b7c14f-c765-41ed-8439-c00278586874")
PROJECT_ID = uuid.UUID("774f4714-33cc-4140-921a-6ac8ac2e66b2")
JOB_ID = uuid.UUID("a66da89f-0c0f-4351-86c1-3e386669535e")


def response(rows: object) -> str:
    return json.dumps({"translations": rows})


class TranslationResponseTests(unittest.TestCase):
    def test_valid_response_maps_exact_ids_and_trims_translation(self) -> None:
        actual = validate_translation_response(
            response(
                [
                    {"id": str(SEGMENT_ID), "translated_text": "  Xin chào.  "},
                    {"id": str(SECOND_SEGMENT_ID), "translated_text": " Hẹn gặp lại."},
                ]
            ),
            [SEGMENT_ID, SECOND_SEGMENT_ID],
        )

        self.assertEqual(
            actual,
            {
                str(SEGMENT_ID): "Xin chào.",
                str(SECOND_SEGMENT_ID): "Hẹn gặp lại.",
            },
        )

    def test_missing_duplicate_unknown_malformed_and_empty_results_fail(self) -> None:
        valid_row = {"id": str(SEGMENT_ID), "translated_text": "Xin chào."}
        invalid_responses = [
            response([]),
            response([valid_row, valid_row]),
            response(
                [
                    {"id": str(SEGMENT_ID), "translated_text": "Xin chào."},
                    {"id": str(uuid.uuid4()), "translated_text": "Không rõ."},
                ]
            ),
            '{"translations":[{"id":',
            response([{"id": str(SEGMENT_ID), "translated_text": "  "}]),
            response([{"id": str(SEGMENT_ID), "translated_text": 123}]),
            response([{"id": str(SEGMENT_ID), "translated_text": "ok", "position": 0}]),
        ]
        expected_ids = [SEGMENT_ID, SECOND_SEGMENT_ID]
        for invalid in invalid_responses:
            with self.subTest(invalid=invalid), self.assertRaises(TranslationValidationError):
                validate_translation_response(invalid, expected_ids)

    def test_unambiguous_json_markdown_fence_is_accepted(self) -> None:
        fenced = "```json\n" + response(
            [{"id": str(SEGMENT_ID), "translated_text": "Xin chào."}]
        ) + "\n```"
        self.assertEqual(
            validate_translation_response(fenced, [SEGMENT_ID]),
            {str(SEGMENT_ID): "Xin chào."},
        )


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)
        self.request_count = 0

    def generate_content(self, **_kwargs: object) -> _FakeResponse:
        self.request_count += 1
        return _FakeResponse(next(self._responses))


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.models = _FakeModels(responses)
        self.closed = False

    def close(self) -> None:
        self.closed = True


class TranslationPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session, session.begin():
            session.add(
                Project(
                    id=PROJECT_ID,
                    name="translation validation test",
                    target_language="vi",
                    current_revision=0,
                )
            )
            session.add(
                Job(
                    id=JOB_ID,
                    project_id=PROJECT_ID,
                    operation_type="transcribe_translate",
                    input_revision=0,
                    status="running",
                    stage="transcript_ready",
                )
            )
            session.add_all(
                [
                    Segment(
                        id=SEGMENT_ID,
                        project_id=PROJECT_ID,
                        position=0,
                        start_seconds=0,
                        end_seconds=1,
                        source_text="Hello there.",
                        translated_text=None,
                        revision=0,
                    ),
                    Segment(
                        id=SECOND_SEGMENT_ID,
                        project_id=PROJECT_ID,
                        position=1,
                        start_seconds=1,
                        end_seconds=2,
                        source_text="How are you?",
                        translated_text=None,
                        revision=0,
                    ),
                ]
            )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_later_invalid_batch_leaves_all_persisted_segments_unchanged(self) -> None:
        fake_client = _FakeClient(
            [
                response([{"id": str(SEGMENT_ID), "translated_text": "Xin chào."}]),
                response([]),
            ]
        )

        with self.assertRaises(TranslationValidationError):
            translate_project(
                self.engine,
                project_id=PROJECT_ID,
                job_id=JOB_ID,
                input_revision=0,
                stage_callback=lambda _stage: None,
                client_factory=lambda: fake_client,
                model="test-model",
                batch_size=1,
            )

        with Session(self.engine) as session:
            segments = session.scalars(
                select(Segment).where(Segment.project_id == PROJECT_ID).order_by(Segment.position)
            ).all()
            job = session.get(Job, JOB_ID)
            self.assertEqual([segment.id for segment in segments], [SEGMENT_ID, SECOND_SEGMENT_ID])
            self.assertEqual([segment.source_text for segment in segments], ["Hello there.", "How are you?"])
            self.assertEqual([segment.translated_text for segment in segments], [None, None])
            self.assertEqual([segment.position for segment in segments], [0, 1])
            self.assertEqual(
                [(segment.start_seconds, segment.end_seconds) for segment in segments],
                [(0, 1), (1, 2)],
            )
            self.assertEqual(job.stage, "transcript_ready")
        self.assertEqual(fake_client.models.request_count, 2)
        self.assertTrue(fake_client.closed)

    def test_no_segments_do_not_create_a_gemini_client(self) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(Segment.__table__.delete())
        factory_calls = 0

        def forbidden_factory() -> object:
            nonlocal factory_calls
            factory_calls += 1
            raise AssertionError("Gemini must not be called for a zero-Segment transcript.")

        result = translate_project(
            self.engine,
            project_id=PROJECT_ID,
            job_id=JOB_ID,
            input_revision=0,
            stage_callback=lambda _stage: None,
            client_factory=forbidden_factory,
            model="test-model",
        )
        self.assertEqual((result.segment_count, result.batch_count), (0, 0))
        self.assertEqual(factory_calls, 0)

    def test_existing_translation_is_preserved_and_not_sent_to_gemini(self) -> None:
        edited_translation = "Bản dịch đã được chỉnh sửa."
        with Session(self.engine) as session, session.begin():
            segment = session.get(Segment, SEGMENT_ID)
            segment.translated_text = edited_translation

        factory_calls = 0

        def forbidden_factory() -> object:
            nonlocal factory_calls
            factory_calls += 1
            raise AssertionError("Edited translation data must not be sent for replacement.")

        with self.assertRaises(TranslationConflictError):
            translate_project(
                self.engine,
                project_id=PROJECT_ID,
                job_id=JOB_ID,
                input_revision=0,
                stage_callback=lambda _stage: None,
                client_factory=forbidden_factory,
                model="test-model",
            )

        with Session(self.engine) as session:
            segment = session.get(Segment, SEGMENT_ID)
            self.assertEqual(segment.translated_text, edited_translation)
            self.assertEqual(segment.source_text, "Hello there.")
            self.assertEqual(segment.position, 0)
            self.assertEqual((segment.start_seconds, segment.end_seconds), (0, 1))
            self.assertEqual(session.get(Job, JOB_ID).stage, "transcript_ready")
        self.assertEqual(factory_calls, 0)


if __name__ == "__main__":
    unittest.main()
