# ParkWise — Project Requirements

## 1. Objective

Develop a parking management system that minimizes entry queues and maximizes parking-space utilization.

## 2. Core users

- Administrator / parking operator
- Vehicle owner / customer

## 3. Functional requirements

1. Register, view, update, search, and delete vehicle records.
2. Create, view, update, and delete parking slots where no transaction history prevents deletion.
3. Prevent duplicate vehicle registration numbers and slot codes.
4. Prevent check-in when a parking slot is unavailable.
5. Prevent multiple active parking sessions for the same vehicle.
6. Record vehicle check-in time and slot allocation.
7. Calculate parking fees and release a slot at checkout.
8. Reserve a parking slot for a specified time interval.
9. Reject overlapping confirmed bookings for the same slot.
10. Display facility capacity, occupied slots, available slots, vehicle count, and revenue.
11. Display session history and export report data as CSV.

## 4. Non-functional requirements

- Responsive and minimal user interface.
- Modular FastAPI backend.
- Relational database persistence using SQLAlchemy.
- Backend-side input validation and useful error messages.
- API documentation through OpenAPI / Swagger UI.
- No fabricated demo records inserted automatically.

## 5. TQM alignment

The BBAT104 guideline maps the Parking Management System to minimizing entry queues and maximizing space utilization. The student's individually assigned Quality Goal (Q01–Q20) and five selected features must be confirmed before finalizing the TQM enhancement scope.
