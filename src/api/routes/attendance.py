"""
attendance.py — attendance marking endpoint.

POST /attendance/mark — student marks their own attendance for an active session.

Key business rules enforced here:
  - Student must be enrolled in the batch that the session belongs to (403 otherwise).
  - Student cannot mark the same session twice (409 on duplicate).
  - Session must exist (404 otherwise).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from src.core.security import require_roles
from src.db.database import get_db
from src.db.models.models import Attendance, BatchStudent, Session
from src.schemas.schemas import AttendanceMark

router = APIRouter(tags=["attendance"])


@router.post("/attendance/mark", status_code=status.HTTP_201_CREATED)
def mark_attendance(
    body: AttendanceMark,
    payload: dict = Depends(require_roles("student")),
    db: DBSession = Depends(get_db),
):
    """
    Mark a student's own attendance for a session.

    Returns:
      201  — successfully marked
      403  — student is not enrolled in the session's batch
      404  — session not found
      409  — attendance already marked for this session
      422  — invalid status value (present/absent/late only)
    """
    student_id = int(payload["sub"])

    # Validate session exists — return 404, not 500
    session = db.query(Session).filter(Session.id == body.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {body.session_id} not found.")

    # Check enrollment — return 403 if not enrolled
    enrolled = db.query(BatchStudent).filter(
        BatchStudent.batch_id == session.batch_id,
        BatchStudent.student_id == student_id,
    ).first()
    if not enrolled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in the batch for this session.",
        )

    # Prevent duplicate attendance records
    existing = db.query(Attendance).filter(
        Attendance.session_id == body.session_id,
        Attendance.student_id == student_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Attendance already marked for this session.")

    record = Attendance(
        session_id=body.session_id,
        student_id=student_id,
        status=body.status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": "Attendance marked successfully.",
        "attendance_id": record.id,
        "status": record.status,
    }