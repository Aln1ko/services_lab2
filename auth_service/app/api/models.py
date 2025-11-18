from pydantic import BaseModel,EmailStr
from datetime import datetime
from typing import Any, Dict

class User(BaseModel):
    id: str
    email:EmailStr
    password: str
    full_name: str
    created_at: datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class Event(BaseModel):
    id: str
    payload: Dict[str, Any]
    created_at: datetime
    processed: bool = False
