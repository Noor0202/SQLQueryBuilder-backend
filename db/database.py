# backend\db\database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException  # Import this to handle 401s gracefully

from settings import settings
from logger import logger

# --- DATABASE ENGINE SETUP ---
try:
    if not settings.DATABASE_URL:
        raise ValueError("DATABASE_URL is not configured.")

    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )
    logger.info("Database engine created successfully.")

except Exception as e:
    logger.exception("Failed to create database engine.")
    raise

# --- SESSION FACTORY ---
try:
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    logger.info("Session factory initialized.")

except Exception:
    logger.exception("Failed to initialize session factory.")
    raise

Base = declarative_base()

# --- FASTAPI DB DEPENDENCY ---
def get_db():
    db = SessionLocal()
    try:
        yield db

    except SQLAlchemyError as db_error:
        # Genuine DB errors (connection lost, constraint failed)
        logger.exception("Database session error occurred.")
        db.rollback()
        raise db_error

    except HTTPException:
        # FIX: If we raise 401 Unauthorized, do NOT log it as a DB error.
        # Just let it bubble up to the frontend.
        raise

    except Exception:
        # Unexpected Python errors (code bugs)
        logger.exception("Unexpected database error.")
        db.rollback()
        raise

    finally:
        db.close()
        # logger.debug("Database session closed.") # Commented out to reduce noise