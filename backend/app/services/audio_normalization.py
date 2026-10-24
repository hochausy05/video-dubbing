"""Conservative, boundary-only normalization for Edge-TTS MP3 media."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


NORMALIZATION_VERSION = "boundary-silence-v1"
SILENCE_THRESHOLD_DB = -60
MINIMUM_TRAILING_SILENCE_MS = 500
BOUNDARY_PADDING_MS = 120
FFMPEG_TIMEOUT_SECONDS = 60
FFPROBE_TIMEOUT_SECONDS = 30
_MAXIMUM_SILENCE_DB = -90
_MAX_VOLUME_RE = re.compile(r"max_volume:\s*(-?inf|[-\d.]+)\s*dB", re.IGNORECASE)
_SILENCE_EVENT_RE = re.compile(
    r"silence_start:\s*([\d.]+)|silence_end:\s*([\d.]+)"
)


class AudioNormalizationError(ValueError):
    """Raised when audio is invalid or normalization cannot be safely completed."""


@dataclass(frozen=True)
class AudioNormalizationResult:
    original_duration_ms: int
    final_duration_ms: int
    removed_silence_ms: int
    trimmed: bool
    skipped_reason: str | None

    def as_metadata(self) -> dict[str, object]:
        return {
            "version": NORMALIZATION_VERSION,
            "settings": {
                "silence_threshold_db": SILENCE_THRESHOLD_DB,
                "minimum_trailing_silence_ms": MINIMUM_TRAILING_SILENCE_MS,
                "boundary_padding_ms": BOUNDARY_PADDING_MS,
            },
            **asdict(self),
        }


def _run(command: list[str], *, timeout: int = FFMPEG_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AudioNormalizationError("Audio could not be safely analyzed or normalized.") from error


def measured_audio_duration_ms(path: Path) -> int:
    """Measure a decodable audio stream from the actual file using FFprobe."""
    if not path.is_file() or path.stat().st_size == 0:
        raise AudioNormalizationError("Audio file is empty or unavailable.")
    result = _run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "format=duration:stream=duration", "-of", "json", str(path),
    ], timeout=FFPROBE_TIMEOUT_SECONDS)
    if result.returncode:
        raise AudioNormalizationError("Audio file is invalid or unreadable.")
    try:
        metadata = json.loads(result.stdout)
        raw_duration = metadata.get("format", {}).get("duration")
        if raw_duration in (None, ""):
            raw_duration = next(
                stream["duration"] for stream in metadata["streams"] if stream.get("duration")
            )
        duration = Decimal(str(raw_duration))
    except (KeyError, TypeError, ValueError, InvalidOperation, StopIteration, json.JSONDecodeError) as error:
        raise AudioNormalizationError("Audio file has no valid measured duration.") from error
    duration_ms = int((duration * 1000).to_integral_value(rounding=ROUND_HALF_UP)) \
        if duration.is_finite() and duration > 0 else 0
    if duration_ms <= 0:
        raise AudioNormalizationError("Audio file has no valid measured duration.")
    return duration_ms


def _maximum_volume_db(path: Path) -> float:
    result = _run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect",
        "-f", "null", "-",
    ])
    if result.returncode:
        raise AudioNormalizationError("Audio file could not be decoded for validation.")
    match = _MAX_VOLUME_RE.search(result.stderr)
    if not match:
        raise AudioNormalizationError("Audio signal level could not be verified.")
    return float("-inf") if match.group(1).lower() == "-inf" else float(match.group(1))


def _trailing_silence_start(path: Path) -> float | None:
    duration_seconds = measured_audio_duration_ms(path) / 1000
    result = _run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:d=0.5", "-f", "null", "-",
    ])
    if result.returncode:
        raise AudioNormalizationError("Audio boundaries could not be analyzed.")
    pending_start: float | None = None
    trailing_start: float | None = None
    for start_value, end_value in _SILENCE_EVENT_RE.findall(result.stderr):
        if start_value:
            pending_start = float(start_value)
            trailing_start = None
        elif end_value:
            if pending_start is not None and float(end_value) >= duration_seconds - 0.04:
                trailing_start = pending_start
            pending_start = None
    return pending_start if pending_start is not None else trailing_start


def normalize_audio_file(source: Path, destination: Path) -> AudioNormalizationResult:
    """Trim only confident excess trailing silence; never alter the input file.

    Leading silence and internal pauses are retained. The raw source remains at
    its original controlled path (new TTS callers use a `.original.mp3` path).
    If no confidently long tail is detected, the exact source bytes are copied.
    """
    original_duration_ms = measured_audio_duration_ms(source)
    if _maximum_volume_db(source) <= _MAXIMUM_SILENCE_DB:
        raise AudioNormalizationError("Audio contains no meaningful speech signal.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    silence_start = _trailing_silence_start(source)
    if silence_start is None:
        shutil.copy2(source, destination)
        return AudioNormalizationResult(
            original_duration_ms, original_duration_ms, 0, False,
            "No stable trailing-silence boundary was detected.",
        )

    total_seconds = original_duration_ms / 1000
    tail_ms = round((total_seconds - silence_start) * 1000)
    if tail_ms < MINIMUM_TRAILING_SILENCE_MS:
        shutil.copy2(source, destination)
        return AudioNormalizationResult(
            original_duration_ms, original_duration_ms, 0, False,
            "Trailing silence is below the conservative trimming threshold.",
        )

    trim_end = min(total_seconds, silence_start + BOUNDARY_PADDING_MS / 1000)
    temporary_output = destination.with_name(f"{destination.stem}.normalized.tmp.mp3")
    result = _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
        "-af", f"atrim=end={trim_end:.6f},asetpts=N/SR/TB", "-vn", "-map_metadata", "-1",
        "-codec:a", "libmp3lame", "-q:a", "3", "-write_xing", "1", str(temporary_output),
    ])
    try:
        if result.returncode or not temporary_output.is_file() or temporary_output.stat().st_size == 0:
            raise AudioNormalizationError("Trimmed audio could not be generated safely.")
        decoded = _run([
            "ffmpeg", "-hide_banner", "-v", "error", "-i", str(temporary_output), "-f", "null", "-",
        ])
        if decoded.returncode:
            raise AudioNormalizationError("Trimmed audio failed decode validation.")
        final_duration_ms = measured_audio_duration_ms(temporary_output)
        removed_silence_ms = original_duration_ms - final_duration_ms
        if removed_silence_ms <= 0:
            temporary_output.unlink(missing_ok=True)
            shutil.copy2(source, destination)
            return AudioNormalizationResult(
                original_duration_ms, original_duration_ms, 0, False,
                "MP3 frame duration did not decrease after safe trimming.",
            )
        temporary_output.replace(destination)
        return AudioNormalizationResult(
            original_duration_ms, final_duration_ms, removed_silence_ms, True, None,
        )
    except Exception:
        temporary_output.unlink(missing_ok=True)
        raise


def write_normalization_metadata(path: Path, metadata: dict[str, object]) -> None:
    """Write the versioned report beside a staged/published controlled audio file."""
    metadata_path = path.with_name(f"{path.stem}.normalization.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def read_normalization_metadata(path: Path) -> dict[str, object] | None:
    metadata_path = path.with_name(f"{path.stem}.normalization.json")
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload.get("version") == NORMALIZATION_VERSION else None
