"""Signal-level boundary-silence normalization tests using synthetic MP3 media."""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.audio_normalization import (
    AudioNormalizationError,
    measured_audio_duration_ms,
    normalize_audio_file,
)


def make_mp3(path: Path, parts: list[tuple[str, float]], *, volume: float = 0.08) -> None:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for kind, duration in parts:
        source = (
            f"sine=frequency=440:duration={duration}:sample_rate=24000"
            f",volume={volume}"
            if kind == "speech"
            else f"anullsrc=r=24000:cl=mono:d={duration}"
        )
        command.extend(["-f", "lavfi", "-i", source])
    chain = "".join(f"[{index}:a]" for index in range(len(parts)))
    command.extend([
        "-filter_complex", f"{chain}concat=n={len(parts)}:v=0:a=1[a]",
        "-map", "[a]", "-codec:a", "libmp3lame", "-q:a", "3", str(path),
    ])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise AssertionError(f"Could not create synthetic MP3 fixture: {result.stderr}")


def silence_events(path: Path, minimum_seconds: float = 0.02) -> tuple[list[float], list[float]]:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", f"silencedetect=noise=-60dB:d={minimum_seconds}", "-f", "null", "-",
    ], capture_output=True, text=True, check=False)
    starts = [float(value) for value in re.findall(r"silence_start:\s*([\d.]+)", result.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([\d.]+)", result.stderr)]
    return starts, ends


class AudioNormalizationTests(unittest.TestCase):
    def test_removes_approximately_1000ms_trailing_silence_from_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "one-second-tail.mp3", root / "normalized.mp3"
            make_mp3(source, [("speech", 0.3), ("silence", 1.0)])
            source_bytes = source.read_bytes()
            original_ms = measured_audio_duration_ms(source)
            result = normalize_audio_file(source, output)
            self.assertTrue(result.trimmed)
            self.assertLess(result.final_duration_ms, original_ms)
            self.assertGreaterEqual(result.removed_silence_ms, 650)
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertEqual(measured_audio_duration_ms(output), result.final_duration_ms)

    def test_removes_approximately_800ms_trailing_silence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "tail.mp3", root / "normalized.mp3"
            make_mp3(source, [("speech", 0.3), ("silence", 0.8)])
            result = normalize_audio_file(source, output)
            self.assertTrue(result.trimmed)
            self.assertGreaterEqual(result.removed_silence_ms, 450)
            self.assertLess(result.final_duration_ms, result.original_duration_ms)

    def test_audio_without_excessive_tail_is_byte_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "short-tail.mp3", root / "copy.mp3"
            make_mp3(source, [("speech", 0.3), ("silence", 0.08)])
            result = normalize_audio_file(source, output)
            self.assertFalse(result.trimmed)
            self.assertEqual(result.removed_silence_ms, 0)
            self.assertTrue(result.skipped_reason)
            self.assertEqual(source.read_bytes(), output.read_bytes())

    def test_internal_pause_is_preserved_when_trailing_silence_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "pauses.mp3", root / "normalized.mp3"
            make_mp3(source, [
                ("speech", 0.25), ("silence", 0.65), ("speech", 0.25), ("silence", 0.9),
            ])
            result = normalize_audio_file(source, output)
            self.assertTrue(result.trimmed)
            starts, ends = silence_events(output)
            self.assertTrue(any(start < 0.5 for start in starts), starts)
            self.assertTrue(any(0.7 < end < 1.1 for end in ends), ends)

    def test_low_volume_speech_near_threshold_is_not_treated_as_silence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "quiet.mp3", root / "quiet-copy.mp3"
            make_mp3(source, [("speech", 0.35), ("silence", 0.1)], volume=0.0013)
            result = normalize_audio_file(source, output)
            self.assertFalse(result.trimmed)
            self.assertEqual(source.read_bytes(), output.read_bytes())

    def test_very_short_speech_is_retained_with_nonzero_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "short.mp3", root / "short-normalized.mp3"
            make_mp3(source, [("speech", 0.12), ("silence", 0.8)])
            result = normalize_audio_file(source, output)
            self.assertTrue(result.trimmed)
            self.assertGreater(result.final_duration_ms, 150)
            starts, _ = silence_events(output)
            self.assertTrue(starts and starts[0] >= 0.08, starts)

    def test_completely_silent_and_invalid_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            silent, invalid = root / "silent.mp3", root / "invalid.mp3"
            make_mp3(silent, [("silence", 1.0)])
            invalid.write_bytes(b"not an MP3")
            with self.assertRaises(AudioNormalizationError):
                normalize_audio_file(silent, root / "silent-out.mp3")
            with self.assertRaises(AudioNormalizationError):
                normalize_audio_file(invalid, root / "invalid-out.mp3")

    def test_normalized_file_keeps_short_safe_boundary_padding_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, once, twice = root / "tail.mp3", root / "once.mp3", root / "twice.mp3"
            make_mp3(source, [("speech", 0.3), ("silence", 1.0)])
            first = normalize_audio_file(source, once)
            starts, _ = silence_events(once, 0.02)
            silence_start = max(starts)
            padding_ms = first.final_duration_ms - round(silence_start * 1000)
            self.assertGreaterEqual(padding_ms, 70)
            self.assertLessEqual(padding_ms, 260)
            digest_before = once.read_bytes()
            second = normalize_audio_file(once, twice)
            self.assertFalse(second.trimmed)
            self.assertEqual(second.final_duration_ms, first.final_duration_ms)
            self.assertEqual(twice.read_bytes(), digest_before)

    def test_uncertain_detection_falls_back_to_original_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source.mp3", root / "fallback.mp3"
            make_mp3(source, [("speech", 0.3)])
            with patch("app.services.audio_normalization._trailing_silence_start", return_value=None):
                result = normalize_audio_file(source, output)
            self.assertFalse(result.trimmed)
            self.assertIn("boundary", result.skipped_reason or "")
            self.assertEqual(source.read_bytes(), output.read_bytes())


if __name__ == "__main__":
    unittest.main()
