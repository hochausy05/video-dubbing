"""Backend-only environment configuration."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv


DATABASE_URL_ENV = "DATABASE_URL"
MAX_UPLOAD_SIZE_BYTES_ENV = "MAX_UPLOAD_SIZE_BYTES"
MAX_VIDEO_DURATION_SECONDS_ENV = "MAX_VIDEO_DURATION_SECONDS"
JOB_WORKER_POLL_INTERVAL_SECONDS_ENV = "JOB_WORKER_POLL_INTERVAL_SECONDS"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GEMINI_MODEL_ENV = "GEMINI_MODEL"
TRANSLATION_BATCH_SIZE_ENV = "TRANSLATION_BATCH_SIZE"
TRANSLATION_INPUT_TOKEN_BUDGET_ENV = "TRANSLATION_INPUT_TOKEN_BUDGET"
TRANSLATION_OUTPUT_TOKEN_BUDGET_ENV = "TRANSLATION_OUTPUT_TOKEN_BUDGET"
TRANSLATION_BULK_MAX_SEGMENTS_ENV = "TRANSLATION_BULK_MAX_SEGMENTS"
TRANSLATION_BULK_MAX_SOURCE_CHARACTERS_ENV = "TRANSLATION_BULK_MAX_SOURCE_CHARACTERS"
EDGE_TTS_VOICE_ENV = "EDGE_TTS_VOICE"
EDGE_TTS_CONCURRENCY_ENV = "EDGE_TTS_CONCURRENCY"
TTS_OPTIMIZATION_MAX_RATE_ENV = "TTS_OPTIMIZATION_MAX_RATE_PERCENT"
TTS_OPTIMIZATION_MAX_ATTEMPTS_ENV = "TTS_OPTIMIZATION_MAX_ATTEMPTS"
RENDER_ORIGINAL_AUDIO_GAIN_ENV = "RENDER_ORIGINAL_AUDIO_GAIN"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_EDGE_TTS_VOICE = "vi-VN-HoaiMyNeural"
DEFAULT_TRANSLATION_BATCH_SIZE = 40
DEFAULT_TRANSLATION_INPUT_TOKEN_BUDGET = 262_144
DEFAULT_TRANSLATION_OUTPUT_TOKEN_BUDGET = 16_384
DEFAULT_TRANSLATION_BULK_MAX_SEGMENTS = 500
DEFAULT_TRANSLATION_BULK_MAX_SOURCE_CHARACTERS = 120_000
GEMINI_MAX_INPUT_TOKEN_LIMIT = 1_048_576
GEMINI_MAX_OUTPUT_TOKEN_LIMIT = 65_536
DEFAULT_EDGE_TTS_CONCURRENCY = 5
DEFAULT_TTS_OPTIMIZATION_MAX_RATE_PERCENT = 35
DEFAULT_TTS_OPTIMIZATION_MAX_ATTEMPTS = 4
DEFAULT_RENDER_ORIGINAL_AUDIO_GAIN = 0.10
MAX_TRANSLATION_TEXT_CHARACTERS = 10_000
MAX_UPLOAD_SIZE_BYTES = 104_857_600
MAX_VIDEO_DURATION_SECONDS = 1_800


def get_repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_local_environment() -> None:
    """Load the repository-local ignored .env file without replacing OS variables."""
    load_dotenv(get_repository_root() / ".env", override=False)


def get_storage_root() -> Path:
    """Return the server-managed runtime storage root."""
    return get_repository_root() / "storage"


def get_database_url() -> str:
    """Return the configured PostgreSQL URL without exposing it in errors or logs."""
    load_local_environment()
    database_url = os.getenv(DATABASE_URL_ENV)
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured in the environment.")
    return database_url


def _get_positive_integer_setting(environment_name: str, default: int) -> int:
    """Read a positive integer setting without exposing its value in errors."""
    load_local_environment()
    configured_value = os.getenv(environment_name)
    if configured_value is None:
        return default
    try:
        value = int(configured_value)
    except ValueError as error:
        raise RuntimeError(f"{environment_name} must be a positive integer.") from error
    if value <= 0:
        raise RuntimeError(f"{environment_name} must be a positive integer.")
    return value


def get_max_upload_size_bytes() -> int:
    """Return the configured source-upload byte limit."""
    return _get_positive_integer_setting(MAX_UPLOAD_SIZE_BYTES_ENV, MAX_UPLOAD_SIZE_BYTES)


def get_max_video_duration_seconds() -> int:
    """Return the configured source-video duration limit."""
    return _get_positive_integer_setting(
        MAX_VIDEO_DURATION_SECONDS_ENV, MAX_VIDEO_DURATION_SECONDS
    )


def get_job_worker_poll_interval_seconds() -> float:
    """Return the worker polling interval, defaulting to a low-load one second."""
    load_local_environment()
    configured_value = os.getenv(JOB_WORKER_POLL_INTERVAL_SECONDS_ENV)
    if configured_value is None:
        return 1.0
    try:
        value = float(configured_value)
    except ValueError as error:
        raise RuntimeError(
            f"{JOB_WORKER_POLL_INTERVAL_SECONDS_ENV} must be a positive number."
        ) from error
    if not 0.05 <= value <= 60:
        raise RuntimeError(
            f"{JOB_WORKER_POLL_INTERVAL_SECONDS_ENV} must be between 0.05 and 60 seconds."
        )
    return value


def get_gemini_api_key() -> str:
    """Return the locally configured Gemini credential without logging or exposing it."""
    load_local_environment()
    api_key = os.getenv(GEMINI_API_KEY_ENV)
    if not api_key or not api_key.strip():
        raise RuntimeError("GEMINI_API_KEY must be configured in the root .env or process environment.")
    return api_key.strip()


def get_gemini_model() -> str:
    """Return the centrally configured Gemini model identifier."""
    load_local_environment()
    model = os.getenv(GEMINI_MODEL_ENV, DEFAULT_GEMINI_MODEL).strip()
    if not model or len(model) > 100 or re.fullmatch(r"[A-Za-z0-9._/-]+", model) is None:
        raise RuntimeError("GEMINI_MODEL must be a non-empty model identifier.")
    return model


def get_translation_batch_size() -> int:
    """Return the bounded number of Segments sent in one Gemini request."""
    batch_size = _get_positive_integer_setting(
        TRANSLATION_BATCH_SIZE_ENV, DEFAULT_TRANSLATION_BATCH_SIZE
    )
    if batch_size > 100:
        raise RuntimeError(f"{TRANSLATION_BATCH_SIZE_ENV} must be between 1 and 100.")
    return batch_size


def get_translation_input_token_budget() -> int:
    """Return the app's conservative input-token budget for a Gemini request."""
    value = _get_positive_integer_setting(
        TRANSLATION_INPUT_TOKEN_BUDGET_ENV, DEFAULT_TRANSLATION_INPUT_TOKEN_BUDGET
    )
    if value > GEMINI_MAX_INPUT_TOKEN_LIMIT:
        raise RuntimeError(
            f"{TRANSLATION_INPUT_TOKEN_BUDGET_ENV} exceeds the supported Gemini input limit."
        )
    return value


def get_translation_output_token_budget() -> int:
    """Return the app's conservative output-token cap for a Gemini request."""
    value = _get_positive_integer_setting(
        TRANSLATION_OUTPUT_TOKEN_BUDGET_ENV, DEFAULT_TRANSLATION_OUTPUT_TOKEN_BUDGET
    )
    if value > GEMINI_MAX_OUTPUT_TOKEN_LIMIT:
        raise RuntimeError(
            f"{TRANSLATION_OUTPUT_TOKEN_BUDGET_ENV} exceeds the supported Gemini output limit."
        )
    return value


def get_translation_bulk_max_segments() -> int:
    """Return the legacy-informed ceiling for a full-transcript translation call."""
    value = _get_positive_integer_setting(
        TRANSLATION_BULK_MAX_SEGMENTS_ENV, DEFAULT_TRANSLATION_BULK_MAX_SEGMENTS
    )
    if value > DEFAULT_TRANSLATION_BULK_MAX_SEGMENTS:
        raise RuntimeError(
            f"{TRANSLATION_BULK_MAX_SEGMENTS_ENV} must not exceed "
            f"{DEFAULT_TRANSLATION_BULK_MAX_SEGMENTS}."
        )
    return value


def get_translation_bulk_max_source_characters() -> int:
    """Return the legacy-informed source-character ceiling for full transcript calls."""
    value = _get_positive_integer_setting(
        TRANSLATION_BULK_MAX_SOURCE_CHARACTERS_ENV,
        DEFAULT_TRANSLATION_BULK_MAX_SOURCE_CHARACTERS,
    )
    if value > DEFAULT_TRANSLATION_BULK_MAX_SOURCE_CHARACTERS:
        raise RuntimeError(
            f"{TRANSLATION_BULK_MAX_SOURCE_CHARACTERS_ENV} must not exceed "
            f"{DEFAULT_TRANSLATION_BULK_MAX_SOURCE_CHARACTERS}."
        )
    return value


def get_edge_tts_voice() -> str:
    """Return the configured Vietnamese Edge-TTS voice."""
    load_local_environment()
    voice = os.getenv(EDGE_TTS_VOICE_ENV, DEFAULT_EDGE_TTS_VOICE).strip()
    if not voice or len(voice) > 255 or not voice.startswith("vi-VN-"):
        raise RuntimeError("EDGE_TTS_VOICE must be a Vietnamese vi-VN voice identifier.")
    return voice


def get_edge_tts_concurrency() -> int:
    """Bound concurrent Segment synthesis requests."""
    value = _get_positive_integer_setting(EDGE_TTS_CONCURRENCY_ENV, DEFAULT_EDGE_TTS_CONCURRENCY)
    if value > 5:
        raise RuntimeError("EDGE_TTS_CONCURRENCY must be between 1 and 5.")
    return value


def get_tts_optimization_max_rate_percent() -> int:
    """Return the bounded maximum Edge-TTS rate used by duration optimization."""
    value = _get_positive_integer_setting(
        TTS_OPTIMIZATION_MAX_RATE_ENV, DEFAULT_TTS_OPTIMIZATION_MAX_RATE_PERCENT
    )
    if value < 20 or value > 35:
        raise RuntimeError(f"{TTS_OPTIMIZATION_MAX_RATE_ENV} must be between 20 and 35.")
    return value


def get_tts_optimization_max_attempts() -> int:
    """Bound optimization regeneration rounds for each Segment."""
    value = _get_positive_integer_setting(
        TTS_OPTIMIZATION_MAX_ATTEMPTS_ENV, DEFAULT_TTS_OPTIMIZATION_MAX_ATTEMPTS
    )
    if value > 4:
        raise RuntimeError(f"{TTS_OPTIMIZATION_MAX_ATTEMPTS_ENV} must be between 1 and 4.")
    return value


def get_render_original_audio_gain() -> float:
    """Return the bounded background-audio level used beneath Vietnamese dubbing."""
    load_local_environment()
    configured_value = os.getenv(RENDER_ORIGINAL_AUDIO_GAIN_ENV)
    if configured_value is None:
        return DEFAULT_RENDER_ORIGINAL_AUDIO_GAIN
    try:
        value = float(configured_value)
    except ValueError as error:
        raise RuntimeError(f"{RENDER_ORIGINAL_AUDIO_GAIN_ENV} must be between 0 and 1.") from error
    if not 0 <= value <= 1:
        raise RuntimeError(f"{RENDER_ORIGINAL_AUDIO_GAIN_ENV} must be between 0 and 1.")
    return value
