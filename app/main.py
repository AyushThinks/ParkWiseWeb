"""FastAPI application for the ParkWise parking management system."""

from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
from .database import Base, engine, get_db


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ParkWise API",
    version="1.0.0",
    description="Database-driven parking management system.",
)


@app.get("/api/health", tags=["System"])
def health_check():
    """Confirm that the API process is responding."""
    return {"status": "ok", "service": "ParkWise API"}


@app.get("/api/dashboard", tags=["Dashboard"])
def get_dashboard(db: Session = Depends(get_db)):
    """Return dashboard metrics calculated from persisted database records."""
    total_slots = db.query(models.ParkingSlot).count()
    occupied_slots = db.query(models.ParkingSlot).filter(
        models.ParkingSlot.status == "occupied"
    ).count()
    available_slots = db.query(models.ParkingSlot).filter(
        models.ParkingSlot.status == "available"
    ).count()
    total_vehicles = db.query(models.Vehicle).count()
    active_sessions = db.query(models.ParkingSession).filter(
        models.ParkingSession.status == "active"
    ).count()

    today = datetime.utcnow().date()
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

    return {
        "total_vehicles": total_vehicles,
        "occupied_slots": occupied_slots,
        "available_slots": available_slots,
        "total_slots": total_slots,
        "active_sessions": active_sessions,
        "today_revenue": round(float(today_revenue or 0), 2),
        "occupancy_percent": (
            round(occupied_slots / total_slots * 100)
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
                "entry_time": item.entry_time.isoformat(),
                "status": item.status,
            }
            for item in recent_sessions
        ],
    }


@app.get("/api/slots", response_model=list[schemas.SlotOut], tags=["Slots"])
def list_slots(
    slot_status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.ParkingSlot)
    if slot_status:
        query = query.filter(models.ParkingSlot.status == slot_status)
    return query.order_by(models.ParkingSlot.code).all()


@app.post(
    "/api/slots",
    response_model=schemas.SlotOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Slots"],
)
def create_slot(
    data: schemas.SlotCreate,
    db: Session = Depends(get_db),
):
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
    db: Session = Depends(get_db),
):
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
def delete_slot(slot_id: int, db: Session = Depends(get_db)):
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


@app.get(
    "/api/vehicles",
    response_model=list[schemas.VehicleOut],
    tags=["Vehicles"],
)
def list_vehicles(
    search: str | None = None,
    db: Session = Depends(get_db),
):
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
    db: Session = Depends(get_db),
):
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
    db: Session = Depends(get_db),
):
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
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
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


@app.post("/api/check-in", tags=["Parking"])
def check_in_vehicle(
    vehicle_number: str,
    slot_code: str,
    db: Session = Depends(get_db),
):
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
    db: Session = Depends(get_db),
):
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

    now = datetime.utcnow()
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
    db: Session = Depends(get_db),
):
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
            "entry_time": item.entry_time.isoformat(),
            "exit_time": (
                item.exit_time.isoformat()
                if item.exit_time else None
            ),
            "amount": item.amount,
            "status": item.status,
        }
        for item in sessions
    ]


@app.get("/api/bookings", tags=["Bookings"])
def list_bookings(db: Session = Depends(get_db)):
    bookings = db.query(models.Booking).order_by(
        models.Booking.start_time.desc()
    ).all()

    return [
        {
            "id": item.id,
            "vehicle_number": item.vehicle_number,
            "customer_name": item.customer_name,
            "slot_id": item.slot_id,
            "start_time": item.start_time.isoformat(),
            "end_time": item.end_time.isoformat(),
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
    db: Session = Depends(get_db),
):
    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.registration_number == data.vehicle_number
    ).first()
    if not vehicle:
        raise HTTPException(404, "Register this vehicle before booking.")

    slot = db.get(models.ParkingSlot, data.slot_id)
    if not slot:
        raise HTTPException(404, "Parking slot not found.")

    if data.end_time <= data.start_time:
        raise HTTPException(422, "End time must be after start time.")

    overlapping_booking = db.query(models.Booking).filter(
        models.Booking.slot_id == data.slot_id,
        models.Booking.status == "confirmed",
        models.Booking.start_time < data.end_time,
        models.Booking.end_time > data.start_time,
    ).first()

    if overlapping_booking:
        raise HTTPException(
            409,
            "This slot is already booked during the selected time.",
        )

    booking = models.Booking(**data.model_dump())
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return {
        "message": "Booking created successfully.",
        "booking_id": booking.id,
    }


app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)
