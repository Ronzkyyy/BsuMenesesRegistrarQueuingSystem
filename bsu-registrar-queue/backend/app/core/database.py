"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings



def connect_args_for(url: str) -> dict:
    """Driver options for every engine/connection this app opens.

    PostgreSQL goes through psycopg 3, which auto-prepares any statement run
    5+ times on a connection. The database sits behind Supabase's
    transaction pooler (port 6543), which hands each transaction a different
    server connection, so a prepared statement made on one is missing - or
    already taken - on the next ("prepared statement ... already exists").
    prepare_threshold=None turns server-side preparing off.
    """
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    if url.startswith("postgresql"):
        return {"prepare_threshold": None}
    return {}


engine = create_engine(settings.DATABASE_URL, connect_args=connect_args_for(settings.DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()