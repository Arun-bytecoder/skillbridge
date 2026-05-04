"""
summaries.py — read-only summary and monitoring endpoints.

GET /batches/{id}/summary        — institution or PM: attendance summary for one batch
GET /institutions/{id}/summary   — PM: summary across all batches in an institution
GET /programme/summary           — PM: programme-wide summary across all institutions
GET /monitoring/attendance       — monitoring officer: full read-only attendance dump
                                   (requires monitoring-scoped token, not standard login)

Note on /monitoring/attendance:
  - Only GET is allowed.  All other HTTP methods return 405 Method Not Allowed.
  - The endpoint uses require_monitoring_token (not require_roles) because it checks
    token_type == "monitoring", not just the role claim.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DBSession

from src.core.security import require_monitoring_token, require_roles
from src.db.database import get_db
from src.db.models.models import (
    Attendance, Batch, BatchStudent, Institution, Session, User,
)
from src.schemas.schemas import (
    BatchSummary, InstitutionSummary, MonitoringOut, MonitoringRecord,
    ProgrammeSummary, StudentSummary,
)

router = APIRouter(tags=["summaries"])


# ── Helper: build per-student stats for a batch ───────────────────────────────
def _student_summaries(batch_id: int, db: DBSession) -> list[StudentSummary]:
    """
    For each student enrolled in the batch, compute:
      present / absent / late counts and total sessions.
    """
    sessions = db.query(Session).filter(Session.batch_id == batch_id).all()
    total_sessions = len(sessions)
    session_ids = [s.id for s in sessions]

    enrolled = (
        db.query(BatchStudent, User)
        .join(User, BatchStudent.student_id == User.id)
        .filter(BatchStudent.batch_id == batch_id)
        .all()
    )

    summaries = []
    for bs, user in enrolled:
        records = db.query(Attendance).filter(
            Attendance.student_id == user.id,
            Attendance.session_id.in_(session_ids) if session_ids else False,
        ).all() if session_ids else []

        counts = {"present": 0, "absent": 0, "late": 0}
        for r in records:
            counts[r.status] = counts.get(r.status, 0) + 1

        pct = round((counts["present"] / total_sessions) * 100, 1) if total_sessions else 0.0

        summaries.append(StudentSummary(
            student_id=user.id,
            student_name=user.name,
            present=counts["present"],
            absent=counts["absent"],
            late=counts["late"],
            total_sessions=total_sessions,
            attendance_pct=pct,
        ))

    return summaries


# ── Batch summary ─────────────────────────────────────────────────────────────
@router.get("/batches/{batch_id}/summary", response_model=BatchSummary)
def batch_summary(
    batch_id: int,
    payload: dict = Depends(require_roles("institution", "programme_manager")),
    db: DBSession = Depends(get_db),
):
    """Return attendance summary for a single batch."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found.")

    sessions = db.query(Session).filter(Session.batch_id == batch_id).all()

    return BatchSummary(
        batch_id=batch.id,
        batch_name=batch.name,
        total_sessions=len(sessions),
        students=_student_summaries(batch_id, db),
    )


# ── Institution summary ───────────────────────────────────────────────────────
@router.get("/institutions/{institution_id}/summary", response_model=InstitutionSummary)
def institution_summary(
    institution_id: int,
    payload: dict = Depends(require_roles("programme_manager")),
    db: DBSession = Depends(get_db),
):
    """Return attendance summary across all batches under an institution."""
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Institution {institution_id} not found.")

    batches = db.query(Batch).filter(Batch.institution_id == institution_id).all()
    batch_summaries = []
    for b in batches:
        sessions = db.query(Session).filter(Session.batch_id == b.id).all()
        batch_summaries.append(BatchSummary(
            batch_id=b.id,
            batch_name=b.name,
            total_sessions=len(sessions),
            students=_student_summaries(b.id, db),
        ))

    return InstitutionSummary(
        institution_id=inst.id,
        institution_name=inst.name,
        batches=batch_summaries,
    )


# ── Programme summary ─────────────────────────────────────────────────────────
@router.get("/programme/summary", response_model=ProgrammeSummary)
def programme_summary(
    payload: dict = Depends(require_roles("programme_manager")),
    db: DBSession = Depends(get_db),
):
    """Return programme-wide summary across every institution."""
    institutions = db.query(Institution).all()
    inst_summaries = []
    for inst in institutions:
        batches = db.query(Batch).filter(Batch.institution_id == inst.id).all()
        batch_summaries = []
        for b in batches:
            sessions = db.query(Session).filter(Session.batch_id == b.id).all()
            batch_summaries.append(BatchSummary(
                batch_id=b.id,
                batch_name=b.name,
                total_sessions=len(sessions),
                students=_student_summaries(b.id, db),
            ))
        inst_summaries.append(InstitutionSummary(
            institution_id=inst.id,
            institution_name=inst.name,
            batches=batch_summaries,
        ))

    return ProgrammeSummary(institutions=inst_summaries)


# ── Monitoring attendance — GET only, scoped token required ───────────────────
@router.get("/monitoring/attendance", response_model=MonitoringOut)
def monitoring_attendance(
    payload: dict = Depends(require_monitoring_token),
    db: DBSession = Depends(get_db),
):
    """
    Read-only view of ALL attendance records across the programme.
    Requires a monitoring-scoped token (token_type == "monitoring").
    A standard login token is rejected with 401.
    """
    rows = (
        db.query(Attendance, Session, User, Batch)
        .join(Session, Attendance.session_id == Session.id)
        .join(User, Attendance.student_id == User.id)
        .join(Batch, Session.batch_id == Batch.id)
        .all()
    )

    records = [
        MonitoringRecord(
            attendance_id=att.id,
            session_id=sess.id,
            session_title=sess.title,
            student_id=user.id,
            student_name=user.name,
            status=att.status,
            marked_at=att.marked_at.isoformat(),
            batch_id=batch.id,
            batch_name=batch.name,
        )
        for att, sess, user, batch in rows
    ]

    return MonitoringOut(total_records=len(records), records=records)


# ── 405 handler for non-GET on /monitoring/attendance ────────────────────────
# We register explicit handlers for POST/PUT/DELETE/PATCH so they return 405
# (FastAPI would otherwise return 404 or 405 depending on version).
for _method in ("post", "put", "delete", "patch"):
    @router.api_route(
        "/monitoring/attendance",
        methods=[_method.upper()],
        include_in_schema=False,
    )
    def _monitoring_not_allowed(request: Request):
        return Response(
            content='{"detail":"Method Not Allowed"}',
            status_code=405,
            media_type="application/json",
        )