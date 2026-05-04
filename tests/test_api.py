"""
test_api.py — the 5 required pytest tests.

Test 1: Student signup + login returns a valid JWT
Test 2: Trainer creates a session with all required fields
Test 3: Student successfully marks their own attendance
Test 4: POST to /monitoring/attendance returns 405
Test 5: Request to a protected endpoint with no token returns 401

Tests 1, 2, 3 hit a real SQLite test database (via the `client` fixture from conftest.py).
Tests 4 and 5 also use the test client but don't rely on seeded data.
"""
import pytest
from fastapi.testclient import TestClient

# ── Helper: register and log in a user, return token ─────────────────────────
def signup_and_login(client, email, password, role, name="Test User", institution_id=None):
    body = {"name": name, "email": email, "password": password, "role": role}
    if institution_id:
        body["institution_id"] = institution_id
    client.post("/auth/signup", json=body)
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


# ── Helper: create an institution directly in the DB ─────────────────────────
def seed_institution(db_session, name="Test Institute"):
    from src.db.models.models import Institution
    inst = Institution(name=name)
    db_session.add(inst)
    db_session.commit()
    db_session.refresh(inst)
    return inst


# ── Helper: assign trainer to batch ──────────────────────────────────────────
def seed_batch_trainer(db_session, batch_id, trainer_id):
    from src.db.models.models import BatchTrainer
    db_session.add(BatchTrainer(batch_id=batch_id, trainer_id=trainer_id))
    db_session.commit()


def seed_batch_student(db_session, batch_id, student_id):
    from src.db.models.models import BatchStudent
    db_session.add(BatchStudent(batch_id=batch_id, student_id=student_id))
    db_session.commit()


# ═════════════════════════════════════════════════════════════════════════════
# Test 1 — Successful student signup and login; asserts valid JWT returned
# ═════════════════════════════════════════════════════════════════════════════
def test_student_signup_and_login_returns_jwt(client):
    """
    Registers a new student, logs in, and checks that:
      - login returns 200
      - response contains 'access_token'
      - token is a non-empty string
      - token is a properly formed JWT (3 base64url segments separated by dots)
    This test hits a real SQLite database.
    """
    # Signup
    signup_resp = client.post("/auth/signup", json={
        "name": "Aarav Test",
        "email": "aarav.test@student.in",
        "password": "testpass123",
        "role": "student",
    })
    assert signup_resp.status_code == 201, signup_resp.text

    # Login
    login_resp = client.post("/auth/login", json={
        "email": "aarav.test@student.in",
        "password": "testpass123",
    })
    assert login_resp.status_code == 200, login_resp.text

    data = login_resp.json()
    assert "access_token" in data
    token = data["access_token"]
    assert isinstance(token, str) and len(token) > 0

    # A JWT always has exactly 3 dot-separated segments
    parts = token.split(".")
    assert len(parts) == 3, f"Expected JWT with 3 parts, got: {token[:50]}..."


# ═════════════════════════════════════════════════════════════════════════════
# Test 2 — Trainer creates a session with all required fields
# ═════════════════════════════════════════════════════════════════════════════
def test_trainer_creates_session(client, db_session):
    """
    A trainer creates a batch (via the API), then creates a session in it.
    Asserts that:
      - session creation returns 201
      - response contains correct session data
    This test hits a real SQLite database.
    """
    inst = seed_institution(db_session)

    # Register trainer and get token
    trainer_token = signup_and_login(
        client, "trainer@test.in", "trainerpass", "trainer",
        name="Test Trainer", institution_id=inst.id,
    )
    headers = {"Authorization": f"Bearer {trainer_token}"}

    # Create a batch (trainer auto-linked as trainer)
    batch_resp = client.post("/batches", json={
        "name": "Test Batch",
        "institution_id": inst.id,
    }, headers=headers)
    assert batch_resp.status_code == 201, batch_resp.text
    batch_id = batch_resp.json()["id"]

    # Create a session
    session_resp = client.post("/sessions", json={
        "title": "Intro to Python",
        "date": "2025-06-15",
        "start_time": "10:00:00",
        "end_time": "12:00:00",
        "batch_id": batch_id,
    }, headers=headers)

    assert session_resp.status_code == 201, session_resp.text
    data = session_resp.json()
    assert data["title"] == "Intro to Python"
    assert data["batch_id"] == batch_id
    assert data["date"] == "2025-06-15"


# ═════════════════════════════════════════════════════════════════════════════
# Test 3 — Student successfully marks their own attendance
# ═════════════════════════════════════════════════════════════════════════════
def test_student_marks_attendance(client, db_session):
    """
    Full flow:
      1. Create institution
      2. Register trainer, create batch, create session
      3. Register student, enroll them in the batch (directly via DB helper)
      4. Student marks attendance
    This test hits a real SQLite database.
    """
    from src.db.models.models import User

    inst = seed_institution(db_session)

    # Trainer setup
    trainer_token = signup_and_login(
        client, "trainer2@test.in", "trainerpass", "trainer",
        name="Trainer Two", institution_id=inst.id,
    )
    t_headers = {"Authorization": f"Bearer {trainer_token}"}

    batch_resp = client.post("/batches", json={
        "name": "Attendance Test Batch", "institution_id": inst.id,
    }, headers=t_headers)
    batch_id = batch_resp.json()["id"]

    session_resp = client.post("/sessions", json={
        "title": "Test Session", "date": "2025-07-01",
        "start_time": "09:00:00", "end_time": "11:00:00",
        "batch_id": batch_id,
    }, headers=t_headers)
    session_id = session_resp.json()["id"]

    # Student setup
    student_token = signup_and_login(
        client, "student1@test.in", "studentpass", "student", name="Student One",
    )

    # Enroll student directly via DB (simulates the invite flow without the token ceremony)
    student = db_session.query(User).filter(User.email == "student1@test.in").first()
    seed_batch_student(db_session, batch_id, student.id)

    # Mark attendance
    att_resp = client.post("/attendance/mark", json={
        "session_id": session_id,
        "status": "present",
    }, headers={"Authorization": f"Bearer {student_token}"})

    assert att_resp.status_code == 201, att_resp.text
    data = att_resp.json()
    assert data["status"] == "present"


# ═════════════════════════════════════════════════════════════════════════════
# Test 4 — POST to /monitoring/attendance returns 405
# ═════════════════════════════════════════════════════════════════════════════
def test_post_monitoring_attendance_returns_405(client):
    """
    The /monitoring/attendance endpoint is read-only.
    A POST request must return 405 Method Not Allowed regardless of auth.
    """
    resp = client.post("/monitoring/attendance", json={})
    assert resp.status_code == 405, f"Expected 405, got {resp.status_code}: {resp.text}"


# ═════════════════════════════════════════════════════════════════════════════
# Test 5 — Request to protected endpoint with no token returns 401
# ═════════════════════════════════════════════════════════════════════════════
def test_no_token_returns_401(client):
    """
    Hitting a protected endpoint without an Authorization header must return 401.
    We test this on several endpoints to be thorough.
    """
    endpoints = [
        ("POST", "/batches"),
        ("POST", "/sessions"),
        ("POST", "/attendance/mark"),
        ("GET",  "/programme/summary"),
        ("GET",  "/monitoring/attendance"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json={})
        assert resp.status_code == 401, (
            f"Expected 401 on {method} {path}, got {resp.status_code}"
        )