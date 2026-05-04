"""
seed.py — populate the database with test data.

Creates:
  - 2 institutions
  - 4 trainers (2 per institution)
  - 15 students
  - 3 batches (each linked to an institution and at least one trainer)
  - 8 sessions spread across the batches
  - Attendance records for all students/sessions

Run with:
    python seed.py

The script is idempotent — it deletes all existing data before re-seeding,
so you can run it safely multiple times during development.
"""
import os
import sys

# Allow imports from project root
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta, timezone
import secrets

from src.db.database import SessionLocal, engine
from src.db.models.models import (
    Attendance, Base, Batch, BatchInvite, BatchStudent,
    BatchTrainer, Institution, Session, User,
)
from src.core.security import hash_password

# Ensure tables exist (safe to call even if they already exist)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# ── Wipe existing data (in reverse FK order) ──────────────────────────────────
print("Clearing existing data...")
db.query(Attendance).delete()
db.query(BatchInvite).delete()
db.query(BatchStudent).delete()
db.query(BatchTrainer).delete()
db.query(Session).delete()
db.query(Batch).delete()
db.query(User).delete()
db.query(Institution).delete()
db.commit()

# ── Institutions ──────────────────────────────────────────────────────────────
print("Creating institutions...")
inst_blr = Institution(name="Bangalore Skill Centre")
inst_mum = Institution(name="Mumbai Skill Centre")
db.add_all([inst_blr, inst_mum])
db.flush()

# ── Special roles (non-student, non-trainer) ──────────────────────────────────
print("Creating special-role users...")
inst_admin = User(
    name="Institution Admin BLR",
    email="admin.blr@skillbridge.in",
    hashed_password=hash_password("inst_pass123"),
    role="institution",
    institution_id=inst_blr.id,
)
pm = User(
    name="Programme Manager",
    email="pm@skillbridge.in",
    hashed_password=hash_password("pm_pass123"),
    role="programme_manager",
)
monitor = User(
    name="Monitoring Officer",
    email="monitor@skillbridge.in",
    hashed_password=hash_password("monitor_pass123"),
    role="monitoring_officer",
)
db.add_all([inst_admin, pm, monitor])
db.flush()

# ── Trainers ──────────────────────────────────────────────────────────────────
print("Creating trainers...")
trainers = [
    User(name="Arjun Sharma", email="arjun@skillbridge.in",
         hashed_password=hash_password("trainer_pass123"), role="trainer",
         institution_id=inst_blr.id),
    User(name="Priya Nair", email="priya@skillbridge.in",
         hashed_password=hash_password("trainer_pass123"), role="trainer",
         institution_id=inst_blr.id),
    User(name="Rahul Verma", email="rahul@skillbridge.in",
         hashed_password=hash_password("trainer_pass123"), role="trainer",
         institution_id=inst_mum.id),
    User(name="Sneha Joshi", email="sneha@skillbridge.in",
         hashed_password=hash_password("trainer_pass123"), role="trainer",
         institution_id=inst_mum.id),
]
db.add_all(trainers)
db.flush()

# ── Students ──────────────────────────────────────────────────────────────────
print("Creating 15 students...")
students = [
    User(name=f"Student {i}", email=f"aarav{i}@student.in",
         hashed_password=hash_password("student_pass123"), role="student")
    for i in range(1, 16)
]
db.add_all(students)
db.flush()

# ── Batches ───────────────────────────────────────────────────────────────────
print("Creating batches...")
batch_python = Batch(name="Python Bootcamp", institution_id=inst_blr.id)
batch_data = Batch(name="Data Analytics", institution_id=inst_blr.id)
batch_web = Batch(name="Web Development", institution_id=inst_mum.id)
db.add_all([batch_python, batch_data, batch_web])
db.flush()

# ── Batch-Trainer assignments ─────────────────────────────────────────────────
db.add_all([
    BatchTrainer(batch_id=batch_python.id, trainer_id=trainers[0].id),
    BatchTrainer(batch_id=batch_python.id, trainer_id=trainers[1].id),  # co-trainer
    BatchTrainer(batch_id=batch_data.id,   trainer_id=trainers[1].id),
    BatchTrainer(batch_id=batch_web.id,    trainer_id=trainers[2].id),
    BatchTrainer(batch_id=batch_web.id,    trainer_id=trainers[3].id),
])
db.flush()

# ── Enroll students ───────────────────────────────────────────────────────────
print("Enrolling students...")
# Students 1-6 → Python Bootcamp
for s in students[:6]:
    db.add(BatchStudent(batch_id=batch_python.id, student_id=s.id))
# Students 5-10 → Data Analytics (5&6 are in both)
for s in students[4:10]:
    db.add(BatchStudent(batch_id=batch_data.id, student_id=s.id))
# Students 10-15 → Web Dev
for s in students[9:]:
    db.add(BatchStudent(batch_id=batch_web.id, student_id=s.id))
db.flush()

# ── Sessions ──────────────────────────────────────────────────────────────────
print("Creating sessions...")
base_date = "2025-06-01"
sessions_data = [
    # Python Bootcamp (4 sessions, trainer[0])
    Session(batch_id=batch_python.id, trainer_id=trainers[0].id,
            title="Intro to Python", date="2025-06-01",
            start_time="10:00:00", end_time="12:00:00"),
    Session(batch_id=batch_python.id, trainer_id=trainers[0].id,
            title="Control Flow", date="2025-06-03",
            start_time="10:00:00", end_time="12:00:00"),
    Session(batch_id=batch_python.id, trainer_id=trainers[0].id,
            title="Functions & Modules", date="2025-06-05",
            start_time="10:00:00", end_time="12:00:00"),
    Session(batch_id=batch_python.id, trainer_id=trainers[1].id,
            title="OOP Basics", date="2025-06-07",
            start_time="14:00:00", end_time="16:00:00"),
    # Data Analytics (2 sessions, trainer[1])
    Session(batch_id=batch_data.id, trainer_id=trainers[1].id,
            title="Pandas Introduction", date="2025-06-02",
            start_time="11:00:00", end_time="13:00:00"),
    Session(batch_id=batch_data.id, trainer_id=trainers[1].id,
            title="Data Visualisation", date="2025-06-04",
            start_time="11:00:00", end_time="13:00:00"),
    # Web Development (2 sessions, trainer[2])
    Session(batch_id=batch_web.id, trainer_id=trainers[2].id,
            title="HTML & CSS Fundamentals", date="2025-06-02",
            start_time="09:00:00", end_time="11:00:00"),
    Session(batch_id=batch_web.id, trainer_id=trainers[2].id,
            title="JavaScript Basics", date="2025-06-04",
            start_time="09:00:00", end_time="11:00:00"),
]
db.add_all(sessions_data)
db.flush()

# ── Attendance records ────────────────────────────────────────────────────────
print("Creating attendance records...")
# Python Bootcamp attendance
py_sessions = sessions_data[:4]
py_students = students[:6]
statuses = ["present", "present", "present", "absent", "late", "present"]
for sess in py_sessions:
    for student, st in zip(py_students, statuses):
        db.add(Attendance(session_id=sess.id, student_id=student.id, status=st))

# Data Analytics attendance
da_sessions = sessions_data[4:6]
da_students = students[4:10]
da_statuses = ["present", "absent", "present", "late", "present", "present"]
for sess in da_sessions:
    for student, st in zip(da_students, da_statuses):
        db.add(Attendance(session_id=sess.id, student_id=student.id, status=st))

# Web Dev attendance
wd_sessions = sessions_data[6:8]
wd_students = students[9:]
wd_statuses = ["present", "present", "absent", "present", "late", "present"]
for sess in wd_sessions:
    for student, st in zip(wd_students, wd_statuses):
        db.add(Attendance(session_id=sess.id, student_id=student.id, status=st))

db.commit()
print("\n✅ Seed complete!")
print("\nTest accounts:")
print("  Student:             aarav1@student.in       / student_pass123")
print("  Trainer:             arjun@skillbridge.in    / trainer_pass123")
print("  Institution:         admin.blr@skillbridge.in/ inst_pass123")
print("  Programme Manager:   pm@skillbridge.in       / pm_pass123")
print("  Monitoring Officer:  monitor@skillbridge.in  / monitor_pass123")
db.close()