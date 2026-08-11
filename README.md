# SplitApp

A full-stack expense-splitting application for managing shared trip expenses, calculating balances, and simplifying settlements.

# Demo
https://splitapp-frontend-82ku.onrender.com

## Features

- User signup and JWT-based authentication
- Create and manage trips
- Add trip members
- Add expenses with:
  - Equal split
  - Percentage split
  - Exact amount split
- Automatic balance calculation
- Simplified settlement suggestions
- View-only trip access
- Idempotent expense creation
- PostgreSQL database with Alembic migrations
- REST API built with FastAPI

## Tech Stack

**Frontend**
- HTML
- CSS
- JavaScript

**Backend**
- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- JWT Authentication

**Testing**
- Pytest
- FastAPI TestClient

## Project Structure

```text
SplitApp/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   └── utils/
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── my-trips.html
│   ├── trip.html
│   ├── css/
│   └── js/
│
└── render.yaml
