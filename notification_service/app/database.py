from datetime import datetime
import uuid
from shared.unique_id import generate_unique_id

# Тимчасова база даних в пам'яті
notifications_db = []

def create_notification(user_id: str, notification_type: str, subject: str, message: str, metadata: dict = None):
    notification_id = generate_unique_id(notifications_db)
    
    notification = {
        "id": notification_id,
        "user_id": user_id,
        "notification_type": notification_type,
        "subject": subject,
        "message": message,
        "metadata": metadata or {},
        "sent_at": datetime.now(),
        "status": "sent"  # В реальному додатку буде "pending", "sent", "failed"
    }
    
    notifications_db.append(notification)
    return notification

def get_user_notifications(user_id: str):
    return [n for n in notifications_db if n["user_id"] == user_id]

def get_notifications_by_type(notification_type: str):
    return [n for n in notifications_db if n["notification_type"] == notification_type]