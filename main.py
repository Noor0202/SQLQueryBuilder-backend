# backend/main.py
import os
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from settings import settings
from logger import logger
from db.database import engine, Base

# --- ROUTER IMPORTS ---
try:
    from routes import connections
except ImportError:
    connections = None

try:
    from auth.routes import router as auth_router  # type: ignore
except Exception:
    auth_router = None

app = FastAPI(title="SQL Query Builder API", version="1.0.0")

# -------------------------
# STRICT CORS CONFIGURATION
# -------------------------
# Uses the ALLOWED_ORIGINS string from settings.py (or .env file)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

if connections:
    app.include_router(connections.router)

# -------------------------
# Startup / Shutdown hooks
# -------------------------
@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)
    logger.info("Application startup complete. Database tables verified/created.")

@app.on_event("shutdown")
async def on_shutdown():
    try:
        from db.database import dispose_engine
        dispose_engine()
    except Exception:
        pass

# -------------------------
# Run 
# -------------------------
if __name__ == "__main__":
    # Hardcoded to strictly run on port 8000 locally
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)