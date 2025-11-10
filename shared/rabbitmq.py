import aio_pika
import json

RABBITMQ_HOST = "rabbitmq"

# def publish_notification(user_id: str, notification_type: str, subject: str, message: str):
#     """Відправка повідомлення у чергу RabbitMQ"""
#     connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
#     channel = connection.channel()

#     # гарантуємо, що черга існує
#     channel.queue_declare(queue="notifications")

#     payload = {
#         "user_id": user_id,
#         "notification_type": notification_type,
#         "subject": subject,
#         "message": message,
#     }

#     channel.basic_publish(
#         exchange="",
#         routing_key="notifications",
#         body=json.dumps(payload),
#         properties=pika.BasicProperties(
#             delivery_mode=2,  # зробити повідомлення persistent
#         )
#     )

#     print(f"Sent notification event to RabbitMQ: {payload}")
#     connection.close()


async def publish_notification_async(user_id: str, notification_type: str, subject: str, message: str):
    payload = {
    "user_id": user_id,
    "notification_type": notification_type,
    "subject": subject,
    "message": message,
    }

    connection = await aio_pika.connect_robust(
        f"amqp://guest:guest@{RABBITMQ_HOST}/",
    )
    
    async with connection:
        channel = await connection.channel()
        
        # Створюємо чергу (якщо її ще нема) і робимо її стійкою
        await channel.declare_queue('notifications', durable=True)
        
        message_body = json.dumps(payload).encode()

        message = aio_pika.Message(
            message_body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT # Зробити повідомлення стійким
        )
        
        await channel.default_exchange.publish(
            message,
            routing_key='notifications',
        )
        
        # З'єднання закривається автоматично після виходу з async with connection:
        print(f"Sent notification event to RabbitMQ: {payload}") 
