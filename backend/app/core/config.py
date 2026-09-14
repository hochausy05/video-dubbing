"""Backend-only environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


DATABASE_URL_ENV = "DATABASE_URL"


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
