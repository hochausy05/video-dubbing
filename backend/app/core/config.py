"""Backend-only environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


DATABASE_URL_ENV = "DATABASE_URL"
MAX_UPLOAD_SIZE_BYTES_ENV = "MAX_UPLOAD_SIZE_BYTES"
MAX_VIDEO_DURATION_SECONDS_ENV = "MAX_VIDEO_DURATION_SECONDS"
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
