from datetime import datetime, timedelta
import uuid
from shared.unique_id import generate_unique_id

# Тимчасова база даних в пам'яті
subscriptions_db = []
payments_db = []


def create_subscription(user_id: str, plan: str, trial_days: int = 0):
    subscription_id = generate_unique_id(subscriptions_db)
    
    if trial_days > 0:
        expires_at = datetime.now() + timedelta(days=trial_days)
        status = "trial"
    else:
        expires_at = datetime.now() + timedelta(days=30)  # 30 днів
        status = "active"
    
    subscription = {
        "id": subscription_id,
        "user_id": user_id,
        "plan": plan,
        "status": status,
        "created_at": datetime.now(),
        "expires_at": expires_at
    }
    
    subscriptions_db.append(subscription)
    return subscription

def find_subscription_by_user(user_id: str):
    for index,sub in enumerate(subscriptions_db):
        if sub["user_id"] == user_id:
            return sub,index
    return None,-1