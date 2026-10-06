import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Force a dedicated test database regardless of what's in .env - this
# fixture drops and recreates tables before every test, so it must never
# point at a real dev/prod database. Override via MOMZILLA_TEST_DATABASE_URL
# (e.g. in CI, or to point at a local Postgres on a non-default port).
os.environ["MOMZILLA_DATABASE_URL"] = os.environ.get(
    "MOMZILLA_TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/momzilla_test"
)

import pytest

from backend import db


@pytest.fixture(autouse=True)
def fresh_db():
    """Wipe and recreate all tables before each test, so tests don't leak
    state into each other.

    Requires a real Postgres reachable at MOMZILLA_DATABASE_URL - see
    README "Tests" for the one-line local setup.
    """
    with db.get_pool().connection() as conn:
        conn.execute("DROP TABLE IF EXISTS escalations, students, counselors CASCADE")
    db.init_db()
    yield
