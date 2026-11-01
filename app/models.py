"""SQLAlchemy models for parking operations."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ParkingSlot(Base):
    __tablename__ = "parking_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    zone: Mapped[str] = mapped_column(String(40), default="Block A")
    status: Mapped[str] = mapped_column(String(20), default="available")
    slot_type: Mapped[str] = mapped_column(String(20), default="car")

    sessions: Mapped[list["ParkingSession"]] = relationship(
        back_populates="slot"
    )


class User(Base):
    """Registered user (ADMIN or CUSTOMER)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="CUSTOMER")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    registration_number: Mapped[str] = mapped_column(
        String(20), unique=True, index=True
    )
    owner_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), default="")
    vehicle_type: Mapped[str] = mapped_column(String(20), default="car")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    sessions: Mapped[list["ParkingSession"]] = relationship(
        back_populates="vehicle"
    )


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id"), index=True
    )
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("parking_slots.id"), index=True
    )
    entry_time: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    exit_time: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    amount: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")

    vehicle: Mapped["Vehicle"] = relationship(back_populates="sessions")
    slot: Mapped["ParkingSlot"] = relationship(back_populates="sessions")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vehicle_number: Mapped[str] = mapped_column(String(20), index=True)
    customer_name: Mapped[str] = mapped_column(String(100))
    slot_id: Mapped[int] = mapped_column(ForeignKey("parking_slots.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
