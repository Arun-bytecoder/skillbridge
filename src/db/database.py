"""
database.py — SQLAlchemy engine and session management.

We use SQLAlchemy's modern 2.x style:
  - create_engine() for the connection pool
  - sessionmaker() for creating database sessions
  - get_db() as a FastAPI dependency that yields a session and guarantees cleanup

The DATABASE_URL is read from settings.  For tests, the TEST_DATABASE_URL
environment variable overrides it (allowing SQLite for speed).

Why use a generator dependency (yield)?
  FastAPI calls code before 'yield' before the request handler,
  and code after 'yield' after the response is sent — even on exceptions.
  This guarantees db.close() is always called, preventing connection leaks.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.core.config import settings

# Allow test runs to swap in SQLite without changing .env
_db_url = os.getenv("TEST_DATABASE_URL", settings.DATABASE_URL)

# connect_args is only needed for SQLite (it disables thread-safety check)
_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

engine = create_engine(_db_url, connect_args=_connect_args)

# autocommit=False: we commit explicitly (or rollback on error)
# autoflush=False: we flush explicitly before queries when needed
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models.  All models inherit from this."""
    pass


def get_db():
    """
    FastAPI dependency — yields a SQLAlchemy session, then closes it.
    Use as: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()