# ParkWise — Smart Parking Management System

ParkWise is a database-driven parking management application built with **FastAPI**, **SQLAlchemy**, and a responsive HTML/CSS/JavaScript interface.

## Important: no demo records are inserted

This version does **not** create fake vehicles, fake parking slots, or fake parking sessions. A new database starts empty. The dashboard shows zero until you add real records through the application.

Existing database files are not automatically deleted or reset.

## Features

- Dashboard metrics calculated from database records
- Vehicle registration, search, update, and delete
- Vehicle registration, owner-name, and phone validation
- Parking slot creation, listing, update, and delete
- Vehicle check-in and check-out
- Parking fee calculation at ₹30 per started hour (minimum one hour)
- Booking creation with overlapping-time validation
- Parking session history
- CSV export from the reports screen
- Light/dark theme toggle
- Interactive Swagger API documentation

## Project structure

```text
ParkWise/
├── app/
│   ├── __init__.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── docs/
│   └── PROJECT_REQUIREMENTS.md
├── frontend/
│   ├── app.js
│   ├── index.html
│   └── styles.css
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Run on Windows

Open the project folder in VS Code terminal.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open the dashboard at http://127.0.0.1:8000.

API documentation: http://127.0.0.1:8000/docs

Health check: http://127.0.0.1:8000/api/health

## Deploy on Railway

This project includes a `Procfile` for Railway. Push the project to GitHub,
create a Railway project from that repository, add a PostgreSQL service, and
make the PostgreSQL connection URL available to the web service as
`DATABASE_URL`. Railway commonly supplies a `postgresql://` URL; the app
normalizes it to the installed Psycopg 3 driver automatically. Deploy the
web service and open its generated public domain. No local database file or
sample records need to be uploaded.

## Database

SQLite is the default database. The file `parkwise.db` is created automatically when the application starts. It starts with empty tables.

To use PostgreSQL:

1. Create a database named `parkwise`.
2. Set the `DATABASE_URL` environment variable in your terminal before starting Uvicorn:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/parkwise"
uvicorn app.main:app --reload
```

Do not commit database passwords or `.env` files to GitHub.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | API health |
| GET | `/api/dashboard` | Database dashboard metrics |
| GET, POST | `/api/vehicles` | List and register vehicles |
| PATCH, DELETE | `/api/vehicles/{id}` | Update or delete a vehicle |
| GET, POST | `/api/slots` | List and create parking slots |
| PATCH, DELETE | `/api/slots/{id}` | Update or delete a slot |
| POST | `/api/check-in` | Start a parking session |
| POST | `/api/check-out/{session_id}` | Complete a parking session |
| GET | `/api/sessions` | Parking history |
| GET, POST | `/api/bookings` | List and create bookings |

## Validation rules

- Registration numbers must contain both letters and digits.
- Owner/customer names accept letters, spaces, apostrophes, dots, and hyphens.
- Indian mobile numbers must be ten digits and start from 6–9.
- Slot codes must look like `A12` or `B-04`.
- Duplicate registration numbers and slot codes are rejected.
- A vehicle cannot have two active parking sessions.
- An occupied slot cannot be deleted.
- Vehicle and slot records with transaction history cannot be deleted, preserving historical records.

## Current limitations

- Authentication and role-based authorization are not implemented yet.
- Booking cancellation and payment gateway integration are not implemented.
- The parking rate is currently fixed at ₹30 per started hour.
- This starter build does not yet include all assigned TQM quality-goal features.
- For production use, add database migrations, automated tests, audit logging, secure authentication, and deployment configuration.

## BBAT104 TQM alignment

The course guideline maps Parking Management System to the goal of minimizing entry queues and maximizing space utilization for students whose roll number ends in 8. The individual Quality Goal (Q01–Q20) and its five selected features must be confirmed from the student's roll-number sequence.

## Existing database note

This version does not seed sample data. If you are upgrading from an earlier
ParkWise build, keep a backup of `parkwise.db` before using the new code.
The session model now permits multiple historical sessions to reference the
same slot over time. Existing SQLite tables are not automatically migrated by
SQLAlchemy `create_all`; a proper migration should be applied before reusing
an older database schema. Do not delete your database unless you intentionally
want to remove all saved records.
