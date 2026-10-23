"""SQLite persistence: engine management and declarative base."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

_engine = None


def get_engine():
    """Lazily create the engine so tests can retarget `config.settings` first."""
    global _engine
    if _engine is None:
        from .config import settings

        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: background pipeline runs in worker threads.
        _engine = create_engine(
            f"sqlite:///{settings.db_path}",
            connect_args={"check_same_thread": False},
            future=True,
        )
    return _engine


def reset_engine() -> None:
    """Drop the cached engine (used by tests to redirect the database)."""
    global _engine
    _engine = None


def init_db() -> None:
    from . import models  # noqa: F401  (models must be imported to register tables)

    Base.metadata.create_all(get_engine())


def get_db():
    """FastAPI dependency yielding a short-lived SQLAlchemy session."""
    Session = sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
    )
    db = Session()
    try:
        yield db
    finally:
        db.close()
