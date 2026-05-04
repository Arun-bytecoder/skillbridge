"""
security.py — all authentication and authorisation helpers.

Responsibilities:
  1. Password hashing & verification using bcrypt directly.
     WHY NOT passlib: passlib 1.7.4 (last release 2020) is incompatible with
     bcrypt >= 4.x. bcrypt 4.x changed its internal API and passlib's bcrypt
     handler runs a self-test with a 72+ byte password that bcrypt now rejects
     with ValueError. We use bcrypt directly — it's simpler and actively maintained.

  2. JWT creation — one function for standard tokens, one for monitoring-scoped tokens.
  3. JWT decoding — raises HTTPException on any failure.
  4. FastAPI dependencies for auth + RBAC.

Why two token types?
  The monitoring officer goes through a two-step flow:
    Step 1: POST /auth/login  → 24h standard token  (token_type = "access")
    Step 2: POST /auth/monitoring-token  → 1h monitoring token (token_type = "monitoring")
  The /monitoring/attendance endpoint ONLY accepts token_type == "monitoring".
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.core.config import settings


# ── Password hashing ──────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if `plain` matches the stored bcrypt `hashed` password."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT creation ──────────────────────────────────────────────────────────────
def _build_token(data: dict, expire_minutes: int) -> str:
    """Internal helper — sign and return a JWT."""
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    """Create a standard 24-hour access token. Payload: { sub, role, token_type="access", iat, exp }"""
    return _build_token(
        {"sub": str(user_id), "role": role, "token_type": "access"},
        settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )


def create_monitoring_token(user_id: int) -> str:
    """Create a 1-hour monitoring-scoped token. Only accepted by /monitoring/attendance."""
    return _build_token(
        {"sub": str(user_id), "role": "monitoring_officer", "token_type": "monitoring"},
        settings.MONITORING_TOKEN_EXPIRE_MINUTES,
    )


# ── JWT decoding ──────────────────────────────────────────────────────────────
def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises 401 HTTPException on any failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependencies ──────────────────────────────────────────────────────
# auto_error=False so we can return 401 (not 403) when the header is missing
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """FastAPI dependency — extract and validate JWT from Authorization header."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)


def require_roles(*allowed_roles: str):
    """
    Factory that returns a FastAPI dependency enforcing role-based access.

    Usage:
        @router.get("/...", dependencies=[Depends(require_roles("trainer", "institution"))])

    Raises 403 if the caller's role is not in `allowed_roles`.
    """
    def _check(payload: dict = Depends(get_current_user)) -> dict:
        if payload.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(allowed_roles)}",
            )
        return payload
    return _check


def require_monitoring_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """
    Stricter dependency for /monitoring/attendance.
    Validates token_type == "monitoring" — a standard login token is rejected.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if payload.get("token_type") != "monitoring":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This endpoint requires a monitoring-scoped token. "
                   "Use POST /auth/monitoring-token to obtain one.",
        )
    return payload


def safe_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks on the API key."""
    return secrets.compare_digest(a.encode(), b.encode())