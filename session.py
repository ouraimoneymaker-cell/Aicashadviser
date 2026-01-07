"""Database session management.

This module configures the SQLAlchemy engine and session for the application.
For the MVP we use SQLite, but production deployments should use Postgres or
another relational database. The `get_db` function is a dependency that
yields a session to FastAPI endpoints and automatically closes it.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# For demonstration purposes we use an on‑disk SQLite database. Replace
# `sqlite:///./aicashadvisor.db` with your Postgres connection string in
# production (e.g., `postgresql+psycopg2://user:password@host/dbname`).
SQLALCHEMY_DATABASE_URL = "sqlite:///./aicashadvisor.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed only for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """Yield a database session and ensure it is closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()