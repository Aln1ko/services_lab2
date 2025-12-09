from fastapi import FastAPI
from app.api.routes import router
from app.database import outbox_db,users_db
import asyncio
from shared.rabbitmq import publish_notification_async
from app.api.models import Event
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from shared.rabbitmq import initialize_rabbitmq_connection,connection, channel
import logging
import aio_pika
import json
from .monitoring import prometheus_middleware, metrics_endpoint
from starlette.middleware.base import BaseHTTPMiddleware
from .tracing import setup_tracing


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

outbox_lock = asyncio.Lock()

async def outbox_worker():
    events_to_process = [event for event in outbox_db if not event["processed"] and event.get("status") != "cancelled"]
    if not events_to_process:
        logger.debug("Outbox is empty. Skipping processing.") # Використовуйте debug, щоб не засмічувати лог
        return 
    
    logger.info(f"Processing {len(events_to_process)} events from Outbox.")
    for event in events_to_process:
        if not event["processed"]:
            try:
                event_model = Event(**event)
                async with outbox_lock:
                    # Перевіряємо ще раз, чи не скасував Rollback Listener 
                    # подію, поки ми чекали публікацію в RabbitMQ.
                    if event.get("status") != "cancelled": 
                        event["processed"] = True
                        logger.info(f"Event {event['id']} successfully published and marked as processed.")
                    else:
                        logger.warning(f"Event {event['id']} was cancelled during publication, status preserved.")
                await publish_notification_async(event_model)

               
                # event["processed"] = True
            except Exception as e:
                logger.info(f"Retry later: {e}") # Логуйте, не кидайте
                pass # Планувальник викличе знову через 1 секунду


async def saga_rollback_listener():
    # max_retries = 10
    # retry_delay = 5
    
    # for attempt in range(max_retries):
        try:
            logger.info("🔄 STARTING SAGA ROLLBACK LISTENER...")
            # 1. Створення з'єднання/каналу
            connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
            channel = await connection.channel()
            
            # 2. Оголошення обміну та черги, яку слухає продюсер
            rollback_exchange = await channel.declare_exchange(
                'saga_dlx',
                aio_pika.ExchangeType.DIRECT, 
                durable=True)
            rollback_queue = await channel.declare_queue(
                'saga_rollback_q',
                durable=True)
            
            # 3. Прив'язка черги до DLQ-обміну.
            await rollback_queue.bind(
                rollback_exchange,
                routing_key='saga_rollback')
            logger.info(f"SAGA Rollback Listener bound to 'saga_dlx' with routing key 'saga_rollback'.")

            async with rollback_queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            payload = json.loads(message.body.decode())
                            user_id = payload.get("user_id")

                            logger.warning(f"SAGA Rollback triggered for User ID: {user_id}")
                            
                            # 4. ЛОГІКА КОМПЕНСАЦІЇ (ВІДКАТУ)
                            # Видаляємо користувача з локальної БД
                            global users_db
                            initial_len = len(users_db)
                            users_to_keep = [u for u in users_db if u["id"] != user_id]
                            users_db.clear()
                            users_db.extend(users_to_keep)
                            
                            if len(users_db) < initial_len:
                                logger.info(f"User {user_id} removed from DB.")
                            else:
                                logger.warning(f"User {user_id} not found in DB or already removed.")

                            # Позначаємо запис в Outbox як відмінений/видалений
                            global outbox_db
                            async with outbox_lock: # Забезпечуємо безпеку при видаленні
                                initial_outbox_len = len(outbox_db)

                                entry_arr = [entry1 for entry1 in outbox_db if entry1["payload"].get("user_id") == user_id]
                                outbox_db_to_keep = [
                                    entry for entry in outbox_db 
                                    if entry["payload"].get("user_id") != user_id
                                ]
                                outbox_db.clear()
                                outbox_db.extend(outbox_db_to_keep)
                                entry = entry_arr[0]
                                
                                if len(outbox_db) < initial_outbox_len:
                                    logger.info(f"Entry {entry['id']} removed from DB (SAGA Rollback Complete).")
                                else:
                                    logger.warning(f"Outbox entry for user {user_id} not found/already removed.")

                            
                        except Exception as e:
                            logger.error(f"Error processing DLQ rollback message: {e}")
                            # raise
        except Exception as e:
            logger.error(f"SAGA Rollback Listener failed: {e}")

async def start_rollback_listener_with_retry():
    """Запускає rollback listener з безкінечними спробами перепідключення"""
    while True:
        try:
            await saga_rollback_listener()
        except Exception as e:
            logger.error(f"Rollback listener crashed: {e}")
        
        logger.info("🔄 Restarting rollback listener in 10 seconds...")
        await asyncio.sleep(10)

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Ініціалізація RabbitMQ ---
    try:
        await initialize_rabbitmq_connection()
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")

    scheduler.add_job(outbox_worker, 'interval', seconds=1)
    scheduler.start()
    task = asyncio.create_task(start_rollback_listener_with_retry())

    yield

    scheduler.shutdown()
    logger.info("Outbox Worker stopped.")
    
    if connection and not connection.is_closed:
        await connection.close()
        logger.info("RabbitMQ connection closed.")

    task.cancel()
    try:
        await task # Чекаємо на скасування, щоб запобігти помилці
    except asyncio.CancelledError:
        logger.info("Auth service Saga stopped")
   
    


app = FastAPI(title="Auth Service", version="1.0.0",lifespan=lifespan )

setup_tracing(app, "auth-service")

# Додаємо Middleware для автоматичного збору даних для КОЖНОГО запиту
app.add_middleware(BaseHTTPMiddleware, dispatch=prometheus_middleware)

# Підключаємо всі маршрути
app.include_router(router)
# Додаємо ендпоінт /metrics, який Prometheus буде опитувати
app.add_route("/metrics", metrics_endpoint)

@app.get("/")
async def root():
    return {"message": "Auth Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


