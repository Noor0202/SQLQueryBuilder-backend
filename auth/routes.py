# backend/auth/routes.py

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from db.database import get_db
from auth.schemas import UserRegister, UserLogin, UserResponse
from auth.utils import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)

# IMPORT UPDATED: Now referencing config.py instead of settings.py
from config import settings
from logger import logger

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(user: UserRegister, db: Session = Depends(get_db)):
    query_check = text("SELECT id FROM users WHERE username = :username OR email = :email")
    try:
        existing = db.execute(query_check, {"username": user.username, "email": user.email}).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username or Email already exists")
    except HTTPException:
        raise
    except Exception as e:
        # Replaced exception() with error() per log level constraints
        logger.error(f"Database check failed during registration: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error during check")

    try:
        hashed_pw = get_password_hash(user.password)
    except Exception as e:
        logger.error(f"Password hashing failed during registration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal processing error")

    query_insert = text("""
        INSERT INTO users (username, email, password_hash) 
        VALUES (:username, :email, :password_hash) 
        RETURNING id
    """)

    try:
        result = db.execute(query_insert, {
            "username": user.username,
            "email": user.email,
            "password_hash": hashed_pw
        })
        db.commit()

        new_user_id = result.scalar()
        logger.info(f"New user registered: {user.username} (ID: {new_user_id})")
        return {"message": "User created successfully", "user_id": new_user_id}

    except Exception as e:
        db.rollback()
        # Replaced exception() with error()
        logger.error(f"Registration insert error: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error during registration")


@router.post("/login")
def login(creds: UserLogin, response: Response, db: Session = Depends(get_db)):
    try:
        query = text("SELECT id, username, email, password_hash FROM users WHERE username = :username")
        user = db.execute(query, {"username": creds.username}).mappings().fetchone()

        if not user or not verify_password(creds.password, user["password_hash"]):
            logger.warning(f"Failed login attempt for username: {creds.username}")
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = create_access_token({"sub": str(user["id"]), "username": user["username"]})

        is_production = settings.ENVIRONMENT == "production"
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=is_production,
            samesite="lax" if not is_production else "strict",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        logger.info(f"User logged in: {user['username']}")
        return {"id": user["id"], "username": user["username"], "email": user["email"]}

    except HTTPException:
        raise
    except Exception as e:
        # Replaced exception() with error()
        logger.error(f"Unexpected login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/me", response_model=UserResponse)
def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except Exception as e:
        logger.error(f"Error decoding access token: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal processing error")

    if not payload:
        logger.warning("Invalid or expired token attempting to access /me")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        logger.warning("Token missing user ID payload")
        raise HTTPException(status_code=401, detail="Token missing user ID")

    try:
        query = text("SELECT id, username, email FROM users WHERE id = :uid")
        user = db.execute(query, {"uid": int(user_id)}).mappings().fetchone()

        if not user:
            logger.warning(f"User ID {user_id} parsed from token but not found in database")
            raise HTTPException(status_code=404, detail="User not found")

        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error while fetching current user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/logout")
def logout(response: Response):
    try:
        response.delete_cookie("access_token")
        logger.info("User logged out successfully")
        return {"message": "Logged out"}
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during logout")