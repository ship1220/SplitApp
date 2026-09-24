"""Vercel entrypoint for the FastAPI application and static frontend."""

from pathlib import Path

from fastapi.staticfiles import StaticFiles

from backend.app.main import app


# Keep API routes registered before the catch-all static mount.
frontend_dir = Path(__file__).parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
