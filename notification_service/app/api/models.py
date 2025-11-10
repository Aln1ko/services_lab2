from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import Optional

class NotificationType(str, Enum):
    # Auth-related
    WELCOME = "welcome"
    PASSWORD_CHANGED = "password_changed"
    ACCOUNT_DELETED = "account_deleted"
    
    # Subscription-related  
    SUBSCRIPTION_CONFIRMED = "subscription_confirmed"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    SUBSCRIPTION_CANCELED = "subscription_canceled"
    TRIAL_ACTIVATED = "trial_activated"
    
    # Board-related
    BOARD_DELETED = "board_deleted"
    BOARD_ARCHIVED = "board_archived"
    BOARD_RESTORED = "board_restored"
    INVITATION_SENT = "invitation_sent"
    USER_JOINED = "user_joined"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_REMOVED = "user_removed"
    
    # Task-related
    TASK_MOVED = "task_moved"
    TASK_UPDATED = "task_updated"
    DEADLINE_SET = "deadline_set"
    COMMENT_ADDED = "comment_added"
    TASK_ASSIGNED = "task_assigned"
    TASK_DELETED = "task_deleted"
    TASK_ARCHIVED = "task_archived"
    TASK_RESTORED = "task_restored"

class NotificationRequest(BaseModel):
    user_id: str  # Отримувач повідомлення
    notification_type: NotificationType
    subject: str  # Тема повідомлення
    message: str  # Текст повідомлення
    metadata: Optional[dict] = None  # Додаткові дані (task_id, board_id, etc.)

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    notification_type: NotificationType
    subject: str
    message: str
    metadata: Optional[dict]
    sent_at: datetime
    status: str  # "sent", "failed"