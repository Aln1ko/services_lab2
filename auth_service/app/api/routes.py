import uuid
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import  HTTPAuthorizationCredentials
from typing import List
from datetime import datetime
from app.api.models import UserCreate, User, LoginRequest, Token, PasswordChange
from app.database import users_db, sessions_db
from app.api.dependencies import security, get_current_user
from shared.rabbitmq import publish_notification_async


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

    try:
        await publish_notification_async(
            user_id=user_id,
            notification_type="welcome",
            subject="Welcome to our platform!",
            message=f"Hello {user_data.email}, your account has been created successfully!"
        )
    except Exception as e:
        print(f"Failed to publish welcome notification: {e}")


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
    return {"message": "User successfully deleted"}



@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    # Пошук користувача
    user = None
    for u in users_db:
        if u["email"] == login_data.email and u["password"] == login_data.password:
            user = u
            break
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Створення токена
    token = str(uuid.uuid4())
    sessions_db[token] = {
        "user_id": user["id"],
        "email": user["email"],
        "login_time": datetime.now()
    }
    
    print(f"User {user['email']} logged in successfully")
    return Token(access_token=token, token_type="bearer")



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
