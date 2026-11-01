# ParkWise — Smart Parking Management System

ParkWise is a modern, database-driven parking management application built with **FastAPI**, **SQLAlchemy**, and a responsive HTML/CSS/JavaScript interface.

ParkWise features a **Dual Portal Architecture**:
- 🏢 **Admin Portal**: For parking facility operators to manage parking slots, registered vehicles, monitor live entry/exit sessions, perform check-ins/check-outs, calculate hourly parking fees, and export reports.
- 🚗 **Customer Portal**: For vehicle owners to view real-time slot availability (Cars & Bikes), reserve parking slots in advance with backend double-booking prevention, manage active reservations, and update their profile.
- 🛡️ **Authentication & Authorization**: Secure JWT tokens with Bcrypt password hashing, automated role-based routing (ADMIN vs. CUSTOMER), and server-verified access control.

---

## Architecture & Project Structure

```text
ParkWise/
├── app/
│   ├── __init__.py
│   ├── auth.py             # JWT token generation, Bcrypt hashing & FastAPI dependencies
│   ├── database.py         # SQLAlchemy engine, session maker & automated schema migrations
│   ├── main.py             # FastAPI app, route protection, CORS & frontend page routing
│   ├── models.py           # SQLAlchemy models (User, ParkingSlot, Vehicle, ParkingSession, Booking)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth_routes.py  # Public registration, login, logout, and current-user endpoints
│   │   └── customer_routes.py # Customer dashboard, slots, bookings, cancellation & profile
│   ├── schemas.py          # Pydantic schemas with strict input and format validation
│   └── seed_admin.py       # CLI utility to seed an initial Administrator account
├── docs/
│   └── PROJECT_REQUIREMENTS.md
├── frontend/
│   ├── app.js              # Admin Dashboard controller (protected by role guard)
│   ├── customer.html       # Customer Portal single-page application
│   ├── index.html          # Admin Portal management dashboard
│   ├── landing.html        # Public visitor landing page with portal navigation
│   ├── login.html          # Authentication login page with role redirection
│   ├── signup.html         # Public customer registration page with real-time validation
│   └── styles.css          # ParkWise design system stylesheet (variables, components, dark mode)
├── .env.example            # Environment variables template
├── .gitignore
├── Procfile                # Production process command for Render / Railway
├── requirements.txt        # Python package dependencies
├── test_auth_and_portals.py# Automated test suite (100% test coverage)
└── README.md
```

---

## User Roles & Portal Flow

| Role | Creation | Access / Portal | Capabilities |
|---|---|---|---|
| **CUSTOMER** | Public `/signup.html` registration | Redirected to `/customer` | View live slot availability, filter Car/Bike slots, reserve slots in advance, view and cancel own upcoming bookings, update profile and change password. |
| **ADMIN** | Created via `python -m app.seed_admin` or direct database setup | Redirected to `/admin` (`/index.html`) | Full facility management: add/edit/delete slots, register vehicles, check-in & check-out vehicles, monitor facility revenue & occupancy, view all sessions and reservations, export CSV reports. |

> **Security Note:** Public sign-up strictly creates accounts with the `CUSTOMER` role. The server ignores any client-supplied role values. Admin endpoints verify server-side credentials and reject customer access with `403 Forbidden`.

---

## Local Setup & Quick Start

### 1. Prerequisites
- Python 3.10+ (tested with Python 3.10 – 3.13)
- PowerShell, Bash, or terminal of your choice

### 2. Clone and Setup Environment

```powershell
# Navigate into project directory
cd ParkWise_Complete

# Create a virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows Command Prompt:
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables (Optional for SQLite)

By default, SQLite is used (`parkwise.db`). No configuration is required.
To customize secrets or use PostgreSQL, copy `.env.example` to `.env`:

```ini
DATABASE_URL=sqlite:///./parkwise.db
JWT_SECRET=your-secure-jwt-secret-key-change-in-production
```

### 4. Seed the Initial Administrator

Run the included admin seed script to create the default facility administrator:

```powershell
python -m app.seed_admin
```

Default Admin Credentials:
- **Email:** `admin@parkwise.com`
- **Password:** `Admin@123`
*(Change this password in production or upon first login)*

### 5. Start the Server

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Visitor Landing Page:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Customer Portal:** [http://127.0.0.1:8000/customer](http://127.0.0.1:8000/customer)
- **Admin Portal:** [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)
- **Login Page:** [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login)
- **Sign Up Page:** [http://127.0.0.1:8000/signup](http://127.0.0.1:8000/signup)
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Deploying on Render (with PostgreSQL)

Render natively supports Python web services and managed PostgreSQL databases.

### Step 1: Create a PostgreSQL Database on Render
1. Log in to your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** and select **PostgreSQL**.
3. Set the name to `parkwise-db` and click **Create Database**.
4. Once provisioned, copy the **Internal Database URL** (or **External Database URL** if deploying externally).

### Step 2: Create a Web Service on Render
1. Click **New +** and select **Web Service**.
2. Connect your Git repository containing the ParkWise code.
3. Configure the service:
   - **Name:** `parkwise`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. In the **Environment Variables** section, add:
   - `DATABASE_URL`: Paste the PostgreSQL URL copied from Step 1.
     *(Render URLs like `postgres://...` are automatically mapped to `postgresql+psycopg://` by `app/database.py`).*
   - `JWT_SECRET`: A secure random string (e.g. 64-character hexadecimal or random token).
5. Click **Create Web Service**.

### Step 3: Seed Admin on Render
After the initial deployment finishes:
1. Go to the **Shell** tab of your Render web service.
2. Run:
   ```bash
   python -m app.seed_admin
   ```
3. Your Administrator account is now seeded in PostgreSQL.

---

## Automated Database Schema Migrations

When running against an existing SQLite or PostgreSQL database:
- `app/database.py` includes `run_migrations()` which automatically inspects existing tables.
- If existing `vehicles` or `bookings` tables lack the new `user_id` foreign key column, `ALTER TABLE` is executed safely without data loss.
- Database records from earlier versions of ParkWise remain fully preserved.

---

## Running Automated Tests

A comprehensive test suite is included in `test_auth_and_portals.py`:

```powershell
python test_auth_and_portals.py
```

### Test Coverage Highlights:
- ✅ Public health check and static HTML page routing
- ✅ Customer registration with strict email, phone, and password complexity validation
- ✅ Duplicate email rejection (`409 Conflict`)
- ✅ Customer and Admin authentication with secure password verification
- ✅ Wrong password and unknown email rejection (`401 Unauthorized`)
- ✅ Role-Based Access Control: Customers attempting admin endpoints receive `403 Forbidden`
- ✅ Customer slot availability browsing (read-only)
- ✅ Customer booking creation and backend time-conflict / double-booking prevention (`409 Conflict`)
- ✅ IDOR Protection: Customers cannot view or cancel other customers' bookings
- ✅ Customer cancellation of own upcoming bookings
- ✅ Profile name & phone update, and secure password changing
- ✅ Preserved Admin parking check-in, check-out, fee computation, and session management

---

## API Reference Overview

### Public & Authentication Endpoints
| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | Public | System status check |
| `POST` | `/api/auth/register` | Public | Register new customer account |
| `POST` | `/api/auth/login` | Public | Authenticate user & issue JWT |
| `POST` | `/api/auth/logout` | Authenticated | Clear session cookie |
| `GET` | `/api/auth/me` | Authenticated | Get current authenticated user profile |

### Customer Portal Endpoints (`require_customer`)
| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/customer/dashboard` | Customer | Available slots breakdown, upcoming bookings |
| `GET` | `/api/customer/slots` | Customer | Filter & search available slots (read-only) |
| `GET` | `/api/customer/bookings` | Customer | View customer's own booking history |
| `POST` | `/api/customer/bookings` | Customer | Create advance parking reservation |
| `POST` | `/api/customer/bookings/{id}/cancel` | Customer | Cancel customer's own upcoming booking |
| `GET` | `/api/customer/profile` | Customer | Get customer profile details |
| `PATCH` | `/api/customer/profile` | Customer | Update customer full name and phone |
| `POST` | `/api/customer/change-password` | Customer | Verify current password and set new password |

### Admin Endpoints (`require_admin`)
| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/dashboard` | Admin | Complete facility metrics, revenue, and occupancy |
| `GET`, `POST` | `/api/slots` | Admin | List and add parking slots |
| `PATCH`, `DELETE` | `/api/slots/{id}` | Admin | Edit or delete a parking slot |
| `GET`, `POST` | `/api/vehicles` | Admin | List and register vehicles |
| `PATCH`, `DELETE` | `/api/vehicles/{id}` | Admin | Edit or delete a registered vehicle |
| `POST` | `/api/check-in` | Admin | Vehicle entry check-in |
| `POST` | `/api/check-out/{id}` | Admin | Vehicle exit check-out and fee calculation |
| `GET` | `/api/sessions` | Admin | Parking sessions entry/exit history |
| `GET`, `POST` | `/api/bookings` | Admin | View and create facility reservations |
