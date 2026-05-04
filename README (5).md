# SkillBridge Attendance API

A role-based attendance management REST API for a fictional state-level skilling programme called SkillBridge. Built with FastAPI, PostgreSQL (Neon), and JWT authentication.

---

## 1. Live API

**Base URL:** `https://skillbridge-api.onrender.com`

**Interactive Docs:** `https://skillbridge-api.onrender.com/docs`

> **Note:** Render free tier spins down after 15 minutes of inactivity. The first request may take 30–60 seconds to wake up.

---

## 2. Local Setup (from scratch)

> Assumes Python 3.10 and pip are installed.

### Clone the repository
```bash
git clone https://github.com/Arun-bytecoder/skillbridge.git
cd skillbridge
```

### Create and activate virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Configure environment variables
```bash
cp .env.example .env
```

Edit `.env` with your actual values:
```env
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
SECRET_KEY=your-super-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
MONITORING_TOKEN_EXPIRE_MINUTES=60
MONITORING_API_KEY=skillbridge-monitoring-key-2024
```

### Run database migrations
```bash
alembic upgrade head
```

### Seed the database
```bash
python seed.py
```

### Start the server
```bash
uvicorn src.main:app --reload
```

API is now running at `http://127.0.0.1:8000`
Swagger UI at `http://127.0.0.1:8000/docs`

### Run tests
```bash
# Windows
$env:PYTHONPATH = "C:\path\to\skillbridge"
pytest tests/ -v

# macOS/Linux
PYTHONPATH=. pytest tests/ -v
```

---

## 3. Test Accounts

| Role | Email | Password |
|------|-------|----------|
| Student | aarav1@student.in | student_pass123 |
| Trainer | arjun@skillbridge.in | trainer_pass123 |
| Institution | admin.blr@skillbridge.in | inst_pass123 |
| Programme Manager | pm@skillbridge.in | pm_pass123 |
| Monitoring Officer | monitor@skillbridge.in | monitor_pass123 |

---

## 4. Sample curl Commands

### Authentication

#### Signup
```bash
curl -X POST https://skillbridge-api.onrender.com/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@test.com","password":"pass123","role":"student"}'
```

#### Login (obtain token)
```bash
curl -X POST https://skillbridge-api.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"arjun@skillbridge.in","password":"trainer_pass123"}'
```
Response contains `access_token` — use it as `Bearer <token>` in all protected requests.

#### Monitoring Token (2-step auth)
```bash
# Step 1: Login as monitoring officer to get standard JWT
curl -X POST https://skillbridge-api.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"monitor@skillbridge.in","password":"monitor_pass123"}'

# Step 2: Exchange for scoped monitoring token
curl -X POST https://skillbridge-api.onrender.com/auth/monitoring-token \
  -H "Authorization: Bearer <standard_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"key":"skillbridge-monitoring-key-2024"}'
```

---

### Batches (Trainer / Institution)

#### Create Batch
```bash
curl -X POST https://skillbridge-api.onrender.com/batches \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Python Bootcamp","institution_id":1}'
```

#### Generate Invite Link
```bash
curl -X POST https://skillbridge-api.onrender.com/batches/1/invite \
  -H "Authorization: Bearer <trainer_token>"
```

#### Join Batch (Student)
```bash
curl -X POST https://skillbridge-api.onrender.com/batches/join \
  -H "Authorization: Bearer <student_token>" \
  -H "Content-Type: application/json" \
  -d '{"token":"<invite_token>"}'
```

#### Batch Summary (Institution)
```bash
curl -X GET https://skillbridge-api.onrender.com/batches/1/summary \
  -H "Authorization: Bearer <institution_token>"
```

---

### Sessions (Trainer)

#### Create Session
```bash
curl -X POST https://skillbridge-api.onrender.com/sessions \
  -H "Authorization: Bearer <trainer_token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Intro to Python","date":"2026-05-10","start_time":"09:00","end_time":"11:00","batch_id":1}'
```

#### Get Session Attendance
```bash
curl -X GET https://skillbridge-api.onrender.com/sessions/1/attendance \
  -H "Authorization: Bearer <trainer_token>"
```

---

### Attendance (Student)

#### Mark Attendance
```bash
curl -X POST https://skillbridge-api.onrender.com/attendance/mark \
  -H "Authorization: Bearer <student_token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id":1,"status":"present"}'
```

---

### Summaries

#### Institution Summary (Programme Manager)
```bash
curl -X GET https://skillbridge-api.onrender.com/institutions/1/summary \
  -H "Authorization: Bearer <pm_token>"
```

#### Programme-wide Summary (Programme Manager)
```bash
curl -X GET https://skillbridge-api.onrender.com/programme/summary \
  -H "Authorization: Bearer <pm_token>"
```

#### Monitoring Attendance (Monitoring Officer — scoped token required)
```bash
curl -X GET https://skillbridge-api.onrender.com/monitoring/attendance \
  -H "Authorization: Bearer <monitoring_scoped_token>"
```

---

## 5. Schema Decisions

### `batch_trainers` (Many-to-Many)
A batch can have multiple trainers, and a trainer can manage multiple batches. A junction table `batch_trainers` handles this without data duplication. This mirrors real-world skilling programmes where co-trainers share a batch.

### `batch_invites`
Rather than adding students directly, trainers generate a time-limited invite token. Students use this token to self-enroll via `POST /batches/join`. This approach:
- Avoids trainers needing to know student IDs in advance
- Supports bulk enrollment via a shareable link
- Tracks who created the invite and when it expires (`expires_at`, `used` boolean)

### Dual-Token for Monitoring Officer
The Monitoring Officer has read-only access to sensitive programme-wide data. A standard JWT alone wasn't considered sufficient, so an extra layer was added:

1. **Standard JWT** — obtained via `/auth/login` (24 hour expiry)
2. **Scoped monitoring token** — obtained via `/auth/monitoring-token` by presenting the standard JWT + a hardcoded API key (1 hour expiry, `token_type: monitoring`)

The `/monitoring/attendance` endpoint rejects standard JWTs with 401 — only the scoped token is accepted. This mimics a real-world pattern where sensitive read endpoints require additional credentials beyond just being logged in.

**JWT Payload Structure:**

Standard token:
```json
{
  "user_id": 5,
  "role": "monitoring_officer",
  "iat": 1234567890,
  "exp": 1234654290
}
```

Monitoring scoped token:
```json
{
  "user_id": 5,
  "role": "monitoring_officer",
  "token_type": "monitoring",
  "iat": 1234567890,
  "exp": 1234571490
}
```

**Token rotation in a real deployment:** Store a `token_version` or `jti` (JWT ID) in the database per user. On logout or key rotation, increment the version — any token with an old version is rejected even if not expired.

**One security issue in the current implementation:** The monitoring API key is hardcoded in `.env` with no rotation mechanism. With more time, I'd store hashed API keys in the database with expiry dates and an admin endpoint to rotate them.

---

## 6. What Is Working / Partial / Skipped

### Fully Working ✅
- All 13 endpoints implemented and tested
- Role-based access control on every protected endpoint (403 on wrong role)
- JWT signup and login with bcrypt password hashing
- Dual-token system for Monitoring Officer
- Input validation with 422 responses on missing fields
- 404 on invalid foreign keys (batch_id, session_id)
- 403 when student marks attendance for unenrolled session
- 405 on POST to `/monitoring/attendance`
- 401 on missing/invalid token
- All 5 pytest tests passing against a real SQLite test database
- Database seeded with 2 institutions, 4 trainers, 15 students, 3 batches, 8 sessions, 48 attendance records
- Deployed to Render with Neon PostgreSQL

### Partially Done ⚠️
- Invite token expiry is set but not strictly enforced on the join endpoint (validation logic is present but edge cases not fully tested)

### Skipped ❌
- Refresh token mechanism (tokens must be re-issued manually after expiry)
- Pagination on `/monitoring/attendance` (returns all records)
- Email notifications on invite generation

---

## 7. One Thing I'd Do Differently

I would set up **proper environment-based configuration from day one** — separate `.env` files for development, testing, and production, with a `pytest.ini` that automatically sets `TEST_DATABASE_URL`. This would have avoided the manual `PYTHONPATH` workaround and made the test setup cleaner and more portable for any teammate cloning the repo.
