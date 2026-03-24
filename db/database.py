# backend/db/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

# IMPORT FIX: Use the single-source-of-truth config alias
from config import settings
from logger import logger

# --- DATABASE ENGINE SETUP ---
# Initialize variables as None to ensure they exist even if setup fails
engine = None
SessionLocal = None
Base = declarative_base()

try:
    # database_url safely handles fallbacks as defined in settings.py
    db_url = settings.database_url
    
    engine = create_engine(
        db_url,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        future=True,
    )
    # Log the dialect (e.g., postgresql or sqlite) without exposing credentials
    dialect = db_url.split(":")[0]
    logger.info(f"Database engine created successfully using '{dialect}' backend.")

except Exception as e:
    # CRITICAL FIX: Never terminate. Log the error and create a fallback engine.
    logger.error(f"Failed to create primary database engine: {str(e)}")
    try:
        engine = create_engine(
            "sqlite:///./fallback.db",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )
        logger.warning("Emergency fallback SQLite database engine created to keep application alive.")
    except Exception as fallback_error:
        logger.error(f"Critical failure creating fallback database engine: {str(fallback_error)}")

# --- SESSION FACTORY ---
try:
    if engine:
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
        logger.info("Session factory initialized successfully.")
    else:
        logger.error("Session factory skipped because no valid engine exists.")
except Exception as e:
    logger.error(f"Failed to initialize session factory: {str(e)}")


# --- FASTAPI DB DEPENDENCY ---
def get_db():
    """
    Dependency to yield a database session per request.
    Ensures safe rollbacks and clean closures on completion or failure.
    """
    if not SessionLocal:
        logger.error("Database session requested, but SessionLocal is not initialized.")
        raise HTTPException(status_code=500, detail="Database connection is currently unavailable.")

    db = SessionLocal()
    try:
        yield db

    except SQLAlchemyError as db_error:
        # Genuine DB errors (connection lost, constraint failed)
        logger.error(f"Database session error occurred: {str(db_error)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="A database operation failed.")

    except HTTPException:
        # If we explicitly raise an HTTP exception (like 401 Unauthorized, 404 Not Found),
        # do NOT log it as a DB error. Just let it bubble up to the frontend.
        raise

    except Exception as e:
        # Unexpected Python errors (code bugs)
        logger.error(f"Unexpected error during database operation: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error during database operation.")

    finally:
        try:
            db.close()
        except Exception as close_error:
            logger.error(f"Failed to cleanly close database session: {str(close_error)}")


def dispose_engine():
    """Helper to safely dispose the engine on application shutdown."""
    try:
        if engine:
            engine.dispose()
            logger.info("Database engine disposed cleanly.")
    except Exception as e:
        logger.error(f"Error disposing database engine: {str(e)}")