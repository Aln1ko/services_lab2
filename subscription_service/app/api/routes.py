from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
import uuid
import requests

from app.api.models import (
    SubscriptionCreate, SubscriptionResponse, 
    SubscriptionStatus, SubscriptionPlan,
    PaymentRequest, PaymentResponse
)
from app.database import subscriptions_db, payments_db, create_subscription, find_subscription_by_user, generate_unique_id

router = APIRouter()

# Синхронний виклик до auth-service для перевірки користувача
def verify_user_exists(user_id: str) -> bool:
    try:
        # Виклик до auth-service (синхронна комунікація)
        response = requests.get(f"http://auth-service:8000/users/{user_id}")
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False
    

@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription_endpoint(subscription_data: SubscriptionCreate):
    # Перевірка чи існує користувач
    if not verify_user_exists(subscription_data.user_id):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Перевірка чи вже є підписка
    existing_sub,index = find_subscription_by_user(subscription_data.user_id)
    if existing_sub:
        raise HTTPException(status_code=400, detail="Subscription already exists")
    
    # Створення підписки
    new_subscription = create_subscription(
        user_id=subscription_data.user_id,
        plan=subscription_data.plan
    )
    
    print(f"Subscription created for user: {subscription_data.user_id}")
    
    # Тут буде асинхронний виклик до notification-service (через RabbitMQ)
    # await send_notification(subscription_data.user_id, "subscription_created")
    
    return SubscriptionResponse(**new_subscription)

@router.post("/subscriptions/trial", response_model=SubscriptionResponse)
async def activate_trial(user_id: str):
    if not verify_user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    
    existing_sub,index = find_subscription_by_user(user_id)
    if existing_sub:
        raise HTTPException(status_code=400, detail="User already has subscription")
    
    # Активуємо пробну версію на 14 днів
    trial_subscription = create_subscription(
        user_id=user_id,
        plan=SubscriptionPlan.PREMIUM,
        trial_days=14
    )
    
    print(f"Trial activated for user: {user_id}")
    
    return SubscriptionResponse(**trial_subscription)

@router.delete("/subscriptions/{user_id}")
async def cancel_subscription(user_id: str):
    subscription,index = find_subscription_by_user(user_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Оновлюємо статус
    # subscription["status"] = SubscriptionStatus.CANCELED
    del subscriptions_db[index]
    print(f"Subscription canceled for user: {user_id}")
    
    return {"message": "Subscription canceled successfully"}

@router.get("/subscriptions/{user_id}", response_model=SubscriptionResponse)
async def get_subscription(user_id: str):
    subscription,index = find_subscription_by_user(user_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    return SubscriptionResponse(**subscription)

@router.post("/payments", response_model=PaymentResponse)
async def process_payment(payment_data: PaymentRequest):
    # Імітація платежної системи
    payment_id = generate_unique_id(payments_db)
    
    # Спрощена логіка - завжди успішно
    payment_status = "success"
    
    payment_record = {
        "payment_id": payment_id,
        "user_id": payment_data.user_id,
        "amount": payment_data.amount,
        "currency": payment_data.currency,
        "status": payment_status,
        "created_at": datetime.now()
    }
    
    payments_db.append(payment_record)
    
    # Якщо платіж успішний - оновлюємо підписку
    if payment_status == "success":
        subscription,index = find_subscription_by_user(payment_data.user_id)
        if subscription:
            subscription["status"] = SubscriptionStatus.ACTIVE
            subscription["expires_at"] = datetime.now() + timedelta(days=30)
    
    print(f"Payment processed for user: {payment_data.user_id}")
    
    return PaymentResponse(
        payment_id=payment_id,
        status=payment_status,
        message="Payment processed successfully"
    )