import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import trips, expenses, auth, me
from .rate_limit import RateLimiter

app = FastAPI(title="Split API", version="1.0.0")
app.state.rate_limiter = RateLimiter()

# In local development, allow the frontend to call the API from any
# localhost/static-server origin. In production, set FRONTEND_URL to the
# exact deployed frontend origin, e.g. https://splitclone.onrender.com.
frontend_url = os.getenv("FRONTEND_URL")

allowed_origins = (
    [frontend_url]
    if frontend_url
    else ["*"]
)

@app.middleware("http")
async def enforce_rate_limit(request: Request, call_next):
    # Health checks and browser CORS preflights should never consume a budget.
    if request.url.path == "/api/health" or request.method == "OPTIONS":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    allowed, limit, retry_after = await app.state.rate_limiter.check(
        client_ip, request.method, request.url.path
    )
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again shortly."},
            headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(limit)},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limit)
    return response


# Register CORS last so rate-limit errors also retain the browser's CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-RateLimit-Limit"],
)

app.include_router(trips.router)
app.include_router(expenses.router)
app.include_router(auth.router)
app.include_router(me.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
