"""Create an initial admin user for ParkWise.

Usage:
    python -m app.seed_admin
"""

import os
import sys

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine
from app.models import User
from app.auth import hash_password


def create_admin():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "admin@parkwise.com").first()
        if existing:
            print("Admin user already exists (admin@parkwise.com).")
            return

        admin = User(
            full_name="ParkWise Admin",
            email="admin@parkwise.com",
            phone="9876543210",
            hashed_password=hash_password("Admin@123"),
            role="ADMIN",
        )
        db.add(admin)
        db.commit()
        print("Admin user created successfully.")
        print("Email: admin@parkwise.com")
        print("Password: Admin@123")
        print("Role: ADMIN")
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()

