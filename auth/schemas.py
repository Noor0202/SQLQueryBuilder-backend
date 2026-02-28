# backend/auth/schemas.py

from pydantic import BaseModel, EmailStr, Field
from typing import Annotated

# --- VALIDATED TYPES ---
UsernameStr = Annotated[str, Field(min_length=3)]
PasswordStr = Annotated[str, Field(min_length=6)]

class UserRegister(BaseModel):
    username: UsernameStr
    email: EmailStr
    password: PasswordStr

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True