from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import List, Optional

class TaskStatus(str, Enum):
    TODO = "todo"
    DOING = "doing" 
    DONE = "done"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskCreate(BaseModel):
    title: str
    description: str
    board_id: str
    created_by: str  # ID користувача, який створив завдання

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None

class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    board_id: str
    status: TaskStatus
    priority: TaskPriority
    assignee_id: Optional[str]
    created_by: str
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class CommentCreate(BaseModel):
    task_id: str
    user_id: str
    text: str

class CommentResponse(BaseModel):
    id: str
    task_id: str
    user_id: str
    text: str
    created_at: datetime

class AssignRequest(BaseModel):
    task_id: str
    admin_user_id: str  # Адмін, який призначає
    assignee_id: str    # Користувач, якому призначають