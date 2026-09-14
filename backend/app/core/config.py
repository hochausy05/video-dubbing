"""Backend-only environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


DATABASE_URL_ENV = "DATABASE_URL"


def load_local_environment() -> None:
    """Load the repository-local ignored .env file without replacing OS variables."""
    repository_root = Path(__file__).resolve().parents[3]
    load_dotenv(repository_root / ".env", override=False)


def get_database_url() -> str:
    """Return the configured PostgreSQL URL without exposing it in errors or logs."""
    load_local_environment()
    database_url = os.getenv(DATABASE_URL_ENV)
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured in the environment.")
    return database_url
