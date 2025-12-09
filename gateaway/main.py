from fastapi import FastAPI, HTTPException, Response, Request,Header,Depends
from fastapi.middleware.cors import CORSMiddleware
import requests
import httpx
import uvicorn
from jose import jwt, JWTError

#trafic

KEYCLOAK_URL = "http://keycloak:8080/realms/KpiRealm" 
ISSUER_URL = "http://localhost:8080/realms/KpiRealm"

OPENID_CONFIG_URL = f"{KEYCLOAK_URL}/.well-known/openid-configuration"

JWKS_URL = "" # Буде заповнено після першого запиту
PUBLIC_KEY = "" # Публічний ключ для перевірк
CLIENT_ID = "web-client"

# Список шляхів, які НЕ вимагають JWT для доступу
UNPROTECTED_PATHS = [
    "/auth/login",
    "/auth/callback",
    "/health", 
    "/auth/metrics"
]

app = FastAPI(title="API Gateway")

origins = [
    "https://cad.kpi.ua", # Дозволений сайт кафедри
    "http://localhost"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Дозволити надсилання cookie/заголовків авторизації
    allow_methods=["*"], # Дозволити всі методи (GET, POST, OPTIONS, PUT, DELETE)
    # КРИТИЧНО ВАЖЛИВО: Дозволити заголовок Authorization для JWT
    allow_headers=["Authorization", "Content-Type", "Accept"], 
)

# Карта: (Назва_Сервісу, HTTP_Метод, URL_Шлях_Шаблон) : Required_Scope
AUTHORIZATION_MAP = {
    # АВТЕНТИФІКОВАНЕ ЧИТАННЯ (GET /auth/users)
    ("auth", "GET", "users"): "user:read",
    
    # СТВОРЕННЯ (POST /auth/users)
    ("auth", "POST", "users"): "add:user",

    # ВИДАЛЕННЯ (DELETE /auth/users/{id})
    # ("auth", "DELETE", "users/"): "user:delete", #

}

# Отримання JWKS (публічних ключів)
async def fetch_public_key():
    global JWKS_URL, PUBLIC_KEY
    if not JWKS_URL:
        # Отримати конфігурацію 
        async with httpx.AsyncClient() as client:
            response = await client.get(OPENID_CONFIG_URL)
            response.raise_for_status()
            config = response.json()
            # Отримати URL для ключів
            JWKS_URL = config.get("jwks_uri")
    
    # 3. Отримати самий ключ (JWKS)
    async with httpx.AsyncClient() as client:
        response = await client.get(JWKS_URL)
        response.raise_for_status()
        # Keycloak зазвичай повертає JWKS, звідки беремо перший ключ
        PUBLIC_KEY = response.json()['keys'][0]


async def validate_token(authorization: str = Header(None)):
    """Перевіряє JWT Access Token, підписаний Keycloak."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Invalid token scheme")
        
        # Перевіряємо, чи ми вже отримали публічний ключ
        if not PUBLIC_KEY:
            await fetch_public_key() 

        # Використовуємо PUBLIC_KEY для декодування та перевірки підпису
        
        # Для простоти (але менш безпечно), ми можемо декодувати токен, 
        # використовуючи секрет, але це JWT, тому використовуємо публічний ключ.
        
        # Отримання потрібного алгоритму (наприклад, RS256)
        algorithm = PUBLIC_KEY.get('alg', 'RS256')
        
        # Декодування і валідація токена (audience, issuer, expiration)
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=[algorithm],
            # audience=['account', CLIENT_ID],
            options={"verify_aud": False}, 
            issuer=f"{ISSUER_URL}" 
        )
        
        # Додавання payload токена до запиту для мікросервісів
        return payload

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {e}")

def scope_required(required_scope: str):
    """
    Функція, яка перевіряє наявність потрібного Scope в JWT.
    Використовує JWT Payload, отриманий з validate_token.
    """
    async def scope_checker(authorization: str = Header(None)):
        # Викликаємо нашу основну валідацію, щоб отримати Payload
        try:
            auth_payload = await validate_token(authorization)
        except HTTPException:
            raise
        
        # Перевіряємо, чи існує потрібний Scope у токені
        # Поле 'scope' є рядком, розділеним пробілами
        scopes = auth_payload.get("scope", "")
        
        if required_scope not in scopes.split():
            raise HTTPException(
                status_code=403, 
                detail=f"Forbidden: Missing required scope '{required_scope}'"
            )
        
        # Якщо все добре, повертаємо Payload або True
        return auth_payload
    return scope_checker

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
    
    http_method = request.method
    path_key = path.split('/')[0]
    # Створюємо ключ для пошуку в AUTHORIZATION_MAP
    auth_key = (service_name, http_method, path_key)
    
    target_url = f"{SERVICE_URLS[service_name]}/{path}"
    query_params = request.query_params

    full_path = f"/{service_name}/{path}"
    # Перевіряємо, чи поточний шлях є захищеним. 
    # Робимо перевірку, якщо шлях НЕ в списку UNPROTECTED_PATHS.
    is_protected = not any(p in full_path for p in UNPROTECTED_PATHS)

    required_scope = AUTHORIZATION_MAP.get(auth_key)

    if is_protected:
        if required_scope is None:
             raise HTTPException(
                status_code=405, # Method Not Allowed (або 403)
                detail="Method not allowed for this path or missing scope configuration"
            )
        # Якщо шлях захищений, викликаємо валідацію токена
        auth_header = request.headers.get("Authorization")

        try:
            # Очікуємо виконання асинхронної функції валідації
            auth_payload = await scope_required(required_scope)(auth_header)
            
            # Якщо токен валідний, отримуємо оригінальні заголовки
            headers = dict(request.headers)
            
            
        except HTTPException as e:
            # Перехоплюємо помилки 401/403 з валідатора і повертаємо їх клієнту
            raise e
    else:
        # Якщо шлях НЕ захищений, просто використовуємо оригінальні заголовки
        headers = dict(request.headers)

    # headers = dict(request.headers)
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method = request.method,
            url = target_url,
            params = query_params,
            headers = headers, # Передаємо оригінальний Authorization заголовок
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


# curl -I -X OPTIONS \  -H "Origin: https://cad.kpi.ua" \  -H "Access-Control-Request-Method: GET" \  -H "Access-Control-Request-Headers: Authorization" \  "http://localhost:8000/auth/users"

# fetch('http://localhost:8000/auth/users', {
#     method: 'GET',
#     headers: {
#         'Authorization': 'Bearer YOUR_TEST_TOKEN' 
#     }
# })
# .then(response => {
#     console.log('Response Status:', response.status);
#     // Тут ми виводимо, чи був запит успішним або заблокований
#     if (response.ok) {
#         return response.json();
#     }
#     throw new Error('API returned non-OK status or was blocked.');
# })
# .then(data => console.log('API Data:', data))
# .catch(error => console.error('CORS/Fetch Error:', error));