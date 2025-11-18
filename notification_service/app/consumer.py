import json
from app.database import create_notification, inbox_db
from app.api.models import NotificationType
import logging
import asyncio
import aio_pika
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_HOST = "rabbitmq"  # або "localhost" якщо без Docker Compose

async def process_message(message: aio_pika.IncomingMessage):

    # 1. Отримання Message ID та даних
    message_id = message.headers.get("message_id")
    
    if not message_id:
        logger.error("Message received without 'message_id' header. Ignoring or dead-lettering.")
        return await message.reject(requeue=False)
    
    """Асинхронна обробка отриманого повідомлення."""
    async with message.process(requeue=False): # автоматично відправляє ACK, або NACK при помилці
        try:
            data = json.loads(message.body.decode("utf-8"))
            logger.info(f"Received event ID: {message_id}")
            logger.info(f"Received notification: {data}")

            if message_id in [entry["id"] for entry in inbox_db]:
                logger.warning(f"Message ID {message_id} already processed. Skipping (Idempotency).")
                return

            user_id = data["user_id"]
            # Переконайтеся, що NotificationType доступний
            notification_type = NotificationType(data["notification_type"]) 
            subject = data["subject"]
            message_content = data["message"]
            metadata = data.get("metadata", {})

            n = random.randint(1, 3)
            if(n%2 ==0 or n%2 ==1 ):
                logger.warning("Simulating failure in Notification Service step for SAGA.")
                # Кидаємо помилку, щоб message.process(requeue=False) відхилив повідомлення
                raise Exception("SAGA Step Failure: Notification Service deliberately failed to process.")

            notification = await asyncio.to_thread(
                create_notification,
                user_id=user_id,
                notification_type=notification_type,
                subject=subject,
                message=message_content,
                metadata=metadata
            )
            
            inbox_db.append({"id": message_id})

            logger.info(f"Notification stored: {notification['id']}")

        except Exception as e:
            # Оскільки ми використовуємо message.process(requeue=False), 
            # помилка призведе до NACK та переходу в DLQ.
            logger.error(f"SAGA STEP FAILED: Message sent to DLQ for Rollback: {e}")
            # Не потрібно явно викликати message.reject(), це зробить контекстний менеджер
            raise # Повторно кидаємо помилку, щоб контекстний менеджер спрацював

async def start_consumer():
    """Асинхронний запуск конс'юмера."""
    try:
        connection = await aio_pika.connect_robust(
            f"amqp://guest:guest@{RABBITMQ_HOST}/", # використовуйте URL
            client_properties={"connection_name": "notification_consumer"}
        )
        logger.info(" Connected to RabbitMQ.")

        channel = await connection.channel()

        try:
            await channel.queue_delete('notifications')
            await channel.queue_delete('notifications_dlq')
            logger.info("Deleted existing 'notifications' queue")
        except Exception as e:
            logger.info(f"Queue 'notifications' didn't exist or couldn't be deleted: {e}")

        # 1. Оголошення DLX (Dead Letter Exchange)
        dlx_exchange = await channel.declare_exchange(
            'saga_dlx', 
            aio_pika.ExchangeType.DIRECT, 
            durable=True)
        
        dlq = await channel.declare_queue(
                'saga_rollback',
                durable=True
            )
        
        await dlq.bind(dlx_exchange, routing_key='notifications')
        logger.info("DLQ bound to saga_dlx with routing key 'saga_rollback'")

        # Оголошення черги 
        queue = await channel.declare_queue(
            'notifications',
            durable=True,
            arguments={
            'x-dead-letter-exchange': 'saga_dlx', # Куди відправляти повідомлення після помилки/відхилення
            'x-dead-letter-routing-key': 'saga_rollback'
            }
        )

        logger.info(f" Queue '{'notifications'}' declared.")
        
        # 3. Прив'язка черги до обміну (припускаючи, що ваш outbox публікує з routing_key 'notifications')
        exchange = await channel.declare_exchange(
            'notifications_exchange', 
            aio_pika.ExchangeType.DIRECT, 
            durable=True)
        
        await queue.bind(exchange, routing_key='notifications')
        logger.info("Queue bound to exchange with routing key 'notifications'")

        # Запуск конс'юмера
        await queue.consume(process_message)
        logger.info(" Consumer started successfully. Waiting for messages.")

    except aio_pika.exceptions.AMQPConnectionError as e:
        # RobustConnect буде намагатися перепідключитися
        logger.error(f" Initial RabbitMQ connection failed: {e}")
        return

    except Exception as e:
        logger.error(f" An error occurred during consumer setup: {e}")
        return

    # Запускаємо безкінечний цикл, щоб тримати з'єднання відкритим
    await asyncio.Future()