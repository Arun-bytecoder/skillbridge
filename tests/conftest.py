"""
conftest.py — pytest fixtures shared across all test files.

Key decisions:
  - We use SQLite in-memory for speed.  Two tests hit a real (SQLite) database
    rather than mocking — this catches real FK constraint failures, duplicate
    violations, and ORM bugs.
  - The `client` fixture creates a fresh database for every test function,
    so tests are fully isolated (no shared state between tests).
  - We override the `get_db` dependency so FastAPI uses the test DB session
    instead of the production one.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Point at SQLite before importing anything that reads DATABASE_URL
os.environ["TEST_DATABASE_URL"] = "sqlite:///./test_skillbridge.db"

from src.db.database import Base, get_db
from src.main import app

TEST_DB_URL = "sqlite:///./test_skillbridge.db"
_connect_args = {"check_same_thread": False}

test_engine = create_engine(TEST_DB_URL, connect_args=_connect_args)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function", autouse=False)
def db_session():
    """Yield a fresh database session; drop and recreate tables before each test."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    Yield a FastAPI TestClient wired to the test database.
    FastAPI's dependency injection is overridden so `get_db` returns the
    test session instead of the production one.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # db_session fixture handles close

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()