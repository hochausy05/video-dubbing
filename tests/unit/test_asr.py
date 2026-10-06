"""Pure validation tests for normalized Whisper segment output."""

from types import SimpleNamespace
import unittest
from decimal import Decimal

from app.services.asr import ASRDataError, normalize_segments


class NormalizeSegmentsTests(unittest.TestCase):
    def test_trims_text_and_assigns_deterministic_positions(self) -> None:
        normalized = normalize_segments(
            [
                SimpleNamespace(start=0.0194, end=0.4122, text="  Hello there.  "),
                SimpleNamespace(start=0.8, end=1.1, text="  \n"),
                SimpleNamespace(start=1.5, end=2.003, text=" Next sentence."),
            ]
        )

        self.assertEqual([segment.position for segment in normalized], [0, 1])
        self.assertEqual([segment.source_text for segment in normalized], ["Hello there.", "Next sentence."])
        self.assertEqual(normalized[0].start_seconds, Decimal("0.019"))
        self.assertEqual(normalized[0].end_seconds, Decimal("0.412"))

    def test_empty_transcript_is_valid(self) -> None:
        self.assertEqual(normalize_segments([]), ())
        self.assertEqual(
            normalize_segments([SimpleNamespace(start=0, end=1, text="  ")]),
            (),
        )

    def test_rejects_invalid_or_out_of_order_timestamps(self) -> None:
        invalid_outputs = [
            [SimpleNamespace(start=-0.1, end=0.5, text="negative")],
            [SimpleNamespace(start=1, end=1, text="zero duration")],
            [SimpleNamespace(start=float("nan"), end=2, text="not finite")],
            [
                SimpleNamespace(start=2, end=3, text="later"),
                SimpleNamespace(start=1, end=1.5, text="earlier"),
            ],
            [SimpleNamespace(start=0, end=0.0001, text="below schema precision")],
        ]
        for output in invalid_outputs:
            with self.subTest(output=output), self.assertRaises(ASRDataError):
                normalize_segments(output)


if __name__ == "__main__":
    unittest.main()
