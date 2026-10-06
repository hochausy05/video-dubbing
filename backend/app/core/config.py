"""Backend-only environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


DATABASE_URL_ENV = "DATABASE_URL"
MAX_UPLOAD_SIZE_BYTES_ENV = "MAX_UPLOAD_SIZE_BYTES"
MAX_VIDEO_DURATION_SECONDS_ENV = "MAX_VIDEO_DURATION_SECONDS"
JOB_WORKER_POLL_INTERVAL_SECONDS_ENV = "JOB_WORKER_POLL_INTERVAL_SECONDS"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GEMINI_MODEL_ENV = "GEMINI_MODEL"
TRANSLATION_BATCH_SIZE_ENV = "TRANSLATION_BATCH_SIZE"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_TRANSLATION_BATCH_SIZE = 40
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
        raise RuntimeError("GEMINI_API_KEY must be configured in the local environment.")
    return api_key.strip()


def get_gemini_model() -> str:
    """Return the centrally configured Gemini model identifier."""
    load_local_environment()
    model = os.getenv(GEMINI_MODEL_ENV, DEFAULT_GEMINI_MODEL).strip()
    if not model or len(model) > 100 or any(character.isspace() for character in model):
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
