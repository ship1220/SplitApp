import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import trips, expenses, auth, me

app = FastAPI(title="Split API", version="1.0.0")

# In local development, allow the frontend to call the API from any
# localhost/static-server origin. In production, set FRONTEND_URL to the
# exact deployed frontend origin, e.g. https://splitclone.onrender.com.
frontend_url = os.getenv("FRONTEND_URL")

allowed_origins = (
    [frontend_url]
    if frontend_url
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trips.router)
app.include_router(expenses.router)
app.include_router(auth.router)
app.include_router(me.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
