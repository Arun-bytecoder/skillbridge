"""
schemas.py — Pydantic v2 request/response models.

These serve three purposes:
  1. Input validation — Pydantic rejects bad data and returns 422 automatically.
  2. Output serialisation — FastAPI uses response_model to filter/shape JSON output.
  3. Documentation — Swagger UI uses these schemas for interactive docs.

Naming convention:
  <Resource>Create  — body of a POST request
  <Resource>Out     — response body
"""
from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    institution_id: Optional[int] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {
            "student", "trainer", "institution",
            "programme_manager", "monitoring_officer",
        }
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MonitoringTokenRequest(BaseModel):
    key: str


# ── Batches ───────────────────────────────────────────────────────────────────

class BatchCreate(BaseModel):
    name: str
    institution_id: int


class BatchOut(BaseModel):
    id: int
    name: str
    institution_id: int

    model_config = {"from_attributes": True}


class InviteOut(BaseModel):
    token: str
    expires_at: str
    batch_id: int


class JoinBatchRequest(BaseModel):
    token: str


# ── Sessions ──────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: str
    date: str           # YYYY-MM-DD
    start_time: str     # HH:MM:SS
    end_time: str
    batch_id: int


class SessionOut(BaseModel):
    id: int
    title: str
    date: str
    start_time: str
    end_time: str
    batch_id: int
    trainer_id: int

    model_config = {"from_attributes": True}


# ── Attendance ────────────────────────────────────────────────────────────────

class AttendanceMark(BaseModel):
    session_id: int
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in {"present", "absent", "late"}:
            raise ValueError("status must be present, absent, or late")
        return v


class AttendanceRecord(BaseModel):
    student_id: int
    student_name: str
    status: str
    marked_at: str


class AttendanceListOut(BaseModel):
    session_id: int
    records: List[AttendanceRecord]


# ── Summaries ─────────────────────────────────────────────────────────────────

class StudentSummary(BaseModel):
    student_id: int
    student_name: str
    present: int
    absent: int
    late: int
    total_sessions: int
    attendance_pct: float


class BatchSummary(BaseModel):
    batch_id: int
    batch_name: str
    total_sessions: int
    students: List[StudentSummary]


class InstitutionSummary(BaseModel):
    institution_id: int
    institution_name: str
    batches: List[BatchSummary]


class ProgrammeSummary(BaseModel):
    institutions: List[InstitutionSummary]


class MonitoringRecord(BaseModel):
    attendance_id: int
    session_id: int
    session_title: str
    student_id: int
    student_name: str
    status: str
    marked_at: str
    batch_id: int
    batch_name: str


class MonitoringOut(BaseModel):
    total_records: int
    records: List[MonitoringRecord]