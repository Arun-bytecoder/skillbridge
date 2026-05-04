"""
sessions.py — session management endpoints.

POST /sessions              — trainer creates a session for one of their batches
GET  /sessions/{id}/attendance — trainer views full attendance list for a session
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from src.core.security import require_roles
from src.db.database import get_db
from src.db.models.models import Attendance, Batch, BatchTrainer, Session, User
from src.schemas.schemas import AttendanceListOut, AttendanceRecord, SessionCreate, SessionOut

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreate,
    payload: dict = Depends(require_roles("trainer")),
    db: DBSession = Depends(get_db),
):
    """
    Create a new session for a batch.
    - Returns 404 if batch_id doesn't exist.
    - Returns 403 if the caller is not assigned to the batch.
    All required fields (title, date, start_time, end_time, batch_id) are validated
    by Pydantic — missing fields return 422 automatically.
    """
    trainer_id = int(payload["sub"])

    # Validate batch exists
    batch = db.query(Batch).filter(Batch.id == body.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {body.batch_id} not found.")

    # Verify trainer is assigned to this batch
    link = db.query(BatchTrainer).filter(
        BatchTrainer.batch_id == body.batch_id,
        BatchTrainer.trainer_id == trainer_id,
    ).first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this batch.",
        )

    session = Session(
        batch_id=body.batch_id,
        trainer_id=trainer_id,
        title=body.title,
        date=body.date,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}/attendance", response_model=AttendanceListOut)
def get_session_attendance(
    session_id: int,
    payload: dict = Depends(require_roles("trainer")),
    db: DBSession = Depends(get_db),
):
    """
    Return all attendance records for a session.
    Only the trainer assigned to the session (or any trainer on the batch) may call this.
    """
    session = db.query(Session).filter(Session.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")

    # Verify trainer is assigned to this session's batch
    trainer_id = int(payload["sub"])
    link = db.query(BatchTrainer).filter(
        BatchTrainer.batch_id == session.batch_id,
        BatchTrainer.trainer_id == trainer_id,
    ).first()
    if not link:
        raise HTTPException(status_code=403, detail="You are not assigned to this batch.")

    records = (
        db.query(Attendance, User)
        .join(User, Attendance.student_id == User.id)
        .filter(Attendance.session_id == session_id)
        .all()
    )

    return AttendanceListOut(
        session_id=session_id,
        records=[
            AttendanceRecord(
                student_id=att.student_id,
                student_name=user.name,
                status=att.status,
                marked_at=att.marked_at.isoformat(),
            )
            for att, user in records
        ],
    )