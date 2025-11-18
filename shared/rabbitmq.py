import aio_pika
import json
from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict

class Event(BaseModel):
    id: str
    payload: Dict[str, Any]
    created_at: datetime
    processed: bool = False



RABBITMQ_HOST = "rabbitmq"
connection: aio_pika.Connection | None = None
channel: aio_pika.Channel | None = None

async def initialize_rabbitmq_connection():
    global connection, channel
    if connection is None or connection.is_closed:
        print("Connecting to RabbitMQ...")
        connection = await aio_pika.connect_robust(f"amqp://guest:guest@{RABBITMQ_HOST}/",)
        channel = await connection.channel()
        # Встановіть обмін (Exchange) при ініціалізації, а не при кожній публікації
        await channel.declare_exchange("notifications_exchange", aio_pika.ExchangeType.DIRECT, durable=True)
        print("RabbitMQ Channel ready.")


async def publish_notification_async(event:Event ):    
    # connection = await aio_pika.connect_robust(
    #     f"amqp://guest:guest@{RABBITMQ_HOST}/",
    # )
    
    # async with connection:
    #     channel = await connection.channel()
        
    if channel is None or channel.is_closed:
        # Спроба повторної ініціалізації, якщо канал не готовий
        await initialize_rabbitmq_connection() 
    
    if channel is None:
        # Якщо після спроби ініціалізації канал все ще None, кидаємо виняток
        # Це змусить outbox_worker зловити його і спробувати пізніше.
        raise Exception("RabbitMQ channel is not available.")
    
    # Створюємо чергу (якщо її ще нема) і робимо її стійкою
    # await channel.declare_queue('notifications', durable=True)
    
    message_body = json.dumps(event.payload).encode('utf-8')

    message = aio_pika.Message(
        message_body,
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT, # Зробити повідомлення стійким
        headers={"message_id": event.id}
    )
    
    exchange = await channel.get_exchange("notifications_exchange")
    await exchange.publish(
        message,
        routing_key='notifications',
    )
    
    # З'єднання закривається автоматично після виходу з async with connection:
    print(f"Sent notification event to RabbitMQ: {event.payload}") 
