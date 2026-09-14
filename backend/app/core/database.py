"""SQLAlchemy engine, session factory, and safe schema initialization."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_database_url
from app.models.base import Base
import app.models.entities  # noqa: F401  # Register model tables with Base metadata.


def normalize_database_url(database_url: str) -> str:
    """Use psycopg 3 for standard PostgreSQL connection URLs."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    raise ValueError("DATABASE_URL must be a PostgreSQL connection URL.")


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create a synchronous PostgreSQL engine for the FastAPI backend and worker."""
    return create_engine(
        normalize_database_url(database_url or get_database_url()),
        pool_pre_ping=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a closed session for future FastAPI dependencies; no endpoints use it yet."""
    with session_factory() as session:
        yield session


def initialize_database(engine: Engine) -> None:
    """Create DATA-01 tables if absent; existing tables and data are never dropped."""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    database_engine = create_database_engine()
    try:
        initialize_database(database_engine)
        print("Database initialization completed.")
    finally:
        database_engine.dispose()
