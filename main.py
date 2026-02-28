# backend/main.py
import os
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from settings import settings
from logger import logger

# --- CRITICAL FIX IMPORTS ---
from db.database import engine, Base  # Needed to create tables
from db import models                 # Needed so Base knows about the models!

# --- ROUTER IMPORTS ---
# 1. Connections Router (New Feature)
try:
    from routes import connections
except ImportError:
    connections = None
    logger.warning("Could not import connections router.")

# 2. Auth Router
try:
    from auth.routes import router as auth_router  # type: ignore
except Exception:
    auth_router = None
    print("auth.routes import failed (auth router will not be mounted).")

logger.info(f"Starting app (env={settings.ENVIRONMENT})")

app = FastAPI(title="SQL Query Builder API", version="1.0.0")

# -------------------------
# CORS: robust origin parsing (explicit list + regex fallback)
# -------------------------
def _default_dev_origins() -> List[str]:
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

try:
    _origins = settings.cors_origins_list
except Exception:
    _origins = []

if not _origins:
    logger.warning("No ALLOWED_ORIGINS configured; falling back to common dev origins.")
    _origins = _default_dev_origins()

logger.info(f"✅ Allowed CORS Origins: {_origins}")

# Dev-friendly regex to accept localhost / 127.0.0.1 with any port
_localhost_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=_localhost_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Request logging middleware
# -------------------------
@app.middleware("http")
async def log_request_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method == "OPTIONS":
        acrm = request.headers.get("access-control-request-method")
        acrh = request.headers.get("access-control-request-headers")
        logger.info(
            f"Preflight (OPTIONS) {request.url.path} | Origin: {origin} | "
            f"AC-Request-Method: {acrm} | AC-Request-Headers: {acrh}"
        )
    else:
        logger.info(f"Incoming Request: {request.method} {request.url} | Origin: {origin}")

    response = await call_next(request)
    return response

# -------------------------
# Health & Root
# -------------------------
@app.get("/", include_in_schema=False)
def root():
    return {"status": "running", "docs_url": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}

# -------------------------
# Mount routers
# -------------------------
if auth_router:
    app.include_router(auth_router)
    logger.info("Auth router included.")

if connections:
    app.include_router(connections.router)
    logger.info("Connections router included.")

# -------------------------
# Generic preflight handler (robust fallback)
# -------------------------
@app.options("/{full_path:path}")
async def preflight_handler(request: Request, full_path: str):
    origin = request.headers.get("origin")
    acrm = request.headers.get("access-control-request-method")
    acrh = request.headers.get("access-control-request-headers", "")
    logger.info(f"OPTIONS preflight received for /{full_path} | origin={origin} | acrm={acrm} | acrh={acrh}")

    if not acrm:
        return Response(status_code=204)

    allowed_origins = _origins or _default_dev_origins()
    echo_origin = None

    if origin in allowed_origins:
        echo_origin = origin
    else:
        import re
        if origin and re.match(_localhost_regex, origin):
            echo_origin = origin
        else:
            echo_origin = allowed_origins[0]

    headers = {
        "Access-Control-Allow-Origin": echo_origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": acrh or "Authorization, Content-Type",
        "Access-Control-Allow-Credentials": "true",
    }

    return Response(status_code=204, headers=headers)

# -------------------------
# Global exception handler (optional)
# -------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception while processing request.")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# -------------------------
# Startup / Shutdown hooks
# -------------------------
@app.on_event("startup")
async def on_startup():
    # --- THIS FIXES YOUR ERROR ---
    # It checks the DB for missing tables (like db_connections) and creates them.
    Base.metadata.create_all(bind=engine)
    logger.info("Application startup complete. Database tables verified/created.")

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Application shutdown initiated.")
    try:
        from db.database import dispose_engine
        dispose_engine()
    except Exception:
        logger.exception("Error disposing engine on shutdown.")

# -------------------------
# Run (only when executed directly)
# -------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 8000)),
        reload=(settings.ENVIRONMENT == "development"),
    )