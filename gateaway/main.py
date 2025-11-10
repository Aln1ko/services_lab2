from fastapi import FastAPI, HTTPException, Response, Request
import requests
import httpx
import uvicorn

#trafic

app = FastAPI(title="API Gateway")

# Конфігурація сервісів
SERVICE_URLS = {
    "auth": "http://auth-service:8000",
    "subscription": "http://subscription-service:8000",
    "board": "http://board-service:8000",
    "task": "http://task-service:8000",
    "notification": "http://notification-service:8000",
}

@app.get("/")
async def root():
    return {"message": "API Gateway is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(service_name: str, path: str, request: Request):
    if service_name not in SERVICE_URLS:
        raise HTTPException(status_code=404, detail="Service not found")
    
    target_url = f"{SERVICE_URLS[service_name]}/{path}"
    
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method = request.method,
            url = target_url,
            headers = dict(request.headers),
            content = await request.body(),
            timeout = 30.0
        )
    
    return Response(
        content = response.content,
        status_code = response.status_code,
        headers = dict(response.headers)
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)