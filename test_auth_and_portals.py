"""Comprehensive automated test suite for ParkWise Authentication and Dual Portals."""

import os
import sys
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.auth import create_access_token, hash_password
from app.database import Base, SessionLocal, engine, run_migrations
from app.main import app
from app.models import Booking, ParkingSlot, ParkingSession, User, Vehicle

client = TestClient(app)


def setup_module():
    """Ensure database tables exist and clean up any previous test records."""
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    try:
        # Clean test records if present
        db.query(Booking).delete()
        db.query(ParkingSession).delete()
        db.query(Vehicle).delete()
        db.query(ParkingSlot).delete()
        db.query(User).delete()
        db.commit()

        # Seed initial slots
        s1 = ParkingSlot(code="A01", zone="Block A", status="available", slot_type="car")
        s2 = ParkingSlot(code="A02", zone="Block A", status="available", slot_type="bike")
        db.add_all([s1, s2])

        # Seed admin
        admin = User(
            full_name="Facility Administrator",
            email="admin@parkwise.com",
            phone="9876543210",
            hashed_password=hash_password("Admin@123"),
            role="ADMIN",
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()


def test_public_pages_and_health():
    """Test public health endpoint and landing / auth HTML page serving."""
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    # Landing page
    r_landing = client.get("/")
    assert r_landing.status_code == 200
    assert "ParkWise" in r_landing.text

    # Login and Signup pages
    r_login = client.get("/login")
    assert r_login.status_code == 200
    assert "Welcome back" in r_login.text

    r_signup = client.get("/signup")
    assert r_signup.status_code == 200
    assert "Create an account" in r_signup.text

    # Customer portal
    r_cust = client.get("/customer")
    assert r_cust.status_code == 200
    assert "Customer Portal" in r_cust.text


def test_customer_registration_and_validation():
    """Test customer signup, email duplicate rejection, and password validation."""
    # 1. Invalid email
    r_bad_email = client.post(
        "/api/auth/register",
        json={
            "full_name": "Alice Green",
            "email": "not-an-email",
            "phone": "9876543211",
            "password": "Password@123",
        },
    )
    assert r_bad_email.status_code == 422

    # 2. Weak password (no uppercase or no digit)
    r_weak_pw = client.post(
        "/api/auth/register",
        json={
            "full_name": "Alice Green",
            "email": "alice@example.com",
            "phone": "9876543211",
            "password": "password",
        },
    )
    assert r_weak_pw.status_code == 422

    # 3. Valid registration
    r_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Alice Green",
            "email": "alice@example.com",
            "phone": "9876543211",
            "password": "Password@123",
        },
    )
    assert r_reg.status_code == 201
    data = r_reg.json()
    assert "access_token" in data
    assert data["user"]["role"] == "CUSTOMER"
    assert data["user"]["email"] == "alice@example.com"

    # 4. Duplicate registration rejection (409 Conflict)
    r_dup = client.post(
        "/api/auth/register",
        json={
            "full_name": "Alice Green",
            "email": "alice@example.com",
            "phone": "9876543211",
            "password": "Password@123",
        },
    )
    assert r_dup.status_code == 409
    assert "already exists" in r_dup.json()["detail"]


def test_customer_and_admin_login():
    """Test customer login, wrong password rejection, and admin login."""
    # 1. Wrong password
    r_bad_pw = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "WrongPassword"},
    )
    assert r_bad_pw.status_code == 401

    # 2. Non-existent email
    r_bad_user = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "Password@123"},
    )
    assert r_bad_user.status_code == 401

    # 3. Customer login
    r_cust_login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "Password@123"},
    )
    assert r_cust_login.status_code == 200
    cust_data = r_cust_login.json()
    assert cust_data["user"]["role"] == "CUSTOMER"
    assert "access_token" in cust_data

    # 4. Admin login
    r_admin_login = client.post(
        "/api/auth/login",
        json={"email": "admin@parkwise.com", "password": "Admin@123"},
    )
    assert r_admin_login.status_code == 200
    admin_data = r_admin_login.json()
    assert admin_data["user"]["role"] == "ADMIN"
    assert "access_token" in admin_data


def test_role_based_access_control():
    """Ensure customers cannot access admin-only APIs or operations."""
    # Clear any cookies from previous login tests
    client.cookies.clear()

    # Get tokens
    admin_token = client.post(
        "/api/auth/login",
        json={"email": "admin@parkwise.com", "password": "Admin@123"},
    ).json()["access_token"]
    client.cookies.clear()

    cust_token = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "Password@123"},
    ).json()["access_token"]
    client.cookies.clear()

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # 1. Admin dashboard endpoint
    # Unauthenticated -> 401
    assert client.get("/api/dashboard").status_code == 401
    # Customer -> 403 Forbidden
    assert client.get("/api/dashboard", headers=cust_headers).status_code == 403
    # Admin -> 200 OK
    assert client.get("/api/dashboard", headers=admin_headers).status_code == 200

    # 2. Admin slot creation
    # Customer -> 403 Forbidden
    r_cust_slot = client.post(
        "/api/slots",
        json={"code": "B01", "zone": "Block B", "slot_type": "car"},
        headers=cust_headers,
    )
    assert r_cust_slot.status_code == 403

    # Admin -> 201 Created
    r_admin_slot = client.post(
        "/api/slots",
        json={"code": "B01", "zone": "Block B", "slot_type": "car"},
        headers=admin_headers,
    )
    assert r_admin_slot.status_code == 201

    # 3. Admin vehicle registration
    r_cust_veh = client.post(
        "/api/vehicles",
        json={"registration_number": "DL01AB1234", "owner_name": "Bob Smith"},
        headers=cust_headers,
    )
    assert r_cust_veh.status_code == 403

    r_admin_veh = client.post(
        "/api/vehicles",
        json={"registration_number": "DL01AB1234", "owner_name": "Bob Smith"},
        headers=admin_headers,
    )
    assert r_admin_veh.status_code == 201


def test_customer_portal_operations_and_booking_conflicts():
    """Test customer slots view, bookings creation, overlap prevention, and cancellation."""
    # Register a second customer for IDOR testing
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Charlie Brown",
            "email": "charlie@example.com",
            "phone": "9876543212",
            "password": "Password@123",
        },
    )

    alice_token = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "Password@123"},
    ).json()["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    charlie_token = client.post(
        "/api/auth/login",
        json={"email": "charlie@example.com", "password": "Password@123"},
    ).json()["access_token"]
    charlie_headers = {"Authorization": f"Bearer {charlie_token}"}
    client.cookies.clear()

    # 1. View slots
    r_slots = client.get("/api/customer/slots", headers=alice_headers)
    assert r_slots.status_code == 200
    slots = r_slots.json()
    assert len(slots) >= 3

    slot_a01 = next(s for s in slots if s["code"] == "A01")

    # 2. Create customer booking
    start_time = datetime.utcnow() + timedelta(hours=2)
    end_time = start_time + timedelta(hours=3)

    r_bk1 = client.post(
        "/api/customer/bookings",
        headers=alice_headers,
        json={
            "vehicle_number": "DL02CD5678",
            "slot_id": slot_a01["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert r_bk1.status_code == 201
    bk1_id = r_bk1.json()["booking_id"]

    # 3. Double-booking conflict prevention
    # Charlie attempts to book the same slot with overlapping time
    conflict_start = start_time + timedelta(hours=1)
    conflict_end = end_time + timedelta(hours=1)

    r_conflict = client.post(
        "/api/customer/bookings",
        headers=charlie_headers,
        json={
            "vehicle_number": "MH01EF9999",
            "slot_id": slot_a01["id"],
            "start_time": conflict_start.isoformat(),
            "end_time": conflict_end.isoformat(),
        },
    )
    assert r_conflict.status_code == 409
    assert "already booked" in r_conflict.json()["detail"]

    # 4. Customer can only view their own bookings
    alice_bookings = client.get("/api/customer/bookings", headers=alice_headers).json()
    assert any(b["id"] == bk1_id for b in alice_bookings)

    charlie_bookings = client.get("/api/customer/bookings", headers=charlie_headers).json()
    assert not any(b["id"] == bk1_id for b in charlie_bookings)

    # 5. IDOR prevention: Charlie cannot cancel Alice's booking
    r_idor_cancel = client.post(
        f"/api/customer/bookings/{bk1_id}/cancel",
        headers=charlie_headers,
    )
    assert r_idor_cancel.status_code == 404

    # 6. Alice can cancel her own booking
    r_alice_cancel = client.post(
        f"/api/customer/bookings/{bk1_id}/cancel",
        headers=alice_headers,
    )
    assert r_alice_cancel.status_code == 200

    # Booking status should now be cancelled
    updated_bk = next(b for b in client.get("/api/customer/bookings", headers=alice_headers).json() if b["id"] == bk1_id)
    assert updated_bk["status"] == "cancelled"


def test_customer_profile_and_password_change():
    """Test customer profile retrieval, update, and password change."""
    alice_token = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "Password@123"},
    ).json()["access_token"]
    alice_headers = {"Authorization": f"Bearer {alice_token}"}

    # 1. Get profile
    r_prof = client.get("/api/customer/profile", headers=alice_headers)
    assert r_prof.status_code == 200
    assert r_prof.json()["full_name"] == "Alice Green"

    # 2. Update profile
    r_upd = client.patch(
        "/api/customer/profile",
        headers=alice_headers,
        json={"full_name": "Alice G. Walker", "phone": "9876543299"},
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["full_name"] == "Alice G. Walker"
    assert r_upd.json()["phone"] == "9876543299"

    # 3. Change password with wrong current password
    r_pw_fail = client.post(
        "/api/customer/change-password",
        headers=alice_headers,
        json={"current_password": "WrongPassword", "new_password": "NewPassword@123"},
    )
    assert r_pw_fail.status_code == 400

    # 4. Change password with correct current password
    r_pw_ok = client.post(
        "/api/customer/change-password",
        headers=alice_headers,
        json={"current_password": "Password@123", "new_password": "NewPassword@123"},
    )
    assert r_pw_ok.status_code == 200

    # 5. Login with new password
    r_new_login = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "NewPassword@123"},
    )
    assert r_new_login.status_code == 200


def test_admin_parking_session_workflow():
    """Ensure existing admin parking operations (check-in, check-out, fee) continue working."""
    admin_token = client.post(
        "/api/auth/login",
        json={"email": "admin@parkwise.com", "password": "Admin@123"},
    ).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Check in DL01AB1234 to B01
    r_checkin = client.post(
        "/api/check-in?vehicle_number=DL01AB1234&slot_code=B01",
        headers=admin_headers,
    )
    assert r_checkin.status_code == 200
    session_id = r_checkin.json()["session_id"]

    # Slot B01 is now occupied
    slots = client.get("/api/slots").json()
    b01 = next(s for s in slots if s["code"] == "B01")
    assert b01["status"] == "occupied"

    # Check out vehicle
    r_checkout = client.post(
        f"/api/check-out/{session_id}",
        headers=admin_headers,
    )
    assert r_checkout.status_code == 200
    assert r_checkout.json()["amount"] >= 30

    # Slot B01 is available again
    slots_after = client.get("/api/slots").json()
    b01_after = next(s for s in slots_after if s["code"] == "B01")
    assert b01_after["status"] == "available"

    # Sessions history contains the completed session
    sessions = client.get("/api/sessions", headers=admin_headers).json()
    assert any(s["id"] == session_id and s["status"] == "completed" for s in sessions)

    # Admin dashboard returns comprehensive stats
    r_dash = client.get("/api/dashboard", headers=admin_headers)
    assert r_dash.status_code == 200
    dash_data = r_dash.json()
    assert "total_vehicles" in dash_data
    assert "available_slots" in dash_data
    assert "reserved_slots" in dash_data
    assert "recent_bookings" in dash_data

    # Admin can cancel a booking
    admin_bk = client.post(
        "/api/bookings",
        headers=admin_headers,
        json={
            "vehicle_number": "DL01AB1234",
            "customer_name": "Walk-in Guest",
            "slot_id": b01["id"],
            "start_time": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
            "end_time": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
        },
    )
    assert admin_bk.status_code == 201
    abk_id = admin_bk.json()["booking_id"]
    r_cancel_abk = client.post(f"/api/bookings/{abk_id}/cancel", headers=admin_headers)
    assert r_cancel_abk.status_code == 200


if __name__ == "__main__":
    setup_module()
    print("Running test_public_pages_and_health...")
    test_public_pages_and_health()
    print("Running test_customer_registration_and_validation...")
    test_customer_registration_and_validation()
    print("Running test_customer_and_admin_login...")
    test_customer_and_admin_login()
    print("Running test_role_based_access_control...")
    test_role_based_access_control()
    print("Running test_customer_portal_operations_and_booking_conflicts...")
    test_customer_portal_operations_and_booking_conflicts()
    print("Running test_customer_profile_and_password_change...")
    test_customer_profile_and_password_change()
    print("Running test_admin_parking_session_workflow...")
    test_admin_parking_session_workflow()
    print("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY! (100% SUCCESS)")
