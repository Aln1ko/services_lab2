import uuid
from fastapi import APIRouter, HTTPException, status, Depends,Request
from fastapi.security import  HTTPAuthorizationCredentials
from typing import List
from datetime import datetime
from app.api.models import UserCreate, User, LoginRequest, Token, PasswordChange, Event
from app.database import users_db, sessions_db, outbox_db
from app.api.dependencies import security, get_current_user
from shared.rabbitmq import publish_notification_async
from starlette.responses import RedirectResponse
import httpx

try:
    from ..config import KEYCLOAK_INTERNAL_URL,KEYCLOAK_EXTERNAL_URL, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
except ImportError:
    # Запасной вариант на случай, если структура папок отличается
    from auth_service.app.config import KEYCLOAK_INTERNAL_URL,KEYCLOAK_EXTERNAL_URL, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI


router = APIRouter()

def generate_unique_user_id():
    """Генерує ID і перевіряє унікальність в пам'яті"""
    max_attempts = 10
    for _ in range(max_attempts):
        user_id = str(uuid.uuid4())

        # Перевіряємо чи немає користувача з таким ID
        user_exists = any(user['id'] == user_id for user in users_db)
        if not user_exists:
            return user_id
            
    raise Exception("Cannot generate unique ID")

@router.get('/users', response_model=List[User])
async def index():
    return users_db

@router.post('/users', status_code=201)
async def add_user(user_data: UserCreate):
    for user in users_db:
        if user["email"] == user_data.email:
            raise HTTPException(status_code=400,detail = "Email already registered" )
        
    user_id = generate_unique_user_id()

    new_user = {
        "id":user_id,
        "email": user_data.email,
        "password":user_data.password,
        "full_name": user_data.full_name,
        "created_at": datetime.now()
    }
    users_db.append(new_user)

    
    payload = {  
            "user_id": user_id,
            "notification_type": "welcome",
            "subject": "Welcome to our platform!",
            "message": f"Hello {user_data.email}, your account has been created successfully!"
    }

    outbox_entry ={
        "id":str(uuid.uuid4()),
        "payload": payload,
        # "exchange": "",
        # "routing_key": "notifications", # Куди потрібно відправити
        "created_at": datetime.now(),
        "processed": False,
    }   
    outbox_db.append(outbox_entry)

    return new_user

@router.put("/users/{user_id}/")
async def change_password(user_id: str, password_data: PasswordChange):
    # Знаходимо користувача
    user = None
    for u in users_db:
        if u["id"] == user_id:
            user = u
            break
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Перевіряємо поточний пароль
    if user["password"] != password_data.current_password:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Оновлюємо пароль
    user["password"] = password_data.new_password
    print(f"Password changed for user: {user['email']}")

    payload = {  
            "user_id": user_id,
            "notification_type": "password_changed",
            "subject": "password_changed",
            "message": f"{user['email']}, has changed password from {password_data.current_password} to {password_data.new_password}"
    }

    outbox_entry ={
        "id":str(uuid.uuid4()),
        "payload": payload,
        # "exchange": "",
        # "routing_key": "notifications", # Куди потрібно відправити
        "created_at": datetime.now(),
        "processed": False,
    }   
    outbox_db.append(outbox_entry)
    
    return {"message": "Password changed successfully"}

@router.delete("/users/{user_id}/")
async def delete_user(user_id: str):
    user = None
    user_index = None
    for index,us in enumerate(users_db):
        if us["id"] == user_id:
            user = us
            user_index = index
            break
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    del users_db[user_index]
    
    print(f"User successfully deleted: {user['email']}")

    payload = {  
            "user_id": user_id,
            "notification_type": "account_deleted",
            "subject": "account_deleted",
            "message": f" User with email {user['email']} deleted aacount "
    }

    outbox_entry ={
        "id":str(uuid.uuid4()),
        "payload": payload,
        # "exchange": "",
        # "routing_key": "notifications", # Куди потрібно відправити
        "created_at": datetime.now(),
        "processed": False,
    }   
    outbox_db.append(outbox_entry)   
    return {"message": "User successfully deleted"}



# @router.post("/login", response_model=Token)
# async def login(login_data: LoginRequest):
#     # Пошук користувача
#     user = None
#     for u in users_db:
#         if u["email"] == login_data.email and u["password"] == login_data.password:
#             user = u
#             break
    
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid credentials"
#         )
    
#     # Створення токена
#     token = str(uuid.uuid4())
#     sessions_db[token] = {
#         "user_id": user["id"],
#         "email": user["email"],
#         "login_time": datetime.now()
#     }
    
#     print(f"User {user['email']} logged in successfully")
#     return Token(access_token=token, token_type="bearer")

@router.get("/login")
async def login():
    """Початок OAUTH2 Authorization Code Grant Flow."""
    
    # Запитувані області (scopes)
    scope = "openid profile email add:user user:read" 
    
    # Формування URL для Keycloak
    auth_url = (
        f"{KEYCLOAK_EXTERNAL_URL}/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scope}"
    )
    # Перенаправляємо користувача на Keycloak
    return RedirectResponse(auth_url)

# ОБРОБКА КОДУ АВТОРИЗАЦІЇ 
@router.get("/callback")
async def callback(code: str, request: Request):
    """ 
    Callback-ендпоінт: отримує код від Keycloak і обмінює його на JWT токени. 
    """
    
    token_url = f"{KEYCLOAK_INTERNAL_URL}/token"
    
    # Данные для обмена кода на токен
    token_data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    
    # Виконання POST-запиту до Keycloak для отримання токенів
    async with httpx.AsyncClient() as client:
        #Keycloak тут доступний на ім'я контейнера 'keycloak'
        token_response = await client.post(
            token_url,
            data=token_data
        )
        
    if token_response.status_code != 200:
        # Помилка обміну (невірний код, секрет тощо)
        print(f"Keycloak error: {token_response.text}")
        raise HTTPException(
            status_code=400, 
            detail="Failed to exchange authorization code for tokens"
        )
    
    tokens = token_response.json()
    
    return {
        "message": "Вдала аутентифікація через Keycloak!", 
        "tokens": tokens,
        "access_token": tokens.get("access_token")
    }

@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Видаляємо сесію
    token = credentials.credentials
    if token not in sessions_db:
        raise HTTPException(status_code=404, detail="Token not found or already invalid")
    
    user_email = sessions_db[token]["email"]
    del sessions_db[token]
    print(f"User {user_email} logged out successfully")
    return {"message": "Logged out successfully"}

# Приклад захищеного ендпоінту
@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "login_time": current_user["login_time"]
    }

@router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    user = None
    for u in users_db:
        if u["id"] == user_id:
            user = u
            break
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**user)
