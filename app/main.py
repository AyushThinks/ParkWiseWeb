"""FastAPI application for the ParkWise parking management system."""

import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
from .auth import format_utc_iso, get_current_user, require_admin, to_utc_naive
from .database import Base, engine, get_db, run_migrations
from .routes import auth_routes, customer_routes

Base.metadata.create_all(bind=engine)
run_migrations()

app = FastAPI(
    title="ParkWise API",
    version="1.0.0",
    description="Database-driven parking management system.",
)

# CORS middleware for development and deployment flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include dedicated modular routers
app.include_router(auth_routes.router)
app.include_router(customer_routes.router)


@app.get("/api/health", tags=["System"])
def health_check():
    """Confirm that the API process is responding."""
    return {"status": "ok", "service": "ParkWise API"}


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------


@app.get("/api/dashboard", tags=["Dashboard"])
def get_dashboard(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return dashboard metrics calculated from persisted database records (Admin only)."""
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    active_reserved_slot_ids = {
        b.slot_id
        for b in db.query(models.Booking.slot_id).filter(
            models.Booking.status == "confirmed",
            models.Booking.end_time > now_utc,
        ).all()
    }
    reserved_slots_count = len(active_reserved_slot_ids)

    total_slots = db.query(models.ParkingSlot).count()
    occupied_slots = db.query(models.ParkingSlot).filter(
        models.ParkingSlot.status == "occupied"
    ).count()
    raw_available = db.query(models.ParkingSlot).filter(
        models.ParkingSlot.status == "available"
    ).count()
    available_slots = max(0, raw_available - reserved_slots_count)
    total_vehicles = db.query(models.Vehicle).count()
    active_sessions = db.query(models.ParkingSession).filter(
        models.ParkingSession.status == "active"
    ).count()

    today = datetime.now(timezone.utc).date()
    today_revenue = db.query(
        func.coalesce(func.sum(models.ParkingSession.amount), 0)
    ).filter(
        models.ParkingSession.status == "completed",
        cast(models.ParkingSession.exit_time, Date) == today,
    ).scalar()

    recent_sessions = (
        db.query(models.ParkingSession)
        .options(
            joinedload(models.ParkingSession.vehicle),
            joinedload(models.ParkingSession.slot),
        )
        .order_by(models.ParkingSession.entry_time.desc())
        .limit(6)
        .all()
    )

    recent_bookings = (
        db.query(models.Booking)
        .order_by(models.Booking.start_time.desc())
        .limit(6)
        .all()
    )

    return {
        "total_vehicles": total_vehicles,
        "occupied_slots": occupied_slots,
        "available_slots": available_slots,
        "reserved_slots": reserved_slots_count,
        "total_slots": total_slots,
        "active_sessions": active_sessions,
        "total_bookings": db.query(models.Booking).count(),
        "today_revenue": round(float(today_revenue or 0), 2),
        "occupancy_percent": (
            round((occupied_slots + reserved_slots_count) / total_slots * 100)
            if total_slots else 0
        ),
        "recent_sessions": [
            {
                "id": item.id,
                "vehicle": (
                    item.vehicle.registration_number
                    if item.vehicle else "Unknown Vehicle"
                ),
                "owner": (
                    item.vehicle.owner_name
                    if item.vehicle else "Unknown Owner"
                ),
                "slot": item.slot.code if item.slot else "Unknown Slot",
                "entry_time": format_utc_iso(item.entry_time),
                "status": item.status,
            }
            for item in recent_sessions
        ],
        "recent_bookings": [
            {
                "id": b.id,
                "vehicle": b.vehicle_number,
                "customer": b.customer_name,
                "slot_id": b.slot_id,
                "slot": (
                    db.get(models.ParkingSlot, b.slot_id).code
                    if db.get(models.ParkingSlot, b.slot_id) else "—"
                ),
                "start_time": format_utc_iso(b.start_time),
                "end_time": format_utc_iso(b.end_time),
                "status": b.status,
            }
            for b in recent_bookings
        ],
    }


# ---------------------------------------------------------------------------
# Slots Management
# ---------------------------------------------------------------------------


@app.get("/api/slots", response_model=list[schemas.SlotOut], tags=["Slots"])
def list_slots(
    slot_status: str | None = None,
    db: Session = Depends(get_db),
):
    """List parking slots with live active reservation status."""
    query = db.query(models.ParkingSlot)
    slots = query.order_by(models.ParkingSlot.code).all()

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    active_reserved_slot_ids = {
        b.slot_id
        for b in db.query(models.Booking.slot_id).filter(
            models.Booking.status == "confirmed",
            models.Booking.end_time > now_utc,
        ).all()
    }

    results = []
    for s in slots:
        status_val = s.status
        if status_val == "available" and s.id in active_reserved_slot_ids:
            status_val = "reserved"

        if slot_status and status_val != slot_status:
            continue

        results.append(
            schemas.SlotOut(
                id=s.id,
                code=s.code,
                zone=s.zone,
                slot_type=s.slot_type,
                status=status_val,
            )
        )
    return results


@app.post(
    "/api/slots",
    response_model=schemas.SlotOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Slots"],
)
def create_slot(
    data: schemas.SlotCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new parking slot (Admin only)."""
    existing = db.query(models.ParkingSlot).filter(
        models.ParkingSlot.code == data.code
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A parking slot with this code already exists.",
        )

    slot = models.ParkingSlot(**data.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return slot


@app.patch(
    "/api/slots/{slot_id}",
    response_model=schemas.SlotOut,
    tags=["Slots"],
)
def update_slot(
    slot_id: int,
    data: schemas.SlotCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update parking slot details (Admin only)."""
    slot = db.get(models.ParkingSlot, slot_id)
    if not slot:
        raise HTTPException(404, "Parking slot not found.")

    duplicate = db.query(models.ParkingSlot).filter(
        models.ParkingSlot.code == data.code,
        models.ParkingSlot.id != slot_id,
    ).first()
    if duplicate:
        raise HTTPException(409, "Slot code already exists.")

    if slot.status == "occupied" and data.slot_type != slot.slot_type:
        raise HTTPException(
            409,
            "Cannot change the type of an occupied parking slot.",
        )

    for field, value in data.model_dump().items():
        setattr(slot, field, value)

    db.commit()
    db.refresh(slot)
    return slot


@app.delete(
    "/api/slots/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Slots"],
)
def delete_slot(
    slot_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a parking slot (Admin only)."""
    slot = db.get(models.ParkingSlot, slot_id)
    if not slot:
        raise HTTPException(404, "Parking slot not found.")

    if slot.status == "occupied":
        raise HTTPException(
            409,
            "Check out the vehicle before deleting this slot.",
        )

    has_sessions = db.query(models.ParkingSession).filter(
        models.ParkingSession.slot_id == slot_id
    ).first()
    has_bookings = db.query(models.Booking).filter(
        models.Booking.slot_id == slot_id
    ).first()

    if has_sessions or has_bookings:
        raise HTTPException(
            409,
            "This slot has transaction history and cannot be deleted.",
        )

    db.delete(slot)
    db.commit()


# ---------------------------------------------------------------------------
# Vehicle Management
# ---------------------------------------------------------------------------


@app.get(
    "/api/vehicles",
    response_model=list[schemas.VehicleOut],
    tags=["Vehicles"],
)
def list_vehicles(
    search: str | None = None,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List registered vehicles (Admin only)."""
    query = db.query(models.Vehicle)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            models.Vehicle.registration_number.ilike(term)
            | models.Vehicle.owner_name.ilike(term)
        )
    return query.order_by(models.Vehicle.id.desc()).all()


@app.post(
    "/api/vehicles",
    response_model=schemas.VehicleOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Vehicles"],
)
def create_vehicle(
    data: schemas.VehicleCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Register a new vehicle (Admin only)."""
    duplicate = db.query(models.Vehicle).filter(
        models.Vehicle.registration_number == data.registration_number
    ).first()

    if duplicate:
        raise HTTPException(409, "This vehicle is already registered.")

    vehicle = models.Vehicle(**data.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@app.patch(
    "/api/vehicles/{vehicle_id}",
    response_model=schemas.VehicleOut,
    tags=["Vehicles"],
)
def update_vehicle(
    vehicle_id: int,
    data: schemas.VehicleCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update vehicle registration details (Admin only)."""
    vehicle = db.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(404, "Vehicle not found.")

    duplicate = db.query(models.Vehicle).filter(
        models.Vehicle.registration_number == data.registration_number,
        models.Vehicle.id != vehicle_id,
    ).first()
    if duplicate:
        raise HTTPException(409, "Registration number already exists.")

    for field, value in data.model_dump().items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)
    return vehicle


@app.delete(
    "/api/vehicles/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Vehicles"],
)
def delete_vehicle(
    vehicle_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a vehicle record (Admin only)."""
    vehicle = db.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(404, "Vehicle not found.")

    has_history = db.query(models.ParkingSession).filter(
        models.ParkingSession.vehicle_id == vehicle_id
    ).first()

    if has_history:
        raise HTTPException(
            409,
            "This vehicle has parking history and cannot be deleted.",
        )

    db.delete(vehicle)
    db.commit()


# ---------------------------------------------------------------------------
# Parking Check-In / Check-Out
# ---------------------------------------------------------------------------


@app.post("/api/check-in", tags=["Parking"])
def check_in_vehicle(
    vehicle_number: str,
    slot_code: str,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Check in a vehicle into an available slot (Admin only)."""
    try:
        registration = schemas.clean_registration(vehicle_number)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.registration_number == registration
    ).first()
    if not vehicle:
        raise HTTPException(
            404,
            "Vehicle is not registered. Register it before check-in.",
        )

    slot = db.query(models.ParkingSlot).filter(
        models.ParkingSlot.code == slot_code.strip().upper()
    ).first()
    if not slot:
        raise HTTPException(404, "Parking slot not found.")
    if slot.status != "available":
        raise HTTPException(409, "This parking slot is not available.")

    active_session = db.query(models.ParkingSession).filter(
        models.ParkingSession.vehicle_id == vehicle.id,
        models.ParkingSession.status == "active",
    ).first()
    if active_session:
        raise HTTPException(
            409,
            "This vehicle already has an active parking session.",
        )

    parking_session = models.ParkingSession(
        vehicle_id=vehicle.id,
        slot_id=slot.id,
    )
    slot.status = "occupied"
    db.add(parking_session)
    db.commit()
    db.refresh(parking_session)

    return {
        "message": "Vehicle checked in successfully.",
        "session_id": parking_session.id,
        "slot": slot.code,
    }


@app.post("/api/check-out/{session_id}", tags=["Parking"])
def check_out_vehicle(
    session_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Check out a vehicle and compute fee (Admin only)."""
    parking_session = (
        db.query(models.ParkingSession)
        .options(joinedload(models.ParkingSession.slot))
        .filter(models.ParkingSession.id == session_id)
        .first()
    )

    if not parking_session:
        raise HTTPException(404, "Parking session not found.")
    if parking_session.status != "active":
        raise HTTPException(409, "This parking session is already closed.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    duration_hours = max(
        1,
        (now - parking_session.entry_time).total_seconds() / 3600,
    )
    amount = round(duration_hours * 30, 2)

    parking_session.exit_time = now
    parking_session.amount = amount
    parking_session.status = "completed"

    if parking_session.slot:
        parking_session.slot.status = "available"

    db.commit()

    return {
        "message": "Vehicle checked out successfully.",
        "duration_hours": round(duration_hours, 2),
        "amount": amount,
    }


@app.get("/api/sessions", tags=["Parking"])
def list_sessions(
    session_status: str | None = None,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List operational parking sessions (Admin only)."""
    query = db.query(models.ParkingSession).options(
        joinedload(models.ParkingSession.vehicle),
        joinedload(models.ParkingSession.slot),
    )

    if session_status:
        query = query.filter(
            models.ParkingSession.status == session_status
        )

    sessions = query.order_by(
        models.ParkingSession.entry_time.desc()
    ).limit(100).all()

    return [
        {
            "id": item.id,
            "vehicle": (
                item.vehicle.registration_number
                if item.vehicle else "Unknown Vehicle"
            ),
            "owner": (
                item.vehicle.owner_name
                if item.vehicle else "Unknown Owner"
            ),
            "slot": item.slot.code if item.slot else "Unknown Slot",
            "entry_time": format_utc_iso(item.entry_time),
            "exit_time": format_utc_iso(item.exit_time),
            "amount": item.amount,
            "status": item.status,
        }
        for item in sessions
    ]


# ---------------------------------------------------------------------------
# Bookings (Admin operations)
# ---------------------------------------------------------------------------


@app.get("/api/bookings", tags=["Bookings"])
def list_bookings(
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all reservations in the system (Admin only)."""
    bookings = db.query(models.Booking).order_by(
        models.Booking.start_time.desc()
    ).all()

    return [
        {
            "id": item.id,
            "vehicle_number": item.vehicle_number,
            "customer_name": item.customer_name,
            "slot_id": item.slot_id,
            "start_time": format_utc_iso(item.start_time),
            "end_time": format_utc_iso(item.end_time),
            "status": item.status,
        }
        for item in bookings
    ]


@app.post(
    "/api/bookings",
    status_code=status.HTTP_201_CREATED,
    tags=["Bookings"],
)
def create_booking(
    data: schemas.BookingCreate,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a reservation from Admin panel (Admin only)."""
    start_utc = to_utc_naive(data.start_time)
    end_utc = to_utc_naive(data.end_time)

    if end_utc <= start_utc:
        raise HTTPException(422, "End time must be after start time.")

    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.registration_number == data.vehicle_number
    ).first()
    if not vehicle:
        raise HTTPException(404, "Register this vehicle before booking.")

    slot = db.get(models.ParkingSlot, data.slot_id)
    if not slot:
        raise HTTPException(404, "Parking slot not found.")

    overlapping_booking = db.query(models.Booking).filter(
        models.Booking.slot_id == data.slot_id,
        models.Booking.status == "confirmed",
        models.Booking.start_time < end_utc,
        models.Booking.end_time > start_utc,
    ).first()

    if overlapping_booking:
        raise HTTPException(
            409,
            "This slot is already booked during the selected time.",
        )

    try:
        booking = models.Booking(
            vehicle_number=data.vehicle_number,
            customer_name=data.customer_name,
            slot_id=data.slot_id,
            start_time=start_utc,
            end_time=end_utc,
            status="confirmed",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        return {
            "message": "Booking created successfully.",
            "booking_id": booking.id,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Failed to create booking: {str(exc)}")


@app.post("/api/bookings/{booking_id}/cancel", tags=["Bookings"])
@app.delete("/api/bookings/{booking_id}", tags=["Bookings"])
def cancel_booking_admin(
    booking_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Cancel or release a reservation (Admin only)."""
    booking = db.get(models.Booking, booking_id)
    if not booking:
        raise HTTPException(404, "Booking not found.")

    booking.status = "cancelled"
    db.commit()
    return {"message": "Booking cancelled successfully."}


# ---------------------------------------------------------------------------
# HTML Page Routing
# ---------------------------------------------------------------------------


@app.get("/")
def home_landing_page():
    """Visitor landing page."""
    return FileResponse("frontend/landing.html")


@app.get("/login")
@app.get("/login.html")
def login_page():
    return FileResponse("frontend/login.html")


@app.get("/signup")
@app.get("/signup.html")
def signup_page():
    return FileResponse("frontend/signup.html")


@app.get("/customer")
@app.get("/customer/{path:path}")
def customer_page():
    return FileResponse("frontend/customer.html")


@app.get("/admin")
@app.get("/admin/{path:path}")
@app.get("/index.html")
def admin_page():
    return FileResponse("frontend/index.html")


# Mount static files (styles.css, app.js, index.html)
app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)
