"""
auth.py — authentication endpoints.

POST /auth/signup       — register a new user (any role)
POST /auth/login        — validate credentials, return 24h JWT
POST /auth/monitoring-token — exchange standard MO token + API key for 1h scoped token

Security note: the API key comparison uses secrets.compare_digest() (constant-time)
to prevent timing attacks.  The known remaining issue is that the key is stored as
plaintext in .env — in production it should be bcrypt-hashed in the database.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.security import (
    create_access_token,
    create_monitoring_token,
    get_current_user,
    hash_password,
    safe_compare,
    verify_password,
)
from src.core.config import settings
from src.db.database import get_db
from src.db.models.models import Institution, User
from src.schemas.schemas import (
    LoginRequest,
    MonitoringTokenRequest,
    SignupRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """
    Register a new user.
    - Validates the role field via Pydantic (returns 422 on invalid role).
    - Returns 409 if the email is already registered.
    - Returns a JWT immediately so the user can start making requests.
    """
    # Check for duplicate email
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    # Validate institution_id if provided
    if body.institution_id:
        if not db.query(Institution).filter(Institution.id == body.institution_id).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Institution {body.institution_id} not found.",
            )

    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        institution_id=body.institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate and return a 24h JWT.
    Returns 401 (not 404) on bad credentials — we don't reveal whether the email exists.
    """
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)


@router.post("/monitoring-token", response_model=TokenResponse)
def monitoring_token(
    body: MonitoringTokenRequest,
    payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Two-step Monitoring Officer token exchange.

    Requires:
      - A valid standard JWT in the Authorization header (from /auth/login)
      - The correct API key in the request body

    Returns a 1-hour monitoring-scoped token accepted ONLY by /monitoring/attendance.

    Why two steps?
      Even a compromised login token alone can't access monitoring endpoints —
      the attacker would also need the API key.  This adds a second factor.
    """
    # Step 1: caller must be a monitoring officer
    if payload.get("role") != "monitoring_officer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only monitoring officers can obtain a monitoring-scoped token.",
        )

    # Step 2: constant-time comparison of the API key
    if not safe_compare(body.key, settings.MONITORING_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    user_id = int(payload["sub"])
    token = create_monitoring_token(user_id)
    return TokenResponse(access_token=token)