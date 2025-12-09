from prometheus_client import Counter, Histogram
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
import time

# 1. Визначення метрик
REQUEST_COUNT = Counter(
    'http_requests_total', 'Total HTTP Requests',
    ['method', 'endpoint', 'status_code']
)
REQUEST_LATENCY = Histogram(
    'http_request_latency_seconds', 'HTTP Request Latency',
    ['method', 'endpoint']
)

# 2. MiddleWare для збору метрик
async def prometheus_middleware(request: Request, call_next):
    """
    Middleware для збору метрик затримки, пропускної здатності та помилок.
    """
    method = request.method
    endpoint = request.url.path
    
    # 2.1 Збір затримки (Latency)
    start_time = time.time()
    
    try:
        response = await call_next(request)
    except Exception as e:
        # Обробка помилок сервера (5xx)
        status_code = 500
        # Збільшення лічильника помилок
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        raise e
        
    end_time = time.time()
    
    status_code = response.status_code
    latency = end_time - start_time
    
    # 2.2 Збір пропускної здатності (Throughput) та частоти помилок (Error Rate)
    # Через лічильник (Counter)
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    
    # 2.3 Збереження затримки
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)
    
    return response

# 3. Експозиція метрик (наприклад, /metrics)
from prometheus_client import generate_latest

def metrics_endpoint(request: Request):
    """Експортує метрики у форматі Prometheus."""
    return Response(content=generate_latest(), media_type="text/plain")
