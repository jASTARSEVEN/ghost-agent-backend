# actions/schemas.py
from pydantic import BaseModel
from typing import Optional

class RefundRequest(BaseModel):
    order_number: str
    user_id: str
    amount: float
    auto_reason: Optional[str] = "Customer requested refund"
    policy_notes: Optional[str] = None
    currency: Optional[str] = "USD"

class RefundResponse(BaseModel):
    status: str
    order_number: str
    message: str
