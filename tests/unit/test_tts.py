"""Deterministic adaptive pacing and Edge-TTS service unit tests."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
import shutil
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import aiohttp
from edge_tts.exceptions import NoAudioReceived

from app.services.tts import (
    TTSError,
    adaptive_rate_percent,
    measured_audio_duration_ms,
    synthesize_segment,
)
from app.services.audio_normalization import AudioNormalizationResult
from app.services.audio_normalization import measured_audio_duration_ms as measure_audio_file
from app.services.audio_normalization import read_normalization_metadata
from test_audio_normalization import make_mp3


def _fake_normalizer(source: Path, destination: Path) -> AudioNormalizationResult:
    shutil.copy2(source, destination)
    return AudioNormalizationResult(1_742, 1_742, 0, False, "Fixture has no trailing silence.")


def _copy_fake_normalizer(duration_ms: int):
    def normalize(source: Path, destination: Path) -> AudioNormalizationResult:
        shutil.copy2(source, destination)
        return AudioNormalizationResult(duration_ms, duration_ms, 0, False, "Fixture has no trailing silence.")
    return normalize


class AdaptivePacingTests(unittest.TestCase):
    def test_thresholds_are_strict_and_checked_descending(self) -> None:
        self.assertEqual(adaptive_rate_percent("一 二 三 四 五 六 七", Decimal("2")), 6)  # 3.5
        self.assertEqual(adaptive_rate_percent("一 二 三 四 五 六 七", Decimal("1.65")), 20)
        self.assertEqual(adaptive_rate_percent("一 二 三 四 五 六 七 八", Decimal("2")), 12)  # 4.0
        self.assertEqual(adaptive_rate_percent("一 二 三 四 五 六", Decimal("2")), 6)  # 3.0
        self.assertEqual(adaptive_rate_percent("一 二 三 四 五", Decimal("2")), 0)  # 2.5
        self.assertEqual(adaptive_rate_percent("一 二 一 二 一 二 一 二 四", Decimal("2")), 20)  # 4.5 cap

    def test_exact_thresholds_do_not_increase_rate(self) -> None:
        self.assertEqual(adaptive_rate_percent(" ".join("a" for _ in range(21)), Decimal("5")), 12)
        self.assertEqual(adaptive_rate_percent("a b c d e f g", Decimal("2")), 6)
        self.assertEqual(adaptive_rate_percent(" ".join("a" for _ in range(14)), Decimal("5")), 0)

    def test_unicode_whitespace_tokens_and_invalid_input(self) -> None:
        self.assertEqual(adaptive_rate_percent("  Xin  chào, thế giới!  ", Decimal("0.9")), 20)
        for duration in (0, -1, float("nan"), float("inf")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                adaptive_rate_percent("Xin chào", duration)
        with self.assertRaises(ValueError):
            adaptive_rate_percent(" \n ", 1)


class EdgeTtsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_synthesized_audio_is_normalized_and_raw_media_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = root / "provider-output.mp3"
            destination = root / "segment.mp3"
            make_mp3(fixture, [("speech", 0.3), ("silence", 1.0)])
            original = fixture.read_bytes()

            class Communicate:
                def __init__(self, text: str, voice: str, **kwargs) -> None:
                    self.text, self.voice, self.rate = text, voice, kwargs["rate"]

                async def save(self, target: str) -> None:
                    shutil.copy2(fixture, target)

            duration_ms = await synthesize_segment(
                "Xin chào", destination, voice="vi-VN-HoaiMyNeural", rate_percent=20,
                semaphore=asyncio.Semaphore(1), communicate_factory=Communicate,
            )
            raw_path = root / "segment.original.mp3"
            metadata = read_normalization_metadata(destination)
            self.assertEqual(raw_path.read_bytes(), original)
            self.assertLess(duration_ms, measure_audio_file(raw_path))
            self.assertEqual(measure_audio_file(destination), duration_ms)
            self.assertEqual(metadata["original_duration_ms"], measure_audio_file(raw_path))
            self.assertEqual(metadata["final_duration_ms"], duration_ms)
            self.assertEqual(metadata["rate_percent"], 20)
            self.assertEqual(len(str(metadata["translation_fingerprint"])), 64)

    async def test_transient_failure_retries_once_then_succeeds_without_changing_text(self) -> None:
        attempts = 0
        sleeps: list[float] = []
        settings: list[tuple[str, str, str]] = []
        original_text = "Xin chào, Việt Nam!"

        class Communicate:
            def __init__(self, text: str, voice: str, **kwargs) -> None:
                self.text = text
                self.voice = voice
                self.kwargs = kwargs
                settings.append((text, voice, kwargs["rate"]))

            async def save(self, destination: str) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise aiohttp.ClientConnectionError("transient")
                Path(destination).write_bytes(b"mocked-audio")

        async def no_sleep(delay: float) -> None:
            sleeps.append(delay)

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "app.services.tts.measured_audio_duration_ms", return_value=1742
        ), patch("app.services.tts.normalize_audio_file", side_effect=_fake_normalizer):
            destination = Path(temp_dir) / "segment.mp3"
            duration = await synthesize_segment(
                original_text,
                destination,
                voice="vi-VN-HoaiMyNeural",
                rate_percent=12,
                semaphore=asyncio.Semaphore(1),
                communicate_factory=Communicate,
                retry_sleep=no_sleep,
            )
            self.assertEqual(duration, 1742)
            self.assertEqual(attempts, 2)
            self.assertEqual(sleeps, [0.5])
            self.assertEqual(settings, [
                (original_text, "vi-VN-HoaiMyNeural", "+12%"),
                (original_text, "vi-VN-HoaiMyNeural", "+12%"),
            ])
            self.assertTrue(destination.is_file())

    async def test_no_audio_received_retries_and_can_succeed(self) -> None:
        attempts = 0
        request_attempts: list[int] = []
        sleeps: list[float] = []

        class Communicate:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            async def save(self, destination: str) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise NoAudioReceived("no provider audio")
                Path(destination).write_bytes(b"mocked-audio")

        async def no_sleep(delay: float) -> None:
            sleeps.append(delay)

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "app.services.tts.measured_audio_duration_ms", return_value=900
        ), patch("app.services.tts.normalize_audio_file", side_effect=_copy_fake_normalizer(900)):
            duration = await synthesize_segment(
                "Xin chào", Path(temp_dir) / "segment.mp3", voice="vi-VN-HoaiMyNeural",
                rate_percent=22, semaphore=asyncio.Semaphore(1), communicate_factory=Communicate,
                retry_sleep=no_sleep, segment_id=uuid.UUID(int=1), artifact_id=uuid.UUID(int=2),
                attempt_callback=request_attempts.append,
            )

        self.assertEqual(duration, 900)
        self.assertEqual(attempts, 2)
        self.assertEqual(request_attempts, [1, 2])
        self.assertEqual(sleeps, [0.5])

    async def test_repeated_no_audio_received_stops_at_three_requests(self) -> None:
        attempts = 0
        request_attempts: list[int] = []
        sleeps: list[float] = []

        class Communicate:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            async def save(self, _destination: str) -> None:
                nonlocal attempts
                attempts += 1
                raise NoAudioReceived("no provider audio")

        async def no_sleep(delay: float) -> None:
            sleeps.append(delay)

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(TTSError):
                await synthesize_segment(
                    "Xin chào", Path(temp_dir) / "segment.mp3", voice="vi-VN-HoaiMyNeural",
                    rate_percent=35, semaphore=asyncio.Semaphore(1), communicate_factory=Communicate,
                    retry_sleep=no_sleep, segment_id=uuid.UUID(int=3), artifact_id=uuid.UUID(int=4),
                    attempt_callback=request_attempts.append,
                )

        self.assertEqual(attempts, 3)
        self.assertEqual(request_attempts, [1, 2, 3])
        self.assertEqual(sleeps, [0.5, 1.0])

    async def test_permanent_failure_is_not_retried(self) -> None:
        for provider_error in (
            ValueError("invalid voice configuration"),
            aiohttp.ClientResponseError(request_info=None, history=(), status=403),
        ):
            attempts = 0

            class Communicate:
                def __init__(self, *_args, **_kwargs) -> None:
                    pass

                async def save(self, _destination: str) -> None:
                    nonlocal attempts
                    attempts += 1
                    raise provider_error

            with self.subTest(error=type(provider_error).__name__), tempfile.TemporaryDirectory() as temp_dir:
                with self.assertRaises(TTSError):
                    await synthesize_segment(
                        "Xin chào", Path(temp_dir) / "bad.mp3", voice="vi-VN-HoaiMyNeural",
                        rate_percent=0, semaphore=asyncio.Semaphore(1), communicate_factory=Communicate,
                    )
            self.assertEqual(attempts, 1)

    async def test_failed_attempt_logs_only_safe_exception_metadata(self) -> None:
        class Communicate:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            async def save(self, _destination: str) -> None:
                raise ValueError("API_KEY=private-provider-detail")

        with tempfile.TemporaryDirectory() as temp_dir, self.assertLogs(
            "autodub.tts", level="WARNING"
        ) as captured:
            with self.assertRaises(TTSError):
                await synthesize_segment(
                    "Xin chào", Path(temp_dir) / "bad.mp3", voice="vi-VN-HoaiMyNeural",
                    rate_percent=0, semaphore=asyncio.Semaphore(1), communicate_factory=Communicate,
                    segment_id=uuid.UUID(int=5), artifact_id=uuid.UUID(int=6),
                )

        output = "\n".join(captured.output)
        self.assertIn("segment_id=00000000-0000-0000-0000-000000000005", output)
        self.assertIn("artifact_id=00000000-0000-0000-0000-000000000006", output)
        self.assertIn("rate_percent=0", output)
        self.assertIn("attempt=1/3", output)
        self.assertIn("exception_class=ValueError", output)
        self.assertIn("http_status=None", output)
        self.assertNotIn("private-provider-detail", output)
        self.assertNotIn("API_KEY", output)

    async def test_repeated_transient_failure_stops_at_retry_limit(self) -> None:
        attempts = 0
        sleeps: list[float] = []

        class Communicate:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            async def save(self, _destination: str) -> None:
                nonlocal attempts
                attempts += 1
                raise aiohttp.ClientConnectionError("transient")

        async def no_sleep(delay: float) -> None:
            sleeps.append(delay)

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(TTSError):
                await synthesize_segment(
                    "Xin chào", Path(temp_dir) / "retry.mp3", voice="vi-VN-HoaiMyNeural",
                    rate_percent=0, semaphore=asyncio.Semaphore(1), communicate_factory=Communicate,
                    retry_sleep=no_sleep,
                )
        self.assertEqual(attempts, 3)
        self.assertEqual(sleeps, [0.5, 1.0])

    async def test_concurrency_is_bounded_by_semaphore(self) -> None:
        active = 0
        maximum = 0

        class Communicate:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            async def save(self, destination: str) -> None:
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                await asyncio.sleep(0.01)
                Path(destination).write_bytes(b"mocked-audio")
                active -= 1

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "app.services.tts.measured_audio_duration_ms", return_value=900
        ), patch("app.services.tts.normalize_audio_file", side_effect=_copy_fake_normalizer(900)):
            semaphore = asyncio.Semaphore(2)
            await asyncio.gather(*(
                synthesize_segment(
                    f"Xin chào {index}", Path(temp_dir) / f"{index}.mp3",
                    voice="vi-VN-HoaiMyNeural", rate_percent=0,
                    semaphore=semaphore, communicate_factory=Communicate,
                )
                for index in range(6)
            ))
        self.assertEqual(maximum, 2)

    def test_ffprobe_rejects_missing_and_invalid_audio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.mp3"
            with self.assertRaises(TTSError):
                measured_audio_duration_ms(missing)
            empty = Path(temp_dir) / "empty.mp3"
            empty.touch()
            with self.assertRaises(TTSError):
                measured_audio_duration_ms(empty)

    def test_ffprobe_parses_real_duration_and_rejects_zero(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            media = Path(temp_dir) / "ok.mp3"
            media.write_bytes(b"placeholder")
            successful = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout='{"format":{"duration":"1.2346"},"streams":[{"codec_type":"audio"}]}',
                stderr="",
            )
            with patch("app.services.audio_normalization.subprocess.run", return_value=successful):
                self.assertEqual(measured_audio_duration_ms(media), 1235)
            zero = subprocess.CompletedProcess(args=[], returncode=0, stdout='{"format":{"duration":"0"}}', stderr="")
            with patch("app.services.audio_normalization.subprocess.run", return_value=zero), self.assertRaises(TTSError):
                measured_audio_duration_ms(media)


if __name__ == "__main__":
    unittest.main()
