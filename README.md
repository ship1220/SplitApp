# SplitApp

A full-stack expense-splitting application for managing shared trip expenses, calculating balances, and simplifying settlements.

# Demo
splitapp-sigma.vercel.app

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
## Deploy on Vercel

The repository is configured to deploy from its root directory. Vercel runs the FastAPI application as a Python Function and serves the existing frontend from the same domain. The frontend sends API requests to `/api`, so no separate backend URL or CORS setup is needed.

### Persistent database

Vercel Functions have temporary filesystems. Do not use the default local SQLite database in a Vercel deployment. Create a managed PostgreSQL database (for example, Neon or Supabase), and use its PostgreSQL connection string as the Vercel `DATABASE_URL` environment variable. Prefer the provider's pooled connection string if it offers one. Also set `JWT_SECRET` to a long random secret. Add both variables to Production and Preview as needed.

If the current Render database contains trips or accounts you need, copy that data into the new PostgreSQL database before switching users to Vercel. Point `DATABASE_URL` at the destination and run the migrations from the `backend` directory before deploying:

```powershell
cd backend
$env:DATABASE_URL = "<your PostgreSQL connection string>"
alembic upgrade head
```

Apply migrations with the same connection string in future releases when a new Alembic migration is added. The Vercel build does not run database migrations automatically.

### Deploy steps

1. Import this repository into Vercel and keep the project root directory at the repository root (the folder containing `vercel.json`).
2. Add `DATABASE_URL` and `JWT_SECRET` under the Vercel project's environment variables.
3. Deploy. Open `/api/health` on the resulting domain; it should return `{"status":"ok"}`.

The current Render deployment can stay online during setup. Once the Vercel deployment and its database have been populated and checked, update your public link to the Vercel domain.
