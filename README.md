# split — expense splitter

A fullstack "who owes whom" trip expense tracker: FastAPI + SQLAlchemy (Postgres-ready)
backend, plain HTML/CSS/JS frontend. No login — trips are accessed via share links
(an edit link and a view-only link).

## Structure

```
splitclone/
  backend/
    app/
      main.py            FastAPI app, CORS, table creation (fresh-DB fallback only)
      database.py         SQLAlchemy engine/session (Postgres or SQLite)
      models.py            Trip, Member, Expense, ExpenseShare
      schemas.py           Pydantic request/response models
      crud.py               DB operations
      utils/settlement.py  Split math + greedy debt-simplification algorithm
      routers/
        trips.py            create/get trip, add member
        expenses.py         add/delete expense
    alembic/                schema migrations (0001 baseline, 0002 balance cache + idempotency)
    tests/
      test_settlement.py    unit tests for split math
      test_api.py            FastAPI TestClient integration tests
    requirements.txt
  frontend/
    index.html              create-trip landing page
    trip.html                Activity / People / Settle tabs
    css/style.css
    js/
      api.js                fetch wrapper
      app.js                landing page logic
      trip.js                 trip page logic
  .github/workflows/test.yml  CI: install + pytest on push
```

## How it works

- **Create a trip** → get back an `edit_token` (full access) and a `view_token`
  (read-only). Both resolve to the same trip via `GET /api/trips/{token}`.
- **Add an expense** with a split type:
  - `equal` — split evenly among selected participants
  - `percentage` — must add up to 100
  - `exact` — must add up to the total amount
- **Balances** (People tab): for each member, `net = total_paid - total_share`.
  Positive = owed money back, negative = owes money.
- **Settle tab**: the minimum-transaction greedy algorithm — sort debtors
  (most negative first) and creditors (most positive first), repeatedly
  settle `min(|debtor|, creditor)` between the two largest, advance
  whichever side hits zero. This is the same approach used in the reference
  app's "Simplified Transfers" screen.

## Run it locally

### 1. Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt

# Uses SQLite by default (./split.db). To use Postgres instead:
# export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/splitdb"

# Apply the schema (see "Migrations" below) before starting the server.
alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

The API is now at `http://127.0.0.1:8000`. Interactive docs at `/docs`.

### 2. Frontend

The frontend is static — no build step. Serve it with any static server:

```bash
cd frontend
python3 -m http.server 5500
```

Open `http://127.0.0.1:5500/index.html`. It talks to the backend at
`http://127.0.0.1:8000` by default. To point it elsewhere (e.g. a deployed
API), set this before the other scripts load, in `trip.html` / `index.html`:

```html
<script>window.SPLIT_API_BASE = "https://your-api.example.com";</script>
<script src="js/api.js"></script>
```

## Migrations

Schema changes go through [Alembic](https://alembic.sqlalchemy.org/), in
`backend/alembic/`. It reads the same `DATABASE_URL` the app uses (falling
back to the local `split.db`), so no separate config is needed.

```bash
cd backend
alembic upgrade head        # apply all migrations
alembic downgrade -1        # roll back one step
alembic revision -m "..."   # start a new migration
```

`main.py` only falls back to `Base.metadata.create_all()` when the database
has zero tables (i.e. a brand-new, empty `split.db` on first run) — it never
touches a database that already has tables, so running the app doesn't fight
with migration state. Once you've run `alembic upgrade head` at least once,
that fallback path is never triggered again.

## Tests

```bash
cd backend
pip install -r requirements.txt   # includes pytest + httpx
pytest -q
```

- `tests/test_settlement.py` — unit tests for the pure split math
  (`resolve_shares`, `simplify_transfers`): equal/percentage/exact splits,
  rounding edge cases, invalid totals, lopsided debtor/creditor counts.
- `tests/test_api.py` — FastAPI `TestClient` integration tests against a
  throwaway SQLite file per test: create trip → add expense → balances are
  correct, view-token gets `403` on write endpoints, and a repeated
  `Idempotency-Key` returns the original expense instead of duplicating it.

CI (`.github/workflows/test.yml`) runs this same suite on every push.

## Deploying

- **Backend**: any host that runs Python (Render, Railway, Fly.io, a VPS).
  Point `DATABASE_URL` at a real Postgres instance, run `alembic upgrade
  head` as part of your deploy step, set `JWT_SECRET` to a long random value,
  and set `FRONTEND_URL` to the exact deployed frontend origin.
- **Frontend**: any static host (Vercel, Netlify, GitHub Pages, S3). Set
  `window.SPLIT_API_BASE` to your deployed backend URL before loading
  `frontend/js/api.js`.
- **Render**: this repository includes `render.yaml` for a simple
  backend + frontend + PostgreSQL deployment.

## Notes / things to harden before real use

- There's no auth — anyone with an edit link can add/delete expenses.
  That mirrors the reference app's model (link-based access), but if you
  want real accounts you'd add a users table + JWT and scope trips to owners.
- Rounding: split math rounds to paise (2 decimals) and dumps any leftover
  fraction onto the last participant so shares always sum exactly to the
  expense total.
- `Member.net_balance` is maintained on every expense write rather than
  recomputed on every read — if you ever need to rebuild it from scratch
  (e.g. after a manual DB edit), sum `paid - share` per member from the
  `expenses`/`expense_shares` tables, the same way migration `0002` backfills it.
