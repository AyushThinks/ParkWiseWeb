"""Customer-facing routes: dashboard, slots, bookings, and profile management."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import (
    get_current_user,
    hash_password,
    require_customer,
    verify_password,
)
from ..database import get_db
from ..models import Booking, ParkingSession, ParkingSlot, User, Vehicle
from ..schemas import (
    CustomerBookingCreate,
    PasswordChange,
    UserOut,
    UserProfileUpdate,
)

router = APIRouter(prefix="/api/customer", tags=["Customer"])


# ---------------------------------------------------------------------------
# Datetime Utilities for Timezone Safety & Compatibility
# ---------------------------------------------------------------------------


def to_utc_naive(dt: datetime | None) -> datetime | None:
    """Normalize any datetime (aware or naive) into a naive UTC datetime."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def format_utc_iso(dt: datetime | None) -> str | None:
    """Format a naive UTC datetime into an ISO 8601 string ending with 'Z'."""
    if dt is None:
        return None
    iso = dt.isoformat()
    if not iso.endswith("Z") and "+" not in iso:
        iso += "Z"
    return iso


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
def customer_dashboard(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Return a customer-oriented dashboard summary with real-time slot statistics."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    # Find slots with active confirmed reservations right now
    active_reserved_slot_ids = {
        b.slot_id
        for b in db.query(Booking.slot_id).filter(
            Booking.status == "confirmed",
            Booking.start_time <= now_utc,
            Booking.end_time > now_utc,
        ).all()
    }

    # Fetch physical available slots
    physical_available = db.query(ParkingSlot).filter(
        ParkingSlot.status == "available"
    ).all()

    # Exclude currently reserved slots from available count
    effective_available = [
        s for s in physical_available if s.id not in active_reserved_slot_ids
    ]
    total_available = len(effective_available)
    available_car = sum(1 for s in effective_available if s.slot_type == "car")
    available_bike = sum(1 for s in effective_available if s.slot_type == "bike")

    # Total bookings by this customer
    total_customer_bookings = db.query(Booking).filter(
        Booking.user_id == current_user.id
    ).count()

    upcoming_bookings = (
        db.query(Booking)
        .filter(
            Booking.user_id == current_user.id,
            Booking.status == "confirmed",
            Booking.start_time >= now_utc - timedelta(minutes=5),
        )
        .order_by(Booking.start_time)
        .limit(5)
        .all()
    )

    recent_bookings = (
        db.query(Booking)
        .filter(Booking.user_id == current_user.id)
        .order_by(Booking.start_time.desc())
        .limit(6)
        .all()
    )

    def _booking_dict(b: Booking) -> dict:
        slot = db.get(ParkingSlot, b.slot_id)
        return {
            "id": b.id,
            "vehicle_number": b.vehicle_number,
            "slot_id": b.slot_id,
            "slot_code": slot.code if slot else "Unknown",
            "start_time": format_utc_iso(b.start_time),
            "end_time": format_utc_iso(b.end_time),
            "status": b.status,
        }

    def _activity_dict(b: Booking) -> dict:
        slot = db.get(ParkingSlot, b.slot_id)
        slot_code = slot.code if slot else "Unknown"
        is_cancel = b.status == "cancelled"
        desc = (
            f"Cancelled booking #{b.id} for Slot {slot_code} ({b.vehicle_number})"
            if is_cancel
            else f"Reserved Slot {slot_code} for {b.vehicle_number}"
        )
        return {
            "id": b.id,
            "type": "cancellation" if is_cancel else "booking",
            "description": desc,
            "message": desc,
            "time": format_utc_iso(b.start_time),
            "status": b.status,
            "slot_code": slot_code,
            "vehicle_number": b.vehicle_number,
        }

    return {
        "welcome_name": current_user.full_name,
        # Supply both single and plural keys for complete frontend compatibility
        "total_available": total_available,
        "total_available_slots": total_available,
        "available_car": available_car,
        "available_car_slots": available_car,
        "available_bike": available_bike,
        "available_bike_slots": available_bike,
        "total_bookings": total_customer_bookings,
        "upcoming_bookings": [_booking_dict(b) for b in upcoming_bookings],
        "recent_activity": [_activity_dict(b) for b in recent_bookings],
    }


# ---------------------------------------------------------------------------
# Slots (read-only view with real-time availability)
# ---------------------------------------------------------------------------


@router.get("/slots")
def customer_list_slots(
    slot_type: str | None = None,
    slot_status: str | None = None,
    status: str | None = None,
    search: str | None = None,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Return all parking slots (read-only for customers) with real-time status."""
    query = db.query(ParkingSlot)

    if slot_type:
        query = query.filter(ParkingSlot.slot_type == slot_type.strip().lower())

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            ParkingSlot.code.ilike(term)
            | ParkingSlot.zone.ilike(term)
        )

    slots = query.order_by(ParkingSlot.code).all()

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    active_reserved_slot_ids = {
        b.slot_id
        for b in db.query(Booking.slot_id).filter(
            Booking.status == "confirmed",
            Booking.start_time <= now_utc,
            Booking.end_time > now_utc,
        ).all()
    }

    target_status = (slot_status or status or "").strip().lower()

    results = []
    for s in slots:
        eff_status = s.status
        if s.status == "available" and s.id in active_reserved_slot_ids:
            eff_status = "reserved"

        if target_status and eff_status != target_status:
            continue

        results.append(
            {
                "id": s.id,
                "code": s.code,
                "zone": s.zone,
                "status": eff_status,
                "slot_type": s.slot_type,
            }
        )

    return results


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
                "start_time": format_utc_iso(b.start_time),
                "end_time": format_utc_iso(b.end_time),
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
    # 1. Normalize dates to naive UTC for consistent database comparisons
    start_utc = to_utc_naive(data.start_time)
    end_utc = to_utc_naive(data.end_time)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    if end_utc <= start_utc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="End time must be after start time.",
        )

    # Allow a 5-minute grace period so form-filling delay doesn't trigger false errors
    if start_utc < now_utc - timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Start time cannot be in the past. Please select the current or a future time.",
        )

    # 2. Verify slot existence
    slot = db.get(ParkingSlot, data.slot_id)
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected parking slot was not found.",
        )

    # 3. Check physical occupancy if starting immediately
    if start_utc <= now_utc + timedelta(minutes=15) and slot.status == "occupied":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slot {slot.code} is currently occupied by a parked vehicle.",
        )

    # 4. Check for reservation time conflicts (double-booking prevention)
    overlapping = db.query(Booking).filter(
        Booking.slot_id == data.slot_id,
        Booking.status == "confirmed",
        Booking.start_time < end_utc,
        Booking.end_time > start_utc,
    ).first()

    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Slot {slot.code} is already booked for an overlapping period "
                f"({format_utc_iso(overlapping.start_time)} to {format_utc_iso(overlapping.end_time)}). "
                f"Please choose another time or slot."
            ),
        )

    # 5. Ensure vehicle record exists and is associated with this customer
    try:
        vehicle = db.query(Vehicle).filter(
            Vehicle.registration_number == data.vehicle_number
        ).first()

        if not vehicle:
            vehicle = Vehicle(
                registration_number=data.vehicle_number,
                owner_name=current_user.full_name,
                phone=current_user.phone or "",
                vehicle_type=slot.slot_type or "car",
                user_id=current_user.id,
            )
            db.add(vehicle)
        elif vehicle.user_id is None:
            vehicle.user_id = current_user.id

        # 6. Save confirmed booking
        booking = Booking(
            vehicle_number=data.vehicle_number,
            customer_name=current_user.full_name,
            slot_id=data.slot_id,
            start_time=start_utc,
            end_time=end_utc,
            status="confirmed",
            user_id=current_user.id,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        return {
            "message": "Booking confirmed successfully.",
            "booking_id": booking.id,
            "slot_code": slot.code,
            "vehicle_number": booking.vehicle_number,
            "start_time": format_utc_iso(booking.start_time),
            "end_time": format_utc_iso(booking.end_time),
            "status": booking.status,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record booking: {str(exc)}",
        ) from exc


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
            detail="Booking not found or not owned by your account.",
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This booking cannot be cancelled because its status is already '{booking.status}'.",
        )

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    start_utc = to_utc_naive(booking.start_time)
    if start_utc <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel a booking that has already started or elapsed.",
        )

    try:
        booking.status = "cancelled"
        db.commit()
        return {"message": "Booking cancelled successfully."}
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel booking: {str(exc)}",
        ) from exc


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
    try:
        current_user.full_name = data.full_name
        current_user.phone = data.phone
        db.commit()
        db.refresh(current_user)
        return current_user
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(exc)}",
        ) from exc


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

    try:
        current_user.hashed_password = hash_password(data.new_password)
        db.commit()
        return {"message": "Password changed successfully."}
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(exc)}",
        ) from exc
