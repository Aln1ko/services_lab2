from pydantic import BaseModel,EmailStr
from datetime import datetime
from enum import Enum

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    TRIAL = "trial"
    EXPIRED = "expired"

class SubscriptionPlan(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

class SubscriptionCreate(BaseModel):
    user_id: str
    plan: SubscriptionPlan = SubscriptionPlan.PREMIUM


class SubscriptionResponse(BaseModel):
    id: str
    user_id: str
    plan: SubscriptionPlan
    status: SubscriptionStatus
    created_at: datetime
    expires_at: datetime

class PaymentRequest(BaseModel):
    user_id: str
    amount: float
    currency: str = "USD"

class PaymentResponse(BaseModel):
    payment_id: str
    status: str  # "success", "failed"
    message: str