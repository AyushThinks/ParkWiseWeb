"""Database engine and SQLAlchemy session dependency."""

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./parkwise.db")

# Railway commonly supplies postgresql://. Explicitly select psycopg 3,
# which is included in requirements.txt, for both Railway and local PostgreSQL.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base class for all database models."""


def get_db():
    """Yield one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Ensure newly added columns exist in older database files."""
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            tables = inspector.get_table_names()

            if "vehicles" in tables:
                columns = [c["name"] for c in inspector.get_columns("vehicles")]
                if "user_id" not in columns:
                    conn.execute(
                        text("ALTER TABLE vehicles ADD COLUMN user_id INTEGER")
                    )
                    conn.commit()

            if "bookings" in tables:
                columns = [c["name"] for c in inspector.get_columns("bookings")]
                if "user_id" not in columns:
                    conn.execute(
                        text("ALTER TABLE bookings ADD COLUMN user_id INTEGER")
                    )
                    conn.commit()
    except Exception as exc:
        print(f"Migration note: {exc}")
