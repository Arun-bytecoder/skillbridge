"""
batches.py — batch management endpoints.

POST /batches           — create a batch (trainer or institution role)
POST /batches/{id}/invite — generate a single-use invite token (trainer)
POST /batches/join      — student uses an invite token to enroll
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.security import get_current_user, require_roles
from src.db.database import get_db
from src.db.models.models import Batch, BatchInvite, BatchStudent, BatchTrainer, Institution
from src.schemas.schemas import BatchCreate, BatchOut, InviteOut, JoinBatchRequest

router = APIRouter(tags=["batches"])


@router.post("/batches", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(
    body: BatchCreate,
    payload: dict = Depends(require_roles("trainer", "institution")),
    db: Session = Depends(get_db),
):
    """
    Create a new batch.
    - Both trainer and institution roles are permitted.
    - Validates that the institution_id exists (returns 404 otherwise).
    - If created by a trainer, automatically links them as the first batch trainer.
    """
    # Validate institution
    inst = db.query(Institution).filter(Institution.id == body.institution_id).first()
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institution {body.institution_id} not found.",
        )

    batch = Batch(name=body.name, institution_id=body.institution_id)
    db.add(batch)
    db.flush()  # get batch.id without committing

    # If a trainer created this batch, add them as the first trainer
    if payload["role"] == "trainer":
        trainer_link = BatchTrainer(batch_id=batch.id, trainer_id=int(payload["sub"]))
        db.add(trainer_link)

    db.commit()
    db.refresh(batch)
    return batch


@router.post("/batches/{batch_id}/invite", response_model=InviteOut)
def generate_invite(
    batch_id: int,
    payload: dict = Depends(require_roles("trainer")),
    db: Session = Depends(get_db),
):
    """
    Generate a single-use, 7-day invite token for a batch.
    Only trainers assigned to that batch may generate invites.
    Returns the token (a real system would format this as a full URL).
    """
    # Validate batch exists
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found.")

    # Verify trainer is assigned to this batch
    trainer_id = int(payload["sub"])
    link = db.query(BatchTrainer).filter(
        BatchTrainer.batch_id == batch_id,
        BatchTrainer.trainer_id == trainer_id,
    ).first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this batch.",
        )

    expires = datetime.now(timezone.utc) + timedelta(days=7)
    invite = BatchInvite(
        batch_id=batch_id,
        token=secrets.token_urlsafe(32),
        created_by=trainer_id,
        expires_at=expires,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return InviteOut(
        token=invite.token,
        expires_at=invite.expires_at.isoformat(),
        batch_id=invite.batch_id,
    )


@router.post("/batches/join", status_code=status.HTTP_200_OK)
def join_batch(
    body: JoinBatchRequest,
    payload: dict = Depends(require_roles("student")),
    db: Session = Depends(get_db),
):
    """
    Student uses an invite token to join a batch.
    - Returns 404 on unknown or already-used token.
    - Returns 400 if the token has expired.
    - Returns 409 if the student is already enrolled.
    - Marks the token as used after enrollment.
    """
    invite = db.query(BatchInvite).filter(
        BatchInvite.token == body.token,
        BatchInvite.used.is_(False),
    ).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite token not found or already used.")

    # Check expiry (expires_at may be naive or aware depending on DB driver)
    now = datetime.now(timezone.utc)
    expires = invite.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        raise HTTPException(status_code=400, detail="Invite token has expired.")

    student_id = int(payload["sub"])

    # Check if already enrolled
    existing = db.query(BatchStudent).filter(
        BatchStudent.batch_id == invite.batch_id,
        BatchStudent.student_id == student_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You are already enrolled in this batch.")

    # Enroll student and mark token as used
    db.add(BatchStudent(batch_id=invite.batch_id, student_id=student_id))
    invite.used = True
    db.commit()

    return {"message": f"Successfully joined batch {invite.batch_id}."}