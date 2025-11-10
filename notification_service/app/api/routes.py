from fastapi import APIRouter, HTTPException
from datetime import datetime
import requests

from app.api.models import NotificationRequest, NotificationResponse, NotificationType
from app.database import notifications_db, create_notification, get_user_notifications
# import pika
import json

router = APIRouter()

@router.get("/notifications/user/{user_id}", response_model=list[NotificationResponse])
async def get_user_notifications_endpoint(user_id: str):
    notifications = get_user_notifications(user_id)
    return [NotificationResponse(**notification) for notification in notifications]

@router.get("/notifications/types/{notification_type}", response_model=list[NotificationResponse])
async def get_notifications_by_type_endpoint(notification_type: str):
    notifications = [n for n in notifications_db if n["notification_type"] == notification_type]
    return [NotificationResponse(**notification) for notification in notifications]

# def publish_to_queue(notification_data: NotificationRequest):
#     connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
#     channel = connection.channel()
    
#     channel.queue_declare(queue='notifications')  # создаем очередь (если нет)
    
#     message = notification_data.dict()
#     channel.basic_publish(
#         exchange='',
#         routing_key='notifications',
#         body=json.dumps(message)
#     )
    
#     connection.close()

# @router.post("/notifications/send")
# async def send_notification(notification_data: NotificationRequest):
#     publish_to_queue(notification_data)
#     return {"status": "queued", "notification_type": notification_data.notification_type}

@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notitications():
    return notifications_db