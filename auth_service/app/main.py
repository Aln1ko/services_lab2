from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Auth Service", version="1.0.0")

# Підключаємо всі маршрути
app.include_router(router)

@app.get("/")
async def root():
    return {"message": "Auth Service is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


