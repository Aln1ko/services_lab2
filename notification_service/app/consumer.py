import json
from app.database import create_notification
from app.api.models import NotificationType
import logging
import asyncio
import aio_pika

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_HOST = "rabbitmq"  # або "localhost" якщо без Docker Compose

# def wait_for_rabbitmq(max_retries=30, retry_interval=5):
#     """Чекаємо поки RabbitMQ стане доступним"""
#     logger.info("🔄 Waiting for RabbitMQ...")
#     for attempt in range(max_retries):
#         try:
#             connection = pika.BlockingConnection(
#                 pika.ConnectionParameters(host=RABBITMQ_HOST)
#             )
#             connection.close()
#             logger.info("✅ RabbitMQ is ready!")
#             print("RabbitMQ is ready!")
#             return True
#         except Exception as e:
#             logger.warning(f"❌ RabbitMQ not ready (attempt {attempt + 1}/{max_retries}): {e}")
#             print(f"RabbitMQ not ready (attempt {attempt + 1}/{max_retries}): {e}")
#             if attempt < max_retries - 1:
#                 time.sleep(retry_interval)
#     logger.error("❌ Failed to connect to RabbitMQ after multiple attempts")
#     return False

# def callback(ch, method, properties, body):
#     """Обробка отриманого повідомлення"""
#     data = json.loads(body.decode("utf-8"))
#     logger.info(f"📨 Received notification: {data}")
#     print(f"Received notification: {data}")

#     try:
#         user_id = data["user_id"]
#         notification_type = NotificationType(data["notification_type"])
#         subject = data["subject"]
#         message = data["message"]
#         metadata = data.get("metadata", {})

#         notification = create_notification(
#             user_id=user_id,
#             notification_type=notification_type,
#             subject=subject,
#             message=message,
#             metadata=metadata
#         )
#         logger.info(f"💾 Notification stored: {notification['id']}")
#         print(f"Notification stored: {notification['id']}")
#     except Exception as e:
#         logger.error(f"❌ Failed to process message: {e}")
#         print(f"Failed to process message: {e}")

# def start_consumer():
#     logger.info("🚀 Starting RabbitMQ consumer...")
#     if not wait_for_rabbitmq():
#         logger.error("❌ Cannot start consumer - RabbitMQ unavailable")
#         print("Failed to connect to RabbitMQ after multiple attempts")
#         return
    
#     connection = pika.BlockingConnection(
#         pika.ConnectionParameters(host=RABBITMQ_HOST)
#     )
#     channel = connection.channel()

#     # Створюємо чергу (якщо її ще нема)
#     channel.queue_declare(queue="notifications")

#     logger.info("✅ Queue 'notifications' declared")
#     print("[*] Waiting for messages. To exit press CTRL+C")

#     logger.info("🔄 Waiting for messages...")

#     # Підписка на чергу
#     channel.basic_consume(
#         queue="notifications",
#         on_message_callback=callback,
#         auto_ack=True
#     )

#     logger.info("✅ Consumer started successfully")
    
#     channel.start_consuming()

async def process_message(message: aio_pika.IncomingMessage):
    """Асинхронна обробка отриманого повідомлення."""
    async with message.process(requeue=True): # автоматично відправляє ACK, або NACK при помилці
        try:
            data = json.loads(message.body.decode("utf-8"))
            logger.info(f"Received notification: {data}")

            user_id = data["user_id"]
            # Переконайтеся, що NotificationType доступний
            notification_type = NotificationType(data["notification_type"]) 
            subject = data["subject"]
            message_content = data["message"]
            metadata = data.get("metadata", {})

            notification = await asyncio.to_thread(
                create_notification,
                user_id=user_id,
                notification_type=notification_type,
                subject=subject,
                message=message_content,
                metadata=metadata
            )
            
            logger.info(f"Notification stored: {notification['id']}")

        except Exception as e:
            logger.error(f"Failed to process message, putting back in queue: {e}")
            # Оскільки ми використовуємо `message.process(requeue=True)`,
            # помилка автоматично призведе до NACK та повернення в чергу

async def start_consumer():
    """Асинхронний запуск конс'юмера."""
    try:
        connection = await aio_pika.connect_robust(
            f"amqp://guest:guest@{RABBITMQ_HOST}/", # використовуйте URL
            client_properties={"connection_name": "notification_consumer"}
        )
        logger.info("✅ Connected to RabbitMQ.")

        channel = await connection.channel()
        
        # Оголошення черги (durable=True для стійкості)
        queue = await channel.declare_queue(
            'notifications',
            durable=True
        )
        logger.info(f"✅ Queue '{'notifications'}' declared.")
        
        # Запуск конс'юмера
        await queue.consume(process_message)
        logger.info("✅ Consumer started successfully. Waiting for messages.")

    except aio_pika.exceptions.AMQPConnectionError as e:
        # RobustConnect буде намагатися перепідключитися
        logger.error(f"❌ Initial RabbitMQ connection failed: {e}")
        return

    except Exception as e:
        logger.error(f"❌ An error occurred during consumer setup: {e}")
        return

    # Запускаємо безкінечний цикл, щоб тримати з'єднання відкритим
    await asyncio.Future()