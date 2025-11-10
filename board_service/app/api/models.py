from pydantic import BaseModel,EmailStr
from datetime import datetime
from enum import Enum
from typing import List, Optional

class BoardStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    UNPACKED = "unpacked"

class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"


class BoardCreate(BaseModel):
    name: str
    admin_user_id: str

class BoardUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[BoardStatus] = None

class Board(BaseModel):
    id: str
    name: str
    admin_user_id: str
    users: List[str]  
    status: BoardStatus
    created_at: datetime
    updated_at: datetime



class UserInviteRequest(BaseModel):
    board_id: str
    admin_user_id: str  # ID адміністратора, який запрошує
    invited_user_id: str  # ID запрошеного користувача

class UserJoinRequest(BaseModel):
    board_id: str
    user_id: str  # ID користувача, який приєднується

class UserRoleUpdate(BaseModel):
    board_id: str
    admin_user_id: str  # ID адміністратора, який змінює роль
    target_user_id: str  # ID користувача, якому змінюють роль
    new_role: UserRole

class UserRemoveRequest(BaseModel):
    board_id: str
    admin_user_id: str  # ID адміністратора, який видаляє
    target_user_id: str  # ID користувача, якого видаляють

class BoardUserResponse(BaseModel):
    user_id: str
    role: UserRole
    joined_at: datetime