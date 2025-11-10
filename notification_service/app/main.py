from fastapi import FastAPI
from app.api.routes import router
from app.consumer import start_consumer
import threading
import asyncio
import logging
from contextlib import asynccontextmanager


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# def run_consumer():
#     """Запуск споживача в окремому потоці"""
#     try:
#         start_consumer()
#     except Exception as e:
#         print(f"Consumer thread error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Notification Service starting up...")
    consumer_task = asyncio.create_task(start_consumer())
    logger.info("Notification consumer task created.")

    yield

    logger.info("Notification Service shutting down...")
    consumer_task.cancel()
    try:
        await consumer_task # Чекаємо на скасування, щоб запобігти помилці
    except asyncio.CancelledError:
        logger.info("Notification consumer task cancelled successfully.")
   

app = FastAPI(title="Notification Service", version="1.0.0",lifespan=lifespan)

# Підключаємо всі маршрути
app.include_router(router)

@app.get("/")
async def root():
    return {"message": "Notification Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
 
