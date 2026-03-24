import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from logger import logger

# --- SAFE IMPORTS ---
try:
    from db.database import engine, Base
except Exception as e:
    logger.error(f"Failed to import database modules: {e}")
    engine, Base = None, None

try:
    from routes import connections
except Exception as e:
    logger.warning(f"Failed to import connections router: {e}")
    connections = None

try:
    from auth.routes import router as auth_router  # type: ignore
except Exception as e:
    logger.warning(f"Failed to import auth router: {e}")
    auth_router = None

app = FastAPI(title="SQL Query Builder API", version="1.0.0")

# -------------------------
# GLOBAL EXCEPTION HANDLER
# -------------------------
# Prevents the app from terminating under any unhandled endpoint condition
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "An internal server error occurred.", "details": str(exc)}
    )

# -------------------------
# STRICT CORS CONFIGURATION
# -------------------------
try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
except Exception as e:
    logger.error(f"Failed to configure CORS middleware: {e}")

# -------------------------
# Health & Root
# -------------------------
@app.get("/", include_in_schema=False)
def root():
    try:
        return {"status": "running", "docs_url": "/docs"}
    except Exception as e:
        logger.error(f"Error serving root endpoint: {e}")
        return {"status": "error"}

@app.get("/health")
def health():
    try:
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error serving health endpoint: {e}")
        return {"status": "error"}

# -------------------------
# Mount routers
# -------------------------
if auth_router:
    try:
        app.include_router(auth_router)
    except Exception as e:
        logger.error(f"Failed to mount auth_router: {e}")

if connections:
    try:
        app.include_router(connections.router)
    except Exception as e:
        logger.error(f"Failed to mount connections router: {e}")

# -------------------------
# Startup / Shutdown hooks
# -------------------------
@app.on_event("startup")
async def on_startup():
    try:
        if Base and engine:
            Base.metadata.create_all(bind=engine)
            logger.info("Application startup complete. Database tables verified/created.")
        else:
            logger.warning("Application startup complete, but database modules were missing.")
    except Exception as e:
        logger.error(f"Error during application startup: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    try:
        from db.database import dispose_engine
        dispose_engine()
        logger.info("Database engine disposed.")
    except Exception as e:
        logger.error(f"Error during application shutdown: {e}")

# -------------------------
# Run 
# -------------------------
if __name__ == "__main__":
    try:
        logger.info(f"Starting uvicorn server on {settings.APP_HOST}:{settings.APP_PORT}")
        uvicorn.run(
            "main:app", 
            host=settings.APP_HOST, 
            port=settings.APP_PORT, 
            reload=settings.APP_RELOAD
        )
    except Exception as e:
        logger.error(f"Critical error preventing uvicorn from starting: {e}")