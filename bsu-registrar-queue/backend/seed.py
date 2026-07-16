"""
Local dev helper: create tables and seed dummy accounts/queues/students.
Safe to run multiple times - seed_initial_data() skips if data already exists.
"""
from app.core.init_db import init_db, seed_initial_data
from app.core.database import SessionLocal

init_db()
db = SessionLocal()
try:
    seed_initial_data(db)
finally:
    db.close()
