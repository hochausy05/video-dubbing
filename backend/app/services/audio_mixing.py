"""Deterministic, timeline-based ducking envelope generation."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Iterable

from app.schemas.render import RenderAudioSettings


def merge_speech_intervals(
    intervals: Iterable[tuple[int, int]], *, duration_ms: int, bridge_gap_ms: int
) -> tuple[tuple[int, int], ...]:
    """Validate output-timeline intervals and bridge short gaps to avoid pumping."""
    ordered = sorted(intervals)
    merged: list[list[int]] = []
    for start, end in ordered:
        if start < 0 or end <= start or end > duration_ms:
            raise ValueError("Speech intervals must be positive and within the planned timeline.")
        if merged and start <= merged[-1][1] + bridge_gap_ms:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return tuple((start, end) for start, end in merged)


def build_ducking_envelope_pcm(
    intervals: Iterable[tuple[int, int]],
    *,
    duration_ms: int,
    settings: RenderAudioSettings,
) -> bytes:
    """Return a 1 kHz signed-16-bit mono gain envelope, one sample per output ms."""
    if duration_ms <= 0 or duration_ms > 2_520_000:
        raise ValueError("Envelope duration is outside the supported video duration.")
    merged = merge_speech_intervals(
        intervals, duration_ms=duration_ms, bridge_gap_ms=settings.bridge_gap_ms
    )
    def encoded(gain: float) -> bytes:
        sample = max(-32768, min(32767, round(gain * 32767)))
        return sample.to_bytes(2, "little", signed=True)

    background_sample = encoded(settings.background_gain)
    ducked_sample = encoded(settings.ducked_gain)
    pcm = bytearray(background_sample * duration_ms)

    def set_gain(point: int, gain: float) -> None:
        sample = encoded(gain)
        pcm[point * 2:point * 2 + 2] = sample

    for start, end in merged:
        attack_start = max(0, start - settings.attack_ms)
        attack_length = start - attack_start
        for point in range(attack_start, start):
            fraction = (point - attack_start + 1) / max(attack_length, 1)
            set_gain(point, settings.background_gain + (
                settings.ducked_gain - settings.background_gain
            ) * fraction)
        pcm[start * 2:end * 2] = ducked_sample * (end - start)
        release_end = min(duration_ms, end + settings.release_ms)
        release_length = release_end - end
        for point in range(end, release_end):
            fraction = (point - end + 1) / max(release_length, 1)
            set_gain(point, settings.ducked_gain + (
                settings.background_gain - settings.ducked_gain
            ) * fraction)
    return bytes(pcm)


def write_ducking_envelope(
    path: Path,
    intervals: Iterable[tuple[int, int]],
    *,
    duration_ms: int,
    settings: RenderAudioSettings,
) -> None:
    """Write the bounded-rate envelope as a job-scoped mono WAV side input."""
    pcm = build_ducking_envelope_pcm(intervals, duration_ms=duration_ms, settings=settings)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(1000)
        output.writeframes(pcm)
