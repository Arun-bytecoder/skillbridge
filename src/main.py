"""
main.py — FastAPI application entry point.

This is the first file to read.  It:
  1. Creates the FastAPI app with metadata for Swagger UI.
  2. Creates all database tables on startup (dev convenience — use Alembic in production).
  3. Registers all route modules under their prefixes.
  4. Exposes a health-check endpoint at GET /.

To run locally:
    uvicorn src.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.database import engine
from src.db.models.models import Base  # noqa: F401 — imported so metadata is populated

# Import all route modules
from src.api.routes import auth, batches, sessions, attendance, summaries

# ── Create tables ─────────────────────────────────────────────────────────────
# In development this is convenient.  In production, always use Alembic migrations
# so schema changes are tracked and reversible.
Base.metadata.create_all(bind=engine)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="SkillBridge Attendance API",
    description=(
        "Role-based attendance management REST API for the SkillBridge skilling programme.\n\n"
        "**Roles:** student · trainer · institution · programme_manager · monitoring_officer\n\n"
        "**Live URL:** https://skillbridge-api.up.railway.app\n\n"
        "**Auth:** Most endpoints require `Authorization: Bearer <token>`. "
        "Use POST /auth/login to obtain a token."
    ),
    version="1.0.0",
)

# Allow all origins — tighten this in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(sessions.router)
app.include_router(attendance.router)
app.include_router(summaries.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["health"])
def health():
    """Basic health check — returns 200 if the server is up."""
    return {"status": "ok", "service": "SkillBridge Attendance API"}