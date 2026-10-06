import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from backend import db
from backend.auth import hash_password
from backend.main import app

client = TestClient(app)


def make_counselor(username="counselor-a", password="correct-horse-battery-staple"):
    counselor_id = str(uuid.uuid4())
    db.create_counselor(
        id=counselor_id,
        name="Test Counselor",
        contact_email="test@example.edu",
        username=username,
        password_hash=hash_password(password),
    )
    return counselor_id


def test_login_rejects_wrong_password():
    make_counselor(username="a", password="correct-horse-battery-staple")
    resp = client.post("/auth/login", json={"username": "a", "password": "wrong"})
    assert resp.status_code == 401


def test_login_succeeds_and_returns_usable_token():
    make_counselor(username="b", password="correct-horse-battery-staple")
    resp = client.post("/auth/login", json={"username": "b", "password": "correct-horse-battery-staple"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["name"] == "Test Counselor"


def test_alerts_endpoint_requires_auth():
    resp = client.get("/counselor/alerts")
    assert resp.status_code in (401, 403)


def test_counselor_cannot_see_another_counselors_alerts():
    counselor_a = make_counselor(username="c1", password="correct-horse-battery-staple")
    counselor_b_id = str(uuid.uuid4())
    db.create_counselor(
        id=counselor_b_id,
        name="Counselor B",
        contact_email="b@example.edu",
        username="c2",
        password_hash=hash_password("another-correct-horse"),
    )

    db.create_student(id="student-x", display_name="Student X", assigned_counselor_id=counselor_a)
    from backend.escalation import board
    from backend.models import EscalationRecord
    from datetime import datetime, timezone

    board.add(
        EscalationRecord(
            id=str(uuid.uuid4()),
            student_id="student-x",
            counselor_id=counselor_a,
            tier="high",
            created_at=datetime.now(timezone.utc),
        )
    )

    token_b = client.post("/auth/login", json={"username": "c2", "password": "another-correct-horse"}).json()[
        "access_token"
    ]
    resp = client.get("/counselor/alerts", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 200
    assert resp.json() == []  # counselor B must not see counselor A's alert
