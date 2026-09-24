import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

# Local development falls back to SQLite. Vercel Functions have an ephemeral
# filesystem, so require a managed database instead of silently losing data.
database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
if os.getenv("VERCEL") and not database_url:
    raise RuntimeError("DATABASE_URL must point to a persistent database on Vercel")

DATABASE_URL = database_url or "sqlite:///./split.db"
# Some managed database providers publish the legacy postgres:// scheme.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
connect_args = (
    {"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {}
)

engine_options = {
    "connect_args": connect_args,
    "pool_pre_ping": True,
}
if os.getenv("VERCEL"):
    # Supabase's transaction pooler is designed for serverless functions;
    # avoid retaining client-side connections across function invocations.
    engine_options["poolclass"] = NullPool

engine = create_engine(DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
