# backend/schemas.py
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

# --- AUTH SCHEMAS (Keep existing) ---
class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    class Config:
        from_attributes = True

# --- NEW CONNECTION SCHEMAS ---
class DBConnectionBase(BaseModel):
    name: str
    host: str
    port: str = "5432"
    db_name: str
    username: str
    ssl_mode: str = "prefer"

class DBConnectionCreate(DBConnectionBase):
    password: str  # Input only, never returned

class DBConnectionResponse(DBConnectionBase):
    id: int
    created_at: datetime
    # Note: password is intentionally excluded here
    class Config:
        from_attributes = True

class QueryRequest(BaseModel):
    sql: str
    page: int = 1
    limit: int = 100