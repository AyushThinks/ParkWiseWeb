"""Customer-facing routes: dashboard, slots, bookings, and profile management."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import (
    get_current_user,
    hash_password,
    require_customer,
    verify_password,
)
from ..database import get_db
from ..models import Booking, ParkingSlot, User
from ..schemas import (
    CustomerBookingCreate,
    PasswordChange,
    UserOut,
    UserProfileUpdate,
)

router = APIRouter(prefix="/api/customer", tags=["Customer"])


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
def customer_dashboard(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Return a customer-oriented dashboard summary."""
    total_available = db.query(ParkingSlot).filter(
        ParkingSlot.status == "available"
    ).count()

    available_car = db.query(ParkingSlot).filter(
        ParkingSlot.status == "available",
        ParkingSlot.slot_type == "car",
    ).count()

    available_bike = db.query(ParkingSlot).filter(
        ParkingSlot.status == "available",
        ParkingSlot.slot_type == "bike",
    ).count()

    upcoming_bookings = (
        db.query(Booking)
        .filter(
            Booking.user_id == current_user.id,
            Booking.status == "confirmed",
            Booking.start_time >= datetime.utcnow(),
        )
        .order_by(Booking.start_time)
        .limit(5)
        .all()
    )

    recent_bookings = (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.start_time.desc())
        .limit(5)
        .all()
    )

    def _booking_dict(b: Booking) -> dict:
        slot = db.get(ParkingSlot, b.slot_id)
        return {
            "id": b.id,
            "vehicle_number": b.vehicle_number,
            "slot_id": b.slot_id,
            "slot_code": slot.code if slot else "Unknown",
            "start_time": b.start_time.isoformat(),
            "end_time": b.end_time.isoformat(),
            "status": b.status,
        }

    return {
        "welcome_name": current_user.full_name,
        "total_available_slots": total_available,
        "available_car_slots": available_car,
        "available_bike_slots": available_bike,
        "upcoming_bookings": [_booking_dict(b) for b in upcoming_bookings],
        "recent_activity": [_booking_dict(b) for b in recent_bookings],
    }


# ---------------------------------------------------------------------------
# Slots (read-only view)
# ---------------------------------------------------------------------------


@router.get("/slots")
def customer_list_slots(
    slot_type: str | None = None,
    slot_status: str | None = None,
    search: str | None = None,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Return all parking slots (read-only for customers)."""
    query = db.query(ParkingSlot)

    if slot_type:
        query = query.filter(ParkingSlot.slot_type == slot_type)
    if slot_status:
        query = query.filter(ParkingSlot.status == slot_status)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            ParkingSlot.code.ilike(term)
            | ParkingSlot.zone.ilike(term)
        )

    slots = query.order_by(ParkingSlot.code).all()

    return [
        {
            "id": s.id,
            "code": s.code,
            "zone": s.zone,
            "status": s.status,
            "slot_type": s.slot_type,
        }
        for s in slots
    ]


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------


@router.get("/bookings")
def customer_list_bookings(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Return bookings belonging to the current customer."""
    bookings = (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.start_time.desc())
        .all()
    )

    results = []
    for b in bookings:
        slot = db.get(ParkingSlot, b.slot_id)
        results.append(
            {
                "id": b.id,
                "vehicle_number": b.vehicle_number,
                "customer_name": b.customer_name,
                "slot_id": b.slot_id,
                "slot_code": slot.code if slot else "Unknown",
                "start_time": b.start_time.isoformat(),
                "end_time": b.end_time.isoformat(),
                "status": b.status,
            }
        )

    return results


@router.post("/bookings", status_code=status.HTTP_201_CREATED)
def customer_create_booking(
    data: CustomerBookingCreate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Create a new booking on behalf of the authenticated customer."""
    slot = db.get(ParkingSlot, data.slot_id)
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parking slot not found.",
        )

    if data.end_time <= data.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="End time must be after start time.",
        )

    if data.start_time < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Start time cannot be in the past.",
        )

    # Check for time-slot conflicts
    overlapping = db.query(Booking).filter(
        Booking.slot_id == data.slot_id,
        Booking.status == "confirmed",
        Booking.start_time < data.end_time,
        Booking.end_time > data.start_time,
    ).first()

    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot is already booked during the selected time.",
        )

    booking = Booking(
        vehicle_number=data.vehicle_number,
        customer_name=current_user.full_name,
        slot_id=data.slot_id,
        start_time=data.start_time,
        end_time=data.end_time,
        user_id=current_user.id,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return {
        "message": "Booking created successfully.",
        "booking_id": booking.id,
    }


@router.post("/bookings/{booking_id}/cancel")
def customer_cancel_booking(
    booking_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Cancel a confirmed booking that belongs to the current customer."""
    booking = db.get(Booking, booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only confirmed bookings can be cancelled.",
        )

    if booking.start_time <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel a booking that has already started.",
        )

    booking.status = "cancelled"
    db.commit()

    return {"message": "Booking cancelled successfully."}


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@router.get("/profile", response_model=UserOut)
def customer_get_profile(
    current_user: User = Depends(require_customer),
):
    """Return the current customer's profile."""
    return current_user


@router.patch("/profile", response_model=UserOut)
def customer_update_profile(
    data: UserProfileUpdate,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Update the current customer's name and phone number."""
    current_user.full_name = data.full_name
    current_user.phone = data.phone
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password")
def customer_change_password(
    data: PasswordChange,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Change the current customer's password after verifying the old one."""
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.hashed_password = hash_password(data.new_password)
    db.commit()

    return {"message": "Password changed successfully."}
