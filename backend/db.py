"""Persistent storage for everything EXCEPT conversation content.

Counselor accounts, the student roster, and escalation records need to
survive a restart/redeploy, so they live in Postgres. Conversation history
does not belong here and never should - it stays in
backend/session_store.py, in process memory only. Keeping these on
physically separate storage makes "no human can see the conversation" an
architectural fact, not a policy someone could accidentally violate by
adding a column.
"""

import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

# Aiven (and most managed Postgres providers) hand you a single connection
# string with sslmode already baked in - e.g.
# postgresql://user:pass@host:port/dbname?sslmode=require
try:
    DATABASE_URL = os.environ["MOMZILLA_DATABASE_URL"]
except KeyError:
    raise RuntimeError(
        "MOMZILLA_DATABASE_URL is not set. Copy .env.example to .env and set it to "
        "your Postgres connection string (e.g. an Aiven PostgreSQL service's URL)."
    ) from None

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def reset_pool_for_testing() -> None:
    """Close and drop the cached pool so the next get_pool() picks up a
    changed DATABASE_URL. Only ever used by tests/conftest.py."""
    global _pool
    if _pool is not None:
        _pool.close()
    _pool = None


def init_db() -> None:
    with get_pool().connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS counselors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                contact_email TEXT NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                assigned_counselor_id TEXT NOT NULL REFERENCES counselors(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS escalations (
                seq BIGSERIAL PRIMARY KEY,
                id TEXT UNIQUE NOT NULL,
                student_id TEXT NOT NULL,
                counselor_id TEXT NOT NULL,
                tier TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_escalations_counselor ON escalations(counselor_id)"
        )


# --- counselors -----------------------------------------------------------

def create_counselor(id: str, name: str, contact_email: str, username: str, password_hash: str) -> None:
    with get_pool().connection() as conn:
        conn.execute(
            "INSERT INTO counselors (id, name, contact_email, username, password_hash) "
            "VALUES (%s, %s, %s, %s, %s)",
            (id, name, contact_email, username, password_hash),
        )


def get_counselor_by_username(username: str) -> dict | None:
    with get_pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM counselors WHERE username = %s", (username,)
        ).fetchone()


def get_counselor_by_id(counselor_id: str) -> dict | None:
    with get_pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM counselors WHERE id = %s", (counselor_id,)
        ).fetchone()


def counselor_count() -> int:
    with get_pool().connection() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM counselors").fetchone()["n"]


# --- students ---------------------------------------------------------------

def get_student(student_id: str) -> dict | None:
    with get_pool().connection() as conn:
        return conn.execute("SELECT * FROM students WHERE id = %s", (student_id,)).fetchone()


def create_student(id: str, display_name: str, assigned_counselor_id: str) -> None:
    with get_pool().connection() as conn:
        conn.execute(
            "INSERT INTO students (id, display_name, assigned_counselor_id) VALUES (%s, %s, %s)",
            (id, display_name, assigned_counselor_id),
        )


def get_any_counselor_id() -> str | None:
    with get_pool().connection() as conn:
        row = conn.execute("SELECT id FROM counselors LIMIT 1").fetchone()
        return row["id"] if row else None


# --- escalations --------------------------------------------------------

def insert_escalation(id: str, student_id: str, counselor_id: str, tier: str, created_at) -> None:
    with get_pool().connection() as conn:
        conn.execute(
            "INSERT INTO escalations (id, student_id, counselor_id, tier, created_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (id, student_id, counselor_id, tier, created_at),
        )


def list_escalations_for_counselor(counselor_id: str) -> list[dict]:
    # Tie-break on seq (a real auto-incrementing column), not id (a random
    # UUID with no relation to insertion order) or created_at alone (two
    # escalations can land on the same timestamp).
    with get_pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM escalations WHERE counselor_id = %s ORDER BY seq DESC",
            (counselor_id,),
        ).fetchall()


def list_all_escalations() -> list[dict]:
    with get_pool().connection() as conn:
        return conn.execute("SELECT * FROM escalations ORDER BY seq DESC").fetchall()
