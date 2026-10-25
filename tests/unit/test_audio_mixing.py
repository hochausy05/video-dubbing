from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from app.schemas.render import RenderAudioSettings
from app.services.audio_mixing import (
    build_ducking_envelope_pcm,
    merge_speech_intervals,
    write_ducking_envelope,
)


class AudioMixingEnvelopeTests(unittest.TestCase):
    def test_zero_speech_uses_background_gain_for_entire_timeline(self) -> None:
        settings = RenderAudioSettings(mode="ducking", background_gain=0.4, ducked_gain=0.1)
        pcm = build_ducking_envelope_pcm([], duration_ms=20, settings=settings)
        self.assertEqual(len(pcm), 40)
        self.assertEqual(int.from_bytes(pcm[:2], "little", signed=True), round(0.4 * 32767))

    def test_single_interval_has_smooth_attack_duck_release_and_zero_start(self) -> None:
        settings = RenderAudioSettings(
            mode="ducking", background_gain=0.4, ducked_gain=0.1,
            attack_ms=10, release_ms=20, bridge_gap_ms=0,
        )
        pcm = build_ducking_envelope_pcm([(15, 20), (0, 5)], duration_ms=45, settings=settings)
        values = [int.from_bytes(pcm[index:index + 2], "little", signed=True) / 32767
                  for index in range(0, len(pcm), 2)]
        self.assertAlmostEqual(values[0], 0.1, delta=0.001)
        self.assertLess(values[9], 0.4)
        self.assertGreater(values[9], 0.1)
        self.assertAlmostEqual(values[15], 0.1, delta=0.001)
        self.assertGreater(values[25], values[20])
        self.assertAlmostEqual(values[44], 0.4, delta=0.001)

    def test_nearby_and_overlapping_intervals_merge_without_gain_recovery(self) -> None:
        merged = merge_speech_intervals([(100, 200), (205, 260), (250, 300), (800, 900)],
                                        duration_ms=1000, bridge_gap_ms=10)
        self.assertEqual(merged, ((100, 300), (800, 900)))

    def test_invalid_interval_and_duration_are_rejected(self) -> None:
        settings = RenderAudioSettings(mode="ducking")
        with self.assertRaises(ValueError):
            build_ducking_envelope_pcm([(-1, 4)], duration_ms=10, settings=settings)
        with self.assertRaises(ValueError):
            build_ducking_envelope_pcm([], duration_ms=0, settings=settings)

    def test_gain_and_timing_settings_are_bounded(self) -> None:
        with self.assertRaises(ValueError):
            RenderAudioSettings(mode="ducking", background_gain=0.2, ducked_gain=0.3)
        with self.assertRaises(ValueError):
            RenderAudioSettings(mode="fixed", tts_gain=1.1)
        with self.assertRaises(ValueError):
            RenderAudioSettings(mode="ducking", attack_ms=1)
        with self.assertRaises(ValueError):
            RenderAudioSettings(mode="fixed", tts_gain=True)
        with self.assertRaises(ValueError):
            RenderAudioSettings(mode="fixed", background_gain=float("nan"))

    def test_interval_near_video_end_clips_release_without_extending_duration(self) -> None:
        settings = RenderAudioSettings(mode="ducking", release_ms=250)
        pcm = build_ducking_envelope_pcm([(900, 1000)], duration_ms=1000, settings=settings)
        self.assertEqual(len(pcm), 2000)
        self.assertEqual(int.from_bytes(pcm[-2:], "little", signed=True), round(settings.ducked_gain * 32767))

    def test_envelope_wav_has_one_millisecond_sample_rate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "envelope.wav"
            write_ducking_envelope(
                path, [(2, 5)], duration_ms=10,
                settings=RenderAudioSettings(mode="ducking"),
            )
            with wave.open(str(path), "rb") as envelope:
                self.assertEqual((envelope.getframerate(), envelope.getnchannels(), envelope.getnframes()),
                                 (1000, 1, 10))


if __name__ == "__main__":
    unittest.main()
