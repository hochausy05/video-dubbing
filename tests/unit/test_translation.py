"""Strict Gemini response and transactional translation behavior tests."""

from __future__ import annotations

import json
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Job, Project, Segment
from app.models.base import Base
from app.services.translation import (
    SegmentSnapshot,
    TranslationConflictError,
    TranslationProviderError,
    TranslationValidationError,
    _build_prompt,
    _plan_translation_batches,
    _create_gemini_client,
    _request_batch,
    _RequestMetrics,
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
    def __init__(self, responses: list[object]) -> None:
        self._responses = iter(responses)
        self.request_count = 0
        self.requests: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> _FakeResponse:
        self.request_count += 1
        self.requests.append(kwargs)
        result = next(self._responses)
        if isinstance(result, Exception):
            raise result
        return _FakeResponse(result)


class _FakeClient:
    """Deterministic mock provider used by unit tests; never calls Gemini."""

    def __init__(self, responses: list[object]) -> None:
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
                response([]),
            ]
        )

        with patch("app.services.translation.get_translation_bulk_max_segments", return_value=1):
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
        self.assertEqual(fake_client.models.request_count, 3)
        self.assertTrue(fake_client.closed)

    def test_short_transcript_uses_one_bulk_request_with_timeline_context(self) -> None:
        client = _FakeClient([response([
            {"id": str(SEGMENT_ID), "translated_text": "Xin chào."},
            {"id": str(SECOND_SEGMENT_ID), "translated_text": "Bạn khỏe không?"},
        ])])
        result = translate_project(
            self.engine, project_id=PROJECT_ID, job_id=JOB_ID,
            input_revision=0, stage_callback=lambda _stage: None,
            client_factory=lambda: client, model="test-model",
        )
        self.assertEqual((result.segment_count, result.batch_count, result.request_count), (2, 1, 1))
        request = client.models.requests[0]
        prompt = str(request["contents"])
        payload = json.loads(prompt.split("Input JSON:\n", 1)[1])
        self.assertEqual(payload["context"], [])
        self.assertEqual([row["id"] for row in payload["segments_to_translate"]], [
            str(SEGMENT_ID), str(SECOND_SEGMENT_ID)
        ])
        self.assertEqual(payload["segments_to_translate"][0]["start_seconds"], "0.000")
        self.assertEqual(payload["segments_to_translate"][0]["end_seconds"], "1.000")
        self.assertEqual(payload["segments_to_translate"][0]["source_duration_seconds"], "1.000")
        self.assertEqual(payload["segments_to_translate"][0]["order"], 0)
        self.assertEqual(result.retry_count, 0)
        self.assertGreaterEqual(result.duration_ms, 0)

    def test_267_segments_fit_one_request_when_budgets_allow(self) -> None:
        segments = [
            SegmentSnapshot(
                id=uuid.uuid5(PROJECT_ID, str(index)),
                project_id=PROJECT_ID,
                position=index,
                start_seconds=index,
                end_seconds=index + 1,
                source_text=f"你好{index}",
                revision=0,
                warnings=None,
            )
            for index in range(267)
        ]
        with Session(self.engine) as session, session.begin():
            session.execute(Segment.__table__.delete())
            session.add_all([
                Segment(
                    id=row.id,
                    project_id=PROJECT_ID,
                    position=row.position,
                    start_seconds=row.start_seconds,
                    end_seconds=row.end_seconds,
                    source_text=row.source_text,
                    translated_text=None,
                    revision=0,
                )
                for row in segments
            ])
        mocked_response = response([
            {"id": str(row.id), "translated_text": f"Bản dịch {row.position}"}
            for row in segments
        ])
        client = _FakeClient([mocked_response])
        with (
            patch("app.services.translation.get_translation_input_token_budget", return_value=262_144),
            patch("app.services.translation.get_translation_output_token_budget", return_value=65_536),
            patch("app.services.translation.get_translation_bulk_max_segments", return_value=500),
            patch("app.services.translation.get_translation_bulk_max_source_characters", return_value=120_000),
        ):
            result = translate_project(
                self.engine, project_id=PROJECT_ID, job_id=JOB_ID,
                input_revision=0, stage_callback=lambda _stage: None,
                client_factory=lambda: client, model="test-model", batch_size=40,
            )
        self.assertEqual((result.segment_count, result.batch_count, result.request_count), (267, 1, 1))
        self.assertEqual(client.models.request_count, 1)
        self.assertEqual(client.models.requests[0]["config"].max_output_tokens, 65_536)
        with Session(self.engine) as session:
            persisted = session.scalars(
                select(Segment).where(Segment.project_id == PROJECT_ID).order_by(Segment.position)
            ).all()
        self.assertEqual(len(persisted), 267)
        self.assertEqual(len({row.id for row in persisted}), 267)
        self.assertEqual([row.position for row in persisted], list(range(267)))
        self.assertEqual([row.start_seconds for row in persisted], list(range(267)))
        self.assertEqual([row.translated_text for row in persisted], [f"Bản dịch {index}" for index in range(267)])

    def test_over_budget_transcript_uses_ordered_batches_with_context_only_rows(self) -> None:
        segments = [
            SegmentSnapshot(
                id=uuid.uuid5(PROJECT_ID, str(index)),
                project_id=PROJECT_ID,
                position=index,
                start_seconds=index * 2,
                end_seconds=index * 2 + 1,
                source_text=f"dialogue {index}",
                revision=0,
                warnings=None,
            )
            for index in range(5)
        ]
        batches = _plan_translation_batches(
            segments,
            batch_size=2,
            input_token_budget=20_000,
            output_token_budget=20_000,
            bulk_max_segments=2,
            bulk_max_source_characters=120_000,
            context_window=1,
        )
        self.assertEqual([[row.position for row in batch.targets] for batch in batches], [[0, 1], [2, 3], [4]])
        self.assertEqual([[row.position for row in batch.context] for batch in batches], [[2], [1, 4], [3]])
        for batch in batches:
            prompt = _build_prompt(batch)
            payload = json.loads(prompt.split("Input JSON:\n", 1)[1])
            self.assertEqual(
                [row["order"] for row in payload["segments_to_translate"]],
                [row.position for row in batch.targets],
            )
            self.assertTrue(all(row["context_only"] for row in payload["context"]))
            self.assertTrue(all(not row["context_only"] for row in payload["segments_to_translate"]))

        context_batch = batches[1]
        rows_including_forbidden_context = [
            {"id": str(row.id), "translated_text": "Bản dịch."}
            for row in (*context_batch.targets, context_batch.context[0])
        ]
        fake_client = _FakeClient([
            response(rows_including_forbidden_context),
            response(rows_including_forbidden_context),
        ])
        with self.assertRaises(TranslationValidationError):
            _request_batch(
                fake_client,
                "test-model",
                context_batch,
                output_token_budget=20_000,
                metrics=_RequestMetrics(),
            )
        self.assertEqual(fake_client.models.request_count, 2)

    def test_input_or_output_budget_exhaustion_splits_or_fails_without_truncating(self) -> None:
        segments = [
            SegmentSnapshot(
                id=uuid.uuid5(PROJECT_ID, str(index)),
                project_id=PROJECT_ID,
                position=index,
                start_seconds=index,
                end_seconds=index + 1,
                source_text="短い台詞",
                revision=0,
                warnings=None,
            )
            for index in range(4)
        ]
        batches = _plan_translation_batches(
            segments,
            batch_size=4,
            input_token_budget=20_000,
            output_token_budget=400,
            bulk_max_segments=500,
            bulk_max_source_characters=120_000,
            context_window=0,
        )
        self.assertGreater(len(batches), 1)
        self.assertEqual([row.id for batch in batches for row in batch.targets], [row.id for row in segments])
        input_limited_batches = _plan_translation_batches(
            segments,
            batch_size=4,
            input_token_budget=1_400,
            output_token_budget=20_000,
            bulk_max_segments=500,
            bulk_max_source_characters=120_000,
            context_window=0,
        )
        self.assertEqual([len(batch.targets) for batch in input_limited_batches], [2, 2])
        with self.assertRaises(TranslationValidationError):
            _plan_translation_batches(
                [segments[0]],
                batch_size=1,
                input_token_budget=20_000,
                output_token_budget=100,
                bulk_max_segments=0,
                bulk_max_source_characters=120_000,
                context_window=0,
            )

    def test_real_client_configuration_disables_sdk_retries_and_bounds_timeout(self) -> None:
        from google import genai

        with patch("app.services.translation.get_gemini_api_key", return_value="mock-key"):
            with patch.object(genai, "Client") as client_constructor:
                _create_gemini_client()
        options = client_constructor.call_args.kwargs["http_options"]
        self.assertEqual(options.retry_options.attempts, 1)
        self.assertEqual(options.timeout, 120_000)

    def test_quota_error_fails_without_retry(self) -> None:
        error = RuntimeError("quota exceeded; daily limit")
        error.status_code = 429  # type: ignore[attr-defined]
        client = _FakeClient([error])
        with patch("app.services.translation.time.sleep") as sleep:
            with self.assertRaises(TranslationProviderError) as raised:
                translate_project(
                    self.engine, project_id=PROJECT_ID, job_id=JOB_ID,
                    input_revision=0, stage_callback=lambda _stage: None,
                    client_factory=lambda: client, model="test-model", batch_size=2,
                )
        self.assertEqual(raised.exception.category, "quota")
        self.assertEqual(client.models.request_count, 1)
        sleep.assert_not_called()

    def test_transient_error_retries_once_and_succeeds_without_real_sleep(self) -> None:
        ok = response([
            {"id": str(SEGMENT_ID), "translated_text": "Xin chào."},
            {"id": str(SECOND_SEGMENT_ID), "translated_text": "Bạn khỏe không?"},
        ])
        client = _FakeClient([TimeoutError("network timeout"), ok])
        with patch("app.services.translation.time.sleep") as sleep:
            result = translate_project(
                self.engine, project_id=PROJECT_ID, job_id=JOB_ID,
                input_revision=0, stage_callback=lambda _stage: None,
                client_factory=lambda: client, model="test-model", batch_size=2,
            )
        self.assertEqual(result.segment_count, 2)
        self.assertEqual(client.models.request_count, 2)
        sleep.assert_called_once_with(0.5)

    def test_repeated_transient_error_stops_after_one_retry(self) -> None:
        client = _FakeClient([TimeoutError("timeout"), TimeoutError("timeout")])
        with patch("app.services.translation.time.sleep") as sleep:
            with self.assertRaises(TranslationProviderError) as raised:
                translate_project(
                    self.engine, project_id=PROJECT_ID, job_id=JOB_ID,
                    input_revision=0, stage_callback=lambda _stage: None,
                    client_factory=lambda: client, model="test-model", batch_size=2,
                )
        self.assertEqual(raised.exception.category, "transient")
        self.assertEqual(client.models.request_count, 2)
        sleep.assert_called_once_with(0.5)
        with Session(self.engine) as session:
            self.assertEqual(session.get(Segment, SEGMENT_ID).translated_text, None)

    def test_authentication_error_is_not_retried(self) -> None:
        error = RuntimeError("invalid API key")
        error.status_code = 401  # type: ignore[attr-defined]
        client = _FakeClient([error])
        with patch("app.services.translation.time.sleep") as sleep:
            with self.assertRaises(TranslationProviderError) as raised:
                translate_project(
                    self.engine, project_id=PROJECT_ID, job_id=JOB_ID,
                    input_revision=0, stage_callback=lambda _stage: None,
                    client_factory=lambda: client, model="test-model", batch_size=2,
                )
        self.assertEqual(raised.exception.category, "permanent")
        self.assertEqual(client.models.request_count, 1)
        sleep.assert_not_called()

    def test_malformed_response_retries_once_then_fails_without_source_fallback(self) -> None:
        client = _FakeClient([response([]), response([])])
        with self.assertRaises(TranslationValidationError):
            translate_project(
                self.engine, project_id=PROJECT_ID, job_id=JOB_ID,
                input_revision=0, stage_callback=lambda _stage: None,
                client_factory=lambda: client, model="test-model", batch_size=2,
            )
        self.assertEqual(client.models.request_count, 2)
        with Session(self.engine) as session:
            segments = session.scalars(select(Segment).order_by(Segment.position)).all()
            self.assertEqual([s.translated_text for s in segments], [None, None])
            self.assertEqual([s.source_text for s in segments], ["Hello there.", "How are you?"])

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
