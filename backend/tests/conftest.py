"""Shared test fixtures.

Unit tests never touch the network. Integration tests (marked `integration`) use ONLY the
separate test database (MONGODB_TEST_DB_NAME) and are skipped when MongoDB is not configured.
"""

import os

# Must be set before the app is imported: forces the test database everywhere.
os.environ["APP_ENV"] = "test"

import pytest  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.database import database as dbmod  # noqa: E402
from app.database.models import ALL_COLLECTIONS  # noqa: E402


@pytest.fixture
def no_db_settings(monkeypatch):
    """Settings with MongoDB deliberately unconfigured (overrides backend/.env)."""
    monkeypatch.setenv("MONGODB_URI", "")
    get_settings.cache_clear()
    dbmod.close_client()
    yield get_settings()
    get_settings.cache_clear()
    dbmod.close_client()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.app_env == "test"
    if not settings.mongodb_configured:
        pytest.skip("MongoDB not configured in backend/.env; integration tests skipped")
    return settings


@pytest.fixture(scope="session")
def test_db(test_settings):
    """The test database, initialized once per session and emptied at the end."""
    db = dbmod.get_database(test_settings)
    # Safety: never run destructive test clean-up against a non-test database.
    assert db.name == test_settings.mongodb_test_db_name and db.name.endswith("_test"), db.name
    try:
        dbmod.ping(test_settings)
    except Exception as exc:  # pragma: no cover - depends on network
        pytest.skip(f"MongoDB unreachable: {exc.__class__.__name__}")
    report = dbmod.initialize_database(db)
    assert report["ok"], report
    yield db
    for name in ALL_COLLECTIONS:
        db[name].delete_many({})
    dbmod.close_client()


@pytest.fixture
def clean_db(test_db):
    """Empty every collection before a test (keeps validators and indexes)."""
    for name in ALL_COLLECTIONS:
        test_db[name].delete_many({})
    return test_db
